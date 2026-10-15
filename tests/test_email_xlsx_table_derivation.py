"""Fictional, occurrence-bound Email XLSX physical-row proof."""

from __future__ import annotations

import hashlib
from email.message import EmailMessage
from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

import pytest
from openpyxl import Workbook
from test_sandbox_runner import IMAGE, fake_docker

from email_brain.synthetic_formats import SHEET_TYPE
from masterbrain.datacore.contracts import stable_id
from masterbrain.datacore.document_contract import encode_request, source_for
from masterbrain.datacore.document_worker import extract_document
from masterbrain.datacore.email_xlsx_table_derivation import (
    EmailAttachmentXlsxTableUnavailable,
    prove_email_attachment_xlsx_table_derivation,
)
from masterbrain.datacore.xlsx_tables_processor import DockerXlsxTableProcessor
from masterbrain.datacore.xlsx_tables_worker import process_request


def _xlsx(*, blank_row: bool = False, formula: bool = False) -> bytes:
    book = Workbook()
    sheet = book.active
    sheet.append(["Name", "Amount"])
    if blank_row:
        sheet.append([None, None])
    sheet.append(["Fictional", "=1+2" if formula else 100])
    output = BytesIO()
    book.save(output)
    book.close()
    return output.getvalue()


def _mail(document: bytes, subject: str = "Fictional") -> bytes:
    message = EmailMessage()
    message["From"] = "sender@example.invalid"
    message["To"] = "owner@example.invalid"
    message["Subject"] = subject
    message.set_content("Synthetic message")
    message.add_attachment(
        document, maintype="application",
        subtype=SHEET_TYPE.removeprefix("application/"), filename="rent.xlsx",
    )
    message.set_boundary("synthetic-xlsx-table-boundary")
    return message.as_bytes()


def _case(monkeypatch: pytest.MonkeyPatch, *, document: bytes | None = None,
          subject: str = "Fictional"):
    document = document if document is not None else _xlsx()
    raw = _mail(document, subject)
    raw_sha = hashlib.sha256(raw).hexdigest()
    part_sha = hashlib.sha256(document).hexdigest()
    version_id = stable_id("version", raw_sha, "1.2", part_sha)
    source = source_for(document, version_id, "attachment.xlsx", part_sha, SHEET_TYPE)
    normalized = extract_document(document, source)
    response = process_request(encode_request(
        document, version_id, "attachment.xlsx", part_sha, SHEET_TYPE,
    ))
    processor, calls, _ = fake_docker(
        monkeypatch, processor=DockerXlsxTableProcessor(IMAGE), output=response,
    )
    args = {
        "raw_sha256": raw_sha,
        "raw_size_bytes": len(raw),
        "part_path": "1.2",
        "part_sha256": part_sha,
        "text_sha256": hashlib.sha256(normalized.text.encode()).hexdigest(),
        "normalizer": "sandbox-fileos-document-v1-" + "a" * 64,
        "processor": processor,
    }
    return raw, normalized, args, calls


def test_exact_attachment_proves_rows_without_releasing_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw, normalized, args, calls = _case(monkeypatch)
    assert normalized.status == "extracted"
    proof = prove_email_attachment_xlsx_table_derivation(raw, **args)
    assert proof.raw_sha256 == args["raw_sha256"]
    assert proof.part_sha256 == args["part_sha256"]
    assert proof.sheet_count == 1 and proof.row_count == 2 and proof.cell_count == 4
    assert len(proof.row_layout_sha256) == 64
    assert "Fictional" not in repr(proof)
    assert calls


def test_same_bytes_different_email_preserves_occurrence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document = _xlsx()
    raw1, _, args1, _ = _case(monkeypatch, document=document)
    first = prove_email_attachment_xlsx_table_derivation(raw1, **args1)
    raw2, _, args2, _ = _case(monkeypatch, document=document, subject="Other fictional")
    second = prove_email_attachment_xlsx_table_derivation(raw2, **args2)
    assert first.part_sha256 == second.part_sha256
    assert first.raw_sha256 != second.raw_sha256
    assert first.row_layout_sha256 == second.row_layout_sha256


def test_physical_blank_row_differs_even_when_indexed_text_matches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw1, _, args1, _ = _case(monkeypatch, document=_xlsx())
    first = prove_email_attachment_xlsx_table_derivation(raw1, **args1)
    raw2, _, args2, _ = _case(monkeypatch, document=_xlsx(blank_row=True))
    second = prove_email_attachment_xlsx_table_derivation(raw2, **args2)
    assert first.text_sha256 == second.text_sha256
    assert first.row_layout_sha256 != second.row_layout_sha256


@pytest.mark.parametrize("field,value", [
    ("raw_sha256", "0" * 64),
    ("raw_size_bytes", 1),
    ("part_path", "1.3"),
    ("part_sha256", "0" * 64),
    ("text_sha256", "0" * 64),
    ("normalizer", "sandbox-fileos-document-v1-" + "b" * 64),
])
def test_changed_basis_refuses(
    monkeypatch: pytest.MonkeyPatch, field: str, value: object,
) -> None:
    raw, _, args, _ = _case(monkeypatch)
    args[field] = value
    with pytest.raises(EmailAttachmentXlsxTableUnavailable):
        prove_email_attachment_xlsx_table_derivation(raw, **args)


def test_changed_parent_and_formula_refuse(monkeypatch: pytest.MonkeyPatch) -> None:
    raw, _, args, _ = _case(monkeypatch)
    with pytest.raises(EmailAttachmentXlsxTableUnavailable):
        prove_email_attachment_xlsx_table_derivation(raw + b"changed", **args)
    raw_formula, normalized, formula_args, _ = _case(
        monkeypatch, document=_xlsx(formula=True),
    )
    assert normalized.status == "deferred"
    with pytest.raises(EmailAttachmentXlsxTableUnavailable):
        prove_email_attachment_xlsx_table_derivation(raw_formula, **formula_args)


def test_malformed_sheet_refuses(monkeypatch: pytest.MonkeyPatch) -> None:
    document = _xlsx()
    output = BytesIO()
    with ZipFile(BytesIO(document)) as original, ZipFile(output, "w", ZIP_DEFLATED) as changed:
        for item in original.infolist():
            body = original.read(item.filename)
            if item.filename == "xl/worksheets/sheet1.xml":
                body = b"malformed"
            changed.writestr(item, body)
    raw, _, args, _ = _case(monkeypatch, document=output.getvalue())
    with pytest.raises(EmailAttachmentXlsxTableUnavailable):
        prove_email_attachment_xlsx_table_derivation(raw, **args)
