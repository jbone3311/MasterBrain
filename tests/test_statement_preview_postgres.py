"""Fictional, owner-only API and source-bound statement proposal previews."""

from __future__ import annotations

import hashlib
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import psycopg
import pytest
import test_postgres as pg
from fastapi.testclient import TestClient
from test_statement_persistence_postgres import HEADER, TEXT, source_document, worker

from email_brain.api import create_app
from email_brain.auth import Credential, TokenRegistry
from email_brain.domain.models import TenantContext
from email_brain.store import Conflict, NotFound, Store
from masterbrain.datacore.contracts import stable_id
from masterbrain.statement_persistence import StatementProposalReader, StatementProposalStore

database, tenant = pg.database, pg.tenant
pytestmark = pytest.mark.postgres


def reader(ctx: TenantContext) -> TenantContext:
    return replace(ctx, scopes=frozenset({"knowledge.read", "brain.content.read"}))


def api_client(
    store: Store, ctx: TenantContext, *, scopes: set[str], kind: str = "human",
) -> TestClient:
    token = "synthetic-" + uuid4().hex
    credential = Credential(
        token_sha256=hashlib.sha256(token.encode()).hexdigest(),
        tenant_id=ctx.tenant_id,
        actor_id=ctx.actor_id,
        scopes=scopes,
        expires_at=datetime.now(UTC) + timedelta(hours=1),
        client_kind=kind,
        source_ids={"synthetic_statement_source"} if kind == "assistant" else None,
    )
    return TestClient(
        create_app(store, TokenRegistry([credential])),
        base_url="http://127.0.0.1", headers={"Authorization": "Bearer " + token},
    )


@pytest.mark.parametrize("source_kind", ["email", "fileos"])
def test_owner_preview_quotes_exact_current_document_and_no_reviewed_claim(
    database: tuple[Store, str], tenant: tuple[TenantContext, UUID], source_kind: str,
) -> None:
    store, admin = database
    ctx = tenant[0]
    document_id, _, _ = source_document(admin, worker(ctx), kind=source_kind)
    proposal = StatementProposalStore(store).project_current_document(
        worker(ctx), document_id, uuid4()
    )
    result = StatementProposalReader(store).read_page(reader(ctx), proposal["proposal_id"])
    assert result["source_kind"] == source_kind
    assert result["status"] == "reconciled" and result["row_count"] == 1
    assert result["rows"][0]["quote"] == TEXT[
        result["rows"][0]["text_start"]:result["rows"][0]["text_end"]
    ]
    assert result["rows"][0]["assertion_status"] == "proposed_extraction"
    assert result["rows"][0]["amount"] == "100.000000000000"
    assert result["currency_assumption"].startswith("USD")
    assert result["reviewed"] is False and result["source_effects"] is False
    assert result["page"] == {"next_after": None, "truncated": False}
    with store.transaction(reader(ctx)) as conn:
        assert conn.execute("SELECT count(*) AS n FROM knowledge_claims").fetchone()["n"] == 0


def test_owner_api_requires_both_scopes_and_refuses_assistant_worker(
    database: tuple[Store, str], tenant: tuple[TenantContext, UUID],
) -> None:
    store, admin = database
    ctx = tenant[0]
    document_id, _, _ = source_document(admin, worker(ctx))
    proposal_id = StatementProposalStore(store).project_current_document(
        worker(ctx), document_id, uuid4()
    )["proposal_id"]
    path = f"/v1/knowledge/statement-proposals/{proposal_id}"
    allowed = api_client(store, ctx, scopes={"knowledge.read", "brain.content.read"})
    response = allowed.get(path)
    assert response.status_code == 200
    assert response.json()["proposal_id"] == proposal_id
    assert response.json()["untrusted_content"] is True
    assert response.headers["cache-control"] == "no-store"
    assert api_client(store, ctx, scopes={"knowledge.read"}).get(path).status_code == 403
    assert api_client(
        store, ctx, scopes={"knowledge.read", "brain.content.read"}, kind="assistant"
    ).get(path).status_code == 403
    assert api_client(
        store, ctx, scopes={"knowledge.read", "brain.content.read"}, kind="worker"
    ).get(path).status_code == 403
    assert allowed.get("/v1/knowledge/statement-proposals/bad-id").status_code == 404
    assert allowed.get(path + "?limit=26").status_code == 422


def test_preview_pages_rows_and_refuses_ungranted_or_stale_source(
    database: tuple[Store, str], tenant: tuple[TenantContext, UUID],
) -> None:
    store, admin = database
    ctx = tenant[0]
    holding = "ACME Fictional Corporation 2 $50.00 $100.00 $40.00 $20.00 $80.00"
    body = (
        "Account No: 000000\nPeriod: April - 2024\nLong $2600.00\n"
        f"{HEADER}\n" + (holding + "\n") * 26
    )
    document_id, item_id, version_id = source_document(admin, worker(ctx), body=body)
    proposal_id = StatementProposalStore(store).project_current_document(
        worker(ctx), document_id, uuid4()
    )["proposal_id"]
    preview = StatementProposalReader(store)
    page = preview.read_page(reader(ctx), proposal_id)
    assert len(page["rows"]) == 25 and page["page"]["next_after"] == 24
    last = preview.read_page(reader(ctx), proposal_id, after=24)
    assert [row["ordinal"] for row in last["rows"]] == [25]
    assert last["page"]["next_after"] is None
    with pytest.raises(NotFound):
        preview.read_page(
            replace(reader(ctx), source_ids=frozenset({"some_other_source"})), proposal_id
        )
    new_version = stable_id("version", item_id, "next")
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
    with pytest.raises(Conflict, match="not current"):
        preview.read_page(reader(ctx), proposal_id)


def test_long_source_quote_is_bounded_with_visible_truncation(
    database: tuple[Store, str], tenant: tuple[TenantContext, UUID],
) -> None:
    store, admin = database
    ctx = tenant[0]
    description = "Fictional " * 29
    holding = f"ACME {description}2 $50.00 $100.00 $40.00 $20.00 $80.00"
    body = (
        "Account No: 000000\nPeriod: April - 2024\nLong $100.00\n"
        f"{HEADER}\n{holding}"
    )
    document_id, _, _ = source_document(admin, worker(ctx), body=body)
    proposal_id = StatementProposalStore(store).project_current_document(
        worker(ctx), document_id, uuid4()
    )["proposal_id"]
    result = StatementProposalReader(store).read_page(reader(ctx), proposal_id)
    row = result["rows"][0]
    assert row["quote_truncated"] is True
    assert len(row["quote"]) == 300
    assert row["quote"] == body[row["text_start"]:row["text_start"] + 300]
