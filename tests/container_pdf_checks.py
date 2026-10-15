"""Explicit real restricted-image PDF tests; not ordinary test discovery."""

import hashlib
import json
import os
import secrets
import subprocess
import sys
from dataclasses import replace
from uuid import uuid4

import pytest
import test_postgres as pg
from pdf_samples import mail_packet, variant
from test_document_controller import document_files
from test_processing_controller import private_write
from test_recovery_jobs import worker_principal

from email_brain.attachments import receive_attachments
from email_brain.auth import Principal
from email_brain.blobs import EncryptedBlobStore
from email_brain.document_jobs import POLICY, DocumentJobs
from email_brain.pdf_contract import PdfUnavailable
from email_brain.pdf_processor import DockerPdfProcessor
from email_brain.schemas import SearchRequest
from email_brain.store import Store
from email_brain.synthetic_mailbox import project_events
from masterbrain.datacore.email_pdf_derivation import (
    EmailAttachmentPdfUnavailable,
    prove_email_attachment_pdf_derivation,
)
from masterbrain.datacore.persistence import EMAIL_DOCUMENT_NORMALIZER_PREFIX, DataCoreStore
from masterbrain.knowledge_schema import SourceTierReviewWrite
from masterbrain.source_tier_email_pdf_replay import SourceTierEmailPdfReplayStore
from masterbrain.source_tier_reviews import SourceTierReviews

database, tenant = pg.database, pg.tenant


@pytest.fixture
def processor():
    image = os.environ.get("EMAIL_BRAIN_PDF_IMAGE_ID")
    if not image:
        pytest.fail("explicit PDF container checks require an approved prebuilt image")
    return DockerPdfProcessor(image)


@pytest.mark.parametrize(
    "kind,reason",
    [
        ("text", "bounded_pdf_v1"),
        ("partial", "pages_without_text"),
        ("image", "no_text"),
        ("encrypted", "encrypted"),
        ("empty_password", "encrypted"),
        ("damaged", "invalid_pdf"),
        ("pages", "page_limit"),
        ("annotation", "unsupported_features"),
        ("active", "unsupported_features"),
        ("stream", "stream_limit"),
        ("text_limit", "text_limit"),
    ],
)
def test_actual_source_bound_pdf_profiles(processor, kind, reason):
    raw, source, _ = mail_packet(variant(kind))
    result = processor.extract(raw, part_path=source.part_path, part_sha256=source.part_sha256)
    assert result.source == source and result.reason == reason
    assert result.scanner_status == "unscanned"
    if result.pages:
        assert "pdfonlyproof" in result.pages[0].text
    if kind == "partial":
        assert result.pages[1].text == "" and result.status == "partial"
    # Processing never rewrites the original ingestion receipt.
    assert receive_attachments(raw)[0].status == "deferred"


def test_actual_child_rejects_mismatched_part_before_pdf_read(processor):
    raw, source, _ = mail_packet(variant("text"))
    with pytest.raises(PdfUnavailable, match="^pdf_processing_unavailable$"):
        processor.extract(raw, part_path=source.part_path, part_sha256="a" * 64)


def test_actual_image_proves_only_complete_retained_attachment_text(processor):
    raw, source, _ = mail_packet(variant("text"))
    extracted = processor.extract(
        raw, part_path=source.part_path, part_sha256=source.part_sha256,
    )
    assert extracted.status == "extracted"
    text = "\n".join(page.text for page in extracted.pages)
    normalizer = (
        f"{EMAIL_DOCUMENT_NORMALIZER_PREFIX}:{processor.processor_version}:{POLICY}"
    )
    proof = prove_email_attachment_pdf_derivation(
        raw, raw_sha256=source.raw_sha256, raw_size_bytes=len(raw),
        part_path=source.part_path, part_sha256=source.part_sha256,
        text=text, text_sha256=hashlib.sha256(text.encode()).hexdigest(),
        normalizer=normalizer, processor=processor,
    )
    assert proof.page_count == 1 and proof.raw_sha256 == source.raw_sha256
    partial_raw, partial_source, _ = mail_packet(variant("partial"))
    with pytest.raises(EmailAttachmentPdfUnavailable):
        prove_email_attachment_pdf_derivation(
            partial_raw, raw_sha256=partial_source.raw_sha256,
            raw_size_bytes=len(partial_raw), part_path=partial_source.part_path,
            part_sha256=partial_source.part_sha256, text=text,
            text_sha256=hashlib.sha256(text.encode()).hexdigest(),
            normalizer=normalizer, processor=processor,
        )


def test_existing_known_answer_mailbox_pdf_in_real_container(processor):
    for event in project_events(42, 0):
        if event.kind != "created":
            continue
        for part in receive_attachments(event.item.raw):
            if part.original_filename == "overview.pdf":
                result = processor.extract(
                    event.item.raw, part_path=part.part_id, part_sha256=part.sha256
                )
                assert result.reason == "bounded_pdf_v1"
                assert "pdfproofs42p0000" in result.pages[0].text
                return
    pytest.fail("expected authored PDF not found")


@pytest.mark.postgres
def test_actual_approved_document_to_sql_search_and_evidence(database, tenant, processor):
    store, _ = database
    ctx, account = tenant
    event = next(
        event
        for event in project_events(42, 0)
        if event.kind == "created" and any(a.name == "overview.pdf" for a in event.attachments)
    )
    store.ingest_page(ctx, account, None, "pdf-ready", [event.item])
    with store.transaction(ctx) as conn:
        receipt = conn.execute(
            "SELECT id FROM attachment_receipts WHERE account_id=%s "
            "AND safe_filename='overview.pdf'",
            (account,),
        ).fetchone()["id"]
    query = SearchRequest(query="pdfproofs42p0000", include_documents=True)
    assert store.search(ctx, query) == []
    jobs = DocumentJobs(store, processor.processor_version)
    jobs.enqueue(
        Principal(ctx, "human"), account, receipt, processor.processor_version, POLICY, uuid4()
    )
    worker = Principal(replace(ctx, scopes=frozenset({"email.document.process"})), "worker")
    completed = jobs.run_once(worker, account, processor)
    assert completed["status"] == "completed"
    hits = store.search(ctx, query)
    assert len(hits) == 1 and hits[0]["document_id"] == completed["extraction_id"]
    evidence = store.document_evidence(ctx, completed["extraction_id"])
    assert evidence["scanner_status"] == "unscanned"
    assert "pdfproofs42p0000" in evidence["pages"][0]["excerpt"]
    original = store.evidence(ctx, evidence["evidence_id"])
    assert next(a for a in original["attachments"] if a["id"] == receipt)["status"] == "deferred"
    with store.transaction(ctx) as conn:
        assert (
            conn.execute(
                "SELECT opaque_cursor FROM sync_cursors WHERE account_id=%s", (account,)
            ).fetchone()["opaque_cursor"]
            == "pdf-ready"
        )


@pytest.mark.postgres
def test_actual_image_seals_reviewed_email_pdf_receipt_without_source_effects(
    database, tenant, processor,
):
    """Exercise ADR-229 with the actual pinned image rather than a fake pipe."""
    store, admin = database
    ctx, account = tenant
    raw, _, _ = mail_packet(variant("text"))
    store.ingest_page(ctx, account, None, "reviewed-pdf-ready", [replace(pg.item(), raw=raw)])
    with store.transaction(ctx) as conn:
        attachment = conn.execute(
            "SELECT id,evidence_id FROM attachment_receipts WHERE account_id=%s",
            (account,),
        ).fetchone()
    assert attachment is not None
    jobs = DocumentJobs(store, processor.processor_version)
    jobs.enqueue(
        Principal(ctx, "human"), account, attachment["id"],
        processor.processor_version, POLICY, uuid4(),
    )
    job_worker = worker_principal(admin, ctx)
    job_worker = replace(
        job_worker,
        context=replace(
            job_worker.context, scopes=frozenset({"email.document.process"}),
        ),
    )
    completed = jobs.run_once(job_worker, account, processor)
    assert completed is not None and completed["status"] == "completed"
    assert completed["extraction_id"] is not None
    core = DataCoreStore(store)
    bridge_ctx = pg.datacore_context(ctx)
    core.bridge_current_email_version(
        bridge_ctx, attachment["evidence_id"], uuid4(),
        code_revision="actual-email-pdf-tier-v1",
    )
    core.bridge_email_attachment(
        bridge_ctx, attachment["id"], uuid4(),
        code_revision="actual-email-pdf-tier-v1",
    )
    derived = core.bridge_email_document_extraction(
        bridge_ctx, completed["extraction_id"], uuid4(),
        code_revision="actual-email-pdf-tier-v1",
    )
    reviewer = replace(
        ctx, scopes=ctx.scopes | frozenset({"knowledge.review", "brain.content.read"}),
    )
    with store.transaction(reviewer) as conn:
        source = conn.execute(
            "SELECT d.evidence_id,d.body_sha256,e.source_version_id,e.sha256 "
            "FROM brain_normalized_documents d JOIN brain_evidence e "
            "ON e.tenant_id=d.tenant_id AND e.id=d.evidence_id WHERE d.id=%s",
            (derived.document_id,),
        ).fetchone()
    assert source is not None
    review_id = SourceTierReviews(store).publish(
        reviewer, source["evidence_id"], SourceTierReviewWrite(
            evidence_id=source["evidence_id"], document_id=derived.document_id,
            document_sha256=source["body_sha256"],
            source_version_id=source["source_version_id"],
            source_sha256=source["sha256"], source_tier="T3",
            authority_kind="internal_record", source_quote="pdfonlyproof",
        ), uuid4(),
    )["object_id"]
    worker = replace(
        ctx, scopes=frozenset({"brain.document.publish", "email.evidence.read"}),
    )
    receipt = SourceTierEmailPdfReplayStore(store, processor).record_current_pdf_replay(
        worker, review_id, expected_account_id=account,
    )
    assert receipt == {
        "review_id": review_id, "worker_observed_pdf_text_replay": True,
        "source_effects": False, "financial_claim_approved": False,
    }
    with store.transaction(worker) as conn:
        saved = conn.execute(
            "SELECT raw_sha256,normalizer,page_count FROM "
            "knowledge_source_tier_email_pdf_replays WHERE review_id=%s",
            (review_id,),
        ).fetchone()
        assert conn.execute("SELECT count(*) AS n FROM knowledge_claims").fetchone()["n"] == 0
    assert saved is not None
    assert saved["raw_sha256"] == hashlib.sha256(raw).hexdigest()
    assert saved["normalizer"] == (
        f"{EMAIL_DOCUMENT_NORMALIZER_PREFIX}:{processor.processor_version}:{POLICY}"
    )
    assert saved["page_count"] == 1
    assert store.load_raw(ctx, account, saved["raw_sha256"]) == raw


@pytest.mark.postgres
def test_document_cli_encrypted_source_check_execute_restart(database, tenant, processor, tmp_path):
    ctx, account = tenant
    key = secrets.token_bytes(32)
    root = tmp_path.resolve() / "pdf-objects"
    store = Store(
        database[0].dsn,
        blobs=EncryptedBlobStore(
            root, {(ctx.tenant_id, "pdf-key"): key}, {ctx.tenant_id: "pdf-key"}
        ),
    )
    raw, _, _ = mail_packet(variant("text"))
    store.ingest_page(ctx, account, None, "pdf-cli-ready", [replace(pg.item(), raw=raw)])
    with store.transaction(ctx) as conn:
        receipt = conn.execute(
            "SELECT id FROM attachment_receipts WHERE account_id=%s", (account,)
        ).fetchone()["id"]
        saved = conn.execute(
            "SELECT raw_mime,blob_ref FROM raw_objects WHERE account_id=%s", (account,)
        ).fetchone()
        assert saved["raw_mime"] is None and saved["blob_ref"] is not None
    query = SearchRequest(query="pdfonlyproof", include_documents=True)
    assert store.search(ctx, query) == []
    jobs = DocumentJobs(store, processor.processor_version)
    job = jobs.enqueue(
        Principal(ctx, "human"), account, receipt, processor.processor_version, POLICY, uuid4()
    )
    path, config, _, token = document_files(
        tmp_path,
        ctx.tenant_id,
        ctx.actor_id,
        account,
        "sha256:" + processor.processor_version.removeprefix("sandbox-pdf-v1-"),
    )
    config.update(blob_root=str(root), keys_file=str(path.parent / "keys.json"))
    private_write(path, config)
    private_write(
        path.parent / "keys.json",
        {"tenant_id": str(ctx.tenant_id), "keys": [{"key_id": "pdf-key", "key_hex": key.hex()}]},
    )

    def invoke(*extra):
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "email_brain.cli",
                "process-documents",
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
        for secret in (token, key.hex(), store.dsn, str(account), "pdfonlyproof"):
            assert secret not in result.stdout
        return json.loads(result.stdout)

    assert invoke("--check") == {
        "configuration_valid": True,
        "execution_verified": False,
        "claims": 0,
    }
    assert jobs.get(ctx, account, job["id"])["attempts"] == 0
    assert invoke()["results"]["completed"] == 1
    assert invoke()["results"]["no_result"] == 1
    status = jobs.get(ctx, account, job["id"])
    assert status["attempts"] == 1 and status["status"] == "completed"
    hits = store.search(ctx, query)
    assert len(hits) == 1 and hits[0]["document_id"] == status["extraction_id"]
    evidence = store.document_evidence(ctx, status["extraction_id"])
    assert evidence["scanner_status"] == "unscanned"
    assert "pdfonlyproof" in evidence["pages"][0]["excerpt"]
    assert store.load_raw(ctx, account, saved["blob_ref"]["sha256"]) == raw
    with store.transaction(ctx) as conn:
        assert (
            conn.execute(
                "SELECT count(*) AS n FROM document_extractions WHERE account_id=%s", (account,)
            ).fetchone()["n"]
            == 1
        )
        assert (
            conn.execute(
                "SELECT opaque_cursor FROM sync_cursors WHERE account_id=%s", (account,)
            ).fetchone()["opaque_cursor"]
            == "pdf-cli-ready"
        )
