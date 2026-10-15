"""Synthetic, private Markdown-to-proposal staging with no automatic review."""

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
from test_project_facts_postgres import NOW, QUOTE, _prepared, _source

from email_brain.api import create_app
from email_brain.auth import Credential, TokenRegistry
from email_brain.store import Conflict, NotFound
from masterbrain.knowledge import KnowledgeCore
from masterbrain.knowledge_proposals import KnowledgeProposalBatches
from masterbrain.knowledge_schema import (
    CommitmentWrite,
    EntityWrite,
    EventWrite,
    KnowledgeProposalDecision,
    KnowledgeProposalReviewRequest,
    KnowledgeProposalStageRequest,
    MemberWrite,
    ProjectDossierRequest,
    ProjectWrite,
)
from masterbrain.librarian_dossier_intake import (
    DossierMarkdownInspection,
    DossierProposalImport,
    DossierProposalStageRequest,
    inspect_project_dossier_markdown,
)
from masterbrain.project_dossier_markdown import ProjectDossierMarkdown

pytestmark = pytest.mark.postgres
database, tenant = pg.database, pg.tenant
NEW_EVENT = "event_" + "f" * 32
NEW_COMMITMENT = "commitment_" + "e" * 32
NEW_MEMBER = "member_" + "c" * 32


def _candidate(store, ctx, project_id, evidence_id):
    entity, event, commitment, _, _, _ = _published(
        store, ctx, project_id, evidence_id,
    )
    markdown = ProjectDossierMarkdown(store).export(
        ctx, project_id, ProjectDossierRequest(),
    )["markdown"]
    markdown = markdown.replace(event.object_id, NEW_EVENT)
    markdown = markdown.replace(commitment.object_id, NEW_COMMITMENT)
    common = dict(
        evidence_ids=[evidence_id], source_quote=QUOTE, confidence=1.0,
        observed_at=NOW, reviewed=True,
    )
    event_body = EventWrite(
        kind="event", project_id=project_id, event_type="review",
        title="Fictional review", **common,
    ).model_dump(mode="json")
    commitment_body = CommitmentWrite(
        kind="commitment", project_id=project_id,
        description="Fictional promise", state="open",
        owner_entity_id=entity.object_id, **common,
    ).model_dump(mode="json")
    event_body.pop("reviewed")
    commitment_body.pop("reviewed")
    body = DossierProposalStageRequest(
        markdown=markdown,
        selections=[
            {"claimed_id": NEW_EVENT, "assertion": event_body},
            {"claimed_id": NEW_COMMITMENT, "assertion": commitment_body},
        ],
    )
    return body


def _member_candidate(store, ctx, project_id, evidence_id):
    entity, _, _, member, _, _ = _published(store, ctx, project_id, evidence_id)
    markdown = ProjectDossierMarkdown(store).export(
        ctx, project_id, ProjectDossierRequest(),
    )["markdown"].replace(member.object_id, NEW_MEMBER)
    assertion = MemberWrite(
        kind="member", project_id=project_id, entity_id=entity.object_id,
        role="broker", evidence_ids=[evidence_id], source_quote=QUOTE,
        confidence=1.0, observed_at=NOW, reviewed=True,
    ).model_dump(mode="json")
    assertion.pop("reviewed")
    return DossierProposalStageRequest(
        markdown=markdown,
        selections=[{"claimed_id": NEW_MEMBER, "assertion": assertion}],
    )


def _separate_entity_member_candidate(store, ctx, account, project_id, evidence_id):
    entity_evidence = _source(
        store, ctx, account, "fictional-member-entity-2", "fictional-fact-message-1",
    )
    entity = KnowledgeCore(store).publish(ctx, EntityWrite(
        kind="entity", entity_type="person", name="Fictional Morgan",
        evidence_ids=[entity_evidence], source_quote=QUOTE,
        confidence=1.0, observed_at=NOW, reviewed=True,
    ), uuid4())
    member = KnowledgeCore(store).publish(ctx, MemberWrite(
        kind="member", project_id=project_id, entity_id=entity.object_id,
        role="counsel", evidence_ids=[evidence_id], source_quote=QUOTE,
        confidence=1.0, observed_at=NOW, reviewed=True,
    ), uuid4())
    markdown = ProjectDossierMarkdown(store).export(
        ctx, project_id, ProjectDossierRequest(),
    )["markdown"].replace(member.object_id, NEW_MEMBER)
    assertion = MemberWrite(
        kind="member", project_id=project_id, entity_id=entity.object_id,
        role="counsel", evidence_ids=[evidence_id], source_quote=QUOTE,
        confidence=1.0, observed_at=NOW, reviewed=True,
    ).model_dump(mode="json")
    assertion.pop("reviewed")
    return DossierProposalStageRequest(
        markdown=markdown,
        selections=[{"claimed_id": NEW_MEMBER, "assertion": assertion}],
    ), entity_evidence


def test_member_row_stages_privately_then_requires_explicit_review(database, tenant):
    store, admin = database
    ctx, _, project_id, evidence_id = _prepared(store, tenant)
    body = _member_candidate(store, ctx, project_id, evidence_id)
    service = DossierProposalImport(store)
    with psycopg.connect(admin) as conn:
        before = conn.execute(
            "SELECT count(*) FROM knowledge_project_members WHERE tenant_id=%s",
            (ctx.tenant_id,),
        ).fetchone()[0]
    key = uuid4()
    staged = service.stage(ctx, body, key)
    assert staged["row_count"] == 1 and staged["reviewed"] is False
    assert service.stage(ctx, body, key)["changed"] is False
    page = KnowledgeProposalBatches(store).preview(ctx, staged["batch_id"])
    assert page["proposals"][0]["status"] == "proposed"
    with psycopg.connect(admin) as conn:
        assert conn.execute(
            "SELECT import_quote_evidence_id,import_entity_citation_id "
            "FROM knowledge_proposals WHERE tenant_id=%s AND id=%s",
            (ctx.tenant_id, page["proposals"][0]["proposal_id"]),
        ).fetchone() == (evidence_id, evidence_id)
        assert conn.execute(
            "SELECT count(*) FROM knowledge_project_members WHERE tenant_id=%s",
            (ctx.tenant_id,),
        ).fetchone()[0] == before
    reviewed = KnowledgeProposalBatches(store).review(
        ctx, staged["batch_id"], KnowledgeProposalReviewRequest(
            batch_sha256=staged["batch_sha256"],
            decisions=[KnowledgeProposalDecision(
                proposal_id=page["proposals"][0]["proposal_id"],
                decision="approved",
            )],
        ), uuid4(),
    )
    assert reviewed["approved"] == 1
    with psycopg.connect(admin) as conn:
        rows = conn.execute(
            "SELECT id FROM knowledge_project_members WHERE tenant_id=%s",
            (ctx.tenant_id,),
        ).fetchall()
    assert len(rows) == before + 1
    assert NEW_MEMBER not in {row[0] for row in rows}


def test_generic_member_proposal_keeps_nullable_import_columns(database, tenant):
    store, admin = database
    ctx, _, project_id, evidence_id = _prepared(store, tenant)
    body = _member_candidate(store, ctx, project_id, evidence_id)
    generic = KnowledgeProposalStageRequest(
        proposals=[body.selections[0].assertion],
    )
    batches = KnowledgeProposalBatches(store)
    staged = batches.stage(ctx, generic, uuid4())
    page = batches.preview(ctx, staged["batch_id"])
    assert page["proposals"][0]["status"] == "proposed"
    with psycopg.connect(admin) as conn:
        assert conn.execute(
            "SELECT import_quote_evidence_id,import_entity_citation_id "
            "FROM knowledge_proposals WHERE tenant_id=%s AND id=%s",
            (ctx.tenant_id, page["proposals"][0]["proposal_id"]),
        ).fetchone() == (None, None)


@pytest.mark.parametrize(
    ("imported", "quote_id", "entity_id", "reason"),
    [
        (True, None, "same", "missing imported proposal quote citation"),
        (True, "same", None, "missing imported member entity citation"),
        (True, "other", "same", "missing imported proposal quote citation"),
        (False, "same", None, "unexpected imported proposal citation"),
    ],
)
def test_sql_guard_rejects_missing_or_unbound_import_citations(
    database, tenant, imported, quote_id, entity_id, reason,
):
    store, _ = database
    ctx, _, project_id, evidence_id = _prepared(store, tenant)
    body = _member_candidate(store, ctx, project_id, evidence_id)
    payload = body.selections[0].assertion
    batch_id = "kbatch_" + uuid4().hex
    proposal_id = "kproposal_" + uuid4().hex
    quote = evidence_id if quote_id == "same" else (
        "evidence_" + "a" * 32 if quote_id == "other" else None
    )
    entity = evidence_id if entity_id == "same" else None
    with pytest.raises(psycopg.Error, match=reason), store.transaction(ctx) as conn:
        conn.execute(
            "INSERT INTO knowledge_proposal_batches(tenant_id,id,proposer_id,"
            "idempotency_key,request_sha256,row_count,import_context_sha256) "
            "VALUES (%s,%s,%s,%s,%s,1,%s)",
            (ctx.tenant_id, batch_id, ctx.actor_id, uuid4(), "a" * 64,
             "b" * 64 if imported else None),
        )
        conn.execute(
            "INSERT INTO knowledge_proposals(tenant_id,id,batch_id,ordinal,"
            "payload,payload_sha256,evidence_count,import_quote_evidence_id,"
            "import_entity_citation_id) VALUES (%s,%s,%s,0,%s,%s,1,%s,%s)",
            (ctx.tenant_id, proposal_id, batch_id, Jsonb(payload), "c" * 64,
             quote, entity),
        )


def test_member_import_binds_entity_and_role_citations(database, tenant):
    store, admin = database
    ctx, _, project_id, evidence_id = _prepared(store, tenant)
    body = _member_candidate(store, ctx, project_id, evidence_id)
    importer = DossierProposalImport(store)
    bad_entity = body.model_copy(deep=True)
    bad_entity.selections[0].assertion["entity_id"] = "entity_" + "a" * 32
    with pytest.raises(ValueError):
        importer.stage(ctx, bad_entity, uuid4())
    bad_role = body.model_copy(deep=True)
    bad_role.selections[0].assertion["role"] = "counsel"
    with pytest.raises(ValueError):
        importer.stage(ctx, bad_role, uuid4())
    bad_citation = body.model_copy(deep=True)
    member_line = next(
        line for line in bad_citation.markdown.splitlines()
        if line.startswith("- member `" + NEW_MEMBER)
    )
    bad_citation.markdown = bad_citation.markdown.replace(
        member_line, member_line.replace(
            "citation `" + evidence_id + "`", "citation `evidence_" + "a" * 32 + "`",
            1,
        ),
    )
    with pytest.raises(Conflict):
        importer.stage(ctx, bad_citation, uuid4())
    with psycopg.connect(admin) as conn:
        assert conn.execute(
            "SELECT count(*) FROM knowledge_proposal_batches WHERE tenant_id=%s",
            (ctx.tenant_id,),
        ).fetchone()[0] == 0


def test_member_import_rejects_wrong_valid_entity_citation_and_revocation(
    database, tenant, monkeypatch,
):
    store, admin = database
    ctx, account, project_id, evidence_id = _prepared(store, tenant)
    body, entity_evidence = _separate_entity_member_candidate(
        store, ctx, account, project_id, evidence_id,
    )
    wrong = body.model_copy(deep=True)
    member_line = next(
        line for line in wrong.markdown.splitlines()
        if line.startswith("- member `" + NEW_MEMBER)
    )
    wrong.markdown = wrong.markdown.replace(
        member_line, member_line.replace(
            "citation `" + entity_evidence + "`",
            "citation `" + evidence_id + "`", 1,
        ),
    )
    with pytest.raises(ValueError, match="entity citation mismatch"):
        DossierProposalImport(store).stage(ctx, wrong, uuid4())

    original = DossierMarkdownInspection.inspect

    def inspect_then_revoke(service, context, markdown):
        result = original(service, context, markdown)
        with psycopg.connect(admin) as conn:
            conn.execute(
                "UPDATE brain_source_items i SET current_version_id=NULL "
                "FROM brain_source_versions v JOIN brain_evidence e "
                "ON e.tenant_id=v.tenant_id AND e.source_version_id=v.id "
                "WHERE i.tenant_id=v.tenant_id AND i.id=v.item_id "
                "AND e.tenant_id=%s AND e.id=%s", (ctx.tenant_id, entity_evidence),
            )
        return result

    monkeypatch.setattr(DossierMarkdownInspection, "inspect", inspect_then_revoke)
    key = uuid4()
    with pytest.raises(Conflict):
        DossierProposalImport(store).stage(ctx, body, key)
    with psycopg.connect(admin) as conn:
        assert conn.execute(
            "SELECT count(*) FROM knowledge_proposal_batches "
            "WHERE tenant_id=%s AND idempotency_key=%s",
            (ctx.tenant_id, key),
        ).fetchone()[0] == 0


def test_member_and_invalid_event_batch_rolls_back_atomically(database, tenant):
    store, admin = database
    ctx, _, project_id, evidence_id = _prepared(store, tenant)
    body = _member_candidate(store, ctx, project_id, evidence_id)
    event_id = next(
        row["claimed_id"]
        for row in inspect_project_dossier_markdown(body.markdown)["candidates"]
        if row["kind"] == "event"
    )
    request = body.model_dump(mode="json")
    request["markdown"] = request["markdown"].replace(event_id, NEW_EVENT)
    invalid_event = EventWrite(
        kind="event", project_id=project_id, event_type="review",
        title="Fictional review", evidence_ids=[
            evidence_id, "evidence_" + "b" * 32,
        ], source_quote=QUOTE, confidence=1.0, observed_at=NOW, reviewed=True,
    ).model_dump(mode="json")
    invalid_event.pop("reviewed")
    request["selections"].append({"claimed_id": NEW_EVENT, "assertion": invalid_event})
    body = DossierProposalStageRequest.model_validate(request)
    key = uuid4()
    with pytest.raises(NotFound):
        DossierProposalImport(store).stage(ctx, body, key)
    with psycopg.connect(admin) as conn:
        assert conn.execute(
            "SELECT count(*) FROM knowledge_proposal_batches "
            "WHERE tenant_id=%s AND idempotency_key=%s", (ctx.tenant_id, key),
        ).fetchone()[0] == 0


def test_member_private_preview_and_review_recheck_entity_source(database, tenant):
    store, admin = database
    ctx, account, project_id, evidence_id = _prepared(store, tenant)
    body, entity_evidence = _separate_entity_member_candidate(
        store, ctx, account, project_id, evidence_id,
    )
    batches = KnowledgeProposalBatches(store)
    staged = DossierProposalImport(store).stage(ctx, body, uuid4())
    page = batches.preview(ctx, staged["batch_id"])
    with psycopg.connect(admin) as conn:
        conn.execute(
            "UPDATE brain_source_items i SET current_version_id=NULL "
            "FROM brain_source_versions v JOIN brain_evidence e "
            "ON e.tenant_id=v.tenant_id AND e.source_version_id=v.id "
            "WHERE i.tenant_id=v.tenant_id AND i.id=v.item_id "
            "AND e.tenant_id=%s AND e.id=%s", (ctx.tenant_id, entity_evidence),
        )
    with pytest.raises(Conflict):
        batches.preview(ctx, staged["batch_id"])
    with pytest.raises(Conflict):
        batches.review(ctx, staged["batch_id"], KnowledgeProposalReviewRequest(
            batch_sha256=staged["batch_sha256"],
            decisions=[KnowledgeProposalDecision(
                proposal_id=page["proposals"][0]["proposal_id"],
                decision="approved",
            )],
        ), uuid4())
    with psycopg.connect(admin) as conn:
        assert conn.execute(
            "SELECT count(*) FROM knowledge_proposal_decisions "
            "WHERE tenant_id=%s AND batch_id=%s",
            (ctx.tenant_id, staged["batch_id"]),
        ).fetchone()[0] == 0


def test_member_review_holds_linked_entity_citation_source_until_commit(
    database, tenant, monkeypatch,
):
    store, admin = database
    ctx, account, project_id, evidence_id = _prepared(store, tenant)
    body, entity_evidence = _separate_entity_member_candidate(
        store, ctx, account, project_id, evidence_id,
    )
    batches = KnowledgeProposalBatches(store)
    staged = DossierProposalImport(store).stage(ctx, body, uuid4())
    page = batches.preview(ctx, staged["batch_id"])
    original = KnowledgeProposalBatches._lock_linked_citation_basis
    checked = False

    def check_after_entity_lock(conn, context, allowed, kind, object_id):
        nonlocal checked
        original(conn, context, allowed, kind, object_id)
        if kind == "entity" and not checked:
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
                        other.execute(statement, (ctx.tenant_id, entity_evidence))

    with monkeypatch.context() as patcher:
        patcher.setattr(KnowledgeProposalBatches, "_lock_linked_citation_basis",
                        staticmethod(check_after_entity_lock))
        result = batches.review(ctx, staged["batch_id"], KnowledgeProposalReviewRequest(
            batch_sha256=staged["batch_sha256"],
            decisions=[KnowledgeProposalDecision(
                proposal_id=page["proposals"][0]["proposal_id"],
                decision="approved",
            )],
        ), uuid4())
    assert checked and result["approved"] == 1


def test_two_rows_stage_private_replay_then_explicit_mixed_review(database, tenant):
    store, admin = database
    ctx, _, project_id, evidence_id = _prepared(store, tenant)
    body = _candidate(store, ctx, project_id, evidence_id)
    importer = DossierProposalImport(store)
    key = uuid4()
    with psycopg.connect(admin) as conn:
        before = conn.execute(
            "SELECT count(*) FROM knowledge_events WHERE tenant_id=%s",
            (ctx.tenant_id,),
        ).fetchone()[0]
    staged = importer.stage(ctx, body, key)
    assert staged["changed"] is True
    assert staged["reviewed"] is False
    assert staged["row_count"] == 2
    assert len(staged["import_context_sha256"]) == 64
    assert importer.stage(ctx, body, key)["changed"] is False
    page = KnowledgeProposalBatches(store).preview(ctx, staged["batch_id"])
    assert page["import_context_sha256"] == staged["import_context_sha256"]
    assert [p["status"] for p in page["proposals"]] == ["proposed", "proposed"]
    with psycopg.connect(admin) as conn:
        assert conn.execute(
            "SELECT count(*) FROM knowledge_events WHERE tenant_id=%s",
            (ctx.tenant_id,),
        ).fetchone()[0] == before
        assert conn.execute(
            "SELECT import_context_sha256 FROM knowledge_proposal_batches "
            "WHERE tenant_id=%s AND id=%s", (ctx.tenant_id, staged["batch_id"]),
        ).fetchone()[0] == staged["import_context_sha256"]
    with pytest.raises(psycopg.Error), store.transaction(ctx) as conn:
        conn.execute(
            "UPDATE knowledge_proposal_batches SET import_context_sha256=%s "
            "WHERE id=%s", ("0" * 64, staged["batch_id"]),
        )
    decisions = KnowledgeProposalReviewRequest(
        batch_sha256=staged["batch_sha256"],
        decisions=[
            KnowledgeProposalDecision(
                proposal_id=page["proposals"][0]["proposal_id"], decision="approved",
            ),
            KnowledgeProposalDecision(
                proposal_id=page["proposals"][1]["proposal_id"],
                decision="rejected", reason="Fictional commitment needs revision",
            ),
        ],
    )
    reviewed = KnowledgeProposalBatches(store).review(
        ctx, staged["batch_id"], decisions, uuid4(),
    )
    assert reviewed["approved"] == reviewed["rejected"] == 1
    with psycopg.connect(admin) as conn:
        assert conn.execute(
            "SELECT count(*) FROM knowledge_events WHERE tenant_id=%s",
            (ctx.tenant_id,),
        ).fetchone()[0] == before + 1
        assert conn.execute(
            "SELECT object_id FROM knowledge_proposal_decisions "
            "WHERE tenant_id=%s AND proposal_id=%s",
            (ctx.tenant_id, page["proposals"][0]["proposal_id"]),
        ).fetchone()[0] != NEW_EVENT


def test_changed_context_mismatch_and_existing_claim_fail_closed(database, tenant):
    store, admin = database
    ctx, _, project_id, evidence_id = _prepared(store, tenant)
    body = _candidate(store, ctx, project_id, evidence_id)
    importer = DossierProposalImport(store)
    key = uuid4()
    importer.stage(ctx, body, key)
    changed = body.model_copy(deep=True)
    changed.markdown = changed.markdown.replace(
        'reviewed title "Fictional Melron deal"',
        'reviewed title "Fictional Melron case"',
    )
    with pytest.raises(Conflict):
        importer.stage(ctx, changed, key)
    mismatch = body.model_copy(deep=True)
    mismatch.selections[0].assertion["title"] = "A different fictional review"
    bad_key = uuid4()
    with pytest.raises(ValueError):
        importer.stage(ctx, mismatch, bad_key)
    with psycopg.connect(admin) as conn:
        assert conn.execute(
            "SELECT count(*) FROM knowledge_proposal_batches "
            "WHERE tenant_id=%s AND idempotency_key=%s",
            (ctx.tenant_id, bad_key),
        ).fetchone()[0] == 0
    existing = body.model_copy(deep=True)
    with psycopg.connect(admin) as conn:
        original = conn.execute(
            "SELECT id FROM knowledge_events WHERE tenant_id=%s "
            "AND project_id=%s ORDER BY recorded_at DESC LIMIT 1",
            (ctx.tenant_id, project_id),
        ).fetchone()[0]
    existing.markdown = existing.markdown.replace(NEW_EVENT, original)
    existing.selections[0].claimed_id = original
    with pytest.raises(Conflict):
        importer.stage(ctx, existing, uuid4())


def test_imported_child_requires_existing_local_project(database, tenant):
    store, admin = database
    ctx, _, project_id, evidence_id = _prepared(store, tenant)
    body = _candidate(store, ctx, project_id, evidence_id)
    missing_project = "project_" + "a" * 32
    body.markdown = body.markdown.replace(project_id, missing_project)
    body.selections = body.selections[:1]
    body.selections[0].assertion["project_id"] = missing_project
    key = uuid4()
    with pytest.raises(NotFound):
        DossierProposalImport(store).stage(ctx, body, key)
    with psycopg.connect(admin) as conn:
        assert conn.execute(
            "SELECT count(*) FROM knowledge_proposal_batches "
            "WHERE tenant_id=%s AND idempotency_key=%s",
            (ctx.tenant_id, key),
        ).fetchone()[0] == 0


def test_wrong_cited_full_quote_rolls_back_whole_batch(database, tenant):
    store, admin = database
    ctx, account, project_id, evidence_id = _prepared(store, tenant)
    other_key = "fictional-unrelated-message"
    store.ingest_page(ctx, account, "fictional-fact-message-1", other_key, [
        replace(pg.item(other_key, body="Fictional unrelated material"),
                provider_id=other_key),
    ])
    with store.transaction(ctx) as conn:
        legacy_id = conn.execute(
            "SELECT v.id FROM message_versions v JOIN messages m "
            "ON m.tenant_id=v.tenant_id AND m.id=v.message_id "
            "WHERE m.provider_message_id=%s ORDER BY v.id DESC LIMIT 1",
            (other_key,),
        ).fetchone()["id"]
    other_evidence = pg.DataCoreStore(store).bridge_current_email_version(
        ctx, legacy_id, uuid4(), code_revision="dossier-import-fictional-v1",
    ).evidence_id
    assertion = EventWrite(
        kind="event", project_id=project_id, event_type="review",
        title="Fictional review", evidence_ids=[evidence_id, other_evidence],
        source_quote=QUOTE, confidence=1.0, observed_at=NOW, reviewed=True,
    ).model_dump(mode="json")
    assertion.pop("reviewed")
    key = uuid4()
    with pytest.raises(ValueError, match="cited source span"):
        KnowledgeProposalBatches(store).stage(
            ctx, KnowledgeProposalStageRequest(proposals=[assertion, assertion]), key,
            import_context_sha256="a" * 64,
            import_claims=[
                (NEW_EVENT, evidence_id),
                ("event_" + "e" * 32, other_evidence),
            ],
        )
    with psycopg.connect(admin) as conn:
        assert conn.execute(
            "SELECT count(*) FROM knowledge_proposal_batches "
            "WHERE tenant_id=%s AND idempotency_key=%s",
            (ctx.tenant_id, key),
        ).fetchone()[0] == 0


def test_api_human_scopes_and_exact_whitespace(database, tenant):
    store, _ = database
    ctx, _, project_id, evidence_id = _prepared(store, tenant)
    body = _candidate(store, ctx, project_id, evidence_id)
    route = "/v1/knowledge/dossier-markdown/proposal-batches"

    def api(scopes):
        token = "fictional-dossier-stage-" + uuid4().hex
        credential = Credential(
            token_sha256=hashlib.sha256(token.encode()).hexdigest(),
            tenant_id=ctx.tenant_id, actor_id=ctx.actor_id, scopes=scopes,
            expires_at=datetime.now(UTC) + timedelta(hours=1),
            client_kind="human",
        )
        return TestClient(
            create_app(store, TokenRegistry([credential])),
            headers={"Authorization": "Bearer " + token},
        )

    with api({"knowledge.review", "brain.content.read"}) as client:
        accepted = client.post(
            route, json=body.model_dump(mode="json"),
            headers={"Idempotency-Key": str(uuid4())},
        )
        assert accepted.status_code == 201, accepted.text
        assert accepted.json()["reviewed"] is False
        assert "import_context_sha256" in accepted.json()
        member = _member_candidate(store, ctx, project_id, evidence_id)
        member_response = client.post(
            route, json=member.model_dump(mode="json"),
            headers={"Idempotency-Key": str(uuid4())},
        )
        assert member_response.status_code == 201, member_response.text
        member_page = client.get(
            "/v1/knowledge/proposal-batches/" + member_response.json()["batch_id"],
        )
        assert member_page.status_code == 200, member_page.text
        assert member_page.json()["proposals"][0]["assertion"]["kind"] == "member"
        assert member_page.json()["proposals"][0]["status"] == "proposed"
        truncated = body.model_dump(mode="json")
        truncated["markdown"] = truncated["markdown"].rstrip()
        assert client.post(
            route, json=truncated, headers={"Idempotency-Key": str(uuid4())},
        ).status_code == 422
    with api({"knowledge.review"}) as client:
        assert client.post(
            route, json=body.model_dump(mode="json"),
            headers={"Idempotency-Key": str(uuid4())},
        ).status_code == 403


def test_source_revoked_after_inspection_cannot_stage(database, tenant, monkeypatch):
    store, admin = database
    ctx, _, project_id, evidence_id = _prepared(store, tenant)
    body = _candidate(store, ctx, project_id, evidence_id)
    original = DossierMarkdownInspection.inspect

    def inspect_then_revoke(service, context, markdown):
        result = original(service, context, markdown)
        with psycopg.connect(admin) as conn:
            conn.execute(
                "UPDATE brain_source_items i SET current_version_id=NULL "
                "FROM brain_source_versions v JOIN brain_evidence e "
                "ON e.tenant_id=v.tenant_id AND e.source_version_id=v.id "
                "WHERE i.tenant_id=v.tenant_id AND i.id=v.item_id "
                "AND e.tenant_id=%s AND e.id=%s", (ctx.tenant_id, evidence_id),
            )
        return result

    monkeypatch.setattr(DossierMarkdownInspection, "inspect", inspect_then_revoke)
    key = uuid4()
    with pytest.raises(NotFound):
        DossierProposalImport(store).stage(ctx, body, key)
    with psycopg.connect(admin) as conn:
        assert conn.execute(
            "SELECT count(*) FROM knowledge_proposal_batches "
            "WHERE tenant_id=%s AND idempotency_key=%s",
            (ctx.tenant_id, key),
        ).fetchone()[0] == 0


def test_project_row_can_stage_privately_but_fact_row_cannot(database, tenant):
    store, admin = database
    ctx, _, project_id, evidence_id = _prepared(store, tenant)
    original = ProjectDossierMarkdown(store).export(
        ctx, project_id, ProjectDossierRequest(),
    )["markdown"]
    new_project = "project_" + "d" * 32
    body = ProjectWrite(
        kind="project", title="Fictional Melron deal", state="active",
        evidence_ids=[evidence_id], source_quote=QUOTE, confidence=1.0,
        observed_at=NOW, reviewed=True,
    ).model_dump(mode="json")
    body.pop("reviewed")
    request = DossierProposalStageRequest(
        markdown=original.replace(project_id, new_project),
        selections=[{"claimed_id": new_project, "assertion": body}],
    )
    staged = DossierProposalImport(store).stage(ctx, request, uuid4())
    assert staged["reviewed"] is False
    with psycopg.connect(admin) as conn:
        assert conn.execute(
            "SELECT count(*) FROM knowledge_projects "
            "WHERE tenant_id=%s AND id=%s", (ctx.tenant_id, new_project),
        ).fetchone()[0] == 0
    fact_request = _candidate(store, ctx, project_id, evidence_id)
    fact_id = next(
        row["claimed_id"]
        for row in inspect_project_dossier_markdown(fact_request.markdown)["candidates"]
        if row["kind"] == "fact"
    )
    fact_request = DossierProposalStageRequest(
        markdown=fact_request.markdown,
        selections=[{"claimed_id": fact_id, "assertion": body}],
    )
    with pytest.raises(ValueError):
        DossierProposalImport(store).stage(ctx, fact_request, uuid4())
