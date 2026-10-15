"""Fictional current-evidence inspection of imported dossier Markdown."""

from __future__ import annotations

import hashlib
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import psycopg
import pytest
import test_postgres as pg
from fastapi.testclient import TestClient
from test_project_dossier_markdown_postgres import _published
from test_project_facts_postgres import QUOTE, _prepared

from email_brain.api import create_app
from email_brain.auth import Credential, TokenRegistry
from email_brain.store import AccessDenied, Conflict
from masterbrain.knowledge_schema import ProjectDossierRequest
from masterbrain.librarian_dossier_intake import DossierMarkdownInspection
from masterbrain.project_dossier_markdown import ProjectDossierMarkdown

pytestmark = pytest.mark.postgres
database, tenant = pg.database, pg.tenant


def _export(store, ctx, project_id):
    return ProjectDossierMarkdown(store).export(
        ctx, project_id, ProjectDossierRequest(),
    )["markdown"]


def test_real_fictional_export_checks_every_preview_and_fixed_audit(database, tenant):
    store, admin = database
    ctx, _, project_id, evidence_id = _prepared(store, tenant)
    _published(store, ctx, project_id, evidence_id)
    result = DossierMarkdownInspection(store).inspect(ctx, _export(store, ctx, project_id))
    assert result["citation_spans_checked"] is True
    assert result["source_freshness"] == "not_asserted"
    assert result["proposal_ready"] is False
    assert result["staged"] is False
    assert len(result["candidates"]) == 6
    member = next(row for row in result["candidates"] if row["kind"] == "member")
    assert member["claimed_citation_ids"] == [evidence_id, evidence_id]
    assert member["claimed_quote_previews"] == [QUOTE, QUOTE]
    with psycopg.connect(admin) as conn:
        row = conn.execute(
            "SELECT resource_type,resource_id,metadata FROM audit_events "
            "WHERE tenant_id=%s AND event_type='knowledge.dossier_markdown_inspected' "
            "ORDER BY occurred_at DESC LIMIT 1", (ctx.tenant_id,),
        ).fetchone()
        proposals = conn.execute(
            "SELECT count(*) FROM knowledge_proposals WHERE tenant_id=%s",
            (ctx.tenant_id,),
        ).fetchone()[0]
    assert row == ("dossier", None, {})
    assert proposals == 0


def test_wrong_quote_hidden_source_and_stale_basis_fail_closed(database, tenant):
    store, admin = database
    ctx, _, project_id, evidence_id = _prepared(store, tenant)
    markdown = _export(store, ctx, project_id)
    inspector = DossierMarkdownInspection(store)
    with pytest.raises(Conflict):
        inspector.inspect(ctx, markdown.replace(QUOTE, "invented fictional quote"))
    with pytest.raises(Conflict):
        inspector.inspect(
            replace(ctx, source_ids=frozenset({"fictional_other_source"})), markdown,
        )
    with pytest.raises((AccessDenied, Conflict)):
        inspector.inspect(replace(ctx, tenant_id=uuid4()), markdown)
    with psycopg.connect(admin) as conn:
        conn.execute(
            "UPDATE brain_source_items i SET current_version_id=NULL "
            "FROM brain_source_versions v JOIN brain_evidence e "
            "ON e.tenant_id=v.tenant_id AND e.source_version_id=v.id "
            "WHERE i.tenant_id=v.tenant_id AND i.id=v.item_id "
            "AND e.tenant_id=%s AND e.id=%s", (ctx.tenant_id, evidence_id),
        )
    with pytest.raises(Conflict):
        inspector.inspect(ctx, markdown)


def test_excluded_email_evidence_cannot_be_inspected(database, tenant):
    store, admin = database
    ctx, _, project_id, _ = _prepared(store, tenant)
    markdown = _export(store, ctx, project_id)
    with psycopg.connect(admin) as conn:
        conn.execute(
            "UPDATE message_sync_state SET status='excluded' "
            "WHERE tenant_id=%s AND provider_id='fictional-fact-message-1'",
            (ctx.tenant_id,),
        )
    with pytest.raises(Conflict):
        DossierMarkdownInspection(store).inspect(ctx, markdown)


def test_api_is_human_only_scoped_and_returns_no_partial_inventory(database, tenant):
    store, _ = database
    ctx, _, project_id, _ = _prepared(store, tenant)
    markdown = _export(store, ctx, project_id)
    route = "/v1/knowledge/dossier-markdown/inspect"

    def api(scopes, client_kind="human"):
        token = "fictional-inspect-" + uuid4().hex
        credential = Credential(
            token_sha256=hashlib.sha256(token.encode()).hexdigest(),
            tenant_id=ctx.tenant_id, actor_id=ctx.actor_id, scopes=scopes,
            expires_at=datetime.now(UTC) + timedelta(hours=1),
            client_kind=client_kind,
            source_ids={"fictional_source"} if client_kind == "assistant" else None,
        )
        return TestClient(
            create_app(store, TokenRegistry([credential])),
            headers={"Authorization": "Bearer " + token},
        )

    with api({"knowledge.review", "brain.content.read"}) as client:
        accepted = client.post(route, json={"markdown": markdown})
        assert accepted.status_code == 200, accepted.text
        assert accepted.json()["citation_spans_checked"] is True
        invalid = client.post(route, json={"markdown": markdown.replace(
            QUOTE, "invented fictional quote",
        )})
        assert invalid.status_code == 409
        assert "candidates" not in invalid.text
        assert client.post(route, json={"markdown": "not a dossier"}).status_code == 422
    with api({"knowledge.review"}) as client:
        assert client.post(route, json={"markdown": markdown}).status_code == 403
    with api({"brain.content.read"}, "assistant") as client:
        assert client.post(route, json={"markdown": markdown}).status_code == 403
