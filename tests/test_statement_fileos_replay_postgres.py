"""Disposable PostgreSQL proof of current, confined fictional statement replay."""

from __future__ import annotations

import hashlib
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import psycopg
import pytest
import test_postgres as pg
from test_statement_persistence_postgres import TEXT, worker

import masterbrain.statement_fileos_replay as replay_module
from email_brain.domain.models import TenantContext
from email_brain.store import AccessDenied, Conflict, NotFound, Store
from masterbrain.datacore.contracts import stable_id
from masterbrain.datacore.extraction import EXTRACTOR_VERSION
from masterbrain.datacore.fileos import fileos_root_binding_sha256
from masterbrain.statement_fileos_replay import StatementFileOSReplayStore
from masterbrain.statement_persistence import StatementProposalStore

database, tenant = pg.database, pg.tenant
pytestmark = pytest.mark.postgres


def source_file_document(
    admin: str, ctx: TenantContext, root: Path, *, raw: bytes | None = None,
    body: str = TEXT,
) -> tuple[str, str, str, str]:
    root.mkdir(exist_ok=True)
    source_id = stable_id("source", str(uuid4()))
    item_id = stable_id("item", source_id)
    version_id = stable_id("version", item_id)
    evidence_id = stable_id("evidence", version_id)
    document_id = stable_id("document", evidence_id, body)
    source_bytes = body.encode() if raw is None else raw
    (root / "fictional-statement.txt").write_bytes(source_bytes)
    source_sha = hashlib.sha256(source_bytes).hexdigest()
    text_sha = hashlib.sha256(body.encode()).hexdigest()
    now = datetime(2024, 4, 30, tzinfo=UTC)
    with psycopg.connect(admin) as conn:
        conn.execute(
            "INSERT INTO brain_sources(tenant_id,id,kind,display_name,root_binding_sha256) "
            "VALUES (%s,%s,'fileos','Fictional replay source',%s)",
            (ctx.tenant_id, source_id, fileos_root_binding_sha256(root)),
        )
        conn.execute(
            "INSERT INTO brain_source_items(tenant_id,source_id,id,locator,first_seen_at,"
            "last_seen_at) VALUES (%s,%s,%s,'fictional-statement.txt',%s,%s)",
            (ctx.tenant_id, source_id, item_id, now, now),
        )
        conn.execute(
            "INSERT INTO brain_source_versions(tenant_id,source_id,item_id,id,observed_at,"
            "sha256,size_bytes,media_type,metadata) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,'text/plain','{}'::jsonb)",
            (ctx.tenant_id, source_id, item_id, version_id, now, source_sha,
             len(source_bytes)),
        )
        conn.execute(
            "UPDATE brain_source_items SET current_version_id=%s WHERE tenant_id=%s "
            "AND id=%s", (version_id, ctx.tenant_id, item_id),
        )
        conn.execute(
            "INSERT INTO brain_evidence(tenant_id,id,source_version_id,sha256,storage,"
            "retained) VALUES (%s,%s,%s,%s,'source_bound',false)",
            (ctx.tenant_id, evidence_id, version_id, source_sha),
        )
        conn.execute(
            "INSERT INTO brain_normalized_documents(tenant_id,id,evidence_id,normalizer,"
            "body_sha256,body) VALUES (%s,%s,%s,%s,%s,%s)",
            (ctx.tenant_id, document_id, evidence_id, EXTRACTOR_VERSION, text_sha, body),
        )
    return document_id, item_id, version_id, source_id


def proposal(store: Store, ctx: TenantContext, document_id: str) -> str:
    return StatementProposalStore(store).project_current_document(
        ctx, document_id, uuid4()
    )["proposal_id"]


def test_exact_replay_is_append_only_and_not_a_reviewed_holding(
    database: tuple[Store, str], tenant: tuple[TenantContext, UUID], tmp_path: Path,
) -> None:
    store, admin = database
    ctx = worker(tenant[0])
    root = tmp_path / "fictional-source"
    source_bytes = b"\xef\xbb\xbf" + TEXT.replace("\n", "\r\n").encode() + b"  \n"
    document_id, _, _, _ = source_file_document(admin, ctx, root, raw=source_bytes)
    proposal_id = proposal(store, ctx, document_id)
    replay = StatementFileOSReplayStore(store)
    result = replay.record_current_text_replay(ctx, proposal_id, root)
    assert result == replay.record_current_text_replay(ctx, proposal_id, root)
    assert result == {
        "proposal_id": proposal_id, "worker_observed_text_replay": True,
        "reviewed": False, "source_effects": False,
    }
    with store.transaction(ctx) as conn:
        saved = conn.execute(
            "SELECT source_sha256,text_sha256,source_size_bytes,normalizer "
            "FROM knowledge_statement_fileos_replays WHERE proposal_id=%s", (proposal_id,),
        ).fetchone()
        assert saved is not None
        assert saved["source_sha256"] == hashlib.sha256(source_bytes).hexdigest()
        assert saved["text_sha256"] == hashlib.sha256(TEXT.encode()).hexdigest()
        assert saved["text_sha256"] != saved["source_sha256"]
        assert saved["source_size_bytes"] == len(source_bytes)
        assert saved["normalizer"] == EXTRACTOR_VERSION
        assert conn.execute("SELECT count(*) AS n FROM knowledge_claims").fetchone()["n"] == 0
        assert conn.execute(
            "SELECT count(*) AS n FROM knowledge_statement_fileos_replays "
            "WHERE proposal_id=%s", (proposal_id,),
        ).fetchone()["n"] == 1


def test_unrelated_text_wrong_root_and_changed_bytes_leave_no_receipt(
    database: tuple[Store, str], tenant: tuple[TenantContext, UUID], tmp_path: Path,
) -> None:
    store, admin = database
    ctx = worker(tenant[0])
    root = tmp_path / "fictional-source"
    document_id, _, _, _ = source_file_document(
        admin, ctx, root, raw=b"fictional immutable statement bytes",
    )
    proposal_id = proposal(store, ctx, document_id)
    replay = StatementFileOSReplayStore(store)
    with pytest.raises(Conflict, match="text replay failed"):
        replay.record_current_text_replay(ctx, proposal_id, root)
    other = tmp_path / "other-root"
    other.mkdir()
    (other / "fictional-statement.txt").write_bytes(b"fictional immutable statement bytes")
    with pytest.raises(Conflict, match="basis changed"):
        replay.record_current_text_replay(ctx, proposal_id, other)
    (root / "fictional-statement.txt").write_bytes(b"changed bytes")
    with pytest.raises(Conflict, match="text replay failed"):
        replay.record_current_text_replay(ctx, proposal_id, root)
    with store.transaction(ctx) as conn:
        assert conn.execute(
            "SELECT count(*) AS n FROM knowledge_statement_fileos_replays "
            "WHERE proposal_id=%s", (proposal_id,),
        ).fetchone()["n"] == 0


def test_grant_tenant_stale_and_human_refusal(
    database: tuple[Store, str], tenant: tuple[TenantContext, UUID], tmp_path: Path,
) -> None:
    store, admin = database
    ctx = worker(tenant[0])
    root = tmp_path / "fictional-source"
    document_id, item_id, version_id, _ = source_file_document(admin, ctx, root)
    proposal_id = proposal(store, ctx, document_id)
    replay = StatementFileOSReplayStore(store)
    with pytest.raises(AccessDenied):
        replay.record_current_text_replay(tenant[0], proposal_id, root)
    with pytest.raises(NotFound):
        replay.record_current_text_replay(
            replace(ctx, source_ids=frozenset({"another-source"})), proposal_id, root
        )
    other_tenant, other_actor = uuid4(), uuid4()
    with psycopg.connect(admin) as conn:
        conn.execute("INSERT INTO tenants(id,name) VALUES (%s,'Other fictional tenant')",
                     (other_tenant,))
        conn.execute(
            "INSERT INTO tenant_memberships(tenant_id,user_id,role) VALUES (%s,%s,'owner')",
            (other_tenant, other_actor),
        )
    other_ctx = replace(ctx, tenant_id=other_tenant, actor_id=other_actor)
    with pytest.raises(NotFound):
        replay.record_current_text_replay(other_ctx, proposal_id, root)
    next_version = stable_id("version", item_id, "next")
    with psycopg.connect(admin) as conn:
        conn.execute(
            "INSERT INTO brain_source_versions(tenant_id,source_id,item_id,id,observed_at,"
            "sha256,size_bytes,media_type,metadata) SELECT tenant_id,source_id,item_id,%s,"
            "observed_at,sha256,size_bytes,media_type,metadata "
            "FROM brain_source_versions WHERE tenant_id=%s AND id=%s",
            (next_version, ctx.tenant_id, version_id),
        )
        conn.execute(
            "UPDATE brain_source_items SET current_version_id=%s WHERE tenant_id=%s "
            "AND id=%s", (next_version, ctx.tenant_id, item_id),
        )
    with pytest.raises(Conflict, match="basis changed"):
        replay.record_current_text_replay(ctx, proposal_id, root)


def test_concurrent_replay_and_direct_sql_guard(
    database: tuple[Store, str], tenant: tuple[TenantContext, UUID], tmp_path: Path,
) -> None:
    store, admin = database
    ctx = worker(tenant[0])
    root = tmp_path / "fictional-source"
    document_id, _, _, _ = source_file_document(admin, ctx, root)
    proposal_id = proposal(store, ctx, document_id)
    replay = StatementFileOSReplayStore(store)
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(
            lambda _: replay.record_current_text_replay(ctx, proposal_id, root), range(8)
        ))
    assert len({result["proposal_id"] for result in results}) == 1
    with store.transaction(ctx) as conn:
        assert conn.execute(
            "SELECT count(*) AS n FROM knowledge_statement_fileos_replays "
            "WHERE proposal_id=%s", (proposal_id,),
        ).fetchone()["n"] == 1
        with pytest.raises(psycopg.errors.InsufficientPrivilege), conn.transaction():
            conn.execute(
                "UPDATE knowledge_statement_fileos_replays SET source_size_bytes=1 "
                "WHERE proposal_id=%s", (proposal_id,),
            )
        with pytest.raises(psycopg.errors.InsufficientPrivilege), conn.transaction():
            conn.execute("TRUNCATE knowledge_statement_fileos_replays")
    with psycopg.connect(admin) as conn:
        with pytest.raises(psycopg.errors.RaiseException), conn.transaction():
            conn.execute("TRUNCATE knowledge_statement_fileos_replays")
        with pytest.raises(psycopg.errors.RaiseException, match="invalid statement FileOS"):
            with conn.transaction():
                conn.execute(
                    "INSERT INTO knowledge_statement_fileos_replays(tenant_id,proposal_id,"
                    "document_id,evidence_id,source_version_id,source_id,actor_id,"
                    "source_sha256,source_size_bytes,text_sha256,normalizer,"
                    "root_binding_sha256) "
                    "SELECT tenant_id,%s,document_id,evidence_id,source_version_id,"
                    "source_id,actor_id,%s,source_size_bytes,text_sha256,normalizer,"
                    "root_binding_sha256 FROM knowledge_statement_fileos_replays "
                    "WHERE tenant_id=%s AND proposal_id=%s",
                    (stable_id("statement", "forged"), "0" * 64,
                     ctx.tenant_id, proposal_id),
                )


def test_symlink_and_between_transaction_version_race_fail_closed(
    database: tuple[Store, str], tenant: tuple[TenantContext, UUID], tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, admin = database
    ctx = worker(tenant[0])
    root = tmp_path / "fictional-source"
    document_id, item_id, version_id, _ = source_file_document(admin, ctx, root)
    proposal_id = proposal(store, ctx, document_id)
    leaf = root / "fictional-statement.txt"
    leaf.unlink()
    outside = tmp_path / "fictional-outside.txt"
    outside.write_text(TEXT)
    leaf.symlink_to(outside)
    replay = StatementFileOSReplayStore(store)
    with pytest.raises(Conflict, match="source unavailable or changed"):
        replay.record_current_text_replay(ctx, proposal_id, root)
    leaf.unlink()
    leaf.write_text(TEXT)

    original = replay_module.read_confined_file

    def race(*args: object, **kwargs: object):
        opened = original(*args, **kwargs)  # type: ignore[arg-type]
        next_version = stable_id("version", item_id, "raced")
        with psycopg.connect(admin) as conn:
            conn.execute(
                "INSERT INTO brain_source_versions(tenant_id,source_id,item_id,id,"
                "observed_at,sha256,size_bytes,media_type,metadata) "
                "SELECT tenant_id,source_id,item_id,%s,observed_at,sha256,size_bytes,"
                "media_type,metadata FROM brain_source_versions "
                "WHERE tenant_id=%s AND id=%s",
                (next_version, ctx.tenant_id, version_id),
            )
            conn.execute(
                "UPDATE brain_source_items SET current_version_id=%s WHERE tenant_id=%s "
                "AND id=%s", (next_version, ctx.tenant_id, item_id),
            )
        return opened

    monkeypatch.setattr(replay_module, "read_confined_file", race)
    with pytest.raises(Conflict, match="basis changed"):
        replay.record_current_text_replay(ctx, proposal_id, root)
    with store.transaction(ctx) as conn:
        assert conn.execute(
            "SELECT count(*) AS n FROM knowledge_statement_fileos_replays "
            "WHERE proposal_id=%s", (proposal_id,),
        ).fetchone()["n"] == 0
