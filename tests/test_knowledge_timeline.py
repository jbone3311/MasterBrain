"""Closed API contract for the reviewed-event timeline (PostgreSQL behavior elsewhere)."""

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
from masterbrain.knowledge_schema import TimelineRequest

NOW = datetime(2026, 9, 22, tzinfo=UTC)


def test_timeline_route_requires_scope_and_closed_bounded_query() -> None:
    store = MagicMock(spec=Store)
    knowledge = MagicMock(spec=KnowledgeCore)
    knowledge.timeline.return_value = {
        "results": [], "next_cursor": None, "recorded_cutoff_at": NOW,
        "limit": 2, "visibility": "unsuperseded",
        "coverage": {"undated_events": "excluded"}, "untrusted_content": True,
    }
    query = {
        "start": NOW.isoformat(), "end": (NOW + timedelta(days=1)).isoformat(),
        "limit": "2",
    }
    headers = {"Authorization": f"Bearer {TOKEN}"}
    with TestClient(create_app(
        store, registry({"knowledge.search"}), knowledge_store=knowledge,
    )) as client:
        response = client.get("/v1/knowledge/timeline", params=query, headers=headers)
        assert response.status_code == 200, response.text
        assert response.json()["coverage"]["undated_events"] == "excluded"
        request = knowledge.timeline.call_args.args[1]
        assert request.limit == 2 and request.visibility == "unsuperseded"
        assert request.start == NOW and request.end == NOW + timedelta(days=1)
        for changes in (
            {"end": NOW.isoformat()},
            {"end": (NOW + timedelta(days=367)).isoformat()},
            {"start": "2026-09-22T00:00:00"},
            {"after": "event_" + "1" * 32},
            {"project_id": "event_" + "1" * 32},
            {"visibility": "current"},
            {"limit": "51"},
            {"unknown": "no"},
        ):
            assert client.get(
                "/v1/knowledge/timeline", params={**query, **changes}, headers=headers,
            ).status_code == 422
        assert knowledge.timeline.call_count == 1
    with TestClient(create_app(
        store, registry({"knowledge.read"}), knowledge_store=knowledge,
    )) as client:
        assert client.get(
            "/v1/knowledge/timeline", params=query, headers=headers,
        ).status_code == 403


def test_timeline_query_binds_project_and_recorded_cutoff_before_limit() -> None:
    store = MagicMock(spec=Store)
    conn = store.transaction.return_value.__enter__.return_value
    conn.execute.return_value.fetchone.return_value = {"now": NOW}
    conn.execute.return_value.fetchall.return_value = []
    ctx = TenantContext(uuid4(), uuid4(), frozenset({"knowledge.search"}), uuid4())
    project = "project_" + "1" * 32
    result = KnowledgeCore(store).timeline(ctx, TimelineRequest(
        start=NOW - timedelta(days=1), end=NOW + timedelta(days=1),
        project_id=project, limit=3,
    ))
    assert result["results"] == [] and result["recorded_cutoff_at"] == NOW
    query, params = conn.execute.call_args.args
    assert "ev.project_id=%s" in query
    assert "ev.recorded_at<=allowed.cutoff" in query
    assert "s.recorded_at<=allowed.cutoff" in query
    assert "c.recorded_at<=allowed.cutoff" in query
    assert "r.recorded_at<=allowed.cutoff" in query
    assert "ORDER BY ev.starts_at,ev.id LIMIT %s" in query
    assert "NOT EXISTS (SELECT 1 FROM knowledge_events s" in query
    assert project in params and params[-1] == 4
    assert query.count("%s") == len(params)
    store.audit.assert_called_once()


def test_timeline_cursor_anchor_uses_same_filters_and_fails_closed() -> None:
    store = MagicMock(spec=Store)
    conn = store.transaction.return_value.__enter__.return_value
    clock = MagicMock()
    clock.fetchone.return_value = {"now": NOW}
    anchor = MagicMock()
    event_id = "event_" + "2" * 32
    anchor.fetchone.return_value = {"starts_at": NOW - timedelta(hours=1), "id": event_id}
    page = MagicMock()
    page.fetchall.return_value = []
    conn.execute.side_effect = [clock, anchor, page]
    ctx = TenantContext(uuid4(), uuid4(), frozenset({"knowledge.search"}), uuid4())
    request = TimelineRequest(
        start=NOW - timedelta(days=1), end=NOW + timedelta(days=1),
        recorded_cutoff_at=NOW, after=event_id, visibility="retained",
    )
    assert KnowledgeCore(store).timeline(ctx, request)["results"] == []
    anchor_sql, anchor_params = conn.execute.call_args_list[1].args
    page_sql, page_params = conn.execute.call_args_list[2].args
    assert "ev.id=%s" in anchor_sql and "ev.recorded_at<=allowed.cutoff" in anchor_sql
    assert "(ev.starts_at,ev.id)>(%s,%s)" in page_sql
    assert anchor_sql.count("%s") == len(anchor_params)
    assert page_sql.count("%s") == len(page_params)
    assert page_params[-3:-1] == (NOW - timedelta(hours=1), event_id)

    conn.execute.side_effect = [clock, MagicMock(fetchone=lambda: None)]
    with pytest.raises(NotFound):
        KnowledgeCore(store).timeline(ctx, request)
