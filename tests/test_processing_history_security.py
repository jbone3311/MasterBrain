"""Independent account-history boundaries; only fictional mail and identities."""

from dataclasses import replace
from unittest.mock import MagicMock
from uuid import uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient
from test_isolated_recovery import VERSION, make_held
from test_postgres import database as database
from test_postgres import tenant as tenant
from test_service import TOKEN, registry

from email_brain.api import create_app
from email_brain.auth import Principal
from email_brain.recovery_jobs import RecoveryJobs
from email_brain.store import AccessDenied, Store

HEADERS = {"Authorization": f"Bearer {TOKEN}"}


def client_for(store, ctx):
    credentials = registry({"email.evidence.read"})
    credentials.credentials[0].tenant_id = ctx.tenant_id
    credentials.credentials[0].actor_id = ctx.actor_id
    # History must remain accessible when new isolated approvals are disabled.
    return TestClient(create_app(store, credentials))


def approve(store, ctx, account, monkeypatch):
    receipt = make_held(store, ctx, account, monkeypatch)
    jobs = RecoveryJobs(store, VERSION)
    job = jobs.enqueue(Principal(ctx, "human"), account, receipt, VERSION, uuid4())
    return jobs, receipt, job


@pytest.mark.parametrize("auth", ["missing", "expired", "wrong_scope"])
def test_history_denies_credentials_before_database(auth):
    store = MagicMock(spec=Store)
    credentials = registry({"email.search"}, expired=auth == "expired")
    client = TestClient(create_app(store, credentials))
    response = client.get(
        f"/v1/accounts/{uuid4()}/processing/jobs",
        headers={} if auth == "missing" else HEADERS,
    )
    assert response.status_code == (403 if auth == "wrong_scope" else 401)
    store.transaction.assert_not_called()
    assert "results" not in response.json()


def test_direct_history_library_requires_evidence_scope():
    store = MagicMock(spec=Store)
    store.require = Store.require
    ctx = registry({"email.search"}).authenticate(TOKEN).context
    with pytest.raises(AccessDenied):
        RecoveryJobs(store).list(ctx, uuid4())
    store.transaction.assert_not_called()


@pytest.mark.postgres
def test_same_tenant_other_account_and_foreign_owner_anchors_are_not_usable(
    database, tenant, monkeypatch
):
    store, admin = database
    ctx, account = tenant
    _, _, original = approve(store, ctx, account, monkeypatch)
    other_account = uuid4()
    foreign_tenant, foreign_actor, foreign_account = uuid4(), uuid4(), uuid4()
    with psycopg.connect(admin) as conn:
        conn.execute(
            "INSERT INTO mail_accounts(id,tenant_id,provider,address,secret_ref) "
            "VALUES (%s,%s,'fastmail','other@example.invalid','synthetic:none')",
            (other_account, ctx.tenant_id),
        )
        conn.execute(
            "INSERT INTO tenants(id,name) VALUES (%s,'Synthetic foreign')", (foreign_tenant,)
        )
        conn.execute(
            "INSERT INTO tenant_memberships(tenant_id,user_id,role) VALUES (%s,%s,'owner')",
            (foreign_tenant, foreign_actor),
        )
        conn.execute(
            "INSERT INTO mail_accounts(id,tenant_id,provider,address,secret_ref) "
            "VALUES (%s,%s,'fastmail','foreign@example.invalid','synthetic:none')",
            (foreign_account, foreign_tenant),
        )
    _, _, other = approve(store, ctx, other_account, monkeypatch)
    foreign_ctx = replace(ctx, tenant_id=foreign_tenant, actor_id=foreign_actor)
    _, _, foreign = approve(store, foreign_ctx, foreign_account, monkeypatch)
    client = client_for(store, ctx)
    path = f"/v1/accounts/{account}/processing/jobs"
    for anchor in (other["id"], foreign["id"], uuid4()):
        response = client.get(path, params={"after": str(anchor)}, headers=HEADERS)
        assert response.status_code == 404
        assert "results" not in response.json()
        assert str(original["id"]) not in response.text
    spoofed = {
        **HEADERS,
        "X-Tenant-ID": str(foreign_tenant),
        "X-Actor-ID": str(foreign_actor),
    }
    response = client.get(
        f"/v1/accounts/{foreign_account}/processing/jobs",
        params={"tenant_id": str(foreign_tenant), "actor_id": str(foreign_actor)},
        headers=spoofed,
    )
    assert response.status_code == 404
    own_page = client.get(path, headers=HEADERS)
    assert own_page.status_code == 200
    assert [row["id"] for row in own_page.json()["results"]] == [str(original["id"])]
    foreign_client = client_for(store, foreign_ctx)
    assert (
        foreign_client.get(path, params={"after": str(original["id"])}, headers=HEADERS).status_code
        == 404
    )


@pytest.mark.postgres
def test_history_scope_does_not_survive_owner_membership_removal(database, tenant, monkeypatch):
    store, admin = database
    ctx, account = tenant
    _, _, job = approve(store, ctx, account, monkeypatch)
    client = client_for(store, ctx)
    path = f"/v1/accounts/{account}/processing/jobs"
    assert client.get(path, headers=HEADERS).status_code == 200
    with psycopg.connect(admin) as conn:
        conn.execute(
            "DELETE FROM tenant_memberships WHERE tenant_id=%s AND user_id=%s",
            (ctx.tenant_id, ctx.actor_id),
        )
    response = client.get(path, headers=HEADERS)
    assert response.status_code == 403
    assert str(job["id"]) not in response.text
    assert "results" not in response.json()


@pytest.mark.postgres
def test_history_read_is_nonmutating_and_anchor_survives_status_change(
    database, tenant, monkeypatch
):
    store, _ = database
    ctx, account = tenant
    jobs, receipt, first = approve(store, ctx, account, monkeypatch)
    second = jobs.enqueue(Principal(ctx, "human"), account, receipt, VERSION, uuid4())
    client = client_for(store, ctx)
    path = f"/v1/accounts/{account}/processing/jobs"
    with store.transaction(ctx) as conn:
        before = conn.execute("SELECT * FROM recovery_jobs ORDER BY id").fetchall()
    response = client.get(path, params={"limit": 1}, headers=HEADERS)
    page = response.json()
    assert response.status_code == 200
    assert page["results"][0]["id"] == str(second["id"])
    assert page["next_after"] == str(second["id"])
    private_fields = {
        "lease_token",
        "lease_until",
        "worker_actor_id",
        "actor_id",
        "tenant_id",
        "approval_scopes",
        "idempotency_key",
        "blob_ref",
        "raw_mime",
        "secret_ref",
    }
    assert private_fields.isdisjoint(page["results"][0])
    with store.transaction(ctx) as conn:
        assert conn.execute("SELECT * FROM recovery_jobs ORDER BY id").fetchall() == before
        assert (
            conn.execute(
                "SELECT count(*) AS n FROM audit_events WHERE event_type='recovery.jobs_read'"
            ).fetchone()["n"]
            == 1
        )
    jobs.cancel(Principal(ctx, "human"), account, second["id"])
    following = client.get(path, params={"after": page["next_after"]}, headers=HEADERS)
    assert following.status_code == 200
    assert [row["id"] for row in following.json()["results"]] == [str(first["id"])]
    assert following.json()["next_after"] is None
    refreshed = client.get(path, headers=HEADERS).json()["results"]
    assert refreshed[0]["status"] == "cancelled"
    assert refreshed[1]["status"] == "queued"
