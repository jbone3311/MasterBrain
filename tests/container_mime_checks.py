"""Explicit post-build CI checks: actual restricted Docker + actual PostgreSQL.

Not collected by the default test_*.py suite. Invoke explicitly after image build.
No real mail, external endpoints, cloud credentials or host mounts.
"""

import hashlib
import os
import secrets
from dataclasses import replace
from email.message import EmailMessage

import pytest
import test_postgres as pg

from email_brain.auth import Principal
from email_brain.blobs import EncryptedBlobStore
from email_brain.normalize import MAX_RAW_BYTES, PARSER_VERSION
from email_brain.recovery import Recovery
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
