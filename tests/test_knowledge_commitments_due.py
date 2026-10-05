"""Closed request/SQL/API contract for the reviewed-commitment due view."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from test_service import TOKEN, registry

from email_brain.api import create_app
from email_brain.domain.models import TenantContext
from email_brain.store import NotFound, Store
from masterbrain.knowledge import KnowledgeCore
from masterbrain.knowledge_schema import DueCommitmentsRequest

NOW = datetime(2026, 10, 5, tzinfo=UTC)


def test_due_route_requires_scope_and_closed_bounded_query() -> None:
    store = MagicMock(spec=Store)
    knowledge = MagicMock(spec=KnowledgeCore)
    knowledge.commitments_due.return_value = {
        "results": [], "next_cursor": None, "recorded_cutoff_at": NOW,
        "limit": 2, "visibility": "unsuperseded", "state_filter": "open",
        "coverage": {"undated_commitments": "excluded"}, "untrusted_content": True,
    }
    query = {
        "start": NOW.isoformat(), "end": (NOW + timedelta(days=1)).isoformat(),
        "state": "open", "limit": "2",
    }
    headers = {"Authorization": f"Bearer {TOKEN}"}
    with TestClient(create_app(
        store, registry({"knowledge.search"}), knowledge_store=knowledge,
    )) as client:
        response = client.get("/v1/knowledge/commitments-due", params=query, headers=headers)
        assert response.status_code == 200, response.text
        request = knowledge.commitments_due.call_args.args[1]
        assert request.state == "open" and request.limit == 2
        assert request.start == NOW and request.end == NOW + timedelta(days=1)
        for changes in (
            {"end": NOW.isoformat()},
            {"end": (NOW + timedelta(days=367)).isoformat()},
            {"start": "2026-10-05T00:00:00"},
            {"after": "commitment_" + "1" * 32},
            {"after": "event_" + "1" * 32},
            {"project_id": "event_" + "1" * 32},
            {"state": "active"},
            {"visibility": "current"},
            {"limit": "51"},
            {"unknown": "no"},
        ):
            assert client.get(
                "/v1/knowledge/commitments-due", params={**query, **changes},
                headers=headers,
            ).status_code == 422
        assert knowledge.commitments_due.call_count == 1
    with TestClient(create_app(
        store, registry({"knowledge.read"}), knowledge_store=knowledge,
    )) as client:
        assert client.get(
            "/v1/knowledge/commitments-due", params=query, headers=headers,
        ).status_code == 403


def test_due_query_binds_related_visibility_and_cutoff_before_limit() -> None:
    store = MagicMock(spec=Store)
    conn = store.transaction.return_value.__enter__.return_value
    conn.execute.return_value.fetchone.return_value = {"now": NOW}
    conn.execute.return_value.fetchall.return_value = []
    ctx = TenantContext(uuid4(), uuid4(), frozenset({"knowledge.search"}), uuid4())
    project = "project_" + "1" * 32
    result = KnowledgeCore(store).commitments_due(ctx, DueCommitmentsRequest(
        start=NOW - timedelta(days=1), end=NOW + timedelta(days=1),
        project_id=project, state="open", limit=3,
    ))
    assert result["results"] == [] and result["state_filter"] == "open"
    query, params = conn.execute.call_args.args
    for token in (
        "cm.due_at>=%s", "cm.project_id=%s", "cm.state=%s",
        "cm.recorded_at<=allowed.cutoff", "s.recorded_at<=allowed.cutoff",
        "c.recorded_at<=allowed.cutoff", "r.recorded_at<=allowed.cutoff",
        "knowledge_projects", "knowledge_entities",
        "ORDER BY cm.due_at,cm.id LIMIT %s",
    ):
        assert token in query
    assert project in params and "open" in params and params[-1] == 4
    assert query.count("%s") == len(params)
    store.audit.assert_called_once_with(conn, ctx, "knowledge.commitments_due_read", "due_window")


def test_due_cursor_uses_same_filters_and_hidden_anchor_fails_closed() -> None:
    store = MagicMock(spec=Store)
    conn = store.transaction.return_value.__enter__.return_value
    clock = MagicMock()
    clock.fetchone.return_value = {"now": NOW + timedelta(days=1)}
    commitment_id = "commitment_" + "2" * 32
    anchor = MagicMock()
    anchor.fetchone.return_value = {"due_at": NOW, "id": commitment_id}
    page = MagicMock()
    page.fetchall.return_value = []
    conn.execute.side_effect = [clock, anchor, page]
    ctx = TenantContext(uuid4(), uuid4(), frozenset({"knowledge.search"}), uuid4())
    request = DueCommitmentsRequest(
        start=NOW - timedelta(days=1), end=NOW + timedelta(days=1),
        recorded_cutoff_at=NOW, after=commitment_id, state="open",
    )
    assert KnowledgeCore(store).commitments_due(ctx, request)["results"] == []
    anchor_sql, anchor_params = conn.execute.call_args_list[1].args
    page_sql, page_params = conn.execute.call_args_list[2].args
    assert "cm.id=%s" in anchor_sql and "cm.state=%s" in anchor_sql
    assert "(cm.due_at,cm.id)>(%s,%s)" in page_sql
    for query, params in ((anchor_sql, anchor_params), (page_sql, page_params)):
        assert "cm.recorded_at<=allowed.cutoff" in query
        assert "s.recorded_at<=allowed.cutoff" in query
        assert "c.recorded_at<=allowed.cutoff" in query
        assert "r.recorded_at<=allowed.cutoff" in query
        assert query.count("%s") == len(params)
    assert page_params[-3:-1] == (NOW, commitment_id)

    conn.execute.side_effect = [clock, MagicMock(fetchone=lambda: None)]
    with pytest.raises(NotFound):
        KnowledgeCore(store).commitments_due(ctx, request)
