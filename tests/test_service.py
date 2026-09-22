from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from email_brain.api import create_app
from email_brain.auth import Credential, TokenRegistry
from email_brain.inference import Route, RoutingPolicy, route, validate_classification
from email_brain.normalize import normalize
from email_brain.store import Store
from masterbrain.datacore.persistence import DataCoreStore, SearchHit

TOKEN = "synthetic-test-token-not-a-real-credential-000000"


def registry(
    scopes: set[str] | None = None, kind: str = "human", expired: bool = False
) -> TokenRegistry:
    return TokenRegistry(
        [
            Credential(
                token_sha256=hashlib.sha256(TOKEN.encode()).hexdigest(),
                tenant_id=uuid4(),
                actor_id=uuid4(),
                scopes=scopes or {"email.search"},
                expires_at=datetime.now(UTC) + timedelta(days=-1 if expired else 1),
                client_kind=kind,
            )
        ]
    )


@pytest.fixture
def client() -> TestClient:
    store = MagicMock(spec=Store)
    store.search.return_value = []
    return TestClient(create_app(store, registry()))


def test_auth_required(client: TestClient) -> None:
    assert client.post("/v1/search", json={"query": "secret"}).status_code == 401


def test_search_and_headers(client: TestClient) -> None:
    response = client.post(
        "/v1/search", json={"query": "Melron"}, headers={"Authorization": f"Bearer {TOKEN}"}
    )
    assert response.status_code == 200
    assert response.json()["results"] == []
    assert response.headers["Cache-Control"] == "no-store"
    assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]


@pytest.mark.parametrize("path", ["/", "/app.js", "/document_review.js", "/style.css"])
def test_owner_assets_remain_fixed_same_origin_and_noncacheable(client: TestClient, path: str):
    response = client.get(path)
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    assert "script-src 'self'" in response.headers["Content-Security-Policy"]
    if path == "/":
        assert 'src="/document_review.js"' in response.text
        assert 'id="include-documents" type="checkbox"' in response.text
        assert 'id="document-selection" aria-live="polite"' in response.text
        assert 'id="documents-health" role="status"' in response.text
    elif path.endswith(".js"):
        assert response.headers["Content-Type"].startswith("text/javascript")


def test_body_tenant_cannot_override_identity(client: TestClient) -> None:
    response = client.post(
        "/v1/search",
        json={"query": "x", "tenant_id": str(uuid4())},
        headers={"Authorization": f"Bearer {TOKEN}"},
    )
    assert response.status_code == 422
    assert "tenant_id" not in response.text


def test_scope_denied(client: TestClient) -> None:
    assert (
        client.get("/v1/proposals", headers={"Authorization": f"Bearer {TOKEN}"}).status_code == 403
    )


def test_sync_status_auth_scope_and_server_bound_context():
    store = MagicMock(spec=Store)
    store.sync_status.return_value = {"message_counts": {"quarantined": 1}, "review_required": True}
    credentials = registry()
    client = TestClient(create_app(store, credentials))
    account = uuid4()
    path = f"/v1/accounts/{account}/sync-status"
    assert client.get(path).status_code == 401
    result = client.get(path, headers={"Authorization": f"Bearer {TOKEN}"})
    assert result.status_code == 200 and result.json()["review_required"]
    passed_context, passed_account = store.sync_status.call_args.args
    assert passed_account == account
    assert passed_context.tenant_id == credentials.authenticate(TOKEN).context.tenant_id
    denied = TestClient(create_app(store, registry({"email.evidence.read"})))
    assert denied.get(path, headers={"Authorization": f"Bearer {TOKEN}"}).status_code == 403


def test_quarantine_api_limits_and_no_raw_download():
    store = MagicMock(spec=Store)
    store.quarantines.return_value = {"results": [], "next_after": None, "raw_access": False}
    client = TestClient(create_app(store, registry({"email.evidence.read"})))
    path = f"/v1/accounts/{uuid4()}/quarantine"
    headers = {"Authorization": f"Bearer {TOKEN}"}
    assert client.get(path).status_code == 401
    assert client.get(path, headers=headers).json()["raw_access"] is False
    for query in ("?limit=51", "?limit=0", "?after=not-a-uuid"):
        assert client.get(path + query, headers=headers).status_code == 422
    for suffix in ("/raw", "/reprocess", "/delete"):
        assert client.post(path + suffix, headers=headers).status_code == 404


def test_big_body_rejected(client: TestClient) -> None:
    response = client.post("/v1/search", content=b"x" * 32769)
    assert response.status_code == 413


def test_health_is_not_readiness(client: TestClient) -> None:
    assert client.get("/healthz").json()["mailbox_writes"] == "disabled"
    assert client.get("/readyz").status_code == 401


def test_no_action_endpoint(client: TestClient) -> None:
    for path in ("/v1/actions", "/v1/send", "/v1/delete", "/v1/sql"):
        assert client.post(path, json={}).status_code == 404


def test_brain_api_progressive_scopes_and_bounds() -> None:
    store = MagicMock(spec=Store)
    brain = MagicMock(spec=DataCoreStore)
    brain.search.return_value = [
        SearchHit(
            "chunk_" + "1" * 32,
            "document_" + "2" * 32,
            "evidence_" + "3" * 32,
            "files_test",
            "folder/report.txt",
            "bounded untrusted excerpt",
            0.5,
        )
    ]
    brain.evidence.return_value = {
        "id": "evidence_" + "3" * 32,
        "sha256": "a" * 64,
        "original_content_available": False,
        "untrusted_content": True,
    }
    brain.evidence_content.return_value = {
        "content": "bounded",
        "truncated": False,
        "untrusted_content": True,
    }
    brain.changes.return_value = {"results": [], "next_cursor": None, "limit": 25}
    evidence_id = "evidence_" + "3" * 32

    search_client = TestClient(create_app(store, registry({"brain.search"}), brain_store=brain))
    headers = {"Authorization": f"Bearer {TOKEN}"}
    response = search_client.post(
        "/v1/brain/search", json={"query": "report", "limit": 5}, headers=headers
    )
    assert response.status_code == 200
    assert response.json()["results"][0]["evidence_id"] == evidence_id
    assert response.json()["untrusted_content"] is True
    assert (
        search_client.get(f"/v1/brain/evidence/{evidence_id}", headers=headers).status_code == 403
    )

    evidence_client = TestClient(
        create_app(store, registry({"brain.evidence.read"}), brain_store=brain)
    )
    assert (
        evidence_client.get(f"/v1/brain/evidence/{evidence_id}", headers=headers).status_code == 200
    )
    assert (
        evidence_client.post(
            f"/v1/brain/evidence/{evidence_id}/content",
            json={"max_chars": 100},
            headers=headers,
        ).status_code
        == 403
    )

    content_client = TestClient(
        create_app(store, registry({"brain.content.read"}), brain_store=brain)
    )
    assert (
        content_client.post(
            f"/v1/brain/evidence/{evidence_id}/content",
            json={"max_chars": 100},
            headers=headers,
        ).json()["content"]
        == "bounded"
    )
    assert (
        content_client.post(
            f"/v1/brain/evidence/{evidence_id}/content",
            json={"max_chars": 16001},
            headers=headers,
        ).status_code
        == 422
    )

    changes_client = TestClient(
        create_app(store, registry({"brain.changes.read"}), brain_store=brain)
    )
    assert changes_client.get("/v1/brain/changes?limit=25", headers=headers).status_code == 200


def test_brain_write_scopes_are_worker_only() -> None:
    for scope in ("brain.source.ingest", "brain.document.publish"):
        with pytest.raises(ValueError, match="worker-only"):
            registry({scope}, "human")


def test_expiry_and_bad_token() -> None:
    assert registry(expired=True).authenticate(TOKEN) is None
    assert registry().authenticate("wrong-token" * 5) is None


def test_assistants_cannot_be_reviewers() -> None:
    with pytest.raises(ValueError, match="human-only"):
        registry({"email.review"}, "assistant")


def test_plain_mime_and_raw_hash() -> None:
    raw = b"Subject: Hello\r\nFrom: Person <person@example.invalid>\r\n\r\nMelron\r\n"
    result = normalize(raw)
    assert result.text == "Melron"
    assert result.sender == "person@example.invalid"
    assert result.raw_sha256 == hashlib.sha256(raw).hexdigest()


def test_html_is_text_and_never_fetches() -> None:
    raw = (
        b"Content-Type: text/html\r\n\r\n<script>steal()</script><p>Keep me</p>"
        b"<img src='https://attacker.invalid/track'><style>hide</style>"
    )
    result = normalize(raw)
    assert "Keep me" in result.text
    assert "steal" not in result.text and "attacker" not in result.text


def test_unknown_charset_falls_back() -> None:
    assert normalize(b"Content-Type: text/plain; charset=unknown123\r\n\r\nHello").text == "Hello"


@pytest.mark.parametrize("raw", [b"", b"x" * 1048577])
def test_raw_bounds(raw: bytes) -> None:
    with pytest.raises(ValueError):
        normalize(raw)


def test_remote_is_opt_in_and_bounded_by_policy() -> None:
    assert (
        route(
            deterministic_match=False,
            consequential=False,
            local_failed=True,
            policy=RoutingPolicy(),
        )
        == Route.HUMAN
    )
    assert (
        route(
            deterministic_match=True,
            consequential=False,
            local_failed=False,
            policy=RoutingPolicy(),
        )
        == Route.CODE
    )
    assert (
        route(
            deterministic_match=True,
            consequential=True,
            local_failed=False,
            policy=RoutingPolicy(True, True, True),
        )
        == Route.HUMAN
    )


def test_injection_output_cannot_add_tools() -> None:
    payload = {
        "category": "investment",
        "needs_reply": False,
        "confidence": 0.9,
        "evidence_excerpt": "Melron",
        "send_email": "attacker@example.invalid",
    }
    with pytest.raises(ValidationError):
        validate_classification(json.dumps(payload), "Melron")
    payload.pop("send_email")
    with pytest.raises(ValueError, match="not present"):
        validate_classification(json.dumps(payload), "unrelated")
    assert validate_classification(json.dumps(payload), "Melron").category == "investment"
