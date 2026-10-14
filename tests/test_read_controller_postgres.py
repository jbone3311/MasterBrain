"""Actual operator/HTTPS-contract/SQL integration; all provider responses fictional."""

import hashlib
import json
import subprocess
import sys
from threading import Event
from uuid import uuid4

import httpx
import psycopg
import pytest
import test_postgres as pg
from test_read_controller import private_write, read_files

from email_brain import read_controller as control
from email_brain.schemas import SearchRequest
from email_brain.sync import Checkpoint

database, tenant = pg.database, pg.tenant
pytestmark = pytest.mark.postgres


def setup(database, tenant, tmp_path):
    ctx, account = tenant
    path, config, creds, token = read_files(tmp_path, ctx.tenant_id, ctx.actor_id, account)
    with psycopg.connect(database[1]) as conn:
        conn.execute(
            "UPDATE mail_accounts SET provider_account_id='provider-a' WHERE id=%s", (account,)
        )
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

    def run(**kwargs):
        return control.run_read_controller(
            path, database[0].dsn, allow_provider_read=True, transport_factory=factory, **kwargs
        )

    return path, config, creds, mail, transports, run


def snapshot(store, ctx):
    with store.transaction(ctx) as conn:
        return {
            "workers": conn.execute("SELECT count(*) AS n FROM sync_workers").fetchone()["n"],
            "cursor": conn.execute("SELECT opaque_cursor FROM sync_cursors").fetchone(),
            "messages": conn.execute("SELECT count(*) AS n FROM messages").fetchone()["n"],
            "events": conn.execute("SELECT count(*) AS n FROM provider_events").fetchone()["n"],
            "runs": conn.execute("SELECT count(*) AS n FROM sync_runs").fetchone()["n"],
        }


def scoped_setup(database, tenant, tmp_path):
    path, config, creds, mail, transports, run = setup(database, tenant, tmp_path)
    config["version"] = 2
    config["read_scope"] = {
        "mailbox_id": "inbox",
        "after": "2026-09-18T00:00:00Z",
        "before": "2026-09-21T00:00:00Z",
    }
    private_write(path, config)
    window = control.ScopedReadWindowConfig.model_validate(config["read_scope"]).window()
    with psycopg.connect(database[1]) as conn:
        conn.execute(
            "UPDATE mail_accounts SET read_scope_sha256=%s WHERE id=%s",
            (window.fingerprint(), tenant[1]),
        )
    return path, config, creds, mail, transports, run, window


def test_scoped_operator_preflight_and_fictional_restart(database, tenant, tmp_path):
    _, _, _, mail, transports, run, window = scoped_setup(database, tenant, tmp_path)
    store, _ = database
    ctx, account = tenant
    before = snapshot(store, ctx)
    assert run(check=True)["provider_requests"] == 0
    assert snapshot(store, ctx) == before and not transports and not mail.calls
    methods = []
    original = mail.handle

    def tracked(request):
        if request.method == "POST":
            method, args, _ = json.loads(request.content)["methodCalls"][0]
            methods.append(method)
            if method == "Email/query":
                assert args["filter"] == window.query_filter()
            assert method != "Email/changes"
        return original(request)

    mail.handle = tracked
    for expected in ("progress", "progress", "caught_up"):
        assert run()["results"][expected] == 1
    assert methods == ["Email/query", "Email/get"]
    assert mail.downloads == ["m1"] and all(t.closed for t in transports)
    with store.transaction(ctx) as conn:
        cursor = conn.execute(
            "SELECT opaque_cursor FROM sync_cursors WHERE account_id=%s AND scope='email'",
            (account,),
        ).fetchone()["opaque_cursor"]
        checkpoint = Checkpoint.model_validate_json(cursor)
        assert checkpoint.schema_version == 4
        assert checkpoint.scope_sha256 == window.fingerprint()
    hits = store.search(ctx, SearchRequest(query="Melron"))
    assert len(hits) == 1


def test_scoped_cli_check_has_no_provider_or_lease(database, tenant, tmp_path):
    path, _, _, mail, transports, _, _ = scoped_setup(database, tenant, tmp_path)
    store, _ = database
    ctx, _ = tenant
    before = snapshot(store, ctx)
    result = subprocess.run(
        [sys.executable, "-m", "email_brain.cli", "sync-read", "--config", str(path), "--check"],
        env={"PATH": "/usr/bin:/bin", "EMAIL_BRAIN_DSN": store.dsn},
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0 and not result.stderr
    assert json.loads(result.stdout)["provider_requests"] == 0
    assert snapshot(store, ctx) == before and not transports and not mail.calls


def test_scoped_operator_refuses_pin_drift_before_provider(database, tenant, tmp_path):
    path, config, _, mail, transports, run, _ = scoped_setup(database, tenant, tmp_path)
    store, _ = database
    ctx, _ = tenant
    config["read_scope"]["mailbox_id"] = "other"
    private_write(path, config)
    before = snapshot(store, ctx)
    with pytest.raises(control.ControllerError):
        run(check=True)
    assert snapshot(store, ctx) == before
    assert not transports and not mail.calls


def test_scoped_operator_cannot_cross_tenant(database, tenant, tmp_path):
    path, config, _, mail, transports, run, _ = scoped_setup(database, tenant, tmp_path)
    _, foreign_account = pg.tenant.__wrapped__(database)
    config["account_id"] = str(foreign_account)
    private_write(path, config)
    with pytest.raises(control.ControllerError):
        run(check=True)
    assert not transports and not mail.calls


def test_scoped_operator_paused_before_provider(database, tenant, tmp_path):
    _, _, _, mail, transports, run, _ = scoped_setup(database, tenant, tmp_path)
    assert run()["results"]["progress"] == 1
    before_calls, before_transports = len(mail.calls), len(transports)
    with psycopg.connect(database[1]) as conn:
        conn.execute("UPDATE sync_workers SET paused=true WHERE account_id=%s", (tenant[1],))
    result = run()
    assert result["results"]["paused"] == 1 and result["polls"] == 0
    assert len(mail.calls) == before_calls and len(transports) == before_transports


def test_scoped_operator_rejects_out_of_scope_metadata_before_blob(database, tenant, tmp_path):
    _, _, _, mail, transports, run, _ = scoped_setup(database, tenant, tmp_path)
    store, _ = database
    ctx, _ = tenant
    assert run()["results"]["progress"] == 1  # Baseline, no Email/get yet.
    before = snapshot(store, ctx)
    original = mail.handle

    def out_of_scope(request):
        response = original(request)
        if (
            request.method == "POST"
            and json.loads(request.content)["methodCalls"][0][0] == "Email/get"
        ):
            payload = response.json()
            payload["methodResponses"][0][1]["list"][0]["mailboxIds"] = {"other": True}
            return httpx.Response(200, json=payload)
        return response

    mail.handle = out_of_scope
    result = run()
    assert result["results"]["protocol_error"] == 1 and result["attention_required"]
    assert not mail.downloads and all(t.closed for t in transports)
    after = snapshot(store, ctx)
    assert after["cursor"] == before["cursor"] and after["messages"] == 0


def test_scoped_operator_mid_blob_revocation_cannot_publish(database, tenant, tmp_path):
    _, _, _, mail, transports, run, _ = scoped_setup(database, tenant, tmp_path)
    store, admin = database
    ctx, account = tenant
    assert run()["results"]["progress"] == 1
    before = snapshot(store, ctx)
    original = mail.handle

    def revoke(request):
        response = original(request)
        if request.url.path.startswith("/jmap/download/"):
            with psycopg.connect(admin) as conn:
                conn.execute(
                    "UPDATE mail_accounts SET status='disconnected' WHERE id=%s", (account,)
                )
        return response

    mail.handle = revoke
    with pytest.raises(control.ControllerError):
        run()
    assert mail.downloads == ["m1"] and all(t.closed for t in transports)
    after = snapshot(store, ctx)
    assert after["cursor"] == before["cursor"] and after["messages"] == 0


def test_preflight_restart_catchup_and_no_duplicate(database, tenant, tmp_path):
    _, _, _, mail, transports, run = setup(database, tenant, tmp_path)
    store, _ = database
    ctx, _ = tenant
    before = snapshot(store, ctx)
    assert run(check=True)["provider_requests"] == 0
    assert snapshot(store, ctx) == before and not transports and not mail.calls
    for outcome in ["progress", "progress", "progress", "caught_up"]:
        result = run()  # Fresh controller/client/registry on every invocation.
        assert result["results"][outcome] == 1 and not result["attention_required"]
    hits = store.search(ctx, SearchRequest(query="Melron"))
    assert len(hits) == 1
    assert "Synthetic investment" in store.evidence(ctx, hits[0]["evidence_id"])["excerpt"]
    before, calls = snapshot(store, ctx), len(mail.calls)
    assert run()["results"]["not_due"] == 1
    assert snapshot(store, ctx) == before and len(mail.calls) == calls
    assert all(t.closed for t in transports)


@pytest.mark.parametrize(
    "denial",
    [
        "unenrolled", "foreign", "nonowner", "disabled", "binding", "secret",
        "provider", "scoped", "admin",
    ],
)
def test_preflight_denial_before_provider_or_lease(database, tenant, tmp_path, denial):
    path, config, creds, mail, transports, run = setup(database, tenant, tmp_path)
    store, admin = database
    ctx, account = tenant
    if denial == "foreign":
        _, foreign = pg.tenant.__wrapped__(database)
        config["account_id"] = str(foreign)
        private_write(path, config)
    elif denial == "nonowner":
        creds[0]["actor_id"] = str(uuid4())
        private_write(path.parent / "credentials.json", creds)
    elif denial != "admin":
        statements = {
            "unenrolled": "UPDATE mail_accounts SET provider_account_id=NULL WHERE id=%s",
            "disabled": "UPDATE mail_accounts SET status='disconnected' WHERE id=%s",
            "binding": "UPDATE mail_accounts SET provider_account_id='other' WHERE id=%s",
            "secret": "UPDATE mail_accounts SET secret_ref='other' WHERE id=%s",
            "provider": "UPDATE mail_accounts SET provider='gmail' WHERE id=%s",
            "scoped": "UPDATE mail_accounts SET read_scope_sha256=repeat('a',64) WHERE id=%s",
        }
        with psycopg.connect(admin) as conn:
            conn.execute(statements[denial], (account,))
    with pytest.raises(control.ControllerError):
        if denial == "admin":
            control.run_read_controller(path, admin, check=True)
        else:
            run(check=True)
    assert not mail.calls and not transports
    assert snapshot(store, ctx)["workers"] == 0


@pytest.mark.parametrize(
    "change", ["registry", "token", "owner", "account", "binding", "secret", "lease"]
)
def test_change_during_blob_read_cannot_publish(database, tenant, tmp_path, change):
    path, _, _, mail, transports, run = setup(database, tenant, tmp_path)
    store, admin = database
    ctx, account = tenant
    assert run()["results"]["progress"] == 1
    before = snapshot(store, ctx)
    original = mail.handle
    mutated = []

    def changing(request):
        response = original(request)
        if request.url.path.startswith("/jmap/download/"):
            if change == "registry":
                private_write(path.parent / "credentials.json", [])
            elif change == "token":
                private_write(path.parent / "provider-token", b"synthetic-replacement-token")
            else:
                with psycopg.connect(admin) as conn:
                    if change == "owner":
                        conn.execute(
                            "UPDATE tenant_memberships SET role='member' "
                            "WHERE tenant_id=%s AND user_id=%s",
                            (ctx.tenant_id, ctx.actor_id),
                        )
                    elif change == "lease":
                        conn.execute(
                            "UPDATE sync_workers SET lease_token=%s WHERE account_id=%s",
                            (uuid4(), account),
                        )
                    else:
                        statements = {
                            "account": "UPDATE mail_accounts SET status='disconnected' WHERE id=%s",
                            "binding": "UPDATE mail_accounts SET provider_account_id='other' "
                            "WHERE id=%s",
                            "secret": "UPDATE mail_accounts SET secret_ref='other' WHERE id=%s",
                        }
                        conn.execute(statements[change], (account,))
            mutated.append(True)
        return response

    mail.handle = changing
    if change == "lease":
        # A replaced lease is another worker's account now: no outcome is recorded
        # and nothing is published, but the command is not an operator error.
        result = run(max_iterations=1)
        assert result["results"]["lease_lost"] == 1 and not result["attention_required"]
    else:
        with pytest.raises(control.ControllerError):
            run()
    assert mutated == [True] and all(t.closed for t in transports)
    # The privileged observer reads only this fixture after owner revocation.
    with psycopg.connect(admin) as conn:
        cursor = conn.execute(
            "SELECT opaque_cursor FROM sync_cursors WHERE account_id=%s", (account,)
        ).fetchone()[0]
        assert cursor == before["cursor"]["opaque_cursor"]
        assert (
            conn.execute(
                "SELECT count(*) FROM messages WHERE account_id=%s", (account,)
            ).fetchone()[0]
            == 0
        )
        assert (
            conn.execute(
                "SELECT count(*) FROM provider_events WHERE account_id=%s", (account,)
            ).fetchone()[0]
            == 0
        )
        row = conn.execute(
            "SELECT paused,last_outcome FROM sync_workers WHERE account_id=%s", (account,)
        ).fetchone()
        assert row == (False, "progress"), "revocation is not a malformed-MIME pause"


@pytest.mark.parametrize("status,outcome", [(401, "auth_required"), (429, "retry"), (503, "retry")])
def test_provider_failure_and_persisted_retry_pause(database, tenant, tmp_path, status, outcome):
    _, _, _, mail, transports, run = setup(database, tenant, tmp_path)
    mail.status = status
    first = run(max_iterations=1)
    assert first["results"][outcome] == 1
    before = len(mail.calls)
    second = run()
    assert second["results"]["paused" if status == 401 else "not_due"] == 1
    assert len(mail.calls) == before and all(t.closed for t in transports)


def test_provider_discovery_mismatch_reads_no_mail(database, tenant, tmp_path):
    _, _, _, mail, _, run = setup(database, tenant, tmp_path)
    mail.account = "wrong-provider-account"
    result = run(max_iterations=10)
    assert result["results"]["protocol_error"] == 1 and result["attention_required"]
    assert mail.calls == ["GET"]


def test_encrypted_large_source_through_operator_and_fresh_restart(database, tenant, tmp_path):
    path, config, creds, mail, transports, run = setup(database, tenant, tmp_path)
    root = path.parent / "objects"
    root.mkdir(mode=0o700)
    config.update(
        blob_root=str(root),
        keys_file=str(path.parent / "keys.json"),
        active_key_id="read-key",
        max_raw_bytes=2 * 1024**2,
    )
    private_write(path, config)
    private_write(
        path.parent / "keys.json",
        {"tenant_id": creds[0]["tenant_id"], "keys": [{"key_id": "read-key", "key_hex": "b" * 64}]},
    )
    raw = b"Subject: Large fictional source\r\n\r\n" + b"x" * (1024**2)
    mail.mail = {"a-large": raw, "z-healthy": pg.item().raw}
    for _ in range(10):
        result = run()
        if result["results"]["caught_up"]:
            break
        assert result["results"]["progress"] == 1
    assert result["results"]["caught_up"] == 1 and all(t.closed for t in transports)
    store, _ = database
    ctx, account = tenant
    assert store.sync_status(ctx, account)["message_counts"] == {
        "ready": 1,
        "quarantined": 1,
        "deleted": 0,
        "excluded": 0,
    }
    with store.transaction(ctx) as conn:
        rows = conn.execute(
            "SELECT raw_mime,blob_ref FROM raw_objects WHERE account_id=%s", (account,)
        ).fetchall()
        assert len(rows) == 2 and all(row["raw_mime"] is None for row in rows)
    from email_brain.auth import Principal

    configured_store = control._store(
        control.ReadControllerConfig.model_validate(config), store.dsn, Principal(ctx, "worker")
    )
    assert configured_store.object_inventory(ctx, account)["referenced"] == 2
    assert configured_store.load_raw(ctx, account, hashlib.sha256(raw).hexdigest()) == raw
    assert len(list(root.rglob("*.blob"))) == 2
    assert all(raw not in p.read_bytes() for p in root.rglob("*.blob"))


def test_stop_after_bounded_page_then_restart(database, tenant, tmp_path):
    _, _, _, mail, transports, run = setup(database, tenant, tmp_path)
    stop = Event()
    original = mail.handle

    def stopping(request):
        response = original(request)
        stop.set()
        return response

    mail.handle = stopping
    result = run(stop=stop, max_iterations=100)
    assert result["stopped"] and result["polls"] == 1 and result["results"]["progress"] == 1
    mail.handle = original
    assert run()["results"]["progress"] == 1 and all(t.closed for t in transports)


def test_cli_uses_real_operator_with_fake_transport(
    database, tenant, tmp_path, monkeypatch, capsys
):
    from email_brain import cli

    path, _, _, mail, _, _ = setup(database, tenant, tmp_path)
    real = control.run_read_controller
    monkeypatch.setattr(
        cli,
        "run_read_controller",
        lambda *a, **kw: real(*a, **kw, transport_factory=lambda: httpx.MockTransport(mail.handle)),
    )
    monkeypatch.setenv("EMAIL_BRAIN_DSN", database[0].dsn)
    monkeypatch.setattr(
        "sys.argv", ["email-brain", "sync-read", "--config", str(path), "--allow-provider-read"]
    )
    cli.main()
    assert json.loads(capsys.readouterr().out)["results"]["progress"] == 1
    assert len(mail.calls) == 2
