"""Privacy-safe API error correlation without a database or real content."""

from __future__ import annotations

import logging
from unittest.mock import MagicMock
from uuid import UUID

import psycopg
import pytest
from fastapi.testclient import TestClient
from test_service import TOKEN, registry

from email_brain.api import create_app
from email_brain.blobs import BlobError
from email_brain.store import Store


@pytest.mark.parametrize(
    ("failure", "status", "payload", "code"),
    [
        (RuntimeError("private-canary"), 500, {"error": "internal_error"}, "internal_error"),
        (
            psycopg.OperationalError("private-canary"),
            503,
            {"error": "database_unavailable", "retryable": True},
            "database_unavailable",
        ),
        (
            BlobError(),
            503,
            {"error": "evidence_storage_unavailable"},
            "evidence_storage_unavailable",
        ),
    ],
)
def test_failures_keep_safe_correlation_without_content(
    failure: Exception,
    status: int,
    payload: dict[str, object],
    code: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    store = MagicMock(spec=Store)
    store.search.side_effect = failure
    client = TestClient(create_app(store, registry()), raise_server_exceptions=False)
    with caplog.at_level(logging.ERROR, logger="email_brain.requests"):
        response = client.post(
            "/v1/search",
            json={"query": "private-canary"},
            headers={"Authorization": f"Bearer {TOKEN}"},
        )
    assert response.status_code == status
    assert response.json() == payload
    request_id = response.headers["X-Request-ID"]
    UUID(request_id)
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    events = [
        record.getMessage()
        for record in caplog.records
        if record.name == "email_brain.requests"
    ]
    assert len(events) == 1
    assert f"id={request_id}" in events[0]
    assert "route=/v1/search" in events[0]
    assert f"status={status}" in events[0]
    assert f"code={code}" in events[0]
    assert f"error_type={type(failure).__name__}" in events[0]
    assert "private-canary" not in events[0]
    assert "private-canary" not in response.text
