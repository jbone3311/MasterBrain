"""The API delegates approval, never Docker access or raw evidence bytes."""

from dataclasses import replace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
import test_postgres as pg
from fastapi.testclient import TestClient
from test_isolated_recovery import VERSION, FakeProcessor, make_held
from test_service import TOKEN, registry

from email_brain.api import create_app
from email_brain.auth import Principal
from email_brain.recovery_jobs import RecoveryJobs
from email_brain.store import Store

database, tenant = pg.database, pg.tenant
HEADERS = {"Authorization": f"Bearer {TOKEN}"}


@pytest.mark.parametrize("kind", ["human", "assistant"])
def test_processing_scope_is_worker_only(kind):
    with pytest.raises(ValueError, match="worker-only"):
        registry({"email.process"}, kind)
    assert registry({"email.process"}, "worker").authenticate(TOKEN).client_kind == "worker"


def test_disabled_processing_is_default_and_api_has_no_execution_routes():
    store = MagicMock(spec=Store)
    client = TestClient(create_app(store, registry({"email.review", "email.evidence.read"})))
    account, receipt = uuid4(), uuid4()
    conn = store.transaction.return_value.__enter__.return_value
    conn.execute.return_value.fetchone.return_value = {"id": account, "status": "active"}
    # Explicitly disable even when an arbitrary version is echoed by the caller.
    response = client.post(
        f"/v1/accounts/{account}/quarantine/{receipt}/jobs",
        json={"expected_parser_version": VERSION},
        headers={**HEADERS, "Idempotency-Key": str(uuid4())},
    )
    assert response.status_code == 409
    for suffix in ("execute", "claim", "image", "raw", "keys"):
        assert client.post(f"/v1/processing/{suffix}", headers=HEADERS).status_code == 404


@pytest.mark.parametrize(
    "scope,kind,status",
    [
        ({"email.evidence.read"}, "assistant", 403),
        ({"email.evidence.read"}, "worker", 403),
        ({"email.evidence.read"}, "human", 403),
        ({"email.review"}, "human", 403),
    ],
)
def test_job_authorization_requires_human_review_and_evidence(scope, kind, status):
    store = MagicMock(spec=Store)
    store.require = Store.require
    client = TestClient(create_app(store, registry(scope, kind), recovery_parser_version=VERSION))
    path = f"/v1/accounts/{uuid4()}/quarantine/{uuid4()}/jobs"
    response = client.post(
        path,
        json={"expected_parser_version": VERSION},
        headers={**HEADERS, "Idempotency-Key": str(uuid4())},
    )
    assert response.status_code == status
    store.transaction.assert_not_called()


@pytest.mark.parametrize("extra", ["tenant_id", "actor_id", "image_id", "socket", "raw"])
def test_job_request_rejects_authority_and_execution_configuration(extra):
    store = MagicMock(spec=Store)
    client = TestClient(
        create_app(
            store,
            registry({"email.review", "email.evidence.read"}),
            recovery_parser_version=VERSION,
        )
    )
    response = client.post(
        f"/v1/accounts/{uuid4()}/quarantine/{uuid4()}/jobs",
        json={"expected_parser_version": VERSION, extra: "private-input-must-not-echo"},
        headers={**HEADERS, "Idempotency-Key": str(uuid4())},
    )
    assert response.status_code == 422
    assert "private-input" not in response.text
    store.transaction.assert_not_called()


def test_job_uuid_idempotency_required_and_bad_config_refused():
    store = MagicMock(spec=Store)
    creds = registry({"email.review", "email.evidence.read"})
    client = TestClient(create_app(store, creds, recovery_parser_version=VERSION))
    for key in (None, "not-a-uuid"):
        headers = HEADERS if key is None else {**HEADERS, "Idempotency-Key": key}
        assert (
            client.post(
                f"/v1/accounts/{uuid4()}/quarantine/{uuid4()}/jobs",
                json={"expected_parser_version": VERSION},
                headers=headers,
            ).status_code
            == 422
        )
    for version in ("latest", "sha256:" + "a" * 64, "sandbox-mime-v1-" + "A" * 64):
        with pytest.raises(ValueError):
            create_app(store, creds, recovery_parser_version=version)


@pytest.mark.postgres
def test_api_approval_worker_completion_and_status(database, tenant, monkeypatch):
    store, _ = database
    ctx, account = tenant
    receipt = make_held(store, ctx, account, monkeypatch)
    creds = registry({"email.review", "email.evidence.read", "email.search"})
    creds.credentials[0].tenant_id = ctx.tenant_id
    creds.credentials[0].actor_id = ctx.actor_id
    client = TestClient(create_app(store, creds, recovery_parser_version=VERSION))
    caps = client.get(f"/v1/accounts/{account}/processing", headers=HEADERS)
    assert caps.status_code == 200 and caps.json()["parser_version"] == VERSION
    assert caps.json()["worker_online"] is None
    key = str(uuid4())
    path = f"/v1/accounts/{account}/quarantine/{receipt}/jobs"
    response = client.post(
        path,
        json={"expected_parser_version": VERSION},
        headers={**HEADERS, "Idempotency-Key": key},
    )
    assert response.status_code == 202 and response.json()["status"] == "queued"
    job = response.json()
    assert (
        client.post(
            path,
            json={"expected_parser_version": VERSION},
            headers={**HEADERS, "Idempotency-Key": key},
        ).json()
        == job
    )
    worker = Principal(replace(ctx, scopes=frozenset({"email.process"})), "worker")
    RecoveryJobs(store, VERSION).run_once(worker, account, FakeProcessor())
    status = client.get(f"/v1/accounts/{account}/processing/{job['id']}", headers=HEADERS)
    assert status.status_code == 200 and status.json()["status"] == "completed"
    assert status.json()["outcome"] == "recovered"
    assert (
        not {"lease_token", "actor_id", "worker_actor_id", "raw", "blob_ref"} & status.json().keys()
    )
    hits = client.post("/v1/search", json={"query": "Melron"}, headers=HEADERS).json()["results"]
    assert len(hits) == 1
    assert (
        client.post(f"/v1/accounts/{account}/processing/{job['id']}/cancel", headers=HEADERS).json()
        == status.json()
    )
    assert (
        client.get(f"/v1/accounts/{uuid4()}/processing/{job['id']}", headers=HEADERS).status_code
        == 404
    )


@pytest.mark.postgres
def test_api_cancel_queued_approval_prevents_work(database, tenant, monkeypatch):
    store, _ = database
    ctx, account = tenant
    receipt = make_held(store, ctx, account, monkeypatch)
    creds = registry({"email.review", "email.evidence.read"})
    creds.credentials[0].tenant_id, creds.credentials[0].actor_id = ctx.tenant_id, ctx.actor_id
    client = TestClient(create_app(store, creds, recovery_parser_version=VERSION))
    job = client.post(
        f"/v1/accounts/{account}/quarantine/{receipt}/jobs",
        json={"expected_parser_version": VERSION},
        headers={**HEADERS, "Idempotency-Key": str(uuid4())},
    ).json()
    assert (
        client.post(
            f"/v1/accounts/{account}/processing/{job['id']}/cancel", headers=HEADERS
        ).json()["status"]
        == "cancelled"
    )
    processor = FakeProcessor()
    monkeypatch.setattr(processor, "prepare", lambda raw: pytest.fail("cancelled approval ran"))
    assert (
        RecoveryJobs(store, VERSION).run_once(
            Principal(replace(ctx, scopes=frozenset({"email.process"})), "worker"),
            account,
            processor,
        )
        is None
    )
