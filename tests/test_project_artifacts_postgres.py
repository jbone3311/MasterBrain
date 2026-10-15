"""Fictional PostgreSQL proof of reviewed project-to-evidence occurrence links."""

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
from email_brain.store import Conflict, NotFound, Store
from masterbrain.knowledge import KnowledgeCore
from masterbrain.knowledge_schema import (
    ProjectArtifactLinkWrite,
    ProjectArtifactPageRequest,
    ProjectWrite,
)
from masterbrain.project_artifacts import ProjectArtifactLinks

pytestmark = pytest.mark.postgres
database, tenant = pg.database, pg.tenant
QUOTE = "Melron investment briefing"
NOW = datetime(2026, 10, 14, tzinfo=UTC)


def _evidence(
    store: Store, ctx: pg.TenantContext, account, *,
    key: str, provider_id: str, cursor: str | None, next_cursor: str,
) -> str:
    store.ingest_page(ctx, account, cursor, next_cursor, [
        replace(pg.item(key, body=QUOTE), provider_id=provider_id),
    ])
    with store.transaction(ctx) as conn:
        legacy_id = conn.execute(
            "SELECT v.id FROM message_versions v JOIN messages m "
            "ON m.tenant_id=v.tenant_id AND m.id=v.message_id "
            "WHERE m.provider_message_id=%s ORDER BY v.id DESC LIMIT 1",
            (provider_id,),
        ).fetchone()["id"]
    result = pg.DataCoreStore(store).bridge_current_email_version(
        ctx, legacy_id, uuid4(), code_revision="project-artifact-fictional-v1",
    )
    return result.evidence_id


def _prepared(store: Store, tenant_data: tuple) -> tuple:
    raw_ctx, account = tenant_data
    ctx = replace(
        pg.datacore_context(raw_ctx),
        scopes=pg.datacore_context(raw_ctx).scopes | frozenset({
            "knowledge.review", "knowledge.search", "brain.content.read",
        }),
    )
    source_id = _evidence(
        store, ctx, account, key="projecteone", provider_id="project-message-1",
        cursor=None, next_cursor="project-artifact-page-1",
    )
    project = KnowledgeCore(store).publish(ctx, ProjectWrite(
        kind="project", title="Fictional Melron deal", state="active",
        evidence_ids=[source_id], source_quote=QUOTE,
        confidence=1.0, observed_at=NOW, reviewed=True,
    ), uuid4())
    artifact_id = _evidence(
        store, ctx, account, key="projectetwo", provider_id="project-message-2",
        cursor="project-artifact-page-1", next_cursor="project-artifact-page-2",
    )
    return ctx, account, project.object_id, source_id, artifact_id


def _body(artifact_id: str, basis_id: str, *, quote: str = QUOTE) -> ProjectArtifactLinkWrite:
    return ProjectArtifactLinkWrite(
        artifact_evidence_id=artifact_id, basis_evidence_id=basis_id,
        source_quote=quote, relation="related", observed_at=NOW,
    )


def test_reviewed_artifact_link_replay_paging_and_distinct_occurrences(database, tenant):
    store, _ = database
    ctx, account, project_id, basis_id, first_artifact = _prepared(store, tenant)
    links = ProjectArtifactLinks(store)
    key = uuid4()
    first = links.publish(ctx, project_id, _body(first_artifact, basis_id), key)
    assert first["changed"] and first["reviewed"]
    assert links.publish(ctx, project_id, _body(first_artifact, basis_id), key) == {
        **first, "changed": False,
    }
    with pytest.raises(Conflict):
        links.publish(ctx, project_id, _body(first_artifact, first_artifact), key)
    second_artifact = _evidence(
        store, ctx, account, key="projectethree", provider_id="project-message-3",
        cursor="project-artifact-page-2", next_cursor="project-artifact-page-3",
    )
    assert first_artifact != second_artifact
    with store.transaction(ctx) as conn:
        hashes = conn.execute(
            "SELECT id,sha256 FROM brain_evidence WHERE id=ANY(%s)",
            ([first_artifact, second_artifact],),
        ).fetchall()
    assert len(hashes) == 2 and len({row["sha256"] for row in hashes}) == 1
    second = links.publish(ctx, project_id, _body(second_artifact, basis_id), uuid4())
    page = links.page(ctx, project_id, ProjectArtifactPageRequest(limit=1))
    assert len(page["results"]) == 1 and page["next_cursor"] is not None
    assert page["results"][0]["object_id"] == second["object_id"]
    older = links.page(ctx, project_id, ProjectArtifactPageRequest(
        limit=1, recorded_cutoff_at=page["recorded_cutoff_at"],
        after=page["next_cursor"],
    ))
    assert older["results"][0]["object_id"] == first["object_id"]
    assert older["next_cursor"] is None
    assert {row["artifact_evidence_id"] for row in page["results"] + older["results"]} == {
        first_artifact, second_artifact,
    }
    assert all("source_quote" not in row for row in page["results"])


def test_artifact_link_quote_project_grant_and_sql_guards(database, tenant):
    store, admin = database
    ctx, _, project_id, basis_id, artifact_id = _prepared(store, tenant)
    links = ProjectArtifactLinks(store)
    with pytest.raises(ValueError, match="exact source span"):
        links.publish(
            ctx, project_id, _body(artifact_id, basis_id, quote="Invented quote"), uuid4(),
        )
    restricted = replace(ctx, source_ids=frozenset({"ungranted_source"}))
    with pytest.raises(NotFound):
        links.publish(restricted, project_id, _body(artifact_id, basis_id), uuid4())
    with pytest.raises(NotFound):
        links.page(restricted, project_id, ProjectArtifactPageRequest())
    with pytest.raises(NotFound):
        links.publish(ctx, "project_" + "f" * 32, _body(artifact_id, basis_id), uuid4())
    link = links.publish(ctx, project_id, _body(artifact_id, basis_id), uuid4())
    with pytest.raises(psycopg.Error), store.transaction(ctx) as conn:
        conn.execute(
            "UPDATE knowledge_project_artifacts SET relation='primary' WHERE id=%s",
            (link["object_id"],),
        )
    with pytest.raises(psycopg.Error), psycopg.connect(admin) as conn:
        conn.execute("TRUNCATE knowledge_project_artifacts")
    with pytest.raises(psycopg.Error), store.transaction(ctx) as conn:
        conn.execute(
            "UPDATE knowledge_project_artifact_receipts SET request_sha256=%s "
            "WHERE link_id=%s", ("0" * 64, link["object_id"]),
        )
    with pytest.raises(psycopg.Error), store.transaction(ctx) as conn:
        conn.execute(
            "INSERT INTO knowledge_project_artifacts(tenant_id,id,project_id,"
            "artifact_evidence_id,basis_evidence_id,relation,assertion_status,"
            "source_quote,observed_at,reviewer_id) "
            "VALUES (%s,%s,%s,%s,%s,'related','asserted',%s,%s,%s)",
            (ctx.tenant_id, "partifact_" + uuid4().hex, project_id,
             artifact_id, basis_id, "Invented quote", NOW, ctx.actor_id),
        )
    assert len(links.page(ctx, project_id, ProjectArtifactPageRequest())["results"]) == 1


def test_artifact_link_hidden_after_email_exclusion(database, tenant):
    store, admin = database
    ctx, _, project_id, basis_id, artifact_id = _prepared(store, tenant)
    links = ProjectArtifactLinks(store)
    replay_key = uuid4()
    link = links.publish(ctx, project_id, _body(artifact_id, basis_id), replay_key)
    before = links.page(ctx, project_id, ProjectArtifactPageRequest())
    with psycopg.connect(admin) as conn:
        conn.execute(
            "UPDATE message_sync_state SET status='excluded' "
            "WHERE tenant_id=%s AND provider_id='project-message-2'",
            (ctx.tenant_id,),
        )
    assert links.page(ctx, project_id, ProjectArtifactPageRequest())["results"] == []
    with pytest.raises(NotFound):
        links.page(ctx, project_id, ProjectArtifactPageRequest(
            after=link["object_id"], recorded_cutoff_at=before["recorded_cutoff_at"],
        ))
    with pytest.raises(NotFound):
        links.publish(ctx, project_id, _body(artifact_id, basis_id), uuid4())
    with pytest.raises(NotFound):
        links.publish(ctx, project_id, _body(artifact_id, basis_id), replay_key)


def test_artifact_link_cross_tenant_is_not_disclosed(database, tenant):
    store, _ = database
    ctx, _, project_id, basis_id, artifact_id = _prepared(store, tenant)
    links = ProjectArtifactLinks(store)
    links.publish(ctx, project_id, _body(artifact_id, basis_id), uuid4())
    foreign_ctx, _ = pg.tenant.__wrapped__(database)
    foreign_ctx = replace(
        foreign_ctx, scopes=ctx.scopes,
    )
    with pytest.raises(NotFound):
        links.page(foreign_ctx, project_id, ProjectArtifactPageRequest())
    with pytest.raises(NotFound):
        links.publish(foreign_ctx, project_id, _body(artifact_id, basis_id), uuid4())


def test_artifact_link_hidden_after_artifact_version_changes(database, tenant):
    store, admin = database
    ctx, _, project_id, basis_id, artifact_id = _prepared(store, tenant)
    links = ProjectArtifactLinks(store)
    replay_key = uuid4()
    links.publish(ctx, project_id, _body(artifact_id, basis_id), replay_key)
    with psycopg.connect(admin) as conn:
        conn.execute(
            "UPDATE brain_source_items i SET current_version_id=NULL "
            "FROM brain_source_versions v JOIN brain_evidence e "
            "ON e.tenant_id=v.tenant_id AND e.source_version_id=v.id "
            "WHERE i.tenant_id=v.tenant_id AND i.id=v.item_id "
            "AND e.tenant_id=%s AND e.id=%s",
            (ctx.tenant_id, artifact_id),
        )
    assert links.page(ctx, project_id, ProjectArtifactPageRequest())["results"] == []
    with pytest.raises(NotFound):
        links.publish(ctx, project_id, _body(artifact_id, basis_id), replay_key)


def test_project_and_artifact_sources_are_checked_independently(database, tenant):
    store, admin = database
    ctx, _, project_id, basis_id, visible_artifact = _prepared(store, tenant)
    second_account = uuid4()
    with psycopg.connect(admin) as conn:
        conn.execute(
            "INSERT INTO mail_accounts(id,tenant_id,provider,address,secret_ref) "
            "VALUES (%s,%s,'fastmail','second-fictional@example.invalid','synthetic:none')",
            (second_account, ctx.tenant_id),
        )
    artifact_id = _evidence(
        store, ctx, second_account, key="otheraccountartifact",
        provider_id="other-account-message", cursor=None,
        next_cursor="other-account-page",
    )
    with store.transaction(ctx) as conn:
        source = conn.execute(
            "SELECT v.source_id FROM brain_evidence e JOIN brain_source_versions v "
            "ON v.tenant_id=e.tenant_id AND v.id=e.source_version_id WHERE e.id=%s",
            (basis_id,),
        ).fetchone()["source_id"]
    project_only = replace(ctx, source_ids=frozenset({source}))
    links = ProjectArtifactLinks(store)
    visible = links.publish(ctx, project_id, _body(visible_artifact, basis_id), uuid4())
    with pytest.raises(NotFound):
        links.publish(project_only, project_id, _body(artifact_id, basis_id), uuid4())
    for _ in range(30):
        links.publish(ctx, project_id, _body(artifact_id, basis_id), uuid4())
    visible_page = links.page(project_only, project_id, ProjectArtifactPageRequest(limit=1))
    assert [row["object_id"] for row in visible_page["results"]] == [visible["object_id"]]
    assert visible_page["next_cursor"] is None
    assert len(links.page(ctx, project_id, ProjectArtifactPageRequest(limit=25))["results"]) == 25


def test_reviewed_project_can_link_exact_fileos_occurrence(database, tenant, tmp_path):
    store, _ = database
    ctx, _, project_id, basis_id, _ = _prepared(store, tenant)
    file_root = tmp_path / "fictional-files"
    file_root.mkdir()
    (file_root / "briefing.txt").write_text(
        "Synthetic investment briefing for Melron.", encoding="utf-8",
    )
    manifest = pg.fileos_manifest(file_root, source_id="project_fictional_files")
    core = pg.DataCoreStore(store)
    core.import_fileos_snapshot(ctx, manifest, uuid4())
    file_version_id = manifest["items"][0]["version_id"]
    file_evidence = core.publish_text(
        ctx, file_version_id, "Synthetic investment briefing for Melron.",
        code_revision="project-artifact-fictional-v1",
    ).evidence_id
    links = ProjectArtifactLinks(store)
    created = links.publish(ctx, project_id, _body(file_evidence, basis_id), uuid4())
    page = links.page(ctx, project_id, ProjectArtifactPageRequest())
    assert page["results"][0]["object_id"] == created["object_id"]
    assert page["results"][0]["artifact_evidence_id"] == file_evidence
    assert page["results"][0]["artifact_source_kind"] == "fileos"

    # The project/basis email and the linked FileOS occurrence require separate grants.
    with store.transaction(ctx) as conn:
        email_source = conn.execute(
            "SELECT v.source_id FROM brain_evidence e JOIN brain_source_versions v "
            "ON v.tenant_id=e.tenant_id AND v.id=e.source_version_id WHERE e.id=%s",
            (basis_id,),
        ).fetchone()["source_id"]
    email_only = replace(ctx, source_ids=frozenset({email_source}))
    assert links.page(email_only, project_id, ProjectArtifactPageRequest())["results"] == []
    with pytest.raises(NotFound):
        links.publish(email_only, project_id, _body(file_evidence, basis_id), uuid4())


def test_artifact_link_api_scopes_and_closed_page(database, tenant):
    store, _ = database
    ctx, _, project_id, basis_id, artifact_id = _prepared(store, tenant)
    token = "fictional-artifact-" + uuid4().hex
    path = f"/v1/knowledge/projects/{project_id}/artifacts"

    def client(scopes: set[str]) -> TestClient:
        credential = Credential(
            token_sha256=hashlib.sha256(token.encode()).hexdigest(),
            tenant_id=ctx.tenant_id, actor_id=ctx.actor_id, scopes=scopes,
            expires_at=datetime.now(UTC) + timedelta(hours=1), client_kind="human",
        )
        return TestClient(
            create_app(store, TokenRegistry([credential])),
            headers={"Authorization": "Bearer " + token},
        )

    payload = _body(artifact_id, basis_id).model_dump(mode="json")
    with client({"knowledge.review"}) as denied:
        assert denied.post(path, json=payload,
                           headers={"idempotency-key": str(uuid4())}).status_code == 403
    with client({"knowledge.review", "brain.content.read", "knowledge.search"}) as api:
        created = api.post(path, json=payload,
                           headers={"idempotency-key": str(uuid4())})
        assert created.status_code == 201, created.text
        assert created.json()["reviewed"] is True
        page = api.get(path, params={"limit": 1})
        assert page.status_code == 200, page.text
        assert page.json()["results"][0]["artifact_evidence_id"] == artifact_id
        assert page.json()["results"][0]["artifact_source_kind"] == "email"
        assert page.headers["cache-control"] == "no-store"
        assert api.get(path, params={"limit": 0}).status_code == 422
        assert api.get(path, params={"after": "partifact_bad"}).status_code == 422
    with client({"knowledge.review"}) as denied:
        assert denied.get(path).status_code == 403
