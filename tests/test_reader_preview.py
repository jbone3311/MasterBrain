"""Fictional usability fixture checks. Separate from PostgreSQL product proof."""

import hashlib
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from reader_preview import TOKEN, preview_app


@pytest.fixture(scope="module")
def preview():
    return TestClient(preview_app(), headers={"Authorization": f"Bearer {TOKEN}"})


def test_preview_announces_limits_and_serves_assets(preview):
    assert "No real mail or database is connected" in preview.get("/").text
    assert preview.get("/readyz").json() == {"status": "synthetic-preview-only"}
    for asset in ["app.js", "document_review.js", "message_reader.js", "style.css"]:
        response = preview.get("/" + asset)
        assert response.status_code == 200
        assert response.headers["Cache-Control"] == "no-store"
        assert "img-src 'none'" in response.headers["Content-Security-Policy"]
    assert preview.get("/secrets.txt").status_code == 404


@pytest.mark.parametrize("number", range(4))
def test_preview_examples_and_exports_are_consistent(preview, number):
    search = preview.post("/v1/search", json={"query": "Readerproof"}).json()["results"]
    assert len(search) == 4
    path = f"/v1/reader/{search[number]['evidence_id']}"
    message = preview.get(path).json()
    assert message["untrusted_content"] and not message["mailbox_effects"]
    if number < 3:
        assert message["body_complete"] and "FINALTAIL" in message["body"]
    else:
        assert not message["body_complete"] and message["body_source"] == "stored_projection"
    download = preview.post(path + "/original", json={"acknowledge_unscanned": True})
    assert len(download.content) == message["raw_size"]
    assert hashlib.sha256(download.content).hexdigest() == message["raw_sha256"]
    for part in message["attachments"]:
        data = preview.post(
            path + f"/attachments/{part['id']}", json={"acknowledge_unscanned": True}
        )
        assert data.status_code == 200
        assert hashlib.sha256(data.content).hexdigest() == part["sha256"]


def test_preview_denies_unrecognized_access_and_has_no_mailbox_writes(preview):
    assert preview.get("/readyz", headers={"Authorization": "wrong"}).status_code == 401
    path = "/v1/reader/00000000-0000-4000-8000-000000000011"
    assert preview.post(path + "/original", json={}).status_code == 422
    assert preview.get(f"/v1/reader/{uuid4()}").status_code == 404
    assert preview.post("/v1/send", json={}).status_code == 404
