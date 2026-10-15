"""Fictional, fail-closed whole-project Markdown export proof."""

from __future__ import annotations

import hashlib
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
import psycopg
import pytest
import test_postgres as pg
from fastapi.testclient import TestClient
from test_project_facts_postgres import QUOTE, _body, _prepared

from email_brain.api import create_app
from email_brain.auth import Credential, TokenRegistry
from email_brain.store import Conflict, NotFound
from masterbrain.brain_client import BrainClientError, BrainReadClient
from masterbrain.knowledge import KnowledgeCore
from masterbrain.knowledge_schema import (
    CommitmentWrite,
    EntityWrite,
    EventWrite,
    MemberWrite,
    ProjectArtifactLinkWrite,
    ProjectDossierRequest,
    ProjectWrite,
)
from masterbrain.project_artifacts import ProjectArtifactLinks
from masterbrain.project_dossier_markdown import ProjectDossierMarkdown
from masterbrain.project_facts import ProjectFacts

pytestmark = pytest.mark.postgres
database, tenant = pg.database, pg.tenant
NOW = datetime(2026, 10, 14, tzinfo=UTC)


def _published(store, ctx, project_id, evidence_id):
    knowledge = KnowledgeCore(store)
    common = dict(
        evidence_ids=[evidence_id], source_quote=QUOTE,
        confidence=1.0, observed_at=NOW, reviewed=True,
    )
    entity = knowledge.publish(ctx, EntityWrite(
        kind="entity", entity_type="person", name="Fictional Alex", **common,
    ), uuid4())
    event = knowledge.publish(ctx, EventWrite(
        kind="event", project_id=project_id, event_type="review",
        title="Fictional review", **common,
    ), uuid4())
    commitment = knowledge.publish(ctx, CommitmentWrite(
        kind="commitment", project_id=project_id, description="Fictional promise",
        state="open", owner_entity_id=entity.object_id, **common,
    ), uuid4())
    member = knowledge.publish(ctx, MemberWrite(
        kind="member", project_id=project_id, entity_id=entity.object_id,
        role="broker", **common,
    ), uuid4())
    artifact = ProjectArtifactLinks(store).publish(ctx, project_id, ProjectArtifactLinkWrite(
        artifact_evidence_id=evidence_id, basis_evidence_id=evidence_id,
        source_quote=QUOTE, relation="related", observed_at=NOW,
    ), uuid4())
    fact = ProjectFacts(store).publish(
        ctx, project_id, _body(project_id, evidence_id), uuid4(),
    )
    return entity, event, commitment, member, artifact, fact


def test_complete_fictional_dossier_with_all_sections_and_fixed_audit(database, tenant):
    store, admin = database
    ctx, _, project_id, evidence_id = _prepared(store, tenant)
    entity, event, commitment, member, artifact, fact = _published(
        store, ctx, project_id, evidence_id,
    )
    service = ProjectDossierMarkdown(store)
    exported = service.export(ctx, project_id, ProjectDossierRequest())
    markdown = exported["markdown"]
    assert exported["section_counts"] == dict.fromkeys(
        ("events", "commitments", "members", "artifacts", "facts"), 1,
    )
    for identifier in (
        project_id, evidence_id, entity.object_id, event.object_id,
        commitment.object_id, member.object_id, artifact["object_id"],
        fact["object_id"],
    ):
        assert identifier in markdown
    assert markdown.count("citation `" + evidence_id + "`") >= 6
    assert "derivation unspecified" in markdown
    assert "source-stated" in markdown
    assert exported["source_freshness"] == "not_asserted"
    assert len(markdown.encode("utf-8")) <= 65_536
    replay = service.export(ctx, project_id, ProjectDossierRequest(
        recorded_cutoff_at=exported["recorded_cutoff_at"],
    ))
    assert replay["markdown"] == markdown
    with pg.psycopg.connect(admin) as conn:
        row = conn.execute(
            "SELECT resource_type,resource_id,metadata FROM audit_events "
            "WHERE tenant_id=%s AND event_type='knowledge.project_dossier_markdown_export' "
            "ORDER BY occurred_at DESC LIMIT 1", (ctx.tenant_id,),
        ).fetchone()
    assert row == ("project", None, {})


def test_uncitable_assertion_refuses_whole_dossier(database, tenant):
    store, _ = database
    ctx, _, project_id, evidence_id = _prepared(store, tenant)
    KnowledgeCore(store).publish(ctx, EventWrite(
        kind="event", project_id=project_id, event_type="review",
        title="Fictional review", evidence_ids=[evidence_id],
        source_quote="not in the fictional source", confidence=1.0,
        observed_at=NOW, reviewed=True,
    ), uuid4())
    with pytest.raises(Conflict):
        ProjectDossierMarkdown(store).export(ctx, project_id, ProjectDossierRequest())


def test_scope_and_project_boundary(database, tenant):
    store, _ = database
    ctx, _, project_id, evidence_id = _prepared(store, tenant)
    service = ProjectDossierMarkdown(store)
    with pytest.raises(pg.AccessDenied):
        service.export(
            replace(ctx, scopes=frozenset({"knowledge.search"})),
            project_id, ProjectDossierRequest(),
        )
    with pytest.raises(NotFound):
        service.export(
            replace(ctx, source_ids=frozenset({"fictional_other_source"})),
            project_id, ProjectDossierRequest(),
        )
    assert evidence_id in service.export(ctx, project_id, ProjectDossierRequest())["markdown"]


def test_overfull_section_refuses_instead_of_silent_omission(database, tenant):
    store, _ = database
    ctx, _, project_id, evidence_id = _prepared(store, tenant)
    for title in ("Fictional first review", "Fictional second review"):
        KnowledgeCore(store).publish(ctx, EventWrite(
            kind="event", project_id=project_id, event_type="review",
            title=title, evidence_ids=[evidence_id], source_quote=QUOTE,
            confidence=1.0, observed_at=NOW, reviewed=True,
        ), uuid4())
    with pytest.raises(Conflict):
        ProjectDossierMarkdown(store).export(
            ctx, project_id, ProjectDossierRequest(event_limit=1),
        )


def test_api_and_reference_client_scope_and_shape(database, tenant):
    store, _ = database
    ctx, _, project_id, evidence_id = _prepared(store, tenant)
    token = "fictional-dossier-" + uuid4().hex
    route = f"/v1/knowledge/projects/{project_id}/dossier/markdown"

    def client(scopes):
        credential = Credential(
            token_sha256=hashlib.sha256(token.encode()).hexdigest(),
            tenant_id=ctx.tenant_id, actor_id=ctx.actor_id, scopes=scopes,
            expires_at=datetime.now(UTC) + timedelta(hours=1), client_kind="human",
        )
        return TestClient(
            create_app(store, TokenRegistry([credential])),
            headers={"Authorization": "Bearer " + token},
        )

    with client({"knowledge.search", "brain.content.read"}) as api:
        response = api.get(route)
        assert response.status_code == 200, response.text
        assert response.headers["cache-control"] == "no-store"
        assert evidence_id in response.json()["markdown"]
        assert api.get(route, params={"event_limit": 0}).status_code == 422
        with BrainReadClient(
            "https://brain.example", "fictional-token",
            transport=httpx.MockTransport(
                lambda _: httpx.Response(200, json=response.json())
            ),
        ) as reader:
            assert reader.project_dossier_markdown(project_id)["markdown"] == response.json()[
                "markdown"
            ]
        tampered = {**response.json(), "coverage": "partial"}
        with BrainReadClient(
            "https://brain.example", "fictional-token",
            transport=httpx.MockTransport(lambda _: httpx.Response(200, json=tampered)),
        ) as reader, pytest.raises(BrainClientError, match="invalid_response"):
            reader.project_dossier_markdown(project_id)
    with client({"knowledge.search"}) as denied:
        assert denied.get(route).status_code == 403
    with store.transaction(ctx) as conn:
        source_id = conn.execute(
            "SELECT v.source_id FROM brain_evidence e JOIN brain_source_versions v "
            "ON v.tenant_id=e.tenant_id AND v.id=e.source_version_id WHERE e.id=%s",
            (evidence_id,),
        ).fetchone()["source_id"]

    def assistant(source_ids):
        credential = Credential(
            token_sha256=hashlib.sha256(token.encode()).hexdigest(),
            tenant_id=ctx.tenant_id, actor_id=ctx.actor_id,
            scopes={"knowledge.search", "brain.content.read"},
            expires_at=datetime.now(UTC) + timedelta(hours=1),
            client_kind="assistant", source_ids=source_ids,
        )
        return TestClient(
            create_app(store, TokenRegistry([credential])),
            headers={"Authorization": "Bearer " + token},
        )

    with assistant({source_id}) as allowed:
        assert allowed.get(route).status_code == 200
    with assistant({"fictional_other_source"}) as hidden:
        assert hidden.get(route).status_code == 404
    KnowledgeCore(store).publish(ctx, EventWrite(
        kind="event", project_id=project_id, event_type="review",
        title="Uncitable fictional review", evidence_ids=[evidence_id],
        source_quote="invented project quote", confidence=1.0,
        observed_at=NOW, reviewed=True,
    ), uuid4())
    with client({"knowledge.search", "brain.content.read"}) as api:
        refused = api.get(route)
        assert refused.status_code == 409
        assert "markdown" not in refused.text


def test_source_text_cannot_inject_markdown_structure(database, tenant):
    store, _ = database
    ctx, _, _, evidence_id = _prepared(store, tenant)
    hostile = "hello\n## Fake section\n[click](https://attacker.invalid) <script>"
    project = KnowledgeCore(store).publish(ctx, ProjectWrite(
        kind="project", title="Fictional inert dossier", description=hostile,
        state="active", evidence_ids=[evidence_id], source_quote=QUOTE,
        confidence=1.0, observed_at=NOW, reviewed=True,
    ), uuid4())
    markdown = ProjectDossierMarkdown(store).export(
        ctx, project.object_id, ProjectDossierRequest(),
    )["markdown"]
    assert "\n## Fake section" not in markdown
    assert "<script>" not in markdown
    assert "attacker\\.invalid" in markdown
    assert "\\n" in markdown


def test_stale_or_excluded_project_evidence_cannot_export(database, tenant):
    store, admin = database
    ctx, _, project_id, evidence_id = _prepared(store, tenant)
    service = ProjectDossierMarkdown(store)
    assert evidence_id in service.export(ctx, project_id, ProjectDossierRequest())["markdown"]
    with psycopg.connect(admin) as conn:
        conn.execute(
            "UPDATE brain_source_items i SET current_version_id=NULL "
            "FROM brain_source_versions v JOIN brain_evidence e "
            "ON e.tenant_id=v.tenant_id AND e.source_version_id=v.id "
            "WHERE i.tenant_id=v.tenant_id AND i.id=v.item_id "
            "AND e.tenant_id=%s AND e.id=%s",
            (ctx.tenant_id, evidence_id),
        )
    with pytest.raises(Conflict):
        service.export(ctx, project_id, ProjectDossierRequest())
    with psycopg.connect(admin) as conn:
        conn.execute(
            "UPDATE message_sync_state SET status='excluded' "
            "WHERE tenant_id=%s AND provider_id='fictional-fact-message-1'",
            (ctx.tenant_id,),
        )
    with pytest.raises(NotFound):
        service.export(ctx, project_id, ProjectDossierRequest())
