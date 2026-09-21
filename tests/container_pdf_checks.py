"""Explicit real restricted-image PDF tests; not ordinary test discovery."""

import os

import pytest
from pdf_samples import mail_packet, variant

from email_brain.attachments import receive_attachments
from email_brain.pdf_contract import PdfUnavailable
from email_brain.pdf_processor import DockerPdfProcessor
from email_brain.synthetic_mailbox import project_events


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
    # No mutation of ingestion receipts: integration still requires its own approved design.
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
