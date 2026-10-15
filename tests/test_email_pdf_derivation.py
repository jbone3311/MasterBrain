"""Fictional exact-byte Email attachment PDF derivation, without live mail."""

from __future__ import annotations

import hashlib
from io import BytesIO

import pytest
from pdf_samples import mail_packet, variant
from pypdf import PdfReader, PdfWriter
from test_sandbox_runner import IMAGE, fake_docker

from email_brain.document_jobs import POLICY
from email_brain.pdf_contract import decode_result, encode_request
from email_brain.pdf_processor import DockerPdfProcessor
from email_brain.pdf_worker import process_request
from email_brain.synthetic_formats import pdf_bytes
from masterbrain.datacore.email_pdf_derivation import (
    EmailAttachmentPdfUnavailable,
    prove_email_attachment_pdf_derivation,
)
from masterbrain.datacore.persistence import EMAIL_DOCUMENT_NORMALIZER_PREFIX


def _basis(raw: bytes, source, result, processor: DockerPdfProcessor) -> dict:
    text = "\n".join(page.text for page in result.pages)
    return {
        "raw_sha256": source.raw_sha256,
        "raw_size_bytes": len(raw),
        "part_path": source.part_path,
        "part_sha256": source.part_sha256,
        "text": text,
        "text_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "normalizer": (
            f"{EMAIL_DOCUMENT_NORMALIZER_PREFIX}:{processor.processor_version}:{POLICY}"
        ),
        "processor": processor,
    }


def _prepared(monkeypatch: pytest.MonkeyPatch, document: bytes):
    raw, source, request = mail_packet(document)
    response = process_request(request)
    result = decode_result(response, source)
    processor, calls, _ = fake_docker(
        monkeypatch, processor=DockerPdfProcessor(IMAGE), output=response,
    )
    return raw, source, result, calls, _basis(raw, source, result, processor)


def _two_page_pdf() -> bytes:
    writer = PdfWriter()
    for line in ("fictional first page", "fictional second page"):
        writer.add_page(PdfReader(BytesIO(pdf_bytes((line,))), strict=True).pages[0])
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def test_exact_two_page_attachment_proof_is_content_free(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw, source, result, calls, basis = _prepared(
        monkeypatch, _two_page_pdf(),
    )
    assert result.status == "extracted" and result.page_count == 2
    proof = prove_email_attachment_pdf_derivation(raw, **basis)
    assert proof.raw_sha256 == source.raw_sha256
    assert proof.raw_size_bytes == len(raw)
    assert proof.part_path == "1.2"
    assert proof.part_sha256 == source.part_sha256
    assert proof.text_sha256 == basis["text_sha256"]
    assert proof.page_count == 2
    assert len(calls) > 0
    assert "fictional first page" not in repr(proof)


def test_same_pdf_in_two_mime_occurrences_keeps_parent_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document = variant("text")
    raw, source, result, _, basis = _prepared(monkeypatch, document)
    first = prove_email_attachment_pdf_derivation(raw, **basis)
    other = raw.replace(b"Synthetic PDF receipt", b"Another fictional message", 1)
    assert other != raw
    other_source = type(source)(hashlib.sha256(other).hexdigest(), "1.2", source.part_sha256)
    request = encode_request(other, "1.2", source.part_sha256)
    second_response = process_request(request)
    second_processor, _, _ = fake_docker(
        monkeypatch, processor=DockerPdfProcessor(IMAGE), output=second_response,
    )
    other_basis = _basis(other, other_source, result, second_processor)
    second = prove_email_attachment_pdf_derivation(other, **other_basis)
    assert first.part_sha256 == second.part_sha256
    assert first.raw_sha256 != second.raw_sha256


@pytest.mark.parametrize("field,value", [
    ("raw_size_bytes", 0),
    ("raw_sha256", "0" * 64),
    ("part_path", "1.3"),
    ("part_sha256", "0" * 64),
    ("text", "invented source text"),
    ("text_sha256", "0" * 64),
    ("normalizer", "email-pdf-v1:sandbox-pdf-v1-" + "0" * 64 + ":" + POLICY),
])
def test_changed_basis_refuses_without_content_or_diagnostics(
    monkeypatch: pytest.MonkeyPatch, field: str, value: object,
) -> None:
    raw, _, _, _, basis = _prepared(monkeypatch, variant("text"))
    basis[field] = value
    with pytest.raises(EmailAttachmentPdfUnavailable) as error:
        prove_email_attachment_pdf_derivation(raw, **basis)
    assert str(error.value) == "email_attachment_pdf_derivation_unavailable"


def test_changed_parent_mime_refuses_before_processor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw, _, _, calls, basis = _prepared(monkeypatch, variant("text"))
    with pytest.raises(EmailAttachmentPdfUnavailable):
        prove_email_attachment_pdf_derivation(raw + b"changed", **basis)
    assert calls == []


@pytest.mark.parametrize("kind", ["partial", "image", "encrypted"])
def test_incomplete_or_unreadable_pdf_cannot_claim_complete_text(
    monkeypatch: pytest.MonkeyPatch, kind: str,
) -> None:
    raw, _, result, _, basis = _prepared(monkeypatch, variant(kind))
    assert result.status != "extracted"
    basis["text"] = "invented complete text"
    basis["text_sha256"] = hashlib.sha256(b"invented complete text").hexdigest()
    with pytest.raises(EmailAttachmentPdfUnavailable):
        prove_email_attachment_pdf_derivation(raw, **basis)
