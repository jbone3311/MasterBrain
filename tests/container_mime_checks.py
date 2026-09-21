"""Explicit post-build CI checks: actual restricted Docker + actual PostgreSQL.

Not collected by the default test_*.py suite. Invoke explicitly after image build.
No real mail, external endpoints, cloud credentials or host mounts.
"""

import hashlib
import json
import os
import secrets
import subprocess
import sys
from dataclasses import replace
from email.message import EmailMessage
from uuid import uuid4

import pytest
import test_postgres as pg
from fastapi.testclient import TestClient
from test_processing_controller import controller_files, private_write
from test_service import TOKEN, registry

from email_brain.api import create_app
from email_brain.auth import Principal
from email_brain.blobs import EncryptedBlobStore
from email_brain.normalize import MAX_RAW_BYTES, PARSER_VERSION
from email_brain.recovery import Recovery
from email_brain.recovery_jobs import RecoveryJobs
from email_brain.sandbox_runner import DockerMimeProcessor
from email_brain.schemas import SearchRequest
from email_brain.store import Conflict, Store

database, tenant = pg.database, pg.tenant


@pytest.fixture
def processor():
    image = os.environ.get("EMAIL_BRAIN_SANDBOX_IMAGE_ID")
    if not image:
        pytest.fail("explicit container checks require a prebuilt local image ID")
    return DockerMimeProcessor(image)


def attachment_heavy_mail():
    mail = EmailMessage()
    mail["From"] = "synthetic@example.invalid"
    mail["To"] = "owner@example.invalid"
    mail["Subject"] = "Synthetic large MIME"
    mail.set_content("largebodyproof from retained synthetic mail")
    mail.add_attachment(
        "largeattachmentproof plain evidence", subtype="plain", filename="notes.txt"
    )
    mail.add_attachment(
        b"%PDF synthetic non-executable placeholder\n" + b"x" * MAX_RAW_BYTES,
        maintype="application",
        subtype="pdf",
        filename="large.pdf",
    )
    raw = mail.as_bytes()
    assert MAX_RAW_BYTES < len(raw) < 16 * MAX_RAW_BYTES
    return raw


def test_actual_restricted_container_parses_large_mime_and_defers_binary(processor):
    raw = attachment_heavy_mail()
    normalized, attachments, rejected = processor.prepare(raw)
    assert not rejected and normalized is not None
    assert normalized.raw_sha256 == hashlib.sha256(raw).hexdigest()
    assert "largebodyproof" in normalized.text
    assert len(attachments) == 2
    assert attachments[0].status == "extracted"
    assert "largeattachmentproof" in attachments[0].text
    assert attachments[1].status == "deferred" and attachments[1].text == ""


def test_actual_restricted_container_empty_mime_is_deterministic_rejection(processor):
    normalized, attachments, rejected = processor.prepare(b"")
    assert normalized is None and attachments == [] and rejected


@pytest.mark.postgres
def test_encrypted_source_to_actual_sandbox_to_searchable_database(
    database, tenant, processor, tmp_path
):
    ctx, account = tenant
    blobs = EncryptedBlobStore(
        tmp_path.resolve() / "objects",
        {(ctx.tenant_id, "synthetic-key"): secrets.token_bytes(32)},
        {ctx.tenant_id: "synthetic-key"},
    )
    store = Store(database[0].dsn, blobs=blobs)
    raw = attachment_heavy_mail()
    store.ingest_page(ctx, account, None, "held", [replace(pg.item(), raw=raw)])
    receipt = store.quarantines(ctx, account)["results"][0]
    assert receipt["reason"] == "mime_too_large"
    with pytest.raises(Conflict):
        Recovery(store).retry(Principal(ctx, "human"), account, receipt["id"], PARSER_VERSION)
    with store.transaction(ctx) as conn:
        before = {
            table: conn.execute(f"SELECT * FROM {table}").fetchall()
            for table in ("raw_objects", "provider_events", "sync_cursors")
        }
    recovery = Recovery(store, processor=processor)
    result = recovery.retry(
        Principal(ctx, "human"), account, receipt["id"], processor.parser_version
    )
    assert result["outcome"] == "recovered"
    assert (
        recovery.retry(Principal(ctx, "human"), account, receipt["id"], processor.parser_version)
        == result
    )
    assert store.quarantines(ctx, account)["results"] == []
    for term in ("largebodyproof", "largeattachmentproof"):
        hits = store.search(ctx, SearchRequest(query=term))
        assert len(hits) == 1 and hits[0]["evidence_id"] == result["evidence_id"]
    evidence = store.evidence(ctx, result["evidence_id"])
    assert evidence["parser_version"] == processor.parser_version
    assert evidence["attachment_accounting"]["deferred"] == 1
    assert evidence["attachment_accounting"]["ready"] is False
    with store.transaction(ctx) as conn:
        for table, rows in before.items():
            assert conn.execute(f"SELECT * FROM {table}").fetchall() == rows
    assert store.load_raw(ctx, account, receipt["raw_sha256"]) == raw


@pytest.mark.postgres
def test_api_job_to_actual_container_atomic_completion(database, tenant, processor, tmp_path):
    ctx, account = tenant
    worker_store = Store(
        database[0].dsn,
        blobs=EncryptedBlobStore(
            tmp_path.resolve() / "job-objects",
            {(ctx.tenant_id, "job-key"): secrets.token_bytes(32)},
            {ctx.tenant_id: "job-key"},
        ),
    )
    worker_store.ingest_page(
        ctx, account, None, "held", [replace(pg.item(), raw=attachment_heavy_mail())]
    )
    receipt = worker_store.quarantines(ctx, account)["results"][0]
    creds = registry({"email.review", "email.evidence.read", "email.search"})
    creds.credentials[0].tenant_id, creds.credentials[0].actor_id = ctx.tenant_id, ctx.actor_id
    # The API has neither blob keys nor a processor/controller, only the approved version.
    api = TestClient(
        create_app(Store(database[0].dsn), creds, recovery_parser_version=processor.parser_version)
    )
    headers = {"Authorization": f"Bearer {TOKEN}"}
    response = api.post(
        f"/v1/accounts/{account}/quarantine/{receipt['id']}/jobs",
        json={"expected_parser_version": processor.parser_version},
        headers={**headers, "Idempotency-Key": str(uuid4())},
    )
    assert response.status_code == 202
    job = response.json()
    queue = RecoveryJobs(worker_store, processor.parser_version)
    worker = Principal(replace(ctx, scopes=frozenset({"email.process"})), "worker")
    queue.run_once(worker, account, processor)
    status = api.get(f"/v1/accounts/{account}/processing/{job['id']}", headers=headers)
    assert status.status_code == 200
    assert status.json()["status"] == "completed" and status.json()["outcome"] == "recovered"
    assert queue.run_once(worker, account, processor) is None
    for term in ("largebodyproof", "largeattachmentproof"):
        response = api.post("/v1/search", json={"query": term}, headers=headers)
        assert response.status_code == 200 and len(response.json()["results"]) == 1
    with worker_store.transaction(ctx) as conn:
        attempt = conn.execute("SELECT id FROM recovery_attempts").fetchone()
        assert str(attempt["id"]) == status.json()["attempt_id"]
        assert conn.execute("SELECT count(*) AS n FROM recovery_jobs").fetchone()["n"] == 1


@pytest.mark.postgres
def test_operator_cli_encrypted_job_check_execute_and_restart(
    database, tenant, processor, tmp_path
):
    ctx, account = tenant
    key = secrets.token_bytes(32)
    root = tmp_path.resolve() / "objects"
    store = Store(
        database[0].dsn,
        blobs=EncryptedBlobStore(
            root,
            {(ctx.tenant_id, "cli-key"): key},
            {ctx.tenant_id: "cli-key"},
        ),
    )
    store.ingest_page(ctx, account, None, "held", [replace(pg.item(), raw=attachment_heavy_mail())])
    receipt = store.quarantines(ctx, account)["results"][0]
    jobs = RecoveryJobs(store, processor.parser_version)
    job = jobs.enqueue(
        Principal(ctx, "human"), account, receipt["id"], processor.parser_version, uuid4()
    )
    path, config, _, token = controller_files(
        tmp_path,
        ctx.tenant_id,
        ctx.actor_id,
        account,
        "sha256:" + processor.parser_version.removeprefix("sandbox-mime-v1-"),
    )
    config.update(blob_root=str(root), keys_file=str(path.parent / "keys.json"))
    private_write(path, config)
    private_write(
        path.parent / "keys.json",
        {
            "tenant_id": str(ctx.tenant_id),
            "keys": [{"key_id": "cli-key", "key_hex": key.hex()}],
        },
    )

    def invoke(*extra):
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "email_brain.cli",
                "process-jobs",
                "--config",
                str(path),
                *extra,
            ],
            env={"PATH": "/usr/bin:/bin", "EMAIL_BRAIN_DSN": store.dsn},
            capture_output=True,
            text=True,
            timeout=90,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        assert result.stderr == ""
        for secret in (token, key.hex(), store.dsn, str(account), "largebodyproof"):
            assert secret not in result.stdout
        return json.loads(result.stdout)

    assert invoke("--check")["execution_verified"] is False
    assert jobs.get(ctx, account, job["id"])["attempts"] == 0
    assert invoke()["results"]["completed"] == 1
    assert invoke()["results"]["no_result"] == 1
    status = jobs.get(ctx, account, job["id"])
    assert status["status"] == "completed" and status["attempts"] == 1
    assert len(store.search(ctx, SearchRequest(query="largeattachmentproof"))) == 1
    assert (
        hashlib.sha256(store.load_raw(ctx, account, receipt["raw_sha256"])).hexdigest()
        == receipt["raw_sha256"]
    )
