"""Known-answer, authorization and source-integrity acceptance for the browser trial."""

import hashlib
import os
import shutil
import subprocess
import sys
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
import pytest
import test_postgres as pg
from cross_source_preview import ASSETS, FILES, READ_SCOPES, build_preview, credential
from fastapi.testclient import TestClient
from pydantic import ValidationError

from email_brain.api import create_app
from email_brain.auth import Credential, TokenRegistry
from email_brain.store import Store
from masterbrain.answers import QuoteSelection
from masterbrain.brain_client import BrainClientError, BrainReadClient
from masterbrain.datacore.persistence import DataCoreStore
from masterbrain.knowledge import KnowledgeCore
from masterbrain.knowledge_schema import EntityWrite

# Reuse the repository's disposable-database preflight and least-privileged role.
database = pg.database


@pytest.fixture
def preview(database, tmp_path):
    store, admin = database
    return build_preview(store, admin, tmp_path)


def client_for(preview, token=None):
    return TestClient(
        preview.app, base_url="http://127.0.0.1",
        headers={"Authorization": "Bearer " + (token or preview.token)},
    )


def external_transport(app_client: TestClient) -> httpx.MockTransport:
    """Cross the real FastAPI boundary without opening a network listener."""

    def forward(request: httpx.Request) -> httpx.Response:
        response = app_client.request(
            request.method,
            request.url.path + (f"?{request.url.query.decode()}" if request.url.query else ""),
            headers=dict(request.headers),
            content=request.content,
        )
        return httpx.Response(
            response.status_code, headers=dict(response.headers), content=response.content
        )

    return httpx.MockTransport(forward)


def assistant_credential(
    preview, token: str, sources: set[str], scopes: frozenset[str] = READ_SCOPES
) -> Credential:
    return Credential(
        token_sha256=hashlib.sha256(token.encode()).hexdigest(),
        tenant_id=preview.context.tenant_id,
        actor_id=preview.context.actor_id,
        scopes=set(scopes),
        expires_at=datetime.now(UTC) + timedelta(hours=1),
        client_kind="assistant",
        source_ids=sources,
    )


class ExactQuoteSelector:
    def select(self, question, passages):
        assert question == "insurance"
        return [QuoteSelection(passage.evidence_id, passage.content[:30])
                for passage in passages if passage.content][:2]


@pytest.mark.postgres
def test_grounded_answer_client_matches_api_and_respects_source_grants(preview, database):
    store, _ = database
    token = "assistant-answer-fixture-" + "x" * 32
    registry = TokenRegistry([assistant_credential(preview, token, {"trial_files"})])
    app = create_app(store, registry, answer_selector=ExactQuoteSelector())
    with TestClient(app, base_url="http://127.0.0.1") as client:
        headers = {"Authorization": "Bearer " + token}
        direct = client.post("/v1/brain/answers", json={"question": "insurance"},
                             headers=headers)
        assert direct.status_code == 200, direct.text
        body = direct.json()
        assert body["status"] == "quoted_evidence"
        assert body["citations"]
        assert all(item["source_id"] == "trial_files" for item in body["citations"])
        assert all(0 < len(item["quote"]) <= 30 for item in body["citations"])
        assert body["coverage"]["source_access"] == "enrolled_sources_only"
        with BrainReadClient("http://127.0.0.1", token, allow_insecure_loopback=True,
                             transport=external_transport(client)) as external:
            assert external.answer("insurance") == body

    no_content = assistant_credential(preview, token + "-limited", {"trial_files"}).model_copy(
        update={"scopes": set(READ_SCOPES - {"brain.content.read"})}
    )
    limited = create_app(store, TokenRegistry([no_content]),
                         answer_selector=ExactQuoteSelector())
    with TestClient(limited, base_url="http://127.0.0.1") as client:
        denied = client.post("/v1/brain/answers", json={"question": "insurance"},
                             headers={"Authorization": "Bearer " + token + "-limited"})
        assert denied.status_code == 403


def test_assistant_source_enrollment_is_explicit_and_bounded() -> None:
    common = {
        "token_sha256": "a" * 64,
        "tenant_id": uuid4(),
        "actor_id": uuid4(),
        "expires_at": datetime.now(UTC) + timedelta(hours=1),
        "client_kind": "assistant",
        "scopes": {"brain.search"},
    }
    for sources in (None, set(), {"bad/path"}, {f"source_{n}" for n in range(21)}):
        with pytest.raises(ValidationError):
            Credential(**common, source_ids=sources)
    granted = Credential(**common, source_ids={"trial_files"})
    assert granted.source_ids == {"trial_files"}
    with pytest.raises(ValidationError):
        Credential(**{**common, "client_kind": "human"}, source_ids={"trial_files"})
    with pytest.raises(ValidationError):
        Credential(
            **{**common, "scopes": {"brain.search", "email.evidence.read"}},
            source_ids={"trial_files"},
        )
    assert Credential(**{**common, "scopes": {"email.search"}}).source_ids is None


@pytest.mark.postgres
def test_source_scoped_assistant_cannot_read_other_sources_or_alternate_routes(
    preview, database
) -> None:
    store, _ = database
    token = "assistant-source-fixture-token-" + "x" * 32
    registry = TokenRegistry([assistant_credential(preview, token, {"trial_files"})])
    app = create_app(store, registry)
    with client_for(preview) as owner:
        full = owner.post("/v1/brain/current-search", json={"query": "insurance"}).json()
        email_id = full["layers"]["email_messages"][0]["evidence_id"]
        file_id = full["layers"]["fileos"][0]["evidence_id"]
        email_source = full["layers"]["email_messages"][0]["source_id"]
        assert email_source != "trial_files"
        assert len(full["layers"]["email_messages"]) == 1
    with TestClient(app, base_url="http://127.0.0.1") as client:
        headers = {"Authorization": "Bearer " + token}
        response = client.post(
            "/v1/brain/current-search", json={"query": "insurance"}, headers=headers
        )
        assert response.status_code == 200
        scoped = response.json()
        assert scoped["coverage"]["source_access"] == "enrolled_sources_only"
        assert len(scoped["layers"]["fileos"]) == 1
        assert scoped["layers"]["email_messages"] == []
        assert email_source not in response.text
        assert client.get(f"/v1/brain/evidence/{file_id}", headers=headers).status_code == 200
        assert client.post(
            f"/v1/brain/evidence/{file_id}/content", json={"max_chars": 100},
            headers=headers,
        ).status_code == 200
        for path, body in (
            (f"/v1/brain/evidence/{email_id}", None),
            (f"/v1/brain/evidence/{email_id}/content", {"max_chars": 100}),
        ):
            denied = (
                client.get(path, headers=headers) if body is None
                else client.post(path, json=body, headers=headers)
            )
            assert denied.status_code == 404
            assert email_source not in denied.text
        coverage = client.get("/v1/brain/current-coverage?limit=1", headers=headers)
        assert coverage.status_code == 200
        assert [row["source_id"] for row in coverage.json()["results"]] == ["trial_files"]
        assert coverage.json()["next_cursor"] is None
        assert client.get(
            f"/v1/brain/current-coverage?after={email_source}", headers=headers
        ).status_code == 404
        changes = client.get("/v1/brain/changes?limit=1", headers=headers)
        assert changes.status_code == 200
        assert changes.json()["results"]
        assert all(row["source_id"] == "trial_files" for row in changes.json()["results"])
        with client_for(preview) as owner:
            foreign_change = next(
                row["id"] for row in owner.get("/v1/brain/changes?limit=50").json()["results"]
                if row["source_id"] == email_source
            )
        assert client.get(
            f"/v1/brain/changes?after={foreign_change}", headers=headers
        ).status_code == 404
        for path in ("/v1/knowledge/changes",):
            assert client.get(path, headers=headers).status_code == 403
        for path in ("/v1/brain/unified-search", "/v1/knowledge/search"):
            permitted = client.post(path, json={"query": "insurance"}, headers=headers)
            assert permitted.status_code == 200, permitted.text
        for path in ("/v1/brain/search", "/v1/brain/fileos-search"):
            scoped_read = client.post(
                path, json={"query": "insurance", "limit": 1}, headers=headers
            )
            assert scoped_read.status_code == 200, scoped_read.text
            assert scoped_read.json()["results"]
            assert all(
                row["source_id"] == "trial_files"
                for row in scoped_read.json()["results"]
            )
            assert email_source not in scoped_read.text
        other_tenant = client.post(
            "/v1/brain/search", json={"query": "other-tenant-canary"},
            headers=headers,
        )
        assert other_tenant.status_code == 200
        assert other_tenant.json()["results"] == []
        for path in ("/v1/brain/email-search", "/v1/brain/email-family-search"):
            scoped_read = client.post(path, json={"query": "insurance"}, headers=headers)
            assert scoped_read.status_code == 200, scoped_read.text
            assert email_source not in scoped_read.text
            assert not any(scoped_read.json().get("results", []))
            assert not any(scoped_read.json().get("layers", {}).values())
        for suffix in ("freshness", "inventory", "rebuild-preview", "index"):
            visible = client.get(
                f"/v1/brain/sources/trial_files/{suffix}", headers=headers
            )
            assert visible.status_code == 200, visible.text
        active = client.post(
            "/v1/brain/sources/trial_files/search",
            json={"query": "insurance"}, headers=headers,
        )
        assert active.status_code == 200
        assert active.json()["results"]
        with BrainReadClient(
            "http://127.0.0.1", token, allow_insecure_loopback=True,
            transport=external_transport(client),
        ) as external:
            assert external.current_search("insurance")["layers"]["email_messages"] == []
            assert external.evidence(file_id)["id"] == file_id
            assert [
                row["source_id"] for row in external.current_coverage(limit=1)["results"]
            ] == ["trial_files"]
            assert all(
                row["source_id"] == "trial_files"
                for row in external.changes(limit=50)["results"]
            )
            with pytest.raises(BrainClientError, match="not_found"):
                external.evidence(email_id)

    dual_token = "assistant-dual-source-fixture-" + "z" * 32
    unknown_token = "assistant-unknown-source-fixture-" + "q" * 32
    email_token = "assistant-email-source-fixture-" + "e" * 32
    rotated = create_app(store, TokenRegistry([
        assistant_credential(preview, dual_token, {"trial_files", email_source}),
        assistant_credential(preview, unknown_token, {"not_enrolled_here"}),
        assistant_credential(preview, email_token, {email_source}),
    ]))
    with TestClient(rotated, base_url="http://127.0.0.1") as client:
        dual = client.post(
            "/v1/brain/current-search", json={"query": "insurance"},
            headers={"Authorization": "Bearer " + dual_token},
        )
        assert dual.status_code == 200
        assert dual.json()["layers"] == full["layers"]
        unknown_headers = {"Authorization": "Bearer " + unknown_token}
        unknown = client.post(
            "/v1/brain/current-search", json={"query": "insurance"},
            headers=unknown_headers,
        )
        assert unknown.status_code == 200
        assert all(not hits for hits in unknown.json()["layers"].values())
        assert client.get(
            f"/v1/brain/evidence/{file_id}", headers=unknown_headers
        ).status_code == 404
        for token in (unknown_token, email_token):
            hidden_headers = {"Authorization": "Bearer " + token}
            for suffix in ("freshness", "inventory", "rebuild-preview", "index"):
                assert client.get(
                    f"/v1/brain/sources/trial_files/{suffix}",
                    headers=hidden_headers,
                ).status_code == 404
            assert client.post(
                "/v1/brain/sources/trial_files/search",
                json={"query": "insurance"}, headers=hidden_headers,
            ).status_code == 404
        email_read = client.post(
            "/v1/brain/search", json={"query": "insurance", "limit": 1},
            headers={"Authorization": "Bearer " + email_token},
        )
        assert email_read.status_code == 200
        assert email_read.json()["results"]
        assert all(row["source_id"] == email_source for row in email_read.json()["results"])


@pytest.mark.postgres
def test_source_scoped_knowledge_excludes_mixed_evidence_before_limit(
    preview, database
) -> None:
    store, _ = database
    with client_for(preview) as owner:
        results = owner.post("/v1/brain/current-search", json={"query": "insurance"}).json()
        email_id = results["layers"]["email_messages"][0]["evidence_id"]
        file_id = results["layers"]["fileos"][0]["evidence_id"]
    reviewer = replace(
        preview.context, scopes=preview.context.scopes | frozenset({"knowledge.review"})
    )
    knowledge = KnowledgeCore(store)
    common = {
        "kind": "entity", "entity_type": "artifact",
        "source_quote": "Fictional insurance evidence.", "confidence": 0.9,
        "observed_at": datetime(2026, 9, 24, tzinfo=UTC), "reviewed": True,
    }
    mixed = knowledge.publish(
        reviewer,
        EntityWrite(
            **common, name="insurance insurance insurance insurance",
            evidence_ids=[file_id, email_id],
        ),
        uuid4(),
    )
    file_only = knowledge.publish(
        reviewer,
        EntityWrite(**common, name="insurance", evidence_ids=[file_id]),
        uuid4(),
    )
    email_only = knowledge.publish(
        reviewer,
        EntityWrite(**common, name="insurance email", evidence_ids=[email_id]),
        uuid4(),
    )
    knowledge_only = knowledge.publish(
        reviewer,
        EntityWrite(**common, name="orchidplan", evidence_ids=[file_id]),
        uuid4(),
    )
    other_evidence = DataCoreStore(store).search(
        preview.other_context, "other-tenant-canary", limit=1
    )[0].evidence_id
    other_reviewer = replace(
        preview.other_context,
        scopes=preview.other_context.scopes | frozenset({"knowledge.review"}),
    )
    other_tenant = knowledge.publish(
        other_reviewer,
        EntityWrite(**common, name="insurance outsider", evidence_ids=[other_evidence]),
        uuid4(),
    )
    owner_hits = knowledge.search(preview.context, "insurance", limit=3)
    assert {hit.object_id for hit in owner_hits} == {
        mixed.object_id, file_only.object_id, email_only.object_id
    }
    with client_for(preview) as owner:
        answer = owner.post("/v1/brain/answers", json={"question": "insurance"})
        assert answer.status_code == 200, answer.text
        assert {item["object_id"] for item in answer.json()["reviewed_knowledge"]} == {
            mixed.object_id, file_only.object_id, email_only.object_id
        }
        assert answer.json()["citations"]
        knowledge_answer = owner.post(
            "/v1/brain/answers", json={"question": "orchidplan"}
        )
        assert knowledge_answer.status_code == 200
        assert knowledge_answer.json()["status"] == "no_supported_answer"
        assert knowledge_answer.json()["citations"] == []
        assert [hit["object_id"] for hit in knowledge_answer.json()["reviewed_knowledge"]] == [
            knowledge_only.object_id
        ]
    assert all("insurance" in hit.excerpt.casefold() for hit in owner_hits)
    assert all("<b>" not in hit.excerpt for hit in owner_hits)
    restricted = replace(preview.context, source_ids=frozenset({"trial_files"}))
    scoped_hits = knowledge.search(restricted, "insurance", limit=1)
    assert [hit.object_id for hit in scoped_hits] == [file_only.object_id]
    token = "assistant-knowledge-fixture-token-" + "y" * 32
    knowledge_scopes = READ_SCOPES | frozenset({"knowledge.read", "knowledge.changes.read"})
    app = create_app(store, TokenRegistry([
        assistant_credential(preview, token, {"trial_files"}, knowledge_scopes)
    ]))
    with TestClient(app, base_url="http://127.0.0.1") as client:
        headers = {"Authorization": "Bearer " + token}
        response = client.post(
            "/v1/brain/current-search", json={"query": "insurance", "knowledge_limit": 1},
            headers=headers,
        )
        assert response.status_code == 200
        assert [hit["object_id"] for hit in response.json()["layers"]["knowledge"]] == [
            file_only.object_id
        ]
        assert mixed.object_id not in response.text
        answer = client.post(
            "/v1/brain/answers", json={"question": "insurance"}, headers=headers,
        )
        assert answer.status_code == 200, answer.text
        assert [hit["object_id"] for hit in answer.json()["reviewed_knowledge"]] == [
            file_only.object_id
        ]
        assert all(hit["source_id"] == "trial_files" for hit in answer.json()["citations"])
        with BrainReadClient(
            "http://127.0.0.1", token, allow_insecure_loopback=True,
            transport=external_transport(client),
        ) as external:
            assert external.answer("insurance") == answer.json()
        assert mixed.object_id not in answer.text
        assert email_only.object_id not in answer.text
        direct = client.post(
            "/v1/knowledge/search", json={"query": "insurance", "limit": 1},
            headers=headers,
        )
        assert direct.status_code == 200, direct.text
        assert [hit["object_id"] for hit in direct.json()["results"]] == [
            file_only.object_id
        ]
        for visibility in ("retained", "current_fileos"):
            unified = client.post(
                "/v1/brain/unified-search",
                json={"query": "insurance", "knowledge_limit": 1,
                      "evidence_limit": 1, "evidence_visibility": visibility},
                headers=headers,
            )
            assert unified.status_code == 200, unified.text
            assert [hit["object_id"] for hit in unified.json()["layers"]["knowledge"]] == [
                file_only.object_id
            ]
            assert all(
                hit["source_id"] == "trial_files"
                for hit in unified.json()["layers"]["evidence"]
            )
        visible = client.get(f"/v1/knowledge/entity/{file_only.object_id}", headers=headers)
        assert visible.status_code == 200
        assert [item["evidence_id"] for item in visible.json()["evidence"]] == [file_id]
        for hidden_id in (mixed.object_id, email_only.object_id, other_tenant.object_id):
            assert client.get(
                f"/v1/knowledge/entity/{hidden_id}", headers=headers
            ).status_code == 404
        feed = client.get("/v1/knowledge/changes?limit=2", headers=headers)
        assert feed.status_code == 200, feed.text
        assert {item["object_id"] for item in feed.json()["results"]} == {
            file_only.object_id, knowledge_only.object_id
        }
        assert feed.json()["next_cursor"] is None
        owner_changes = knowledge.changes(
            replace(
                preview.context,
                scopes=preview.context.scopes | frozenset({"knowledge.changes.read"}),
            ),
            limit=50,
        )["results"]
        hidden_cursor = next(
            item["id"] for item in owner_changes if item["object_id"] == mixed.object_id
        )
        assert client.get(
            f"/v1/knowledge/changes?after={hidden_cursor}", headers=headers
        ).status_code == 404
        assert client.get(
            "/v1/knowledge/changes?after=kchange_" + "0" * 32, headers=headers
        ).status_code == 404

    dual_token = "assistant-knowledge-dual-fixture-" + "d" * 32
    email_source = results["layers"]["email_messages"][0]["source_id"]
    dual_app = create_app(store, TokenRegistry([
        assistant_credential(
            preview, dual_token, {"trial_files", email_source},
            knowledge_scopes,
        )
    ]))
    with TestClient(dual_app, base_url="http://127.0.0.1") as client:
        both = client.get(
            f"/v1/knowledge/entity/{mixed.object_id}",
            headers={"Authorization": "Bearer " + dual_token},
        )
        assert both.status_code == 200
        dual_answer = client.post(
            "/v1/brain/answers", json={"question": "insurance"},
            headers={"Authorization": "Bearer " + dual_token},
        )
        assert dual_answer.status_code == 200
        assert {hit["object_id"] for hit in dual_answer.json()["reviewed_knowledge"]} == {
            mixed.object_id, file_only.object_id, email_only.object_id
        }


@pytest.mark.postgres
def test_external_read_client_matches_first_party_api_on_known_answers(preview):
    with client_for(preview) as direct:
        transport = external_transport(direct)
        with BrainReadClient(
            "http://127.0.0.1", preview.token,
            allow_insecure_loopback=True, transport=transport,
        ) as external:
            for query in (
                "Cedar Harbor", "insurance", "Juniper Plaza", "readiness", "nonexistentcanary"
            ):
                expected = direct.post("/v1/brain/current-search", json={"query": query}).json()
                assert external.current_search(query) == expected
            hit = external.current_search("insurance")["layers"]["fileos"][0]
            evidence_id = hit["evidence_id"]
            assert external.evidence(evidence_id) == direct.get(
                f"/v1/brain/evidence/{evidence_id}"
            ).json()
            assert external.evidence_content(evidence_id) == direct.post(
                f"/v1/brain/evidence/{evidence_id}/content", json={"max_chars": 4000}
            ).json()
            knowledge_answer = direct.post(
                "/v1/brain/answers", json={"question": "readiness"}
            )
            assert knowledge_answer.status_code == 200
            assert knowledge_answer.json()["status"] == "no_supported_answer"
            assert knowledge_answer.json()["citations"] == []
            assert len(knowledge_answer.json()["reviewed_knowledge"]) == 1
            assert external.answer("readiness") == knowledge_answer.json()
        with BrainReadClient(
            "http://127.0.0.1", preview.other_token,
            allow_insecure_loopback=True, transport=transport,
        ) as other:
            assert other.current_search("insurance")["layers"]["fileos"] == []
            with pytest.raises(BrainClientError, match="not_found"):
                other.evidence(evidence_id)


@pytest.mark.postgres
def test_default_local_answer_quotes_both_sources_and_client_matches(preview):
    with client_for(preview) as direct:
        response = direct.post("/v1/brain/answers", json={"question": "insurance"})
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["status"] == "quoted_evidence"
        assert {item["source_kind"] for item in body["citations"]} == {
            "email", "fileos"
        }
        for citation in body["citations"]:
            content = direct.post(
                f"/v1/brain/evidence/{citation['evidence_id']}/content",
                json={"max_chars": 1200},
            ).json()
            assert content["content"][citation["start"]:citation["end"]] == citation["quote"]
            assert "insurance" in citation["quote"].casefold()
        with BrainReadClient(
            "http://127.0.0.1", preview.token,
            allow_insecure_loopback=True, transport=external_transport(direct),
        ) as external:
            assert external.answer("insurance") == body
        empty = direct.post("/v1/brain/answers", json={"question": "nonexistentcanary"})
        assert empty.status_code == 200
        assert empty.json()["status"] == "no_supported_evidence"
        assert empty.json()["citations"] == []
        question = "Find the insurance certificate for Cedar Harbor"
        literal = direct.post("/v1/brain/current-search", json={"query": question})
        assert literal.status_code == 200
        assert literal.json()["layers"]["email_messages"] == []
        assert literal.json()["layers"]["fileos"] == []
        natural = direct.post("/v1/brain/answers", json={"question": question})
        assert natural.status_code == 200
        assert natural.json()["status"] == "quoted_evidence"
        assert {item["source_kind"] for item in natural.json()["citations"]} == {
            "email", "fileos"
        }
        with BrainReadClient(
            "http://127.0.0.1", preview.token,
            allow_insecure_loopback=True, transport=external_transport(direct),
        ) as external:
            assert external.answer(question) == natural.json()


@pytest.mark.postgres
def test_explicit_source_focus_has_api_client_and_assistant_parity(preview, database):
    with client_for(preview) as direct:
        with BrainReadClient(
            "http://127.0.0.1", preview.token,
            allow_insecure_loopback=True, transport=external_transport(direct),
        ) as external:
            for focus, expected_kind in (("email", "email"), ("fileos", "fileos")):
                request = {"query": "insurance", "source_focus": focus}
                search = direct.post("/v1/brain/current-search", json=request)
                assert search.status_code == 200, search.text
                assert external.current_search("insurance", source_focus=focus) == search.json()
                layers = search.json()["layers"]
                assert search.json()["coverage"]["source_focus"] == focus
                assert search.json()["coverage"]["knowledge"] == "not_searched"
                excluded = "email" if focus == "fileos" else "fileos"
                assert search.json()["coverage"][excluded] == "not_searched"
                assert layers["knowledge"] == []
                assert bool(layers["email_messages"]) == (focus == "email")
                assert bool(layers["fileos"]) == (focus == "fileos")
                answer = direct.post(
                    "/v1/brain/answers",
                    json={"question": "insurance", "source_focus": focus},
                )
                assert answer.status_code == 200, answer.text
                assert answer.json()["status"] == "quoted_evidence"
                assert answer.json()["coverage"]["answer_context_truncated"] is False
                assert answer.json()["reviewed_knowledge"] == []
                assert {hit["source_kind"] for hit in answer.json()["citations"]} == {
                    expected_kind
                }
                assert external.answer("insurance", source_focus=focus) == answer.json()

    store, _ = database
    token = "assistant-focused-trial-" + "f" * 32
    app = create_app(store, TokenRegistry([
        assistant_credential(preview, token, {"trial_files"})
    ]))
    headers = {"Authorization": "Bearer " + token}
    with TestClient(app, base_url="http://127.0.0.1") as scoped:
        hidden = scoped.post(
            "/v1/brain/answers",
            json={"question": "insurance", "source_focus": "email"},
            headers=headers,
        )
        assert hidden.status_code == 200, hidden.text
        assert hidden.json()["status"] == "no_supported_evidence"
        assert hidden.json()["citations"] == []
        visible = scoped.post(
            "/v1/brain/answers",
            json={"question": "insurance", "source_focus": "fileos"},
            headers=headers,
        )
        assert visible.status_code == 200, visible.text
        assert {hit["source_kind"] for hit in visible.json()["citations"]} == {"fileos"}
        assert "email" not in visible.text


@pytest.mark.postgres
def test_ask_preserves_unresolved_cross_source_date_conflict(preview, database):
    question = "When is Maple Arcade closing?"
    with client_for(preview) as direct:
        response = direct.post("/v1/brain/answers", json={"question": question})
        assert response.status_code == 200, response.text
        answer = response.json()
        assert answer["status"] == "quoted_evidence"
        assert answer["coverage"]["complete"] is False
        assert answer["reviewed_knowledge"] == []
        assert {item["source_kind"] for item in answer["citations"]} == {"email", "fileos"}
        quotes = {item["source_kind"]: item["quote"] for item in answer["citations"]}
        assert "November 12, 2026" in quotes["fileos"]
        assert "November 19, 2026" in quotes["email"]
        assert "November" not in answer["answer"]
        for citation in answer["citations"]:
            content = direct.post(
                f"/v1/brain/evidence/{citation['evidence_id']}/content",
                json={"max_chars": 1200},
            )
            assert content.status_code == 200
            assert content.json()["content"][citation["start"]:citation["end"]] == (
                citation["quote"]
            )
        with BrainReadClient(
            "http://127.0.0.1", preview.token,
            allow_insecure_loopback=True, transport=external_transport(direct),
        ) as external:
            assert external.answer(question) == answer

    store, _ = database
    token = "assistant-maple-conflict-fixture-" + "m" * 32
    scoped_app = create_app(store, TokenRegistry([
        assistant_credential(preview, token, {"trial_files"})
    ]))
    with TestClient(scoped_app, base_url="http://127.0.0.1") as scoped:
        limited = scoped.post(
            "/v1/brain/answers", json={"question": question},
            headers={"Authorization": "Bearer " + token},
        )
        assert limited.status_code == 200, limited.text
        assert limited.json()["coverage"]["source_access"] == "enrolled_sources_only"
        assert [item["source_kind"] for item in limited.json()["citations"]] == ["fileos"]
        assert "November 12, 2026" in limited.json()["citations"][0]["quote"]
        assert "November 19, 2026" not in limited.text


@pytest.mark.postgres
@pytest.mark.parametrize(
    "query,emails,files,reviewed",
    [("Cedar Harbor", 2, 2, 0), ("insurance", 1, 1, 0),
     ("appraisal", 1, 1, 0), ("Juniper Plaza", 1, 1, 0),
     ("Maple Arcade", 1, 1, 0),
     ("readiness", 0, 0, 1), ("nonexistentcanary", 0, 0, 0)],
)
def test_known_answers_use_real_current_api(preview, query, emails, files, reviewed):
    with client_for(preview) as client:
        result = client.post("/v1/brain/current-search", json={"query": query})
        assert result.status_code == 200
        data = result.json()
        assert data["mode"] == "grouped_current_sources"
        assert data["ranking"] == "within_group_only"
        assert data["consistency"] == "independent_layer_reads"
        assert data["coverage"]["complete"] is False
        assert len(data["layers"]["email_messages"]) == emails
        assert len(data["layers"]["fileos"]) == files
        for layer in ("email_messages", "fileos"):
            for hit in data["layers"][layer]:
                assert "<b>" not in hit["excerpt"]
                assert "</b>" not in hit["excerpt"]
                assert query.split()[0].casefold() in hit["excerpt"].casefold()
        assert len(data["layers"]["knowledge"]) == reviewed
        assert "other-tenant-canary" not in result.text


@pytest.mark.postgres
def test_citations_content_coverage_and_no_source_mutation(preview, tmp_path):
    with client_for(preview) as client:
        data = client.post("/v1/brain/current-search", json={"query": "insurance"}).json()
        for layer in ("email_messages", "fileos"):
            hit = data["layers"][layer][0]
            path = "/v1/brain/evidence/" + hit["evidence_id"]
            metadata = client.get(path)
            assert metadata.status_code == 200
            assert hit["evidence_id"] in metadata.text
            content = client.post(path + "/content", json={"max_chars": 4000})
            assert content.status_code == 200
            assert "insurance" in content.text.lower()
            assert "outstanding" in content.text.lower()
            assert client.post(path + "/content", json={"max_chars": 16001}).status_code == 422
        coverage = client.get("/v1/brain/current-coverage")
        assert coverage.status_code == 200
        assert "trial_files" in coverage.text
        freshness = client.get("/v1/brain/sources/trial_files/freshness")
        assert freshness.status_code == 200
        assert "no_completed_run" not in freshness.text
        observed_at = freshness.json()["latest_complete_run"]["observed_at"]
        assert datetime.fromisoformat(observed_at) == datetime(2026, 9, 24, tzinfo=UTC)
        assert client.get("/trial").status_code == 200
        assert "script-src 'self'" in client.get("/trial").headers["content-security-policy"]
        assert client.get("/trial", headers={"Host": "attacker.invalid"}).status_code == 400
        workspace = client.get("/brain")
        assert workspace.status_code == 200
        assert 'src="/brain.js"' in workspace.text
        assert "script-src 'self'" in workspace.headers["content-security-policy"]
        assert client.get("/brain", headers={"Host": "attacker.invalid"}).status_code == 400
    for name, digest in preview.file_hashes.items():
        assert hashlib.sha256((tmp_path / "owner" / name).read_bytes()).hexdigest() == digest
    assert set(path.name for path in (tmp_path / "owner").iterdir()) == set(FILES)


@pytest.mark.postgres
def test_two_nonempty_tenants_cannot_read_each_others_evidence(preview):
    with client_for(preview) as owner, client_for(preview, preview.other_token) as other:
        original = owner.post("/v1/brain/current-search", json={"query": "Cedar Harbor"}).json()
        foreign = other.post("/v1/brain/current-search", json={"query": "other-tenant-canary"})
        assert foreign.status_code == 200
        foreign_hits = foreign.json()["layers"]["fileos"]
        assert len(foreign_hits) == 1
        assert owner.post("/v1/brain/current-search", json={"query": "other-tenant-canary"}).json()[
            "layers"
        ]["fileos"] == []
        for reader, evidence_id in (
            (owner, foreign_hits[0]["evidence_id"]),
            (other, original["layers"]["fileos"][0]["evidence_id"]),
            (other, original["layers"]["email_messages"][0]["evidence_id"]),
        ):
            path = "/v1/brain/evidence/" + evidence_id
            assert reader.get(path).status_code == 404
            assert reader.post(path + "/content", json={"max_chars": 100}).status_code == 404
        assert other.post("/v1/brain/current-search", json={"query": "Juniper Plaza"}).json()[
            "layers"
        ]["email_messages"] == []


@pytest.mark.postgres
def test_read_only_credential_no_unauthorized_content_or_review(preview, database):
    store, _ = database
    search_only = frozenset({"brain.search", "knowledge.search"})
    registry = TokenRegistry([credential(preview.context, preview.token, search_only)])
    app = create_app(store, registry)
    with TestClient(app) as client:
        assert client.post("/v1/brain/current-search", json={"query": "Cedar"}).status_code == 401
        headers = {"Authorization": "Bearer " + preview.token}
        data = client.post(
            "/v1/brain/current-search", json={"query": "Cedar"}, headers=headers
        ).json()
        evidence_id = data["layers"]["fileos"][0]["evidence_id"]
        path = "/v1/brain/evidence/" + evidence_id
        assert client.get(path, headers=headers).status_code == 403
        response = client.post(path + "/content", json={"max_chars": 100}, headers=headers)
        assert response.status_code == 403
        assert client.get("/v1/brain/current-coverage", headers=headers).status_code == 403
        with BrainReadClient(
            "http://127.0.0.1", preview.token,
            allow_insecure_loopback=True, transport=external_transport(client),
        ) as external:
            assert external.current_search("Cedar")["layers"]["fileos"]
            with pytest.raises(BrainClientError, match="access_denied"):
                external.evidence(evidence_id)
            with pytest.raises(BrainClientError, match="access_denied"):
                external.evidence_content(evidence_id)
    assert not any(
        scope.endswith(("publish", "ingest", "activate", "review")) for scope in READ_SCOPES
    )
    assert preview.context == replace(preview.context, scopes=READ_SCOPES)


def test_trial_cleanup_recovers_after_docker_run_loses_its_id(monkeypatch):
    import cross_source_preview as trial

    calls = []

    def fake_docker(*args, env=None):
        calls.append(args)
        if args[0] == "inspect":
            assert args[-1] == "masterbrain-trial-fixture"
            return "expected-marker verified-container-id"
        return ""

    monkeypatch.setattr(trial, "docker", fake_docker)
    trial.cleanup_trial_container("masterbrain-trial-fixture", "expected-marker")
    assert calls[-1] == ("rm", "--force", "verified-container-id")


def test_trial_cleanup_refuses_a_container_with_wrong_marker(monkeypatch, capsys):
    import cross_source_preview as trial

    calls = []

    def fake_docker(*args, env=None):
        calls.append(args)
        return "someone-elses-marker other-container-id"

    monkeypatch.setattr(trial, "docker", fake_docker)
    trial.cleanup_trial_container("masterbrain-trial-fixture", "expected-marker")
    assert [args[0] for args in calls] == ["inspect"]
    assert "Check Docker Desktop for temporary trial container" in capsys.readouterr().err


def test_trial_cleanup_warns_when_docker_cannot_inspect(monkeypatch, capsys):
    import cross_source_preview as trial

    def unavailable(*args, env=None):
        raise subprocess.TimeoutExpired(["docker", *args], 180)

    monkeypatch.setattr(trial, "docker", unavailable)
    trial.cleanup_trial_container("masterbrain-trial-fixture", "expected-marker")
    assert "Check Docker Desktop for temporary trial container" in capsys.readouterr().err


def test_browser_assets_do_not_embed_credentials_or_execute_source_text():
    script = (ASSETS / "trial.js").read_text()
    assert "innerHTML" not in script
    assert "textContent" in script
    assert "localStorage" not in script and "sessionStorage" not in script
    assert "history.replaceState" in script
    assert 'credentials: "omit"' in script
    assert 'redirect: "error"' in script
    html = (ASSETS / "index.html").read_text()
    assert 'src="/trial.js"' in html
    assert "FICTIONAL DATA" in html
    assert "other-tenant-canary" not in html


@pytest.mark.parametrize("dsn", [
    "postgresql://u:p@127.0.0.1/personal",
    "postgresql://u:p@remote.invalid/email_brain_test_bad",
])
def test_preview_refuses_non_test_or_remote_database_before_any_write(dsn, tmp_path):
    with pytest.raises(ValueError, match="disposable loopback"):
        build_preview(Store(dsn), dsn, tmp_path)


@pytest.mark.postgres
def test_actual_disposable_docker_launcher():
    if not shutil.which("docker"):
        if os.environ.get("CI"):
            pytest.fail("CI must run the actual Docker-backed trial startup")
        pytest.skip("Docker required for the disposable launcher smoke test")
    result = subprocess.run(
        [sys.executable, str(ASSETS.parent / "cross_source_preview.py"),
         "--synthetic-preview", "--self-test"],
        capture_output=True, text=True, timeout=240, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Synthetic browser-trial self-test passed" in result.stdout


def test_actual_disposable_local_launcher():
    import cross_source_preview as trial

    if trial.local_postgres_binaries() is None:
        pytest.skip("Local PostgreSQL 17 binaries unavailable")
    result = subprocess.run(
        [sys.executable, str(ASSETS.parent / "cross_source_preview.py"),
         "--synthetic-preview", "--backend", "local", "--self-test"],
        capture_output=True, text=True, timeout=240, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Synthetic browser-trial self-test passed" in result.stdout
    assert "Check temporary synthetic PostgreSQL cluster" not in result.stderr


def test_mac_trial_command_selects_patched_python_and_forwards_test_options():
    command = ASSETS.parents[1] / "Start-MasterBrain-Trial.command"
    script = command.read_text(encoding="utf-8")
    assert "--python '>=3.13,<3.15'" in script
    assert "uv sync --locked --extra dev --python '>=3.13,<3.15' --no-editable" in script
    assert (
        'uv run --no-sync python tests/cross_source_preview.py --synthetic-preview "$@"'
        in script
    )
    assert 'cross_source_preview.py --synthetic-preview "$@"' in script
    subprocess.run(["bash", "-n", str(command)], check=True, timeout=10)


def test_local_backend_refuses_wrong_postgres_version(monkeypatch, tmp_path):
    import cross_source_preview as trial

    initdb = tmp_path / "initdb"
    pg_ctl = tmp_path / "pg_ctl"
    initdb.touch(mode=0o700)
    pg_ctl.touch(mode=0o700)
    monkeypatch.setattr(trial.shutil, "which", lambda name: str(initdb))
    monkeypatch.setattr(
        trial.subprocess, "check_output", lambda *a, **kw: "initdb (PostgreSQL) 16.1"
    )
    assert trial.local_postgres_binaries() is None


def test_browser_javascript_behaviors():
    if not shutil.which("node"):
        if os.environ.get("CI"):
            pytest.fail("CI must run browser-script behavior tests")
        pytest.skip("Node required for browser-script tests")
    subprocess.run(
        ["node", "--test", str(ASSETS.parent / "cross_source_trial.test.cjs")],
        capture_output=True, text=True, timeout=30, check=True,
    )
