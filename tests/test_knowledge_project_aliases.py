"""Closed reviewed project-alias API and read-client boundary."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

import httpx
import pytest
from fastapi.testclient import TestClient
from test_service import TOKEN, registry

from email_brain.api import create_app
from email_brain.store import Store
from masterbrain.brain_client import BrainClientError, BrainReadClient
from masterbrain.knowledge import KnowledgeCore

PROJECT = "project_" + "a" * 32
EVIDENCE = "evidence_" + "b" * 32
PATH = "/v1/knowledge/projects/resolve"
HEADERS = {"Authorization": f"Bearer {TOKEN}"}


def response() -> dict:
    return {
        "candidates": [{
            "object_kind": "project", "object_id": PROJECT,
            "title": "Deal Example", "matched_alias": "123 Main St.",
            "alias_kind": "address", "evidence_id": EVIDENCE,
            "recorded_at": datetime(2026, 10, 14, tzinfo=UTC).isoformat(),
        }],
        "ambiguous": False, "truncated": False,
        "resolution": "reviewed_candidates_only", "visibility": "retained",
        "untrusted_content": True,
    }


def test_project_alias_route_is_scoped_and_closed() -> None:
    store = MagicMock(spec=Store)
    knowledge = MagicMock(spec=KnowledgeCore)
    knowledge.resolve_project_alias.return_value = response()
    with TestClient(create_app(
        store, registry({"knowledge.search"}), knowledge_store=knowledge,
    )) as client:
        result = client.get(PATH, params={"name": "123-MAIN, St", "limit": "2"}, headers=HEADERS)
        assert result.status_code == 200, result.text
        assert result.json()["candidates"][0]["object_id"] == PROJECT
        assert knowledge.resolve_project_alias.call_args.kwargs["limit"] == 2
        for params in (
            {}, {"name": "!!!"}, {"name": "123 Main St", "limit": "0"},
            {"name": "123 Main St", "limit": "26"},
            {"name": "123 Main St", "unknown": "no"},
        ):
            assert client.get(PATH, params=params, headers=HEADERS).status_code == 422
        knowledge.resolve_project_alias.assert_called_once()
    with TestClient(create_app(
        store, registry({"knowledge.read"}), knowledge_store=knowledge,
    )) as client:
        assert client.get(PATH, params={"name": "123 Main St"}, headers=HEADERS).status_code == 403


def test_project_alias_client_accepts_only_ordered_grounded_candidates() -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json=response())

    with BrainReadClient(
        "https://brain.example", "token", transport=httpx.MockTransport(handler),
    ) as client:
        result = client.resolve_project_alias("123-MAIN, St", limit=2)
        assert result["candidates"][0]["object_id"] == PROJECT
        with pytest.raises(BrainClientError, match="invalid_request"):
            client.resolve_project_alias("!!!")
    assert len(calls) == 1
    assert calls[0].method == "GET" and calls[0].url.path == PATH
    assert calls[0].url.params["name"] == "123-MAIN, St"
    assert calls[0].headers["authorization"] == "Bearer token"


@pytest.mark.parametrize("change", [
    {"ambiguous": True}, {"visibility": "current"}, {"truncated": True},
    {"candidates": [{**response()["candidates"][0], "object_id": "project_bad"}]},
    {"candidates": [{**response()["candidates"][0], "matched_alias": "Different Deal"}]},
    {"candidates": [{**response()["candidates"][0], "evidence_id": "evidence_bad"}]},
    {"candidates": response()["candidates"] * 2},
])
def test_project_alias_client_rejects_malformed_response(change: dict) -> None:
    result = {**response(), **change}
    with BrainReadClient(
        "https://brain.example", "token",
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=result)),
    ) as client:
        with pytest.raises(BrainClientError, match="invalid_response"):
            client.resolve_project_alias("123 Main St")
