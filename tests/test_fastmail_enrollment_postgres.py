"""Fictional owner enrollment against disposable PostgreSQL; no provider login."""

from __future__ import annotations

import hashlib
import json
import secrets
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import httpx
import psycopg
import pytest
import test_postgres as pg
from test_processing_controller import private_write
from test_read_controller import read_files

from email_brain import read_controller
from email_brain.auth import Credential, TokenRegistry
from email_brain.fastmail_enrollment import EnrollmentError, run_fastmail_enrollment
from email_brain.processing_controller import _json

pytestmark = pytest.mark.postgres
database, tenant = pg.database, pg.tenant


def source_files(tmp_path, ctx, account, *, address="new@example.invalid"):
    read_path, read, _, _ = read_files(tmp_path, ctx.tenant_id, ctx.actor_id, account)
    read["version"] = 2
    read["read_scope"] = {
        "mailbox_id": "inbox", "after": "2026-09-18T00:00:00Z",
        "before": "2026-09-21T00:00:00Z",
    }
    private_write(read_path, read)
    fingerprint = read_controller.ScopedReadWindowConfig.model_validate(
        read["read_scope"]
    ).window().fingerprint()
    owner_token = secrets.token_urlsafe(40)
    owner_creds = [{
        "token_sha256": hashlib.sha256(owner_token.encode()).hexdigest(),
        "tenant_id": str(ctx.tenant_id), "actor_id": str(ctx.actor_id),
        "scopes": ["email.source.manage"], "client_kind": "human",
        "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
    }]
    private_write(tmp_path / "owner-credentials.json", owner_creds)
    private_write(tmp_path / "owner-token", owner_token.encode())
    config = {
        "version": 1, "expected_tenant_id": str(ctx.tenant_id),
        "expected_owner_actor_id": str(ctx.actor_id), "address": address,
        "read_config_file": str(read_path),
        "owner_credentials_file": str(tmp_path / "owner-credentials.json"),
        "owner_token_file": str(tmp_path / "owner-token"),
    }
    path = tmp_path / "source.json"
    private_write(path, config)
    return path, read_path, read, config, owner_creds, fingerprint


def apply(path, admin, read, fingerprint, *, action="enroll"):
    binding = run_fastmail_enrollment(path, admin, action="check")["binding_sha256"]
    return run_fastmail_enrollment(
        path, admin, action=action, confirmed_account_id=UUID(read["account_id"]),
        confirmed_scope_sha256=fingerprint, confirmed_binding_sha256=binding,
    )


def evidence_state(admin, account):
    with psycopg.connect(admin) as conn:
        return (
            conn.execute(
                "SELECT count(*) FROM messages WHERE account_id=%s", (account,)
            ).fetchone()[0],
            conn.execute(
                "SELECT count(*) FROM raw_objects WHERE account_id=%s", (account,)
            ).fetchone()[0],
            conn.execute(
                "SELECT opaque_cursor FROM sync_cursors WHERE account_id=%s AND scope='email'",
                (account,),
            ).fetchone()[0],
        )


def test_owner_scope_is_human_only():
    base = {
        "token_sha256": "a" * 64, "tenant_id": str(uuid4()), "actor_id": str(uuid4()),
        "scopes": ["email.source.manage"],
        "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
    }
    for kind in ("assistant", "worker"):
        with pytest.raises(ValueError):
            TokenRegistry([Credential.model_validate({**base, "client_kind": kind})])


def test_check_enroll_disconnect_preserve_exact_pin(database, tenant, tmp_path):
    store, admin = database
    ctx, _ = tenant
    account = uuid4()
    path, read_path, read, _, _, fingerprint = source_files(tmp_path, ctx, account)
    with psycopg.connect(admin) as conn:
        before = conn.execute("SELECT count(*) FROM audit_events").fetchone()[0]
    checked = run_fastmail_enrollment(path, admin, action="check")
    assert checked == {
        "action": "check", "account_state": "absent", "account_id": str(account),
        "scope_sha256": fingerprint, "binding_sha256": checked["binding_sha256"],
        "provider_requests": 0, "claims": 0,
    }
    with psycopg.connect(admin) as conn:
        count = conn.execute(
            "SELECT count(*) FROM mail_accounts WHERE id=%s", (account,)
        ).fetchone()[0]
        assert count == 0
        assert conn.execute("SELECT count(*) FROM audit_events").fetchone()[0] == before
        assert conn.execute(
            "SELECT count(*) FROM sync_workers WHERE account_id=%s", (account,)
        ).fetchone()[0] == 0
        assert conn.execute(
            "SELECT count(*) FROM sync_cursors WHERE account_id=%s", (account,)
        ).fetchone()[0] == 0
    with pytest.raises(EnrollmentError):
        run_fastmail_enrollment(
            path, admin, action="enroll", confirmed_account_id=account,
            confirmed_scope_sha256="0" * 64,
            confirmed_binding_sha256=checked["binding_sha256"],
        )
    enrolled = apply(path, admin, read, fingerprint)
    assert enrolled["account_state"] == "active" and enrolled["changed"] is True
    assert enrolled["provider_requests"] == enrolled["claims"] == 0
    assert read_controller.run_read_controller(read_path, store.dsn, check=True)[
        "provider_requests"
    ] == 0
    with psycopg.connect(admin) as conn:
        row = conn.execute(
            "SELECT read_scope_sha256,provider_account_id,status FROM mail_accounts WHERE id=%s",
            (account,),
        ).fetchone()
        assert row == (fingerprint, "provider-a", "active")
        assert conn.execute("SELECT count(*) FROM audit_events").fetchone()[0] == before + 1
        audit = conn.execute(
            "SELECT event_type,resource_id,metadata FROM audit_events "
            "WHERE resource_id=%s ORDER BY occurred_at DESC LIMIT 1", (str(account),)
        ).fetchone()
        assert audit == (
            "fastmail.scope.enroll", str(account), {"scope_sha256": fingerprint}
        )
    with pytest.raises(EnrollmentError):
        apply(path, admin, read, fingerprint)
    disconnected = apply(path, admin, read, fingerprint, action="disconnect")
    assert disconnected["account_state"] == "disconnected" and disconnected["changed"]
    with pytest.raises(read_controller.ControllerError):
        read_controller.run_read_controller(read_path, store.dsn, check=True)
    assert apply(path, admin, read, fingerprint, action="disconnect")["changed"] is False
    with psycopg.connect(admin) as conn:
        assert conn.execute(
            "SELECT read_scope_sha256,status FROM mail_accounts WHERE id=%s", (account,)
        ).fetchone() == (fingerprint, "disconnected")
        assert conn.execute("SELECT count(*) FROM audit_events").fetchone()[0] == before + 2


def test_actual_cli_check_then_explicit_enroll(database, tenant, tmp_path):
    _, admin = database
    ctx, _ = tenant
    account = uuid4()
    path, _, _, _, _, fingerprint = source_files(tmp_path, ctx, account)
    environment = {
        "PATH": "/usr/bin:/bin",
        "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src"),
        "EMAIL_BRAIN_ADMIN_DSN": admin,
    }
    checked = subprocess.run(
        [sys.executable, "-m", "email_brain.cli", "fastmail-source",
         "--config", str(path), "--check"],
        env=environment, text=True, capture_output=True, timeout=30, check=False,
    )
    assert checked.returncode == 0 and not checked.stderr
    response = json.loads(checked.stdout)
    assert response["account_state"] == "absent"
    with psycopg.connect(admin) as conn:
        assert conn.execute(
            "SELECT count(*) FROM mail_accounts WHERE id=%s", (account,)
        ).fetchone()[0] == 0
    missing = subprocess.run(
        [sys.executable, "-m", "email_brain.cli", "fastmail-source",
         "--config", str(path), "--enroll"],
        env=environment, text=True, capture_output=True, timeout=30, check=False,
    )
    assert missing.returncode != 0
    enrolled = subprocess.run(
        [sys.executable, "-m", "email_brain.cli", "fastmail-source",
         "--config", str(path), "--enroll", "--confirm-account", str(account),
         "--confirm-scope", fingerprint, "--confirm-binding", response["binding_sha256"]],
        env=environment, text=True, capture_output=True, timeout=30, check=False,
    )
    assert enrolled.returncode == 0 and not enrolled.stderr
    assert json.loads(enrolled.stdout)["account_state"] == "active"
    assert "synthetic-provider-token-only" not in enrolled.stdout


@pytest.mark.parametrize("drift", ["address", "provider_account_id", "secret_ref"])
def test_review_digest_refuses_source_binding_drift(database, tenant, tmp_path, drift):
    _, admin = database
    ctx, _ = tenant
    account = uuid4()
    path, read_path, read, config, _, fingerprint = source_files(tmp_path, ctx, account)
    reviewed = run_fastmail_enrollment(path, admin, action="check")
    if drift == "address":
        config["address"] = "changed@example.invalid"
        private_write(path, config)
    else:
        read[drift if drift == "provider_account_id" else "provider_secret_ref"] = "changed"
        private_write(read_path, read)
    with pytest.raises(EnrollmentError):
        run_fastmail_enrollment(
            path, admin, action="enroll", confirmed_account_id=account,
            confirmed_scope_sha256=fingerprint,
            confirmed_binding_sha256=reviewed["binding_sha256"],
        )
    with psycopg.connect(admin) as conn:
        assert conn.execute(
            "SELECT count(*) FROM mail_accounts WHERE id=%s", (account,)
        ).fetchone()[0] == 0


def test_disconnect_mid_fake_blob_cannot_publish(database, tenant, tmp_path):
    store, admin = database
    ctx, _ = tenant
    account = uuid4()
    path, read_path, read, _, _, fingerprint = source_files(tmp_path, ctx, account)
    apply(path, admin, read, fingerprint)
    mail = pg.SyntheticMailbox()
    transports = []

    class Transport(httpx.MockTransport):
        closed = False

        def close(self):
            self.closed = True
            super().close()

    def factory():
        transport = Transport(mail.handle)
        transports.append(transport)
        return transport

    assert read_controller.run_read_controller(
        read_path, store.dsn, allow_provider_read=True, transport_factory=factory
    )["results"]["progress"] == 1
    original = mail.handle

    def revoke(request):
        response = original(request)
        if request.url.path.startswith("/jmap/download/"):
            assert apply(path, admin, read, fingerprint, action="disconnect")["changed"]
        return response

    mail.handle = revoke
    with pytest.raises(read_controller.ControllerError):
        read_controller.run_read_controller(
            read_path, store.dsn, allow_provider_read=True, transport_factory=factory
        )
    with psycopg.connect(admin) as conn:
        assert conn.execute(
            "SELECT count(*) FROM messages WHERE account_id=%s", (account,)
        ).fetchone()[0] == 0
        assert conn.execute(
            "SELECT read_scope_sha256,status FROM mail_accounts WHERE id=%s", (account,)
        ).fetchone() == (fingerprint, "disconnected")
    assert all(transport.closed for transport in transports)


def test_disconnect_preserves_committed_fictional_evidence(database, tenant, tmp_path):
    store, admin = database
    ctx, _ = tenant
    account = uuid4()
    path, read_path, read, _, _, fingerprint = source_files(tmp_path, ctx, account)
    apply(path, admin, read, fingerprint)
    mail = pg.SyntheticMailbox()
    for _ in range(2):
        assert read_controller.run_read_controller(
            read_path, store.dsn, allow_provider_read=True,
            transport_factory=lambda: httpx.MockTransport(mail.handle),
        )["results"]["progress"] == 1
    before = evidence_state(admin, account)
    assert before[0] == before[1] == 1
    assert apply(path, admin, read, fingerprint, action="disconnect")["changed"]
    assert evidence_state(admin, account) == before
    with pytest.raises(read_controller.ControllerError):
        read_controller.run_read_controller(read_path, store.dsn, check=True)


def test_foreign_owner_cannot_disconnect_existing_source(database, tenant, tmp_path):
    _, admin = database
    ctx, _ = tenant
    account = uuid4()
    path, _, read, _, _, fingerprint = source_files(tmp_path, ctx, account)
    apply(path, admin, read, fingerprint)
    foreign_ctx, _ = pg.tenant.__wrapped__(database)
    foreign_dir = tmp_path / "foreign"
    foreign_dir.mkdir(mode=0o700)
    foreign_path, _, foreign_read, _, _, foreign_fingerprint = source_files(
        foreign_dir, foreign_ctx, account,
    )
    with pytest.raises(EnrollmentError):
        apply(foreign_path, admin, foreign_read, foreign_fingerprint, action="disconnect")
    with psycopg.connect(admin) as conn:
        assert conn.execute(
            "SELECT tenant_id,status FROM mail_accounts WHERE id=%s", (account,)
        ).fetchone() == (ctx.tenant_id, "active")


@pytest.mark.parametrize("denial", [
    "wrong_owner", "not_owner", "worker_manager", "wrong_worker_tenant",
    "wrong_confirmation", "existing_account", "duplicate_address", "foreign_disconnect",
])
def test_enrollment_denials_leave_no_new_source(database, tenant, tmp_path, denial):
    _, admin = database
    ctx, existing = tenant
    account = existing if denial == "existing_account" else uuid4()
    address = (
        "synthetic@example.invalid" if denial == "duplicate_address"
        else "new@example.invalid"
    )
    path, read_path, read, config, owner_creds, fingerprint = source_files(
        tmp_path, ctx, account,
        address=address,
    )
    if denial == "wrong_owner":
        config["expected_owner_actor_id"] = str(uuid4())
        private_write(path, config)
    elif denial == "not_owner":
        with psycopg.connect(admin) as conn:
            conn.execute(
                "UPDATE tenant_memberships SET role='member' WHERE tenant_id=%s AND user_id=%s",
                (ctx.tenant_id, ctx.actor_id),
            )
    elif denial == "worker_manager":
        owner_creds[0]["client_kind"] = "worker"
        private_write(tmp_path / "owner-credentials.json", owner_creds)
    elif denial == "wrong_worker_tenant":
        creds = _json(tmp_path / "credentials.json")
        creds[0]["tenant_id"] = str(uuid4())
        private_write(tmp_path / "credentials.json", creds)
    elif denial == "wrong_confirmation":
        fingerprint = "0" * 64
    elif denial == "foreign_disconnect":
        foreign_ctx, _ = pg.tenant.__wrapped__(database)
        config["expected_tenant_id"] = str(foreign_ctx.tenant_id)
        private_write(path, config)
    with pytest.raises(EnrollmentError):
        apply(path, admin, read, fingerprint,
              action="disconnect" if denial == "foreign_disconnect" else "enroll")
    with psycopg.connect(admin) as conn:
        assert conn.execute(
            "SELECT count(*) FROM mail_accounts WHERE id=%s", (account,)
        ).fetchone()[0] == (1 if denial == "existing_account" else 0)
