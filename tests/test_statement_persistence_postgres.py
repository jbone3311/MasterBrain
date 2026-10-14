"""Disposable PostgreSQL proof for immutable, nonpublishing statement proposals."""

from __future__ import annotations

import hashlib
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

import psycopg
import pytest
import test_postgres as pg

from email_brain.domain.models import TenantContext
from email_brain.store import AccessDenied, Conflict, NotFound, Store
from masterbrain.datacore.contracts import stable_id
from masterbrain.statement_persistence import StatementProposalStore

database, tenant = pg.database, pg.tenant
pytestmark = pytest.mark.postgres

HEADER = "Symbol Description Quantity Market Price Market Value Cost Price Unrealized TD Cost Basis"
TEXT = (
    "Account No: 000000\nPeriod: April - 2024\nLong $100.00\n"
    f"{HEADER}\nACME Fictional Corporation 2 $50.00 $100.00 $40.00 $20.00 $80.00"
)


def worker(ctx: TenantContext) -> TenantContext:
    return replace(ctx, scopes=frozenset({"brain.document.publish"}))


def source_document(
    admin: str, ctx: TenantContext, *, kind: str = "fileos", body: str = TEXT,
    body_sha: str | None = None, source_id: str | None = None,
) -> tuple[str, str, str]:
    source_id = source_id or stable_id("source", str(uuid4()))
    item_id = stable_id("item", source_id)
    version_id = stable_id("version", item_id)
    evidence_id = stable_id("evidence", version_id)
    document_id = stable_id("document", evidence_id, body)
    source_sha = hashlib.sha256(b"fictional immutable statement bytes").hexdigest()
    text_sha = body_sha or hashlib.sha256(body.encode()).hexdigest()
    with psycopg.connect(admin) as conn:
        conn.execute(
            "INSERT INTO brain_sources(tenant_id,id,kind,display_name,root_binding_sha256) "
            "VALUES (%s,%s,%s,%s,%s)",
            (ctx.tenant_id, source_id, kind, "Fictional statement source",
             hashlib.sha256(b"fictional root").hexdigest() if kind == "fileos" else None),
        )
        conn.execute(
            "INSERT INTO brain_source_items(tenant_id,source_id,id,locator,first_seen_at,"
            "last_seen_at) VALUES (%s,%s,%s,%s,%s,%s)",
            (ctx.tenant_id, source_id, item_id, "fictional-statement.txt",
             datetime(2024, 4, 30, tzinfo=UTC), datetime(2024, 4, 30, tzinfo=UTC)),
        )
        conn.execute(
            "INSERT INTO brain_source_versions(tenant_id,source_id,item_id,id,observed_at,"
            "sha256,size_bytes,media_type,metadata) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,'text/plain','{}'::jsonb)",
            (ctx.tenant_id, source_id, item_id, version_id,
             datetime(2024, 4, 30, tzinfo=UTC), source_sha,
             len(b"fictional immutable statement bytes")),
        )
        conn.execute(
            "UPDATE brain_source_items SET current_version_id=%s WHERE tenant_id=%s AND id=%s",
            (version_id, ctx.tenant_id, item_id),
        )
        conn.execute(
            "INSERT INTO brain_evidence(tenant_id,id,source_version_id,sha256,storage,retained) "
            "VALUES (%s,%s,%s,%s,'inline',true)",
            (ctx.tenant_id, evidence_id, version_id, source_sha),
        )
        conn.execute(
            "INSERT INTO brain_normalized_documents(tenant_id,id,evidence_id,normalizer,"
            "body_sha256,body) VALUES (%s,%s,%s,'fictional-statement-v1',%s,%s)",
            (ctx.tenant_id, document_id, evidence_id, text_sha, body),
        )
    return document_id, item_id, version_id


@pytest.mark.parametrize("kind", ["email", "fileos"])
def test_current_document_atomic_rows_and_replay(
    database: tuple[Store, str], tenant: tuple[TenantContext, UUID], kind: str,
) -> None:
    store, admin = database
    ctx = worker(tenant[0])
    document_id, _, _ = source_document(admin, ctx, kind=kind)
    projector = StatementProposalStore(store)
    key = uuid4()
    result = projector.project_current_document(ctx, document_id, key)
    assert result == projector.project_current_document(ctx, document_id, key)
    assert result["status"] == "reconciled"
    assert result["row_count"] == 1
    assert result["reviewed"] is False and result["source_effects"] is False
    with store.transaction(ctx) as conn:
        parent = conn.execute(
            "SELECT source_kind,text_sha256,source_sha256,row_count,status,expected,actual,"
            "delta,donor_commit,transform_version FROM knowledge_statement_proposals "
            "WHERE id=%s", (result["proposal_id"],),
        ).fetchone()
        rows = conn.execute(
            "SELECT ordinal,row_type,quantity,price,amount,cost_basis,unrealized,"
            "text_start,text_end FROM knowledge_statement_rows WHERE proposal_id=%s",
            (result["proposal_id"],),
        ).fetchall()
        assert conn.execute("SELECT count(*) AS n FROM knowledge_claims").fetchone()["n"] == 0
        assert conn.execute(
            "SELECT count(*) AS n FROM knowledge_statement_receipts WHERE proposal_id=%s",
            (result["proposal_id"],),
        ).fetchone()["n"] == 1
    assert parent is not None and parent["source_kind"] == kind
    assert parent["text_sha256"] == hashlib.sha256(TEXT.encode()).hexdigest()
    assert parent["source_sha256"] != parent["text_sha256"]
    assert (parent["row_count"], parent["status"], parent["expected"],
            parent["actual"], parent["delta"]) == (1, "reconciled", 100, 100, 0)
    assert len(rows) == 1
    assert (rows[0]["quantity"], rows[0]["price"], rows[0]["amount"],
            rows[0]["cost_basis"], rows[0]["unrealized"]) == (2, 50, 100, 80, 20)
    assert TEXT[rows[0]["text_start"]:rows[0]["text_end"]].startswith("ACME Fictional")


def test_scope_hash_staleness_and_key_conflict(
    database: tuple[Store, str], tenant: tuple[TenantContext, UUID],
) -> None:
    store, admin = database
    ctx = worker(tenant[0])
    projector = StatementProposalStore(store)
    document_id, item_id, version_id = source_document(admin, ctx)
    with pytest.raises(AccessDenied, match="scope denied"):
        projector.project_current_document(tenant[0], document_id, uuid4())
    key = uuid4()
    first = projector.project_current_document(ctx, document_id, key)
    with pytest.raises(NotFound):
        projector.project_current_document(
            replace(ctx, source_ids=frozenset({"another_source"})), document_id, uuid4()
        )
    replay = projector.project_current_document(ctx, document_id, uuid4())
    assert replay["proposal_id"] == first["proposal_id"]
    other_doc, _, _ = source_document(admin, ctx)
    with pytest.raises(Conflict, match="request key was reused"):
        projector.project_current_document(ctx, other_doc, key)
    bad_doc, _, _ = source_document(admin, ctx, body_sha="0" * 64)
    with pytest.raises(Conflict, match="text digest changed"):
        projector.project_current_document(ctx, bad_doc, uuid4())
    new_version = stable_id("version", item_id, "new")
    with psycopg.connect(admin) as conn:
        conn.execute(
            "INSERT INTO brain_source_versions(tenant_id,source_id,item_id,id,observed_at,"
            "sha256,size_bytes,media_type,metadata) "
            "SELECT tenant_id,source_id,item_id,%s,observed_at,sha256,size_bytes,"
            "media_type,metadata FROM brain_source_versions WHERE tenant_id=%s AND id=%s",
            (new_version, ctx.tenant_id, version_id),
        )
        conn.execute(
            "UPDATE brain_source_items SET current_version_id=%s WHERE tenant_id=%s AND id=%s",
            (new_version, ctx.tenant_id, item_id),
        )
    with pytest.raises(Conflict, match="source is not current"):
        projector.project_current_document(ctx, document_id, uuid4())


def test_concurrent_replay_and_thousand_row_storage(
    database: tuple[Store, str], tenant: tuple[TenantContext, UUID],
) -> None:
    store, admin = database
    ctx = worker(tenant[0])
    holding = "ACME Fictional Corporation 2 $50.00 $100.00 $40.00 $20.00 $80.00"
    text = (
        "Account No: 000000\nPeriod: April - 2024\nLong $100000.00\n"
        f"{HEADER}\n" + (holding + "\n") * 1000
    )
    document_id, _, _ = source_document(admin, ctx, body=text)
    projector = StatementProposalStore(store)
    keys = [uuid4() for _ in range(8)]
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(
            lambda key: projector.project_current_document(ctx, document_id, key), keys
        ))
    assert len({result["proposal_id"] for result in results}) == 1
    assert all(result["row_count"] == 1000 and result["status"] == "reconciled"
               for result in results)
    with store.transaction(ctx) as conn:
        assert conn.execute(
            "SELECT count(*) AS n FROM knowledge_statement_rows WHERE proposal_id=%s",
            (results[0]["proposal_id"],),
        ).fetchone()["n"] == 1000
        assert conn.execute(
            "SELECT count(*) AS n FROM knowledge_statement_receipts WHERE proposal_id=%s",
            (results[0]["proposal_id"],),
        ).fetchone()["n"] == 8


def test_direct_sql_cannot_forge_basis_or_unsealed_rows(
    database: tuple[Store, str], tenant: tuple[TenantContext, UUID],
) -> None:
    store, admin = database
    ctx = worker(tenant[0])
    document_id, _, _ = source_document(admin, ctx)
    proposal_id = StatementProposalStore(store).project_current_document(
        ctx, document_id, uuid4()
    )["proposal_id"]
    clone_sql = (
        "INSERT INTO knowledge_statement_proposals(tenant_id,id,document_id,evidence_id,"
        "source_version_id,source_id,source_kind,recipe,donor_commit,transform_version,"
        "text_sha256,source_sha256,account_number,period,status,coverage_errors,row_count,"
        "rows_sha256,expected,actual,delta) "
        "SELECT tenant_id,%s,document_id,evidence_id,source_version_id,source_id,"
        "source_kind,recipe,donor_commit,%s,text_sha256,%s,account_number,period,status,"
        "coverage_errors,row_count,rows_sha256,expected,actual,delta "
        "FROM knowledge_statement_proposals WHERE id=%s"
    )
    with psycopg.connect(admin, autocommit=True) as conn:
        with pytest.raises(psycopg.errors.RaiseException, match="invalid statement proposal basis"):
            with conn.transaction():
                conn.execute(
                    clone_sql,
                    (stable_id("statement", "forged"), "forged-v1", "0" * 64, proposal_id),
                )
        source_sha = conn.execute(
            "SELECT source_sha256 FROM knowledge_statement_proposals WHERE id=%s",
            (proposal_id,),
        ).fetchone()[0]
        with pytest.raises(psycopg.errors.RaiseException, match="incomplete statement proposal"):
            with conn.transaction():
                conn.execute(
                    clone_sql,
                    (stable_id("statement", "unsealed"), "unsealed-v1", source_sha,
                     proposal_id),
                )
        with pytest.raises(psycopg.errors.RaiseException, match="invalid statement row basis"):
            with conn.transaction():
                conn.execute(
                    "INSERT INTO knowledge_statement_rows(tenant_id,proposal_id,ordinal,"
                    "row_type,description,symbol,line_date,quantity,price,amount,cost_basis,"
                    "unrealized,currency,text_start,text_end) "
                    "SELECT tenant_id,proposal_id,1,row_type,description,symbol,line_date,"
                    "quantity,price,amount,cost_basis,unrealized,currency,text_start,text_end "
                    "FROM knowledge_statement_rows WHERE proposal_id=%s AND ordinal=0",
                    (proposal_id,),
                )


def test_tenant_isolation_and_immutable_sql(
    database: tuple[Store, str], tenant: tuple[TenantContext, UUID],
) -> None:
    store, admin = database
    ctx = worker(tenant[0])
    document_id, _, _ = source_document(admin, ctx)
    result = StatementProposalStore(store).project_current_document(ctx, document_id, uuid4())
    other_tenant, other_actor = uuid4(), uuid4()
    with psycopg.connect(admin) as conn:
        conn.execute(
            "INSERT INTO tenants(id,name) VALUES (%s,'Other fictional tenant')",
            (other_tenant,),
        )
        conn.execute(
            "INSERT INTO tenant_memberships(tenant_id,user_id,role) VALUES (%s,%s,'owner')",
            (other_tenant, other_actor),
        )
    other = replace(ctx, tenant_id=other_tenant, actor_id=other_actor)
    with pytest.raises(NotFound):
        StatementProposalStore(store).project_current_document(other, document_id, uuid4())
    with store.transaction(other) as conn:
        assert conn.execute("SELECT * FROM knowledge_statement_proposals").fetchall() == []
        assert conn.execute("SELECT * FROM knowledge_statement_rows").fetchall() == []
    with store.transaction(ctx) as conn:
        with pytest.raises(psycopg.errors.InsufficientPrivilege), conn.transaction():
            conn.execute(
                "UPDATE knowledge_statement_proposals SET status='mismatch' WHERE id=%s",
                (result["proposal_id"],),
            )
        with pytest.raises(psycopg.errors.InsufficientPrivilege), conn.transaction():
            conn.execute("TRUNCATE knowledge_statement_rows")
        with pytest.raises(psycopg.errors.InsufficientPrivilege), conn.transaction():
            conn.execute(
                "DELETE FROM knowledge_statement_receipts WHERE proposal_id=%s",
                (result["proposal_id"],),
            )
    with psycopg.connect(admin) as conn:
        with pytest.raises(psycopg.errors.RaiseException), conn.transaction():
            conn.execute(
                "UPDATE knowledge_statement_proposals SET status='mismatch' WHERE id=%s",
                (result["proposal_id"],),
            )
        with pytest.raises(psycopg.errors.RaiseException), conn.transaction():
            conn.execute("TRUNCATE knowledge_statement_rows")
        with pytest.raises(psycopg.errors.RaiseException), conn.transaction():
            conn.execute(
                "DELETE FROM knowledge_statement_receipts WHERE proposal_id=%s",
                (result["proposal_id"],),
            )
