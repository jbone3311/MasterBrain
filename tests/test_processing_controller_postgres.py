"""Operator workflow against real tenant-enforced SQL; fake parser only here."""

import json
from threading import Event
from unittest.mock import Mock
from uuid import uuid4

import psycopg
import pytest
import test_postgres as pg
from test_isolated_recovery import VERSION, FakeProcessor, make_held
from test_processing_controller import controller_files, private_write

from email_brain import processing_controller as control
from email_brain.auth import Principal
from email_brain.recovery_jobs import RecoveryJobs

database, tenant = pg.database, pg.tenant
pytestmark = pytest.mark.postgres


def setup_job(database, tenant, monkeypatch, tmp_path):
    store, _ = database
    ctx, account = tenant
    receipt = make_held(store, ctx, account, monkeypatch)
    jobs = RecoveryJobs(store, VERSION)
    job = jobs.enqueue(Principal(ctx, "human"), account, receipt, VERSION, uuid4())
    path, config, creds, token = controller_files(tmp_path, ctx.tenant_id, ctx.actor_id, account)
    processor = FakeProcessor()
    factory = Mock(return_value=processor)
    monkeypatch.setattr(control, "DockerMimeProcessor", factory)
    return path, config, creds, jobs, job, processor, factory


def test_check_no_claim_then_execute_then_restart_no_duplicate(
    database, tenant, monkeypatch, tmp_path
):
    path, _, _, jobs, job, processor, factory = setup_job(database, tenant, monkeypatch, tmp_path)
    store, _ = database
    ctx, account = tenant
    assert control.run_controller(path, store.dsn, check=True)["claims"] == 0
    assert jobs.get(ctx, account, job["id"])["attempts"] == 0
    factory.assert_not_called()
    prepare = Mock(wraps=processor.prepare)
    monkeypatch.setattr(processor, "prepare", prepare)
    assert control.run_controller(path, store.dsn)["results"]["completed"] == 1
    assert control.run_controller(path, store.dsn)["results"]["no_result"] == 1
    assert prepare.call_count == 1
    assert jobs.get(ctx, account, job["id"])["attempts"] == 1
    with store.transaction(ctx) as conn:
        assert conn.execute("SELECT count(*) AS n FROM recovery_attempts").fetchone()["n"] == 1


@pytest.mark.parametrize("denial", ["foreign", "nonowner", "disabled", "admin"])
def test_preflight_denial_never_claims(database, tenant, monkeypatch, tmp_path, denial):
    path, config, creds, jobs, job, _, factory = setup_job(database, tenant, monkeypatch, tmp_path)
    store, admin = database
    ctx, account = tenant
    if denial == "foreign":
        config["account_id"] = str(uuid4())
        private_write(path, config)
    elif denial == "nonowner":
        creds[0]["actor_id"] = str(uuid4())
        private_write(path.parent / "credentials.json", creds)
    elif denial == "disabled":
        with psycopg.connect(admin) as conn:
            conn.execute("UPDATE mail_accounts SET status='disconnected' WHERE id=%s", (account,))
    with pytest.raises(control.ControllerError):
        control.run_controller(path, admin if denial == "admin" else store.dsn)
    factory.assert_not_called()
    # Privileged test observer checks only this fixture's job, not runtime grants.
    with psycopg.connect(admin) as conn:
        row = conn.execute(
            "SELECT status,attempts FROM recovery_jobs WHERE id=%s", (job["id"],)
        ).fetchone()
        assert row == ("queued", 0)


def test_credential_revocation_during_parse_prevents_evidence(
    database, tenant, monkeypatch, tmp_path
):
    path, _, _, jobs, job, processor, _ = setup_job(database, tenant, monkeypatch, tmp_path)
    store, _ = database
    ctx, account = tenant
    prepare = processor.prepare

    def revoke(raw):
        result = prepare(raw)
        private_write(path.parent / "credentials.json", [])
        return result

    monkeypatch.setattr(processor, "prepare", revoke)
    with pytest.raises(control.ControllerError):
        control.run_controller(path, store.dsn)
    assert jobs.get(ctx, account, job["id"])["status"] == "retry_wait"
    with store.transaction(ctx) as conn:
        assert conn.execute("SELECT count(*) AS n FROM recovery_attempts").fetchone()["n"] == 0
        assert conn.execute("SELECT count(*) AS n FROM message_versions").fetchone()["n"] == 0


def test_graceful_stop_finishes_one_approved_job(database, tenant, monkeypatch, tmp_path):
    path, _, _, jobs, job, processor, _ = setup_job(database, tenant, monkeypatch, tmp_path)
    store, _ = database
    ctx, account = tenant
    stop = Event()
    prepare = processor.prepare

    def stopped(raw):
        stop.set()
        return prepare(raw)

    monkeypatch.setattr(processor, "prepare", stopped)
    result = control.run_controller(path, store.dsn, stop=stop, max_iterations=100)
    assert result["stopped"] and result["polls"] == 1
    assert jobs.get(ctx, account, job["id"])["status"] == "completed"


def test_wrong_image_channel_does_not_claim(database, tenant, monkeypatch, tmp_path):
    path, config, _, jobs, job, _, factory = setup_job(database, tenant, monkeypatch, tmp_path)
    store, _ = database
    ctx, account = tenant
    config["image_id"] = "sha256:" + "b" * 64
    private_write(path, config)
    processor = FakeProcessor()
    processor.parser_version = "sandbox-mime-v1-" + "b" * 64
    factory.return_value = processor
    result = control.run_controller(path, store.dsn)
    assert result["results"]["no_result"] == 1
    assert jobs.get(ctx, account, job["id"])["attempts"] == 0
    assert str(account) not in json.dumps(result)
