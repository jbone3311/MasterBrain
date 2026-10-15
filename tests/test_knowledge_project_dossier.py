"""Closed API and SQL shape for the reviewed project dossier."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock
from uuid import uuid4

from fastapi.testclient import TestClient
from test_service import TOKEN, registry

from email_brain.api import create_app
from email_brain.domain.models import TenantContext
from email_brain.store import Store
from masterbrain.knowledge import KnowledgeCore
from masterbrain.knowledge_schema import ProjectDossierRequest

NOW = datetime(2026, 10, 5, tzinfo=UTC)
PROJECT = "project_" + "1" * 32
PATH = f"/v1/knowledge/projects/{PROJECT}/dossier"
HEADERS = {"Authorization": f"Bearer {TOKEN}"}


def test_project_dossier_route_is_scoped_and_closed() -> None:
    store = MagicMock(spec=Store)
    knowledge = MagicMock(spec=KnowledgeCore)
    knowledge.project_dossier.return_value = {"project": {"object_id": PROJECT}}
    with TestClient(create_app(
        store, registry({"knowledge.search"}), knowledge_store=knowledge,
    )) as client:
        response = client.get(PATH, params={"event_limit": "2"}, headers=HEADERS)
        assert response.status_code == 200, response.text
        assert response.json()["project"]["object_id"] == PROJECT
        request = knowledge.project_dossier.call_args.args[2]
        assert request.event_limit == 2 and request.commitment_limit == 10
        assert request.artifact_limit == 10
        assert request.fact_limit == 10
        for params in (
            {"event_limit": "0"}, {"commitment_limit": "26"},
            {"artifact_limit": "26"},
            {"fact_limit": "26"},
            {"recorded_cutoff_at": "2026-10-05T00:00:00"},
            {"visibility": "current"}, {"unknown": "no"},
        ):
            assert client.get(PATH, params=params, headers=HEADERS).status_code == 422
        knowledge.project_dossier.assert_called_once()
    with TestClient(create_app(
        store, registry({"knowledge.read"}), knowledge_store=knowledge,
    )) as client:
        assert client.get(PATH, headers=HEADERS).status_code == 403


def test_project_dossier_sql_checks_grants_and_cutoff_before_independent_limits() -> None:
    store = MagicMock(spec=Store)
    conn = store.transaction.return_value.__enter__.return_value
    clock = MagicMock()
    clock.fetchone.return_value = {"now": NOW}
    project = MagicMock()
    project.fetchone.return_value = {
        "id": PROJECT, "title": "Fictional project", "description": "Review",
        "state": "active", "recorded_at": NOW - timedelta(days=1),
    }
    events = MagicMock()
    events.fetchall.return_value = []
    commitments = MagicMock()
    commitments.fetchall.return_value = []
    members = MagicMock()
    members.fetchall.return_value = []
    artifacts = MagicMock()
    artifacts.fetchall.return_value = []
    facts = MagicMock()
    facts.fetchall.return_value = []
    evidence = MagicMock()
    evidence.fetchall.return_value = []
    conn.execute.side_effect = [
        clock, project, events, commitments, members, artifacts, facts, evidence,
    ]
    ctx = TenantContext(uuid4(), uuid4(), frozenset({"knowledge.search"}), uuid4())
    result = KnowledgeCore(store).project_dossier(
        ctx, PROJECT, ProjectDossierRequest(event_limit=2, commitment_limit=3),
    )
    assert result["project"]["object_id"] == PROJECT
    for section in ("events", "commitments", "members", "artifacts", "facts"):
        assert result[section] == []
    for call in conn.execute.call_args_list[1:6]:
        query, params = call.args
        assert query.count("%s") == len(params)
        assert "recorded_at<=allowed.cutoff" in query
    event_sql, event_params = conn.execute.call_args_list[2].args
    due_sql, due_params = conn.execute.call_args_list[3].args
    assert "ev.project_id=%s" in event_sql
    assert "ORDER BY ev.recorded_at DESC,ev.id DESC LIMIT %s" in event_sql
    assert "NOT EXISTS (SELECT 1 FROM knowledge_events s" in event_sql
    assert "v.source_id<>ALL(allowed.sources)" in event_sql
    assert event_params[-1] == 3
    assert "cm.project_id=%s" in due_sql
    assert "ORDER BY cm.recorded_at DESC,cm.id DESC LIMIT %s" in due_sql
    assert "NOT EXISTS (SELECT 1 FROM knowledge_commitments s" in due_sql
    assert "v.source_id<>ALL(allowed.sources)" in due_sql
    assert due_params[-1] == 4
    member_sql, member_params = conn.execute.call_args_list[4].args
    assert "km.project_id=%s" in member_sql
    assert "ORDER BY km.recorded_at DESC,km.id DESC LIMIT %s" in member_sql
    assert "knowledge_entities ke_ref" in member_sql
    assert member_params[-1] == 11
    artifact_sql, artifact_params = conn.execute.call_args_list[5].args
    assert "l.project_id=%s" in artifact_sql
    assert "AND i.current_version_id=v.id AND s.status='active'" in artifact_sql
    assert "position(l.source_quote IN d.body)>0" in artifact_sql
    assert "ORDER BY l.recorded_at DESC,l.id DESC LIMIT %s" in artifact_sql
    assert artifact_params[-1] == 11
    fact_sql, fact_params = conn.execute.call_args_list[6].args
    assert "f.project_id=%s" in fact_sql
    assert "ORDER BY f.recorded_at DESC,f.id DESC LIMIT %s" in fact_sql
    assert "unnest(f.evidence_ids)" in fact_sql
    assert fact_params[-1] == 11
    store.audit.assert_called_once_with(
        conn, ctx, "knowledge.project_dossier_read", "project",
    )
