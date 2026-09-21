"""Explicit real restricted-image PDF tests; not ordinary test discovery."""

import os
from dataclasses import replace
from uuid import uuid4

import pytest
import test_postgres as pg
from pdf_samples import mail_packet, variant

from email_brain.attachments import receive_attachments
from email_brain.auth import Principal
from email_brain.document_jobs import POLICY, DocumentJobs
from email_brain.pdf_contract import PdfUnavailable
from email_brain.pdf_processor import DockerPdfProcessor
from email_brain.schemas import SearchRequest
from email_brain.synthetic_mailbox import project_events

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
