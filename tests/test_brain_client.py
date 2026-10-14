"""Read-only external Brain API transport and privacy boundaries."""

import json
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from masterbrain.brain_client import MAX_RESPONSE_BYTES, BrainClientError, BrainReadClient

LAYERS = (
    "fileos", "archive_members", "archive_documents", "archive_images",
    "email_messages", "email_attachments", "email_documents", "knowledge",
)
TIMELINE_START = datetime(2026, 10, 1, tzinfo=UTC)
TIMELINE_EVENT = "event_" + "a" * 32
TIMELINE_EVIDENCE = "evidence_" + "b" * 32
DUE_COMMITMENT = "commitment_" + "c" * 32
DOSSIER_PROJECT = "project_" + "d" * 32
DOSSIER_MEMBER = "member_" + "e" * 32
DOSSIER_ENTITY = "entity_" + "f" * 32


def dossier_result() -> dict[str, object]:
    recorded = (TIMELINE_START - timedelta(days=1)).isoformat()
    return {
        "project": {
            "object_kind": "project", "object_id": DOSSIER_PROJECT,
            "title": "Fictional project", "summary": "Review", "summary_truncated": False,
            "state": "active", "recorded_at": recorded,
            "evidence_ids": [TIMELINE_EVIDENCE],
        },
        "events": [{
            "object_kind": "event", "object_id": TIMELINE_EVENT,
            "event_type": "decision", "title": "Fictional review",
            "starts_at": None, "ends_at": None, "project_id": DOSSIER_PROJECT,
            "recorded_at": recorded,
            "evidence_ids": [TIMELINE_EVIDENCE],
        }],
        "commitments": [{
            "object_kind": "commitment", "object_id": DUE_COMMITMENT,
            "summary": "Submit the fictional package", "summary_truncated": False,
            "state": "open", "due_at": None, "project_id": DOSSIER_PROJECT,
            "owner_entity_id": None,
            "counterparty_entity_id": None, "recorded_at": recorded,
            "evidence_ids": [TIMELINE_EVIDENCE],
        }],
        "members": [{
            "object_kind": "member", "object_id": DOSSIER_MEMBER,
            "project_id": DOSSIER_PROJECT, "entity_id": DOSSIER_ENTITY,
            "entity_name": "Pat Example", "entity_type": "person",
            "role": "broker", "assertion_status": "asserted",
            "valid_from": None, "valid_to": None, "recorded_at": recorded,
            "evidence_ids": [TIMELINE_EVIDENCE],
        }],
        "recorded_cutoff_at": TIMELINE_START.isoformat(),
        "visibility": "unsuperseded", "event_limit": 1, "commitment_limit": 1,
        "member_limit": 1, "events_truncated": False, "commitments_truncated": False,
        "members_truncated": False,
        "coverage": {"order": "recorded_at_descending", "undated_links": "included",
                     "source_freshness": "not_asserted",
                     "interpretation": "reviewed_assertions_not_current_state"},
        "untrusted_content": True,
    }


def test_project_dossier_client_sends_bounded_read_and_validates_context() -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json=dossier_result())

    with BrainReadClient(
        "https://brain.example", "token", transport=httpx.MockTransport(handler),
    ) as client:
        result = client.project_dossier(
            DOSSIER_PROJECT, event_limit=1, commitment_limit=1, member_limit=1,
            recorded_cutoff_at=TIMELINE_START,
        )
        assert result["project"]["object_id"] == DOSSIER_PROJECT
        for invalid in (
            {"project_id": "project_bad"}, {"event_limit": True},
            {"commitment_limit": 26}, {"member_limit": True}, {"visibility": "current"},
            {"recorded_cutoff_at": TIMELINE_START.replace(tzinfo=None)},
        ):
            with pytest.raises(BrainClientError, match="invalid_request"):
                arguments = {"project_id": DOSSIER_PROJECT, "event_limit": 1,
                             "commitment_limit": 1, "member_limit": 1, **invalid}
                client.project_dossier(**arguments)
    assert len(calls) == 1
    assert calls[0].method == "GET"
    assert calls[0].url.path == f"/v1/knowledge/projects/{DOSSIER_PROJECT}/dossier"
    assert calls[0].url.params["event_limit"] == "1"
    assert calls[0].headers["authorization"] == "Bearer token"


@pytest.mark.parametrize("change", [
    {"untrusted_content": False}, {"visibility": "retained"},
    {"events_truncated": "yes"}, {"event_limit": 25},
    {"recorded_cutoff_at": (TIMELINE_START + timedelta(hours=1)).isoformat()},
    {"project": {**dossier_result()["project"], "object_id": "project_bad"}},
    {"project": {**dossier_result()["project"], "evidence_ids": []}},
    {"events": [{**dossier_result()["events"][0], "title": "Private\x00title"}]},
    {"events": [{**dossier_result()["events"][0], "project_id":
                 "project_" + "e" * 32}]},
    {"events": [{**dossier_result()["events"][0], "recorded_at":
                 (TIMELINE_START + timedelta(hours=1)).isoformat()}]},
    {"commitments": [{**dossier_result()["commitments"][0],
                     "owner_entity_id": "entity_bad"}]},
    {"commitments": [{**dossier_result()["commitments"][0],
                     "project_id": "project_" + "e" * 32}]},
    {"commitments": dossier_result()["commitments"] * 2},
    {"members": [{**dossier_result()["members"][0], "entity_id": "entity_bad"}]},
    {"members": dossier_result()["members"] * 2},
    {"coverage": {"source_freshness": "asserted"}},
])
def test_project_dossier_client_rejects_malformed_context(change: dict) -> None:
    result = {**dossier_result(), **change}
    with BrainReadClient(
        "https://brain.example", "token",
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=result)),
    ) as client:
        with pytest.raises(BrainClientError, match="invalid_response"):
            client.project_dossier(
                DOSSIER_PROJECT, event_limit=1, commitment_limit=1, member_limit=1,
                recorded_cutoff_at=TIMELINE_START,
            )


def due_result() -> dict[str, object]:
    return {
        "results": [{
            "object_kind": "commitment", "object_id": DUE_COMMITMENT,
            "summary": "Submit the fictional package", "summary_truncated": False,
            "state": "open", "due_at": (TIMELINE_START + timedelta(hours=1)).isoformat(),
            "project_id": None, "owner_entity_id": None, "counterparty_entity_id": None,
            "evidence_ids": [TIMELINE_EVIDENCE],
        }],
        "next_cursor": DUE_COMMITMENT,
        "recorded_cutoff_at": TIMELINE_START.isoformat(),
        "limit": 1, "visibility": "unsuperseded", "state_filter": "open",
        "coverage": {"undated_commitments": "excluded", "source_freshness": "not_asserted",
                     "interpretation": "reviewed_assertions"},
        "untrusted_content": True,
    }


def test_due_client_sends_bounded_read_and_validates_page() -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json=due_result())

    with BrainReadClient(
        "https://brain.example", "token", transport=httpx.MockTransport(handler)
    ) as client:
        result = client.commitments_due(
            TIMELINE_START, TIMELINE_START + timedelta(days=1), state="open", limit=1,
            recorded_cutoff_at=TIMELINE_START, after="commitment_" + "0" * 32,
        )
        assert result["results"][0]["object_id"] == DUE_COMMITMENT
        for invalid in (
            {"start": TIMELINE_START.replace(tzinfo=None)},
            {"end": TIMELINE_START},
            {"end": TIMELINE_START + timedelta(days=367)},
            {"limit": True},
            {"limit": 51},
            {"state": "active"},
            {"after": DUE_COMMITMENT},
            {"after": "event_" + "a" * 32, "recorded_cutoff_at": TIMELINE_START},
            {"project_id": "project_bad"},
        ):
            arguments = {
                "start": TIMELINE_START,
                "end": TIMELINE_START + timedelta(days=1), **invalid,
            }
            with pytest.raises(BrainClientError, match="invalid_request"):
                client.commitments_due(**arguments)
    assert len(calls) == 1
    assert calls[0].method == "GET"
    assert calls[0].url.path == "/v1/knowledge/commitments-due"
    assert calls[0].url.params["state"] == "open"
    assert calls[0].url.params["after"] == "commitment_" + "0" * 32
    assert calls[0].headers["authorization"] == "Bearer token"


@pytest.mark.parametrize("change", [
    {"untrusted_content": False},
    {"visibility": "retained"},
    {"state_filter": "completed"},
    {"recorded_cutoff_at": (TIMELINE_START + timedelta(hours=1)).isoformat()},
    {"next_cursor": "commitment_" + "d" * 32},
    {"coverage": {"undated_commitments": "included"}},
    {"results": [{**due_result()["results"][0], "summary": "Private\x00text"}]},
    {"results": [{**due_result()["results"][0], "summary_truncated": "no"}]},
    {"results": [{**due_result()["results"][0], "evidence_ids": []}]},
    {"results": [{**due_result()["results"][0], "project_id": "project_bad"}]},
    {"results": [{**due_result()["results"][0], "owner_entity_id": "entity_bad"}]},
    {"results": [{**due_result()["results"][0], "state": "completed"}]},
    {"results": [{**due_result()["results"][0],
                  "due_at": (TIMELINE_START - timedelta(hours=1)).isoformat()}]},
    {"results": due_result()["results"] * 2},
])
def test_due_client_rejects_malformed_pages(change: dict) -> None:
    result = {**due_result(), **change}
    with BrainReadClient(
        "https://brain.example", "token",
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=result)),
    ) as client:
        with pytest.raises(BrainClientError, match="invalid_response"):
            client.commitments_due(
                TIMELINE_START, TIMELINE_START + timedelta(days=1),
                state="open", limit=1, recorded_cutoff_at=TIMELINE_START,
            )


def timeline_result() -> dict[str, object]:
    return {
        "results": [{
            "object_kind": "event", "object_id": TIMELINE_EVENT,
            "event_type": "decision", "title": "Fictional review",
            "starts_at": (TIMELINE_START + timedelta(hours=1)).isoformat(),
            "ends_at": None, "project_id": None,
            "evidence_ids": [TIMELINE_EVIDENCE],
        }],
        "next_cursor": TIMELINE_EVENT,
        "recorded_cutoff_at": TIMELINE_START.isoformat(),
        "limit": 1, "visibility": "unsuperseded",
        "coverage": {"undated_events": "excluded", "source_freshness": "not_asserted",
                     "interpretation": "reviewed_assertions"},
        "untrusted_content": True,
    }


def test_timeline_client_sends_bounded_read_and_validates_page() -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json=timeline_result())

    with BrainReadClient(
        "https://brain.example", "token", transport=httpx.MockTransport(handler)
    ) as client:
        result = client.timeline(
            TIMELINE_START, TIMELINE_START + timedelta(days=1), limit=1,
            recorded_cutoff_at=TIMELINE_START, after="event_" + "0" * 32,
        )
        assert result["results"][0]["object_id"] == TIMELINE_EVENT
        for invalid in (
            {"start": TIMELINE_START.replace(tzinfo=None)},
            {"end": TIMELINE_START},
            {"end": TIMELINE_START + timedelta(days=367)},
            {"limit": True},
            {"limit": 51},
            {"after": TIMELINE_EVENT},
            {"after": "event_bad", "recorded_cutoff_at": TIMELINE_START},
            {"project_id": "project_bad"},
        ):
            arguments = {"start": TIMELINE_START,
                         "end": TIMELINE_START + timedelta(days=1), **invalid}
            with pytest.raises(BrainClientError, match="invalid_request"):
                client.timeline(**arguments)
    assert len(calls) == 1
    assert calls[0].method == "GET" and calls[0].url.path == "/v1/knowledge/timeline"
    assert calls[0].url.params["limit"] == "1"
    assert calls[0].url.params["after"] == "event_" + "0" * 32
    assert calls[0].headers["authorization"] == "Bearer token"


@pytest.mark.parametrize("change", [
    {"untrusted_content": False},
    {"visibility": "retained"},
    {"recorded_cutoff_at": (TIMELINE_START + timedelta(hours=1)).isoformat()},
    {"next_cursor": "event_" + "c" * 32},
    {"coverage": {"undated_events": "included"}},
    {"results": [{**timeline_result()["results"][0], "title": "Private\x00title"}]},
    {"results": [{**timeline_result()["results"][0], "evidence_ids": []}]},
    {"results": [{**timeline_result()["results"][0], "project_id": "project_bad"}]},
    {"results": [{**timeline_result()["results"][0],
                  "starts_at": (TIMELINE_START - timedelta(hours=1)).isoformat()}]},
    {"results": timeline_result()["results"] * 2},
])
def test_timeline_client_rejects_malformed_pages(change: dict) -> None:
    result = {**timeline_result(), **change}
    with BrainReadClient(
        "https://brain.example", "token",
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=result)),
    ) as client:
        with pytest.raises(BrainClientError, match="invalid_response"):
            client.timeline(
                TIMELINE_START, TIMELINE_START + timedelta(days=1), limit=1,
                recorded_cutoff_at=TIMELINE_START,
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
        "coverage": {"complete": False, "source_access": "enrolled_sources_only",
                     "answer_context_truncated": False},
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


def test_answer_client_accepts_bounded_reviewed_member_match() -> None:
    result = answer_result()
    result["reviewed_knowledge"] = [{
        "object_kind": "member", "object_id": DOSSIER_MEMBER,
        "title": "broker", "excerpt": "Pat Example broker",
        "evidence_ids": [TIMELINE_EVIDENCE], "linked_evidence_count": 1,
    }]
    with BrainReadClient(
        "https://brain.example", "synthetic-token",
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=result)),
    ) as client:
        assert client.answer("Who brokers the project?")["reviewed_knowledge"][0][
            "object_kind"
        ] == "member"


@pytest.mark.parametrize("change", [
    {"mode": "freeform"},
    {"coverage": {"complete": True}},
    {"coverage": {"complete": False, "answer_context_truncated": "yes"}},
    {"coverage": {"complete": False, "answer_output_truncated": "yes"}},
    {"citations": [{"evidence_id": "forged"}]},
    {"citations": [{**answer_result()["citations"][0], "quote": "invented"}]},
    {"citations": [{**answer_result()["citations"][0], "quote": "bad\ud800", "end": 4}]},
    {"status": "quoted_evidence", "citations": []},
    {"answer": "x" * 201},
    {"reviewed_knowledge": [{}]},
    {"reviewed_knowledge": [{
        "object_kind": "claim", "object_id": "claim_" + "a" * 32,
        "title": "📄" * 300, "excerpt": "📄" * 1200,
        "evidence_ids": ["evidence_" + "b" * 32], "linked_evidence_count": 1,
    }] * 4},
    {"reviewed_knowledge": [{"object_kind": [], "evidence_ids": [{}]}]},
    {"reviewed_knowledge": [{
        "object_kind": "claim", "object_id": "claim_" + "a" * 32,
        "title": "Private\x00title", "excerpt": "Evidence",
        "evidence_ids": ["evidence_" + "b" * 32],
        "linked_evidence_count": 1,
    }]},
])
def test_answer_client_rejects_malformed_claims(change: dict) -> None:
    result = {**answer_result(), **change}
    with BrainReadClient(
        "https://brain.example", "token",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, content=json.dumps(result).encode())
        ),
    ) as client:
        with pytest.raises(BrainClientError, match="invalid_response"):
            client.answer("fictional question")


def test_explicit_focus_matches_api_and_rejects_widened_responses() -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if request.url.path == "/v1/brain/current-search":
            data = current_result()
            data["coverage"] = {"complete": False, "source_focus": "fileos"}
            return httpx.Response(200, json=data)
        data = answer_result()
        data["coverage"] = {"complete": False, "source_focus": "fileos"}
        return httpx.Response(200, json=data)

    with BrainReadClient(
        "https://brain.example", "token", transport=httpx.MockTransport(handler)
    ) as client:
        assert client.current_search("insurance", source_focus="fileos")["coverage"][
            "source_focus"
        ] == "fileos"
        assert client.answer("insurance", source_focus="fileos")["citations"]
        for invalid in ("files", "", "FileOS"):
            with pytest.raises(BrainClientError, match="invalid_request"):
                client.current_search("insurance", source_focus=invalid)
    assert len(calls) == 2
    assert all(b'"source_focus":"fileos"' in call.content for call in calls)

    widened = current_result()
    widened["coverage"] = {"complete": False, "source_focus": "fileos"}
    widened["layers"]["email_messages"] = [{"evidence_id": "hidden"}]
    with BrainReadClient(
        "https://brain.example", "token",
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=widened)),
    ) as client:
        with pytest.raises(BrainClientError, match="invalid_response"):
            client.current_search("insurance", source_focus="fileos")


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
