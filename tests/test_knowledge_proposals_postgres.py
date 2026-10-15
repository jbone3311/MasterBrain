"""Fictional, disposable SQL/API proof of private Knowledge proposal review."""

from __future__ import annotations

import hashlib
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import psycopg
import pytest
import test_postgres as pg
from fastapi.testclient import TestClient

from email_brain.api import create_app
from email_brain.auth import Credential, TokenRegistry
from email_brain.schemas import SearchRequest
from email_brain.store import Conflict, NotFound, Store
from masterbrain.knowledge import KnowledgeCore
from masterbrain.knowledge_proposals import KnowledgeProposalBatches
from masterbrain.knowledge_schema import (
    KnowledgeProposalDecision,
    KnowledgeProposalReviewRequest,
    KnowledgeProposalStageRequest,
)

pytestmark = pytest.mark.postgres
database, tenant = pg.database, pg.tenant
QUOTE = "Melron investment briefing"


def prepared(store: Store, tenant_data: tuple) -> tuple:
    ctx, account = tenant_data
    store.ingest_page(ctx, account, None, "proposal-synthetic-page", [pg.item()])
    legacy_id = store.search(ctx, SearchRequest(query=QUOTE))[0]["evidence_id"]
    context = replace(
        pg.datacore_context(ctx),
        scopes=pg.datacore_context(ctx).scopes | frozenset({
            "knowledge.review", "knowledge.read", "knowledge.search",
            "brain.content.read",
        }),
    )
    bridged = pg.DataCoreStore(store).bridge_current_email_version(
        context, legacy_id, uuid4(), code_revision="proposal-batch-synthetic-v1",
    )
    return context, bridged.evidence_id


def proposal(evidence_id: str, ordinal: int) -> dict:
    return {
        "kind": "project", "title": f"Melron proposed project {ordinal:02d}",
        "state": "active", "evidence_ids": [evidence_id],
        "source_quote": QUOTE, "confidence": 0.9,
        "observed_at": datetime(2026, 10, 14, tzinfo=UTC).isoformat(),
    }


def decisions(rows: list[dict], rejected: set[int]) -> KnowledgeProposalReviewRequest:
    return KnowledgeProposalReviewRequest(
        batch_sha256="0" * 64,
        decisions=[KnowledgeProposalDecision(
            proposal_id=row["proposal_id"],
            decision="rejected" if row["ordinal"] in rejected else "approved",
            reason="Not supported for publication" if row["ordinal"] in rejected else None,
        ) for row in rows],
    )


def test_forty_private_proposals_review_38_atomically_and_replay(database, tenant):
    store, _ = database
    ctx, evidence_id = prepared(store, tenant)
    queue = KnowledgeProposalBatches(store)
    body = KnowledgeProposalStageRequest(
        proposals=[proposal(evidence_id, number) for number in range(40)]
    )
    stage_key = uuid4()
    staged = queue.stage(ctx, body, stage_key)
    assert staged["row_count"] == 40 and staged["reviewed"] is False
    assert queue.stage(ctx, body, stage_key)["changed"] is False
    with pytest.raises(Conflict):
        queue.stage(ctx, KnowledgeProposalStageRequest(proposals=[proposal(evidence_id, 99)]),
                    stage_key)
    assert KnowledgeCore(store).search(ctx, "Melron proposed") == []
    with store.transaction(ctx) as conn:
        assert conn.execute("SELECT count(*) AS n FROM knowledge_projects").fetchone()["n"] == 0
        assert conn.execute(
            "SELECT count(*) AS n FROM knowledge_change_events"
        ).fetchone()["n"] == 0
    page = queue.preview(ctx, staged["batch_id"])
    assert len(page["proposals"]) == 40 and page["reviewed"] is False
    assert all("reviewed" not in row["assertion"] for row in page["proposals"])
    review = decisions(page["proposals"], {5, 37})
    review.batch_sha256 = staged["batch_sha256"]
    review_key = uuid4()
    accepted = queue.review(ctx, staged["batch_id"], review, review_key)
    assert accepted == {"batch_id": staged["batch_id"], "approved": 38,
                        "rejected": 2, "changed": True}
    assert queue.review(ctx, staged["batch_id"], review, review_key)["changed"] is False
    with pytest.raises(Conflict):
        queue.review(ctx, staged["batch_id"], review, uuid4())
    with store.transaction(ctx) as conn:
        assert conn.execute("SELECT count(*) AS n FROM knowledge_projects").fetchone()["n"] == 38
        assert conn.execute(
            "SELECT count(*) AS n FROM knowledge_change_events"
        ).fetchone()["n"] == 38
        assert conn.execute(
            "SELECT count(*) AS n FROM knowledge_proposal_decisions"
        ).fetchone()["n"] == 40
        assert conn.execute("SELECT count(*) AS n FROM knowledge_receipts").fetchone()["n"] == 38
    assert len(KnowledgeCore(store).search(ctx, "Melron proposed", limit=50)) == 38
    reviewed = queue.preview(ctx, staged["batch_id"])
    assert sum(row["status"] == "approved" for row in reviewed["proposals"]) == 38
    assert sum(row["status"] == "rejected" for row in reviewed["proposals"]) == 2


def test_review_holds_direct_evidence_source_state_until_commit(
    database, tenant, monkeypatch,
):
    store, admin = database
    ctx, evidence_id = prepared(store, tenant)
    queue = KnowledgeProposalBatches(store)
    staged = queue.stage(
        ctx, KnowledgeProposalStageRequest(proposals=[proposal(evidence_id, 1)]), uuid4(),
    )
    page = queue.preview(ctx, staged["batch_id"])
    original = KnowledgeProposalBatches._visible_basis
    checked = False

    def check_after_validation(conn, context, assertion, *args):
        nonlocal checked
        original(conn, context, assertion, *args)
        if not checked:
            checked = True
            for statement in (
                "UPDATE brain_source_items i SET current_version_id=NULL "
                "FROM brain_source_versions v JOIN brain_evidence e "
                "ON e.tenant_id=v.tenant_id AND e.source_version_id=v.id "
                "WHERE i.tenant_id=v.tenant_id AND i.id=v.item_id "
                "AND e.tenant_id=%s AND e.id=%s",
                "UPDATE brain_sources s SET status='paused' "
                "FROM brain_source_versions v JOIN brain_evidence e "
                "ON e.tenant_id=v.tenant_id AND e.source_version_id=v.id "
                "WHERE s.tenant_id=v.tenant_id AND s.id=v.source_id "
                "AND e.tenant_id=%s AND e.id=%s",
            ):
                with pytest.raises(psycopg.errors.LockNotAvailable):
                    with psycopg.connect(admin) as other:
                        other.execute("SET lock_timeout='100ms'")
                        other.execute(statement, (ctx.tenant_id, evidence_id))

    with monkeypatch.context() as patcher:
        patcher.setattr(KnowledgeProposalBatches, "_visible_basis",
                        staticmethod(check_after_validation))
        result = queue.review(ctx, staged["batch_id"],
                              KnowledgeProposalReviewRequest(
                                  batch_sha256=staged["batch_sha256"],
                                  decisions=[KnowledgeProposalDecision(
                                      proposal_id=page["proposals"][0]["proposal_id"],
                                      decision="approved",
                                  )],
                              ), uuid4())
    assert checked and result["approved"] == 1


def test_review_failure_rolls_back_every_row_and_hidden_basis(database, tenant):
    store, admin = database
    ctx, evidence_id = prepared(store, tenant)
    queue = KnowledgeProposalBatches(store)
    with pytest.raises(ValueError):
        queue.stage(ctx, KnowledgeProposalStageRequest(proposals=[{
            **proposal(evidence_id, 1), "source_quote": "Invented quote"
        }]), uuid4())
    staged = queue.stage(ctx, KnowledgeProposalStageRequest(proposals=[
        proposal(evidence_id, 0), proposal(evidence_id, 1),
    ]), uuid4())
    page = queue.preview(ctx, staged["batch_id"])
    review = decisions(page["proposals"], set())
    review.batch_sha256 = staged["batch_sha256"]
    with psycopg.connect(admin) as conn:
        conn.execute(
            "UPDATE message_sync_state SET status='excluded' WHERE tenant_id=%s",
            (ctx.tenant_id,),
        )
    with pytest.raises(NotFound):
        queue.preview(ctx, staged["batch_id"])
    with pytest.raises(NotFound):
        queue.review(ctx, staged["batch_id"], review, uuid4())
    with store.transaction(ctx) as conn:
        assert conn.execute("SELECT count(*) AS n FROM knowledge_projects").fetchone()["n"] == 0
        assert conn.execute(
            "SELECT count(*) AS n FROM knowledge_proposal_decisions"
        ).fetchone()["n"] == 0


def test_project_alias_quote_must_match_its_own_evidence(database, tenant):
    store, _ = database
    ctx, evidence_id = prepared(store, tenant)
    queue = KnowledgeProposalBatches(store)
    base = proposal(evidence_id, 1)
    alias = {
        "alias": "Melron side deal", "alias_kind": "name",
        "evidence_id": evidence_id, "source_quote": "Invented side deal",
    }
    with pytest.raises(ValueError, match="alias quote lacks an exact source span"):
        queue.stage(ctx, KnowledgeProposalStageRequest(proposals=[{
            **base, "aliases": [alias],
        }]), uuid4())
    with store.transaction(ctx) as conn:
        assert conn.execute(
            "SELECT count(*) AS n FROM knowledge_proposal_batches"
        ).fetchone()["n"] == 0
    valid = {**base, "aliases": [{**alias, "source_quote": QUOTE}]}
    staged = queue.stage(ctx, KnowledgeProposalStageRequest(proposals=[valid]), uuid4())
    assert queue.preview(ctx, staged["batch_id"])["proposals"][0]["assertion"][
        "aliases"
    ][0]["source_quote"] == QUOTE


def test_project_alias_quote_in_another_linked_evidence_is_not_enough(database, tenant):
    store, _ = database
    ctx, first_id = prepared(store, tenant)
    _, account = tenant
    second_quote = "Fictional second source names Cedar Lane"
    store.ingest_page(ctx, account, "proposal-synthetic-page", "proposal-second-page", [
        replace(pg.item("proposal-e2", body=second_quote), provider_id="proposal-message-2"),
    ])
    legacy_id = store.search(ctx, SearchRequest(query=second_quote))[0]["evidence_id"]
    second = pg.DataCoreStore(store).bridge_current_email_version(
        ctx, legacy_id, uuid4(), code_revision="proposal-alias-second-source-v1",
    )
    base = {**proposal(first_id, 1), "evidence_ids": [first_id, second.evidence_id]}
    alias = {
        "alias": "Cedar Lane", "alias_kind": "address",
        "evidence_id": second.evidence_id, "source_quote": QUOTE,
    }
    queue = KnowledgeProposalBatches(store)
    with pytest.raises(ValueError, match="alias quote lacks an exact source span"):
        queue.stage(ctx, KnowledgeProposalStageRequest(proposals=[{
            **base, "aliases": [alias],
        }]), uuid4())
    valid = {**base, "aliases": [{**alias, "source_quote": second_quote}]}
    staged = queue.stage(ctx, KnowledgeProposalStageRequest(proposals=[valid]), uuid4())
    assert queue.preview(ctx, staged["batch_id"])["row_count"] == 1


def test_review_bad_related_row_is_all_or_nothing(database, tenant):
    store, _ = database
    ctx, evidence_id = prepared(store, tenant)
    queue = KnowledgeProposalBatches(store)
    valid = proposal(evidence_id, 0)
    bad = {
        "kind": "commitment", "description": "Melron proposed commitment", "state": "open",
        "project_id": "project_" + "f" * 32, "evidence_ids": [evidence_id],
        "source_quote": QUOTE, "confidence": 0.9,
        "observed_at": datetime(2026, 10, 14, tzinfo=UTC).isoformat(),
    }
    staged = queue.stage(ctx, KnowledgeProposalStageRequest(proposals=[valid, bad]), uuid4())
    page = queue.preview(ctx, staged["batch_id"])
    review = decisions(page["proposals"], set())
    review.batch_sha256 = staged["batch_sha256"]
    with pytest.raises(NotFound):
        queue.review(ctx, staged["batch_id"], review, uuid4())
    with store.transaction(ctx) as conn:
        assert conn.execute("SELECT count(*) AS n FROM knowledge_projects").fetchone()["n"] == 0
        assert conn.execute(
            "SELECT count(*) AS n FROM knowledge_proposal_decisions"
        ).fetchone()["n"] == 0


def test_proposal_tenant_source_and_immutable_sql_fences(database, tenant):
    store, admin = database
    ctx, evidence_id = prepared(store, tenant)
    queue = KnowledgeProposalBatches(store)
    staged = queue.stage(
        ctx, KnowledgeProposalStageRequest(proposals=[proposal(evidence_id, 0)]), uuid4(),
    )
    batch_id = staged["batch_id"]
    foreign_ctx, _ = pg.tenant.__wrapped__(database)
    foreign_ctx = replace(foreign_ctx, scopes=ctx.scopes)
    with pytest.raises(NotFound):
        queue.preview(foreign_ctx, batch_id)
    restricted = replace(ctx, source_ids=frozenset({"ungranted_source"}))
    with pytest.raises(NotFound):
        queue.preview(restricted, batch_id)
    with pytest.raises(NotFound):
        queue.stage(
            restricted,
            KnowledgeProposalStageRequest(proposals=[proposal(evidence_id, 1)]),
            uuid4(),
        )
    with store.transaction(foreign_ctx) as conn:
        assert conn.execute(
            "SELECT count(*) AS n FROM knowledge_proposal_batches WHERE id=%s", (batch_id,)
        ).fetchone()["n"] == 0
    with pytest.raises(psycopg.Error), store.transaction(ctx) as conn:
        conn.execute(
            "UPDATE knowledge_proposal_batches SET row_count=2 WHERE id=%s", (batch_id,)
        )
    with pytest.raises(psycopg.Error), psycopg.connect(admin) as conn:
        conn.execute("TRUNCATE knowledge_proposal_review_receipts")
    proposal_id = queue.preview(ctx, batch_id)["proposals"][0]["proposal_id"]
    with pytest.raises(psycopg.Error), store.transaction(ctx) as conn:
        conn.execute(
            "INSERT INTO knowledge_proposal_decisions(tenant_id,batch_id,proposal_id,"
            "decision,reviewer_id,reason) VALUES (%s,%s,%s,'rejected',%s,'No')",
            (ctx.tenant_id, batch_id, proposal_id, ctx.actor_id),
        )
    with pytest.raises(psycopg.Error), store.transaction(ctx) as conn:
        conn.execute(
            "INSERT INTO knowledge_proposal_review_receipts(tenant_id,reviewer_id,"
            "idempotency_key,batch_id,request_sha256,approved_count,rejected_count) "
            "VALUES (%s,%s,%s,%s,%s,0,1)",
            (ctx.tenant_id, ctx.actor_id, uuid4(), batch_id, "0" * 64),
        )
    assert queue.preview(ctx, batch_id)["row_count"] == 1


def _client(store: Store, ctx, scopes: set[str], kind: str = "human") -> TestClient:
    token = "synthetic-" + uuid4().hex
    credential = Credential(
        token_sha256=hashlib.sha256(token.encode()).hexdigest(),
        tenant_id=ctx.tenant_id, actor_id=ctx.actor_id, scopes=scopes,
        expires_at=datetime.now(UTC) + timedelta(hours=1), client_kind=kind,
        source_ids={"synthetic_source"} if kind == "assistant" else None,
    )
    return TestClient(create_app(store, TokenRegistry([credential])),
                      headers={"Authorization": "Bearer " + token})


def test_proposal_api_human_scopes_and_closed_payload(database, tenant):
    store, _ = database
    ctx, evidence_id = prepared(store, tenant)
    body = {"proposals": [proposal(evidence_id, 0)]}
    client = _client(store, ctx, {"knowledge.review", "knowledge.read", "brain.content.read"})
    staged = client.post("/v1/knowledge/proposal-batches", json=body,
                         headers={"idempotency-key": str(uuid4())})
    assert staged.status_code == 201, staged.text
    batch_id = staged.json()["batch_id"]
    page = client.get(f"/v1/knowledge/proposal-batches/{batch_id}")
    assert page.status_code == 200 and page.headers["cache-control"] == "no-store"
    assert page.json()["reviewed"] is False
    assert _client(store, ctx, {"knowledge.read"}).get(
        f"/v1/knowledge/proposal-batches/{batch_id}"
    ).status_code == 403
    assert _client(store, ctx, {"knowledge.review"}).get(
        f"/v1/knowledge/proposal-batches/{batch_id}"
    ).status_code == 403
    assert _client(store, ctx, {"knowledge.read", "brain.content.read"}, "assistant").get(
        f"/v1/knowledge/proposal-batches/{batch_id}"
    ).status_code == 403
    with pytest.raises(ValueError, match="review is human-only"):
        _client(store, ctx, {"knowledge.review"}, "assistant")
    assert client.post("/v1/knowledge/proposal-batches", json={
        "proposals": [{**proposal(evidence_id, 0), "reviewed": True}]
    }, headers={"idempotency-key": str(uuid4())}).status_code == 422
    row = page.json()["proposals"][0]
    reviewed = client.post(f"/v1/knowledge/proposal-batches/{batch_id}/review", json={
        "batch_sha256": page.json()["batch_sha256"],
        "decisions": [{"proposal_id": row["proposal_id"], "decision": "approved"}],
    }, headers={"idempotency-key": str(uuid4())})
    assert reviewed.status_code == 200, reviewed.text
    assert reviewed.json()["approved"] == 1
