"""Known-answer, authorization and source-integrity acceptance for the browser trial."""

import hashlib
import os
import shutil
import subprocess
import sys
from dataclasses import replace

import pytest
import test_postgres as pg
from cross_source_preview import ASSETS, FILES, READ_SCOPES, build_preview, credential
from fastapi.testclient import TestClient

from email_brain.api import create_app
from email_brain.auth import TokenRegistry
from email_brain.store import Store

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


@pytest.mark.postgres
@pytest.mark.parametrize(
    "query,emails,files",
    [("Cedar Harbor", 2, 2), ("insurance", 1, 1), ("appraisal", 1, 1),
     ("Juniper Plaza", 1, 1), ("nonexistentcanary", 0, 0)],
)
def test_known_answers_use_real_current_api(preview, query, emails, files):
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
        assert data["layers"]["knowledge"] == []
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
        assert "2026-09-24" in freshness.text
        assert client.get("/trial").status_code == 200
        assert "script-src 'self'" in client.get("/trial").headers["content-security-policy"]
        assert client.get("/trial", headers={"Host": "attacker.invalid"}).status_code == 400
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
    assert not any(
        scope.endswith(("publish", "ingest", "activate", "review")) for scope in READ_SCOPES
    )
    assert preview.context == replace(preview.context, scopes=READ_SCOPES)


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


def test_browser_javascript_behaviors():
    if not shutil.which("node"):
        if os.environ.get("CI"):
            pytest.fail("CI must run browser-script behavior tests")
        pytest.skip("Node required for browser-script tests")
    subprocess.run(
        ["node", "--test", str(ASSETS.parent / "cross_source_trial.test.cjs")],
        capture_output=True, text=True, timeout=30, check=True,
    )
