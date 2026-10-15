"""Fictional source-bound Email XLSX proof with the shared isolated extractor."""

from __future__ import annotations

import hashlib
from email.message import EmailMessage

import pytest
from test_sandbox_runner import IMAGE, fake_docker

from email_brain.synthetic_formats import SHEET_TYPE, xlsx_bytes
from masterbrain.datacore.contracts import stable_id
from masterbrain.datacore.document_contract import decode_result, encode_request, source_for
from masterbrain.datacore.document_processor import DockerDocumentProcessor
from masterbrain.datacore.document_worker import process_request
from masterbrain.datacore.email_xlsx_derivation import (
    EmailAttachmentXlsxUnavailable,
    prove_email_attachment_xlsx_derivation,
)


def _mail(
    document: bytes, *, subject: str = "Fictional rent roll", filename: str = "rent.xlsx"
) -> bytes:
    message = EmailMessage()
    message["From"] = "sender@example.invalid"
    message["To"] = "owner@example.invalid"
    message["Subject"] = subject
    message.set_content("Synthetic message body")
    message.add_attachment(
        document, maintype="application",
        subtype=SHEET_TYPE.removeprefix("application/"), filename=filename,
    )
    message.set_boundary("synthetic-xlsx-boundary")
    return message.as_bytes()


def _prepared(monkeypatch: pytest.MonkeyPatch, *, document: bytes | None = None,
              subject: str = "Fictional rent roll"):
    document = document or xlsx_bytes("Fictional Atlas", 2450, 3, "xlsxproof")
    raw = _mail(document, subject=subject)
    raw_digest = hashlib.sha256(raw).hexdigest()
    part_digest = hashlib.sha256(document).hexdigest()
    version_id = stable_id("version", raw_digest, "1.2", part_digest)
    source = source_for(document, version_id, "attachment.xlsx", part_digest, SHEET_TYPE)
    response = process_request(encode_request(
        document, version_id, "attachment.xlsx", part_digest, SHEET_TYPE,
    ))
    result = decode_result(response, source)
    processor, calls, _ = fake_docker(
        monkeypatch, processor=DockerDocumentProcessor(IMAGE), output=response,
    )
    basis = {
        "raw_sha256": raw_digest,
        "raw_size_bytes": len(raw),
        "part_path": "1.2",
        "part_sha256": part_digest,
        "text": result.text,
        "text_sha256": hashlib.sha256(result.text.encode()).hexdigest(),
        "processor": processor,
    }
    return raw, result, calls, basis


def test_exact_email_attachment_reuses_shared_xlsx_worker_without_publication(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw, result, calls, basis = _prepared(monkeypatch)
    assert result.status == "extracted" and result.reason == "bounded_xlsx_v1"
    assert "xlsxproof" in result.text
    proof = prove_email_attachment_xlsx_derivation(raw, **basis)
    assert proof.raw_sha256 == basis["raw_sha256"]
    assert proof.part_sha256 == basis["part_sha256"]
    assert proof.sheet_count == 1 and proof.cell_count == 8
    assert proof.processor_version == "sandbox-fileos-document-v1-" + "a" * 64
    assert calls and "xlsxproof" not in repr(proof)


def test_same_xlsx_in_distinct_email_occurrences_keeps_parent_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document = xlsx_bytes("Fictional Atlas", 2450, 3, "sharedbytes")
    first_raw, _, _, first_basis = _prepared(monkeypatch, document=document)
    first = prove_email_attachment_xlsx_derivation(first_raw, **first_basis)
    second_raw, _, _, second_basis = _prepared(
        monkeypatch, document=document, subject="Another fictional message",
    )
    second = prove_email_attachment_xlsx_derivation(second_raw, **second_basis)
    assert first.part_sha256 == second.part_sha256
    assert first.raw_sha256 != second.raw_sha256


@pytest.mark.parametrize("field,value", [
    ("raw_sha256", "0" * 64),
    ("raw_size_bytes", 0),
    ("part_path", "1.3"),
    ("part_sha256", "0" * 64),
    ("text", "invented extracted sheet"),
    ("text_sha256", "0" * 64),
])
def test_changed_basis_refuses_before_any_publication(
    monkeypatch: pytest.MonkeyPatch, field: str, value: object,
) -> None:
    raw, _, _, basis = _prepared(monkeypatch)
    basis[field] = value
    with pytest.raises(EmailAttachmentXlsxUnavailable, match="xlsx_derivation_unavailable"):
        prove_email_attachment_xlsx_derivation(raw, **basis)


def test_changed_parent_or_type_refuses_without_opening_worker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw, _, calls, basis = _prepared(monkeypatch)
    for altered in (raw + b"changed", _mail(b"not a workbook", filename="rent.txt")):
        with pytest.raises(EmailAttachmentXlsxUnavailable):
            prove_email_attachment_xlsx_derivation(altered, **basis)
    renamed = _mail(xlsx_bytes("Fictional Atlas", 2450, 3, "xlsxproof"), filename="rent.txt")
    renamed_basis = {
        **basis,
        "raw_sha256": hashlib.sha256(renamed).hexdigest(),
        "raw_size_bytes": len(renamed),
    }
    with pytest.raises(EmailAttachmentXlsxUnavailable):
        prove_email_attachment_xlsx_derivation(renamed, **renamed_basis)
    assert calls == []


def test_uncached_formula_cannot_prove_complete_sheet(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from io import BytesIO
    from zipfile import ZIP_DEFLATED, ZipFile

    good = xlsx_bytes("Fictional Atlas", 2450, 3, "formula")
    output = BytesIO()
    with ZipFile(BytesIO(good)) as original, ZipFile(output, "w", ZIP_DEFLATED) as changed:
        for item in original.infolist():
            raw = original.read(item.filename)
            if item.filename == "xl/worksheets/sheet1.xml":
                raw = raw.replace(b'<c r="B2"><v>2450</v></c>', b'<c r="B2"><f>1+2</f></c>')
            changed.writestr(item, raw)
    raw, result, _, basis = _prepared(monkeypatch, document=output.getvalue())
    assert result.status == "deferred" and result.reason == "unsupported_features"
    basis["text"] = "invented complete sheet"
    basis["text_sha256"] = hashlib.sha256(b"invented complete sheet").hexdigest()
    with pytest.raises(EmailAttachmentXlsxUnavailable):
        prove_email_attachment_xlsx_derivation(raw, **basis)
