"""Fictional ADR-207 selected artifact links stay private until human review."""

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
from test_project_artifacts_postgres import _body, _evidence, _prepared

from email_brain.api import create_app
from email_brain.auth import Credential, TokenRegistry
from email_brain.store import Conflict, NotFound
from masterbrain.artifact_proposals import ArtifactProposalBatches
from masterbrain.knowledge_schema import (
    ArtifactProposalReviewRequest,
    ProjectArtifactPageRequest,
    ProjectDossierRequest,
)
from masterbrain.librarian_dossier_intake import (
    DossierMarkdownInspection,
    DossierProposalStageRequest,
)
from masterbrain.project_artifacts import ProjectArtifactLinks
from masterbrain.project_dossier_markdown import ProjectDossierMarkdown

pytestmark = pytest.mark.postgres
database, tenant = pg.database, pg.tenant
CLAIM = "partifact_" + "d" * 32
SECOND = "partifact_" + "e" * 32


def _candidate(store, ctx, project_id, basis_id, artifact_id, *, two=False):
    links = ProjectArtifactLinks(store)
    first = links.publish(ctx, project_id, _body(artifact_id, basis_id), uuid4())
    second_id = None
    if two:
        second_id = links.publish(ctx, project_id, _body(artifact_id, basis_id), uuid4())[
            "object_id"
        ]
    markdown = ProjectDossierMarkdown(store).export(
        ctx, project_id, ProjectDossierRequest(),
    )["markdown"].replace(first["object_id"], CLAIM)
    link_body = _body(artifact_id, basis_id).model_dump(mode="json")
    selections = [{"claimed_id": CLAIM, "assertion": link_body}]
    if second_id is not None:
        markdown = markdown.replace(second_id, SECOND)
        selections.append({"claimed_id": SECOND, "assertion": link_body})
    return DossierProposalStageRequest(markdown=markdown, selections=selections)


def _review(staged, proposals, choices):
    return ArtifactProposalReviewRequest(
        batch_sha256=staged["batch_sha256"],
        decisions=[
            {"proposal_id": row["proposal_id"], "decision": choice,
             "reason": "fictional rejection" if choice == "rejected" else None}
            for row, choice in zip(proposals, choices, strict=True)
        ],
    )


def test_artifact_markdown_private_stage_preview_review_and_replay(database, tenant):
    store, admin = database
    ctx, _, project_id, basis_id, artifact_id = _prepared(store, tenant)
    body = _candidate(store, ctx, project_id, basis_id, artifact_id)
    service = ArtifactProposalBatches(store)
    before = ProjectArtifactLinks(store).page(
        ctx, project_id, ProjectArtifactPageRequest(),
    )["results"]
    key = uuid4()
    staged = service.stage(ctx, body, key)
    assert staged["changed"] and staged["reviewed"] is False
    assert service.stage(ctx, body, key) == {**staged, "changed": False}
    preview = service.preview(ctx, staged["batch_id"])
    assert preview["untrusted_content"] is True
    assert preview["proposals"][0]["status"] == "proposed"
    assert preview["proposals"][0]["artifact_source_kind"] == "email"
    assert ProjectArtifactLinks(store).page(
        ctx, project_id, ProjectArtifactPageRequest(),
    )["results"] == before
    changed = body.model_dump(mode="json")
    changed["selections"][0]["assertion"]["relation"] = "primary"
    with pytest.raises(ValueError):
        service.stage(ctx, DossierProposalStageRequest.model_validate(changed), key)
    decision = _review(staged, preview["proposals"], ["approved"])
    review_key = uuid4()
    accepted = service.review(ctx, staged["batch_id"], decision, review_key)
    assert accepted["approved"] == 1 and accepted["rejected"] == 0
    assert service.review(ctx, staged["batch_id"], decision, review_key) == {
        **accepted, "changed": False,
    }
    page = ProjectArtifactLinks(store).page(
        ctx, project_id, ProjectArtifactPageRequest(),
    )["results"]
    assert len(page) == len(before) + 1
    assert page[0]["object_id"] != CLAIM
    with psycopg.connect(admin) as conn:
        assert conn.execute(
            "SELECT count(*) FROM knowledge_artifact_proposal_decisions "
            "WHERE tenant_id=%s AND batch_id=%s", (ctx.tenant_id, staged["batch_id"]),
        ).fetchone()[0] == 1


def test_artifact_batch_mixed_decisions_and_stale_source_refusal(database, tenant):
    store, admin = database
    ctx, _, project_id, basis_id, artifact_id = _prepared(store, tenant)
    body = _candidate(store, ctx, project_id, basis_id, artifact_id, two=True)
    service = ArtifactProposalBatches(store)
    staged = service.stage(ctx, body, uuid4())
    preview = service.preview(ctx, staged["batch_id"])
    assert len(preview["proposals"]) == 2
    result = service.review(
        ctx, staged["batch_id"],
        _review(staged, preview["proposals"], ["approved", "rejected"]), uuid4(),
    )
    assert result["approved"] == result["rejected"] == 1
    with pytest.raises(Conflict, match="already approved"):
        service.stage(ctx, body, uuid4())
    another = service.stage(ctx, DossierProposalStageRequest(
        markdown=body.markdown, selections=body.selections[1:],
    ), uuid4())
    with psycopg.connect(admin) as conn:
        conn.execute(
            "UPDATE brain_source_items i SET current_version_id=NULL "
            "FROM brain_source_versions v JOIN brain_evidence e "
            "ON e.tenant_id=v.tenant_id AND e.source_version_id=v.id "
            "WHERE i.tenant_id=v.tenant_id AND i.id=v.item_id "
            "AND e.tenant_id=%s AND e.id=%s", (ctx.tenant_id, artifact_id),
        )
    with pytest.raises((NotFound, Conflict)):
        service.preview(ctx, another["batch_id"])
    with pytest.raises((NotFound, Conflict)):
        service.review(
            ctx, another["batch_id"],
            _review(another, preview["proposals"], ["approved", "approved"]), uuid4(),
        )
    with psycopg.connect(admin) as conn:
        assert conn.execute(
            "SELECT count(*) FROM knowledge_artifact_proposal_decisions "
            "WHERE tenant_id=%s AND batch_id=%s", (ctx.tenant_id, another["batch_id"]),
        ).fetchone()[0] == 0


def test_artifact_proposals_preserve_same_hash_distinct_occurrences(database, tenant):
    store, admin = database
    ctx, account, project_id, basis_id, first_artifact = _prepared(store, tenant)
    second_artifact = _evidence(
        store, ctx, account, key="projectethree", provider_id="project-message-3",
        cursor="project-artifact-page-2", next_cursor="project-artifact-page-3",
    )
    with store.transaction(ctx) as conn:
        evidence = conn.execute(
            "SELECT id,sha256 FROM brain_evidence WHERE id=ANY(%s)",
            ([first_artifact, second_artifact],),
        ).fetchall()
    assert first_artifact != second_artifact
    assert len(evidence) == 2 and len({row["sha256"] for row in evidence}) == 1

    links = ProjectArtifactLinks(store)
    selected = []
    markdown_ids = []
    for index, artifact_id in enumerate((first_artifact, second_artifact), start=1):
        published = links.publish(ctx, project_id, _body(artifact_id, basis_id), uuid4())
        claim = "partifact_" + f"{index:032x}"
        markdown_ids.append((published["object_id"], claim))
        selected.append({
            "claimed_id": claim,
            "assertion": _body(artifact_id, basis_id).model_dump(mode="json"),
        })
    markdown = ProjectDossierMarkdown(store).export(
        ctx, project_id, ProjectDossierRequest(),
    )["markdown"]
    for original_id, claim in markdown_ids:
        markdown = markdown.replace(original_id, claim)
    service = ArtifactProposalBatches(store)
    staged = service.stage(
        ctx, DossierProposalStageRequest(markdown=markdown, selections=selected), uuid4(),
    )
    preview = service.preview(ctx, staged["batch_id"])
    assert {row["assertion"]["artifact_evidence_id"]
            for row in preview["proposals"]} == {first_artifact, second_artifact}
    reviewed = service.review(
        ctx, staged["batch_id"],
        _review(staged, preview["proposals"], ["approved", "approved"]), uuid4(),
    )
    assert reviewed["approved"] == 2
    with psycopg.connect(admin) as conn:
        approved = conn.execute(
            "SELECT DISTINCT l.artifact_evidence_id FROM knowledge_project_artifacts l "
            "JOIN knowledge_artifact_proposal_decisions d "
            "ON d.tenant_id=l.tenant_id AND d.link_id=l.id "
            "WHERE d.tenant_id=%s AND d.batch_id=%s",
            (ctx.tenant_id, staged["batch_id"]),
        ).fetchall()
    assert {row[0] for row in approved} == {first_artifact, second_artifact}


def test_artifact_25_row_mixed_batch_rolls_back_and_retries(database, tenant, monkeypatch):
    store, admin = database
    ctx, _, project_id, basis_id, artifact_id = _prepared(store, tenant)
    links = ProjectArtifactLinks(store)
    selected = []
    markdown_ids = []
    for index in range(25):
        published = links.publish(ctx, project_id, _body(artifact_id, basis_id), uuid4())
        claim = "partifact_" + f"{index + 1:032x}"
        markdown_ids.append((published["object_id"], claim))
        selected.append({
            "claimed_id": claim,
            "assertion": _body(artifact_id, basis_id).model_dump(mode="json"),
        })
    markdown = ProjectDossierMarkdown(store).export(
        ctx, project_id, ProjectDossierRequest(artifact_limit=25),
    )["markdown"]
    for original_id, claim in markdown_ids:
        markdown = markdown.replace(original_id, claim)
    service = ArtifactProposalBatches(store)
    staged = service.stage(
        ctx, DossierProposalStageRequest(markdown=markdown, selections=selected), uuid4(),
    )
    preview = service.preview(ctx, staged["batch_id"])
    assert staged["row_count"] == len(preview["proposals"]) == 25
    choices = ["approved" if index % 2 == 0 else "rejected" for index in range(25)]
    request = _review(staged, preview["proposals"], choices)
    with psycopg.connect(admin) as conn:
        links_before = conn.execute(
            "SELECT count(*) FROM knowledge_project_artifacts WHERE tenant_id=%s",
            (ctx.tenant_id,),
        ).fetchone()[0]
    original = ProjectArtifactLinks._publish_in_transaction
    calls = 0

    def fail_last_approval(self, conn, context, linked_project, link, key):
        nonlocal calls
        calls += 1
        if calls == 13:
            raise ValueError("fictional final approval fault")
        return original(self, conn, context, linked_project, link, key)

    with monkeypatch.context() as patcher:
        patcher.setattr(ProjectArtifactLinks, "_publish_in_transaction", fail_last_approval)
        with pytest.raises(ValueError, match="final approval fault"):
            service.review(ctx, staged["batch_id"], request, uuid4())
    with psycopg.connect(admin) as conn:
        assert conn.execute(
            "SELECT count(*) FROM knowledge_artifact_proposal_decisions "
            "WHERE tenant_id=%s AND batch_id=%s", (ctx.tenant_id, staged["batch_id"]),
        ).fetchone()[0] == 0
        assert conn.execute(
            "SELECT count(*) FROM knowledge_project_artifacts WHERE tenant_id=%s",
            (ctx.tenant_id,),
        ).fetchone()[0] == links_before
    result = service.review(ctx, staged["batch_id"], request, uuid4())
    assert result["approved"] == 13 and result["rejected"] == 12
    with psycopg.connect(admin) as conn:
        assert conn.execute(
            "SELECT count(*) FROM knowledge_artifact_proposal_decisions "
            "WHERE tenant_id=%s AND batch_id=%s", (ctx.tenant_id, staged["batch_id"]),
        ).fetchone()[0] == 25
        assert conn.execute(
            "SELECT count(*) FROM knowledge_project_artifacts WHERE tenant_id=%s",
            (ctx.tenant_id,),
        ).fetchone()[0] == links_before + 13


def test_artifact_review_second_publication_fault_is_atomic(database, tenant, monkeypatch):
    store, admin = database
    ctx, _, project_id, basis_id, artifact_id = _prepared(store, tenant)
    body = _candidate(store, ctx, project_id, basis_id, artifact_id, two=True)
    service = ArtifactProposalBatches(store)
    staged = service.stage(ctx, body, uuid4())
    preview = service.preview(ctx, staged["batch_id"])
    request = _review(staged, preview["proposals"], ["approved", "approved"])
    before = len(ProjectArtifactLinks(store).page(
        ctx, project_id, ProjectArtifactPageRequest(),
    )["results"])
    original = ProjectArtifactLinks._publish_in_transaction
    calls = 0

    def fail_second(self, conn, context, linked_project, link, key):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise ValueError("fictional second artifact fault")
        return original(self, conn, context, linked_project, link, key)

    with monkeypatch.context() as patcher:
        patcher.setattr(ProjectArtifactLinks, "_publish_in_transaction", fail_second)
        with pytest.raises(ValueError, match="second artifact fault"):
            service.review(ctx, staged["batch_id"], request, uuid4())
    assert len(ProjectArtifactLinks(store).page(
        ctx, project_id, ProjectArtifactPageRequest(),
    )["results"]) == before
    with psycopg.connect(admin) as conn:
        assert conn.execute(
            "SELECT count(*) FROM knowledge_artifact_proposal_decisions "
            "WHERE tenant_id=%s AND batch_id=%s", (ctx.tenant_id, staged["batch_id"]),
        ).fetchone()[0] == 0
    assert service.review(ctx, staged["batch_id"], request, uuid4())["approved"] == 2


def test_artifact_review_holds_current_item_and_source_until_commit(
    database, tenant, monkeypatch,
):
    store, admin = database
    ctx, _, project_id, basis_id, artifact_id = _prepared(store, tenant)
    service = ArtifactProposalBatches(store)
    staged = service.stage(
        ctx, _candidate(store, ctx, project_id, basis_id, artifact_id), uuid4(),
    )
    preview = service.preview(ctx, staged["batch_id"])
    with store.transaction(ctx) as conn:
        source_id = conn.execute(
            "SELECT v.source_id FROM brain_evidence e JOIN brain_source_versions v "
            "ON v.tenant_id=e.tenant_id AND v.id=e.source_version_id WHERE e.id=%s",
            (artifact_id,),
        ).fetchone()["source_id"]
    original = ProjectArtifactLinks._validate_basis_in_transaction
    checked = False

    def check_concurrent_revocation(self, conn, context, linked_project, link):
        nonlocal checked
        result = original(self, conn, context, linked_project, link)
        if not checked:
            checked = True
            for statement, target in (
                ("UPDATE brain_source_items SET current_version_id=NULL "
                 "WHERE tenant_id=%s AND id=(SELECT v.item_id "
                 "FROM brain_evidence e JOIN brain_source_versions v "
                 "ON v.tenant_id=e.tenant_id AND v.id=e.source_version_id "
                 "WHERE e.tenant_id=%s AND e.id=%s)", artifact_id),
                ("UPDATE brain_sources SET status='paused' "
                 "WHERE tenant_id=%s AND id=%s", source_id),
            ):
                with pytest.raises(psycopg.errors.LockNotAvailable):
                    with psycopg.connect(admin) as other:
                        other.execute("SET lock_timeout='100ms'")
                        params = ((ctx.tenant_id, ctx.tenant_id, target)
                                  if target == artifact_id
                                  else (ctx.tenant_id, target))
                        other.execute(statement, params)
        return result

    with monkeypatch.context() as patcher:
        patcher.setattr(ProjectArtifactLinks, "_validate_basis_in_transaction",
                        check_concurrent_revocation)
        result = service.review(
            ctx, staged["batch_id"],
            _review(staged, preview["proposals"], ["approved"]), uuid4(),
        )
    assert checked and result["approved"] == 1
    with store.transaction(ctx) as conn:
        assert conn.execute(
            "SELECT status FROM brain_sources WHERE id=%s", (source_id,),
        ).fetchone()["status"] == "active"


def test_artifact_import_refuses_wrong_kind_and_current_grant(database, tenant):
    store, _ = database
    ctx, _, project_id, basis_id, artifact_id = _prepared(store, tenant)
    body = _candidate(store, ctx, project_id, basis_id, artifact_id)
    service = ArtifactProposalBatches(store)
    wrong = body.model_copy(deep=True)
    wrong.markdown = wrong.markdown.replace(
        f"to email evidence `{artifact_id}`", f"to fileos evidence `{artifact_id}`",
    )
    with pytest.raises(ValueError, match="does not match"):
        service.stage(ctx, wrong, uuid4())
    denied = replace(ctx, source_ids=frozenset())
    with pytest.raises((NotFound, Conflict)):
        service.stage(denied, body, uuid4())
    staged = service.stage(ctx, body, uuid4())
    preview = service.preview(ctx, staged["batch_id"])
    with pytest.raises((NotFound, Conflict)):
        service.preview(denied, staged["batch_id"])
    with pytest.raises((NotFound, Conflict)):
        service.review(
            denied, staged["batch_id"],
            _review(staged, preview["proposals"], ["approved"]), uuid4(),
        )


def test_fileos_artifact_proposal_rechecks_both_source_grants(
    database, tenant, tmp_path,
):
    store, _ = database
    ctx, _, project_id, basis_id, _ = _prepared(store, tenant)
    root = tmp_path / "fictional-artifact-source"
    root.mkdir()
    (root / "briefing.txt").write_text("Synthetic Melron term sheet.", encoding="utf-8")
    manifest = pg.fileos_manifest(root, source_id="artifact_proposal_files")
    core = pg.DataCoreStore(store)
    core.import_fileos_snapshot(ctx, manifest, uuid4())
    artifact_id = core.publish_text(
        ctx, manifest["items"][0]["version_id"], "Synthetic Melron term sheet.",
        code_revision="artifact-proposal-fictional-v1",
    ).evidence_id
    body = _candidate(store, ctx, project_id, basis_id, artifact_id)
    service = ArtifactProposalBatches(store)
    staged = service.stage(ctx, body, uuid4())
    preview = service.preview(ctx, staged["batch_id"])
    assert preview["proposals"][0]["artifact_source_kind"] == "fileos"
    with store.transaction(ctx) as conn:
        email_source = conn.execute(
            "SELECT v.source_id FROM brain_evidence e JOIN brain_source_versions v "
            "ON v.tenant_id=e.tenant_id AND v.id=e.source_version_id WHERE e.id=%s",
            (basis_id,),
        ).fetchone()["source_id"]
    email_only = replace(ctx, source_ids=frozenset({email_source}))
    file_only = replace(ctx, source_ids=frozenset({"artifact_proposal_files"}))
    for restricted in (email_only, file_only):
        with pytest.raises((NotFound, Conflict)):
            service.preview(restricted, staged["batch_id"])
        with pytest.raises((NotFound, Conflict)):
            service.review(
                restricted, staged["batch_id"],
                _review(staged, preview["proposals"], ["approved"]), uuid4(),
            )
    assert service.review(
        ctx, staged["batch_id"],
        _review(staged, preview["proposals"], ["approved"]), uuid4(),
    )["approved"] == 1
    assert ProjectArtifactLinks(store).page(
        ctx, project_id, ProjectArtifactPageRequest(limit=1),
    )["results"][0]["artifact_source_kind"] == "fileos"


def test_artifact_import_refuses_valid_preview_with_wrong_full_basis_quote(
    database, tenant,
):
    store, _ = database
    ctx, account, project_id, _, artifact_id = _prepared(store, tenant)
    prefix = "Fictional basis briefing " + "A" * 300
    real_quote = prefix + " correct ending"
    wrong_quote = prefix + " unrelated ending"
    cursor = "project-artifact-page-2"

    def evidence(key, text):
        nonlocal cursor
        store.ingest_page(ctx, account, cursor, key, [
            replace(pg.item(key, body=text), provider_id=key),
        ])
        cursor = key
        with store.transaction(ctx) as conn:
            version_id = conn.execute(
                "SELECT v.id FROM message_versions v JOIN messages m "
                "ON m.tenant_id=v.tenant_id AND m.id=v.message_id "
                "WHERE m.provider_message_id=%s ORDER BY v.id DESC LIMIT 1",
                (key,),
            ).fetchone()["id"]
        return pg.DataCoreStore(store).bridge_current_email_version(
            ctx, version_id, uuid4(), code_revision="artifact-proposal-quote-v1",
        ).evidence_id

    real_id = evidence("artifact-real-basis", real_quote)
    wrong_id = evidence("artifact-wrong-basis", wrong_quote)
    published = ProjectArtifactLinks(store).publish(
        ctx, project_id, _body(artifact_id, real_id, quote=real_quote), uuid4(),
    )
    markdown = ProjectDossierMarkdown(store).export(
        ctx, project_id, ProjectDossierRequest(),
    )["markdown"].replace(published["object_id"], CLAIM)
    original_line = next(
        line for line in markdown.splitlines()
        if line.startswith("- artifact link `" + CLAIM)
    )
    wrong_line = original_line.replace(
        "citation `" + real_id + "`", "citation `" + wrong_id + "`",
    )
    assert "quote prefix" in wrong_line
    altered = markdown.replace(original_line, wrong_line)
    inspected = DossierMarkdownInspection(store).inspect(ctx, altered)
    assert any(row["claimed_id"] == CLAIM for row in inspected["candidates"])
    with pytest.raises(ValueError, match="exact source span"):
        ArtifactProposalBatches(store).stage(
            ctx, DossierProposalStageRequest(
                markdown=altered,
                selections=[{
                    "claimed_id": CLAIM,
                    "assertion": _body(
                        artifact_id, wrong_id, quote=real_quote,
                    ).model_dump(mode="json"),
                }],
            ), uuid4(),
        )


def test_artifact_stage_rechecks_source_after_markdown_inspection(
    database, tenant, monkeypatch,
):
    store, admin = database
    ctx, _, project_id, basis_id, artifact_id = _prepared(store, tenant)
    body = _candidate(store, ctx, project_id, basis_id, artifact_id)
    original = DossierMarkdownInspection.inspect

    def inspect_then_revoke(self, context, markdown):
        inventory = original(self, context, markdown)
        with psycopg.connect(admin) as conn:
            conn.execute(
                "UPDATE brain_source_items i SET current_version_id=NULL "
                "FROM brain_source_versions v JOIN brain_evidence e "
                "ON e.tenant_id=v.tenant_id AND e.source_version_id=v.id "
                "WHERE i.tenant_id=v.tenant_id AND i.id=v.item_id "
                "AND e.tenant_id=%s AND e.id=%s", (ctx.tenant_id, artifact_id),
            )
        return inventory

    with monkeypatch.context() as patcher:
        patcher.setattr(DossierMarkdownInspection, "inspect", inspect_then_revoke)
        with pytest.raises((NotFound, Conflict)):
            ArtifactProposalBatches(store).stage(ctx, body, uuid4())
    with psycopg.connect(admin) as conn:
        assert conn.execute(
            "SELECT count(*) FROM knowledge_artifact_proposal_batches WHERE tenant_id=%s",
            (ctx.tenant_id,),
        ).fetchone()[0] == 0


def test_artifact_proposal_sql_tenant_immutability_and_citation_guards(database, tenant):
    store, admin = database
    ctx, _, project_id, basis_id, artifact_id = _prepared(store, tenant)
    body = _candidate(store, ctx, project_id, basis_id, artifact_id)
    service = ArtifactProposalBatches(store)
    staged = service.stage(ctx, body, uuid4())
    proposal = service.preview(ctx, staged["batch_id"])["proposals"][0]
    foreign_ctx, _ = pg.tenant.__wrapped__(database)
    foreign_ctx = replace(foreign_ctx, scopes=ctx.scopes)
    with pytest.raises(NotFound):
        service.preview(foreign_ctx, staged["batch_id"])
    with pytest.raises(psycopg.Error), store.transaction(ctx) as conn:
        conn.execute(
            "UPDATE knowledge_artifact_proposal_batches SET row_count=2 WHERE id=%s",
            (staged["batch_id"],),
        )
    with pytest.raises(psycopg.Error), psycopg.connect(admin) as conn:
        conn.execute("TRUNCATE knowledge_artifact_proposal_review_receipts")
    with pytest.raises(psycopg.Error), store.transaction(ctx) as conn:
        conn.execute(
            "INSERT INTO knowledge_artifact_proposal_decisions(tenant_id,batch_id,"
            "proposal_id,decision,reviewer_id,reason) "
            "VALUES (%s,%s,%s,'rejected',%s,'No')",
            (ctx.tenant_id, staged["batch_id"], proposal["proposal_id"], ctx.actor_id),
        )
    other_link = ProjectArtifactLinks(store).publish(
        ctx, project_id,
        _body(artifact_id, basis_id).model_copy(update={"relation": "primary"}),
        uuid4(),
    )["object_id"]
    with store.transaction(ctx) as conn:
        receipt = conn.execute(
            "SELECT idempotency_key FROM knowledge_project_artifact_receipts "
            "WHERE link_id<>%s ORDER BY link_id LIMIT 1", (other_link,),
        ).fetchone()
        other_receipt = conn.execute(
            "SELECT idempotency_key FROM knowledge_project_artifact_receipts "
            "WHERE link_id=%s", (other_link,),
        ).fetchone()
    assert receipt is not None
    assert other_receipt is not None
    with pytest.raises(psycopg.Error, match="invalid artifact proposal approval receipt"):
        with store.transaction(ctx) as conn:
            conn.execute(
                "INSERT INTO knowledge_artifact_proposal_decisions(tenant_id,batch_id,"
                "proposal_id,decision,reviewer_id,publication_key,link_id) "
                "VALUES (%s,%s,%s,'approved',%s,%s,%s)",
                (ctx.tenant_id, staged["batch_id"], proposal["proposal_id"],
                 ctx.actor_id, receipt["idempotency_key"], other_link),
            )
    with pytest.raises(psycopg.Error, match="invalid artifact proposal approval receipt"):
        with store.transaction(ctx) as conn:
            conn.execute(
                "INSERT INTO knowledge_artifact_proposal_decisions(tenant_id,batch_id,"
                "proposal_id,decision,reviewer_id,publication_key,link_id) "
                "VALUES (%s,%s,%s,'approved',%s,%s,%s)",
                (ctx.tenant_id, staged["batch_id"], proposal["proposal_id"],
                 ctx.actor_id, other_receipt["idempotency_key"], other_link),
            )
    invalid_batch = "kabatch_" + uuid4().hex
    with pytest.raises(psycopg.Error, match="invalid artifact proposal citation or kind"):
        with store.transaction(ctx) as conn:
            conn.execute(
                "INSERT INTO knowledge_artifact_proposal_batches(tenant_id,id,proposer_id,"
                "idempotency_key,request_sha256,import_context_sha256,row_count) "
                "VALUES (%s,%s,%s,%s,%s,%s,1)",
                (ctx.tenant_id, invalid_batch, ctx.actor_id, uuid4(), "a" * 64,
                 "b" * 64),
            )
            conn.execute(
                "INSERT INTO knowledge_artifact_proposals(tenant_id,id,batch_id,"
                "ordinal,claimed_id,project_id,payload,payload_sha256,"
                "artifact_evidence_id,basis_evidence_id,artifact_source_kind) "
                "VALUES (%s,%s,%s,0,%s,%s,%s,%s,%s,%s,'email')",
                (ctx.tenant_id, "kaproposal_" + uuid4().hex, invalid_batch,
                 "partifact_" + uuid4().hex, project_id, Jsonb(proposal["assertion"]),
                 "c" * 64, artifact_id, "evidence_" + "f" * 32),
            )
    assert service.preview(ctx, staged["batch_id"])["row_count"] == 1
    assert basis_id in body.markdown


def test_artifact_proposal_api_requires_human_content_scope(database, tenant):
    store, _ = database
    ctx, _, project_id, basis_id, artifact_id = _prepared(store, tenant)
    body = _candidate(store, ctx, project_id, basis_id, artifact_id)
    route = "/v1/knowledge/dossier-markdown/artifact-proposal-batches"

    def api(scopes, kind="human"):
        token = "fictional-artifact-stage-" + uuid4().hex
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
        preview = client.get("/v1/knowledge/artifact-proposal-batches/" + batch_id)
        assert preview.status_code == 200, preview.text
        row_id = preview.json()["proposals"][0]["proposal_id"]
        reviewed = client.post(
            "/v1/knowledge/artifact-proposal-batches/" + batch_id + "/review",
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
