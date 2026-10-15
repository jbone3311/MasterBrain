"""Fictional ADR-206 fact Markdown proposals stay private until explicit review."""

from __future__ import annotations

import hashlib
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import psycopg
import pytest
import test_postgres as pg
from fastapi.testclient import TestClient
from psycopg.types.json import Jsonb
from test_project_dossier_markdown_postgres import _published
from test_project_facts_postgres import _body, _prepared

from email_brain.api import create_app
from email_brain.auth import Credential, TokenRegistry
from email_brain.store import Conflict, NotFound
from masterbrain.fact_proposals import FactProposalBatches
from masterbrain.knowledge_schema import (
    FactProposalReviewRequest,
    ProjectDossierRequest,
    ProjectFactPageRequest,
)
from masterbrain.librarian_dossier_intake import DossierProposalStageRequest
from masterbrain.project_dossier_markdown import ProjectDossierMarkdown
from masterbrain.project_facts import ProjectFacts

pytestmark = pytest.mark.postgres
database, tenant = pg.database, pg.tenant
CLAIM = "pfact_" + "d" * 32
SECOND = "pfact_" + "e" * 32


def _candidate(store, ctx, project_id, evidence_id, *, two=False):
    *_, first = _published(store, ctx, project_id, evidence_id)
    second_id = None
    if two:
        second_id = ProjectFacts(store).publish(
            ctx, project_id,
            _body(project_id, evidence_id, value="Second fictional amount"), uuid4(),
        )["object_id"]
    markdown = ProjectDossierMarkdown(store).export(
        ctx, project_id, ProjectDossierRequest(),
    )["markdown"].replace(first["object_id"], CLAIM)
    first_body = _body(project_id, evidence_id).model_dump(mode="json")
    first_body.pop("reviewed")
    selections = [{"claimed_id": CLAIM, "assertion": first_body}]
    if second_id is not None:
        markdown = markdown.replace(second_id, SECOND)
        second_body = _body(
            project_id, evidence_id, value="Second fictional amount",
        ).model_dump(mode="json")
        second_body.pop("reviewed")
        selections.append({"claimed_id": SECOND, "assertion": second_body})
    return DossierProposalStageRequest(markdown=markdown, selections=selections)


def _decisions(staged, choices):
    return FactProposalReviewRequest(
        batch_sha256=staged["batch_sha256"],
        decisions=[
            {"proposal_id": row["proposal_id"], "decision": choice,
             "reason": "fictional rejection" if choice == "rejected" else None}
            for row, choice in zip(choices[0], choices[1], strict=True)
        ],
    )


def test_fact_markdown_private_stage_preview_review_and_replay(database, tenant):
    store, admin = database
    ctx, _, project_id, evidence_id = _prepared(store, tenant)
    body = _candidate(store, ctx, project_id, evidence_id)
    service = FactProposalBatches(store)
    before = ProjectFacts(store).page(ctx, project_id, ProjectFactPageRequest())["results"]
    key = uuid4()
    staged = service.stage(ctx, body, key)
    assert staged["changed"] and staged["reviewed"] is False
    assert service.stage(ctx, body, key) == {**staged, "changed": False}
    preview = service.preview(ctx, staged["batch_id"])
    assert preview["untrusted_content"] is True
    assert preview["proposals"][0]["status"] == "proposed"
    assert preview["proposals"][0]["assertion"]["kind"] == "project_fact"
    assert ProjectFacts(store).page(ctx, project_id, ProjectFactPageRequest())["results"] == before
    changed = body.model_dump(mode="json")
    changed["selections"][0]["assertion"]["confidence"] = 0.8
    with pytest.raises(Conflict):
        service.stage(ctx, DossierProposalStageRequest.model_validate(changed), key)
    decision = _decisions(staged, (preview["proposals"], ["approved"]))
    review_key = uuid4()
    accepted = service.review(ctx, staged["batch_id"], decision, review_key)
    assert accepted == {"batch_id": staged["batch_id"], "approved": 1,
                        "rejected": 0, "changed": True}
    assert service.review(ctx, staged["batch_id"], decision, review_key) == {
        **accepted, "changed": False,
    }
    page = ProjectFacts(store).page(ctx, project_id, ProjectFactPageRequest())
    assert len(page["results"]) == len(before) + 1
    assert page["results"][0]["object_id"] != CLAIM
    with psycopg.connect(admin) as conn:
        assert conn.execute(
            "SELECT count(*) FROM knowledge_fact_proposal_decisions "
            "WHERE tenant_id=%s AND batch_id=%s", (ctx.tenant_id, staged["batch_id"]),
        ).fetchone()[0] == 1


def test_fact_batch_mixed_decisions_and_stale_source_refusal(database, tenant):
    store, admin = database
    ctx, _, project_id, evidence_id = _prepared(store, tenant)
    body = _candidate(store, ctx, project_id, evidence_id, two=True)
    service = FactProposalBatches(store)
    staged = service.stage(ctx, body, uuid4())
    preview = service.preview(ctx, staged["batch_id"])
    assert len(preview["proposals"]) == 2
    result = service.review(
        ctx, staged["batch_id"],
        _decisions(staged, (preview["proposals"], ["approved", "rejected"])),
        uuid4(),
    )
    assert result["approved"] == result["rejected"] == 1
    another = service.stage(ctx, body, uuid4())
    with psycopg.connect(admin) as conn:
        conn.execute(
            "UPDATE brain_source_items i SET current_version_id=NULL "
            "FROM brain_source_versions v JOIN brain_evidence e "
            "ON e.tenant_id=v.tenant_id AND e.source_version_id=v.id "
            "WHERE i.tenant_id=v.tenant_id AND i.id=v.item_id "
            "AND e.tenant_id=%s AND e.id=%s", (ctx.tenant_id, evidence_id),
        )
    with pytest.raises((NotFound, Conflict)):
        service.preview(ctx, another["batch_id"])
    with pytest.raises((NotFound, Conflict)):
        service.review(
            ctx, another["batch_id"],
            FactProposalReviewRequest(
                batch_sha256=another["batch_sha256"],
                decisions=[
                    {"proposal_id": row["proposal_id"], "decision": "approved"}
                    for row in preview["proposals"]
                ],
            ), uuid4(),
        )
    with psycopg.connect(admin) as conn:
        assert conn.execute(
            "SELECT count(*) FROM knowledge_fact_proposal_decisions "
            "WHERE tenant_id=%s AND batch_id=%s", (ctx.tenant_id, another["batch_id"]),
        ).fetchone()[0] == 0


def test_fact_review_second_publication_failure_rolls_back_all(database, tenant, monkeypatch):
    store, admin = database
    ctx, _, project_id, evidence_id = _prepared(store, tenant)
    body = _candidate(store, ctx, project_id, evidence_id, two=True)
    service = FactProposalBatches(store)
    staged = service.stage(ctx, body, uuid4())
    preview = service.preview(ctx, staged["batch_id"])
    before = len(ProjectFacts(store).page(
        ctx, project_id, ProjectFactPageRequest(),
    )["results"])
    original = ProjectFacts._publish_in_transaction
    calls = 0

    def fail_second(self, conn, context, linked_project, fact, key):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise ValueError("fictional second publication fault")
        return original(self, conn, context, linked_project, fact, key)

    request = _decisions(staged, (preview["proposals"], ["approved", "approved"]))
    with monkeypatch.context() as patcher:
        patcher.setattr(ProjectFacts, "_publish_in_transaction", fail_second)
        with pytest.raises(ValueError, match="second publication fault"):
            service.review(ctx, staged["batch_id"], request, uuid4())
    assert len(ProjectFacts(store).page(
        ctx, project_id, ProjectFactPageRequest(),
    )["results"]) == before
    with psycopg.connect(admin) as conn:
        assert conn.execute(
            "SELECT count(*) FROM knowledge_fact_proposal_decisions "
            "WHERE tenant_id=%s AND batch_id=%s", (ctx.tenant_id, staged["batch_id"]),
        ).fetchone()[0] == 0
    assert service.review(ctx, staged["batch_id"], request, uuid4())["approved"] == 2


def test_fact_proposal_sql_tenant_immutability_and_citation_guards(database, tenant):
    store, admin = database
    ctx, _, project_id, evidence_id = _prepared(store, tenant)
    body = _candidate(store, ctx, project_id, evidence_id)
    service = FactProposalBatches(store)
    staged = service.stage(ctx, body, uuid4())
    batch_id = staged["batch_id"]
    proposal = service.preview(ctx, batch_id)["proposals"][0]
    foreign_ctx, _ = pg.tenant.__wrapped__(database)
    foreign_ctx = replace(foreign_ctx, scopes=ctx.scopes)
    with pytest.raises(NotFound):
        service.preview(foreign_ctx, batch_id)
    with store.transaction(foreign_ctx) as conn:
        assert conn.execute(
            "SELECT count(*) AS n FROM knowledge_fact_proposal_batches WHERE id=%s",
            (batch_id,),
        ).fetchone()["n"] == 0
    with pytest.raises(psycopg.Error), store.transaction(ctx) as conn:
        conn.execute(
            "UPDATE knowledge_fact_proposal_batches SET row_count=2 WHERE id=%s",
            (batch_id,),
        )
    with pytest.raises(psycopg.Error), psycopg.connect(admin) as conn:
        conn.execute("TRUNCATE knowledge_fact_proposal_review_receipts")
    with pytest.raises(psycopg.Error), store.transaction(ctx) as conn:
        conn.execute(
            "INSERT INTO knowledge_fact_proposal_decisions(tenant_id,batch_id,"
            "proposal_id,decision,reviewer_id,reason) "
            "VALUES (%s,%s,%s,'rejected',%s,'No')",
            (ctx.tenant_id, batch_id, proposal["proposal_id"], ctx.actor_id),
        )
    invalid_batch = "kfbatch_" + uuid4().hex
    with pytest.raises(psycopg.Error, match="invalid fact proposal quote citation"):
        with store.transaction(ctx) as conn:
            conn.execute(
                "INSERT INTO knowledge_fact_proposal_batches(tenant_id,id,proposer_id,"
                "idempotency_key,request_sha256,import_context_sha256,row_count) "
                "VALUES (%s,%s,%s,%s,%s,%s,1)",
                (ctx.tenant_id, invalid_batch, ctx.actor_id, uuid4(), "a" * 64,
                 "b" * 64),
            )
            conn.execute(
                "INSERT INTO knowledge_fact_proposals(tenant_id,id,batch_id,ordinal,"
                "claimed_id,payload,payload_sha256,quote_evidence_id,evidence_count) "
                "VALUES (%s,%s,%s,0,%s,%s,%s,%s,1)",
                (ctx.tenant_id, "kfproposal_" + uuid4().hex, invalid_batch,
                 "pfact_" + uuid4().hex, Jsonb(proposal["assertion"]), "c" * 64,
                 "evidence_" + "f" * 32),
            )
    assert service.preview(ctx, batch_id)["row_count"] == 1
    assert evidence_id in body.markdown


def test_fact_markdown_rejects_unrendered_and_false_citation(database, tenant):
    store, _ = database
    ctx, _, project_id, evidence_id = _prepared(store, tenant)
    request = _candidate(store, ctx, project_id, evidence_id)
    payload = request.model_dump(mode="json")
    payload["selections"][0]["assertion"]["source_quote"] = "invented quote"
    with pytest.raises(ValueError, match="does not match"):
        FactProposalBatches(store).stage(
            ctx, DossierProposalStageRequest.model_validate(payload), uuid4(),
        )
    payload = request.model_dump(mode="json")
    payload["selections"][0]["assertion"]["valid_from"] = datetime.now(UTC).isoformat()
    with pytest.raises(ValueError, match="unrendered"):
        FactProposalBatches(store).stage(
            ctx, DossierProposalStageRequest.model_validate(payload), uuid4(),
        )
    assert evidence_id in request.markdown


def test_fact_proposal_api_requires_human_content_scope(database, tenant):
    store, _ = database
    ctx, _, project_id, evidence_id = _prepared(store, tenant)
    body = _candidate(store, ctx, project_id, evidence_id)
    route = "/v1/knowledge/dossier-markdown/fact-proposal-batches"

    def api(scopes, kind="human"):
        token = "fictional-fact-stage-" + uuid4().hex
        credential = Credential(
            token_sha256=hashlib.sha256(token.encode()).hexdigest(),
            tenant_id=ctx.tenant_id, actor_id=ctx.actor_id, scopes=scopes,
            expires_at=datetime.now(UTC) + timedelta(hours=1),
            client_kind=kind,
            source_ids={"source_fictional"} if kind == "assistant" else None,
        )
        return TestClient(
            create_app(store, TokenRegistry([credential])),
            headers={"Authorization": "Bearer " + token},
        )

    with api({"knowledge.review", "brain.content.read"}) as client:
        staged = client.post(
            route, json=body.model_dump(mode="json"),
            headers={"Idempotency-Key": str(uuid4())},
        )
        assert staged.status_code == 201, staged.text
        batch_id = staged.json()["batch_id"]
        preview = client.get("/v1/knowledge/fact-proposal-batches/" + batch_id)
        assert preview.status_code == 200, preview.text
        row_id = preview.json()["proposals"][0]["proposal_id"]
        reviewed = client.post(
            "/v1/knowledge/fact-proposal-batches/" + batch_id + "/review",
            json={"batch_sha256": staged.json()["batch_sha256"],
                  "decisions": [{"proposal_id": row_id, "decision": "rejected",
                                 "reason": "fictional"}]},
            headers={"Idempotency-Key": str(uuid4())},
        )
        assert reviewed.status_code == 200, reviewed.text
        assert reviewed.json()["rejected"] == 1
    with api({"knowledge.review"}) as client:
        assert client.post(
            route, json=body.model_dump(mode="json"),
            headers={"Idempotency-Key": str(uuid4())},
        ).status_code == 403
    with api({"brain.content.read"}, "assistant") as client:
        assert client.post(
            route, json=body.model_dump(mode="json"),
            headers={"Idempotency-Key": str(uuid4())},
        ).status_code == 403
