"""Real SQL authority and publication through the explicit PDF operator workflow."""

import json
from threading import Event
from unittest.mock import Mock
from uuid import uuid4

import psycopg
import pytest
import test_postgres as pg
from test_document_controller import document_files
from test_document_jobs import FakePdf, assert_no_result, setup, snapshot
from test_processing_controller import private_write

from email_brain import document_controller as control
from email_brain.processing_controller import ControllerError
from email_brain.schemas import SearchRequest

database, tenant = pg.database, pg.tenant
pytestmark = pytest.mark.postgres


def setup_controller(database, tenant, monkeypatch, tmp_path):
    jobs, human, worker, receipt, job = setup(database, tenant)
    path, config, creds, token = document_files(
        tmp_path, worker.context.tenant_id, worker.context.actor_id, tenant[1]
    )
    processor = FakePdf()
    processor.extract = Mock(wraps=processor.extract)
    factory = Mock(return_value=processor)
    monkeypatch.setattr(control, "DockerPdfProcessor", factory)
    return path, config, creds, token, jobs, job, processor, factory


def test_preflight_then_execute_restart_preserves_original_evidence(
    database, tenant, monkeypatch, tmp_path
):
    path, _, _, token, jobs, job, processor, factory = setup_controller(
        database, tenant, monkeypatch, tmp_path
    )
    store, _ = database
    ctx, account = tenant
    before = snapshot(store, ctx)
    assert control.run_document_controller(path, store.dsn, check=True)["claims"] == 0
    assert jobs.get(ctx, account, job["id"])["attempts"] == 0
    factory.assert_not_called()
    assert control.run_document_controller(path, store.dsn)["results"]["completed"] == 1
    result = control.run_document_controller(path, store.dsn)
    assert result["results"]["no_result"] == 1
    assert processor.extract.call_count == 1
    status = jobs.get(ctx, account, job["id"])
    assert status["status"] == "completed" and status["attempts"] == 1
    hits = store.search(ctx, SearchRequest(query="pdfonlyproof", include_documents=True))
    assert len(hits) == 1 and hits[0]["document_id"] == status["extraction_id"]
    assert snapshot(store, ctx) == before
    for sensitive in (token, store.dsn, str(account), "pdfonlyproof"):
        assert sensitive not in json.dumps(result)


@pytest.mark.parametrize(
    "denial", ["foreign", "nonowner", "disabled", "enrolled", "nonsynthetic", "admin"]
)
def test_preflight_denial_cannot_claim(database, tenant, monkeypatch, tmp_path, denial):
    path, config, creds, _, _, job, _, factory = setup_controller(
        database, tenant, monkeypatch, tmp_path
    )
    store, admin = database
    _, account = tenant
    if denial == "foreign":
        _, other = pg.tenant.__wrapped__(database)
        config["account_id"] = str(other)
        private_write(path, config)
    elif denial == "nonowner":
        creds[0]["actor_id"] = str(uuid4())
        private_write(path.parent / "credentials.json", creds)
    else:
        with psycopg.connect(admin) as conn:
            if denial == "disabled":
                conn.execute(
                    "UPDATE mail_accounts SET status='disconnected' WHERE id=%s", (account,)
                )
            elif denial == "enrolled":
                conn.execute(
                    "UPDATE mail_accounts SET provider_account_id='fictional' WHERE id=%s",
                    (account,),
                )
            elif denial == "nonsynthetic":
                conn.execute(
                    "UPDATE mail_accounts SET secret_ref='vault:fictional' WHERE id=%s", (account,)
                )
    with pytest.raises(ControllerError):
        control.run_document_controller(path, admin if denial == "admin" else store.dsn, check=True)
    factory.assert_not_called()
    with psycopg.connect(admin) as conn:
        assert conn.execute(
            "SELECT status,attempts FROM document_jobs WHERE id=%s", (job["id"],)
        ).fetchone() == ("queued", 0)


def test_file_revocation_during_extraction_prevents_publication(
    database, tenant, monkeypatch, tmp_path
):
    path, _, _, _, jobs, job, processor, _ = setup_controller(
        database, tenant, monkeypatch, tmp_path
    )
    store, _ = database
    ctx, account = tenant
    before = snapshot(store, ctx)
    extract = processor.extract

    def revoke(*args, **kwargs):
        result = extract(*args, **kwargs)
        private_write(path.parent / "credentials.json", [])
        return result

    processor.extract = revoke
    with pytest.raises(ControllerError):
        control.run_document_controller(path, store.dsn)
    assert jobs.get(ctx, account, job["id"])["status"] == "retry_wait"
    assert_no_result(store, ctx)
    assert snapshot(store, ctx) == before


def test_signal_stop_finishes_only_inflight_work(database, tenant, monkeypatch, tmp_path):
    path, _, _, _, jobs, job, processor, _ = setup_controller(
        database, tenant, monkeypatch, tmp_path
    )
    store, _ = database
    ctx, account = tenant
    stop = Event()
    extract = processor.extract

    def finish(*args, **kwargs):
        stop.set()
        return extract(*args, **kwargs)

    processor.extract = finish
    result = control.run_document_controller(path, store.dsn, max_iterations=100, stop=stop)
    assert result["stopped"] and result["polls"] == 1
    assert jobs.get(ctx, account, job["id"])["status"] == "completed"


def test_changed_image_cannot_claim_other_channel(database, tenant, monkeypatch, tmp_path):
    path, config, _, _, jobs, job, processor, _ = setup_controller(
        database, tenant, monkeypatch, tmp_path
    )
    config["image_id"] = "sha256:" + "b" * 64
    private_write(path, config)
    processor.processor_version = "sandbox-pdf-v1-" + "b" * 64
    assert control.run_document_controller(path, database[0].dsn)["results"]["no_result"] == 1
    assert jobs.get(tenant[0], tenant[1], job["id"])["attempts"] == 0
    processor.extract.assert_not_called()


def test_human_cancellation_during_extraction_fences_controller(
    database, tenant, monkeypatch, tmp_path
):
    path, _, _, _, jobs, job, processor, _ = setup_controller(
        database, tenant, monkeypatch, tmp_path
    )
    store, _ = database
    ctx, account = tenant
    extract = processor.extract

    def cancel(*args, **kwargs):
        from email_brain.auth import Principal

        jobs.cancel(Principal(ctx, "human"), account, job["id"])
        return extract(*args, **kwargs)

    processor.extract = cancel
    result = control.run_document_controller(path, store.dsn)
    assert result["results"]["cancelled"] == 1
    assert_no_result(store, ctx)
