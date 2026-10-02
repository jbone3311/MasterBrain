"""Read-only external Brain API transport and privacy boundaries."""

import httpx
import pytest

from masterbrain.brain_client import MAX_RESPONSE_BYTES, BrainClientError, BrainReadClient

LAYERS = (
    "fileos", "archive_members", "archive_documents", "archive_images",
    "email_messages", "email_attachments", "email_documents", "knowledge",
)


def current_result() -> dict[str, object]:
    return {
        "mode": "grouped_current_sources",
        "ranking": "within_group_only",
        "consistency": "independent_layer_reads",
        "untrusted_content": True,
        "coverage": {"complete": False},
        "layers": {name: [] for name in LAYERS},
    }


def answer_result() -> dict[str, object]:
    return {
        "mode": "grounded_extractive_v1",
        "status": "quoted_evidence",
        "answer": "Relevant passages from current indexed evidence are quoted below.",
        "citations": [{
            "evidence_id": "evidence_123", "document_id": "document_123",
            "source_id": "trial_files", "source_kind": "fileos",
            "quote": "fictional proof", "start": 0, "end": 15,
            "body_sha256": "a" * 64,
        }],
        "coverage": {"complete": False, "source_access": "enrolled_sources_only"},
        "untrusted_content": True,
    }


def test_answer_client_uses_same_read_only_origin_and_validates_response() -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json=answer_result())

    with BrainReadClient(
        "https://brain.example", "synthetic-token", transport=httpx.MockTransport(handler)
    ) as client:
        assert client.answer("What is pending?")["citations"][0]["source_id"] == "trial_files"
        for bad in (" ", "bad\x00question", "x" * 501):
            with pytest.raises(BrainClientError, match="invalid_request"):
                client.answer(bad)
    assert len(calls) == 1
    assert calls[0].url.path == "/v1/brain/answers"
    assert calls[0].headers["authorization"] == "Bearer synthetic-token"
    assert b'"question":"What is pending?"' in calls[0].content


@pytest.mark.parametrize("change", [
    {"mode": "freeform"},
    {"coverage": {"complete": True}},
    {"citations": [{"evidence_id": "forged"}]},
    {"citations": [{**answer_result()["citations"][0], "quote": "invented"}]},
    {"status": "quoted_evidence", "citations": []},
    {"answer": "x" * 201},
])
def test_answer_client_rejects_malformed_claims(change: dict) -> None:
    result = {**answer_result(), **change}
    with BrainReadClient(
        "https://brain.example", "token",
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=result)),
    ) as client:
        with pytest.raises(BrainClientError, match="invalid_response"):
            client.answer("fictional question")


def test_fixed_read_only_paths_and_separate_expansion() -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if request.url.path == "/v1/brain/current-search":
            return httpx.Response(200, json=current_result())
        if request.url.path == "/v1/brain/evidence/evidence_123":
            return httpx.Response(200, json={"id": "evidence_123", "source_kind": "email"})
        if request.url.path == "/v1/brain/evidence/evidence_123/content":
            return httpx.Response(200, json={
                "evidence_id": "evidence_123", "content": "fictional proof", "truncated": False,
            })
        if request.url.path == "/v1/brain/current-coverage":
            return httpx.Response(200, json={
                "complete": False, "results": [{"source_id": "trial_files"}],
                "next_cursor": None, "limit": 1,
            })
        if request.url.path == "/v1/brain/changes":
            return httpx.Response(200, json={
                "results": [{"id": "change_123", "source_id": "trial_files"}],
                "next_cursor": None, "limit": 1,
            })
        return httpx.Response(404)

    with BrainReadClient(
        "https://brain.example", "synthetic-token", transport=httpx.MockTransport(handler)
    ) as client:
        assert client.current_search("Cedar Harbor")["coverage"] == {"complete": False}
        assert client.evidence("evidence_123")["source_kind"] == "email"
        assert client.evidence_content("evidence_123")["content"] == "fictional proof"
        assert client.current_coverage(limit=1)["results"][0]["source_id"] == "trial_files"
        assert client.changes(after="change_111", limit=1)["results"][0]["id"] == "change_123"
    assert [(call.method, call.url.path) for call in calls] == [
        ("POST", "/v1/brain/current-search"),
        ("GET", "/v1/brain/evidence/evidence_123"),
        ("POST", "/v1/brain/evidence/evidence_123/content"),
        ("GET", "/v1/brain/current-coverage"),
        ("GET", "/v1/brain/changes"),
    ]
    assert all(call.headers["authorization"] == "Bearer synthetic-token" for call in calls)
    assert all(call.headers["cache-control"] == "no-store" for call in calls)
    assert b'"query":"Cedar Harbor"' in calls[0].content
    assert b'"max_chars":4000' in calls[2].content
    assert calls[3].url.query == b"limit=1"
    assert calls[4].url.query == b"limit=1&after=change_111"
    with pytest.raises(BrainClientError, match="client_closed"):
        client.current_search("again")


@pytest.mark.parametrize("url", [
    "http://brain.example", "http://localhost", "https://user:pass@brain.example",
    "https://brain.example/path", "https://brain.example/?token=secret",
    "https://brain.example/#fragment", "file:///private/data", "not-a-url",
])
def test_rejects_unsafe_or_ambiguous_origins(url: str) -> None:
    with pytest.raises(BrainClientError, match="invalid_origin"):
        BrainReadClient(url, "token", allow_insecure_loopback=True)


def test_explicit_loopback_only_and_credential_validation() -> None:
    with pytest.raises(BrainClientError, match="invalid_origin"):
        BrainReadClient("http://127.0.0.1:8123", "token")
    with BrainReadClient(
        "http://127.0.0.1:8123", "token", allow_insecure_loopback=True,
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=current_result())),
    ) as client:
        assert client.current_search("fictional")["mode"] == "grouped_current_sources"
    for token in ("", "token\r\nInjected: yes", "token with space", "☃"):
        with pytest.raises(BrainClientError, match="invalid_credential"):
            BrainReadClient("https://brain.example", token)


def test_request_bounds_refuse_without_network() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json=current_result())

    with BrainReadClient(
        "https://brain.example", "token", transport=httpx.MockTransport(handler)
    ) as client:
        for query in (" ", "x" * 501, "bad\x00query"):
            with pytest.raises(BrainClientError, match="invalid_request"):
                client.current_search(query)
        for evidence_id in ("../secret", "evidence?x", "", "A" * 129):
            with pytest.raises(BrainClientError, match="invalid_request"):
                client.evidence(evidence_id)
        with pytest.raises(BrainClientError, match="invalid_request"):
            client.evidence_content("evidence_123", max_chars=16001)
        for limit in (0, 51, True):
            with pytest.raises(BrainClientError, match="invalid_request"):
                client.changes(limit=limit)
        with pytest.raises(BrainClientError, match="invalid_request"):
            client.current_coverage(after="../other")
    assert calls == 0


@pytest.mark.parametrize("response,code", [
    (httpx.Response(302, headers={"location": "https://attacker.invalid/"}), "request_failed"),
    (httpx.Response(401, text="secret token"), "access_denied"),
    (httpx.Response(403, text="private email"), "access_denied"),
    (httpx.Response(429, text="slow down"), "rate_limited"),
    (httpx.Response(503, text="database password"), "service_unavailable"),
    (httpx.Response(200, content=b"not json", headers={"content-type": "application/json"}),
     "invalid_response"),
    (httpx.Response(200, text="plain"), "invalid_response"),
    (httpx.Response(200, json={"mode": "wrong"}), "invalid_response"),
    (httpx.Response(200, content=b" " * (MAX_RESPONSE_BYTES + 1),
                    headers={"content-type": "application/json"}), "response_too_large"),
])
def test_failure_codes_are_bounded_and_do_not_follow_redirects(
    response: httpx.Response, code: str
) -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return response

    with BrainReadClient(
        "https://brain.example", "private-token", transport=httpx.MockTransport(handler)
    ) as client:
        with pytest.raises(BrainClientError) as error:
            client.current_search("fictional")
    assert error.value.code == code
    assert str(error.value) == code
    assert "private-token" not in repr(error.value)
    assert calls == 1


def test_transport_timeout_is_scrubbed() -> None:
    def fail(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("private source URL or credential")

    with BrainReadClient(
        "https://brain.example", "private-token", transport=httpx.MockTransport(fail)
    ) as client:
        with pytest.raises(BrainClientError) as error:
            client.current_search("fictional")
    assert error.value.code == "timeout"
    assert "private" not in str(error.value)


def test_server_cookie_is_never_returned_on_later_read() -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(
            200, json=current_result(), headers={"set-cookie": "session=untrusted; Path=/"}
        )

    with BrainReadClient(
        "https://brain.example", "token", transport=httpx.MockTransport(handler)
    ) as client:
        client.current_search("first")
        client.current_search("second")
    assert all("cookie" not in request.headers for request in calls)


def test_evidence_identity_and_content_bounds_are_verified() -> None:
    responses = iter([
        httpx.Response(200, json={"id": "evidence_other", "source_kind": "email"}),
        httpx.Response(200, json={
            "evidence_id": "evidence_123", "content": "x" * 101, "truncated": False,
        }),
    ])
    with BrainReadClient(
        "https://brain.example", "token",
        transport=httpx.MockTransport(lambda request: next(responses)),
    ) as client:
        with pytest.raises(BrainClientError, match="invalid_response"):
            client.evidence("evidence_123")
        with pytest.raises(BrainClientError, match="invalid_response"):
            client.evidence_content("evidence_123", max_chars=100)
