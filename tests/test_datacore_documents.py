from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from email_brain.synthetic_formats import SHEET_TYPE, WORD_TYPE, docx_bytes, pdf_bytes, xlsx_bytes
from masterbrain.datacore.contracts import stable_id
from masterbrain.datacore.document_contract import (
    CONTRACT,
    PDF_TYPE,
    DocumentResult,
    DocumentUnavailable,
    decode_request,
    decode_result,
    encode_request,
    encode_result,
    source_for,
)
from masterbrain.datacore.document_worker import extract_document, process_request
from masterbrain.datacore.extraction import (
    ExtractionStatus,
    extract_document_source_version,
)
from masterbrain.datacore.fileos import snapshot_tree


def source(raw: bytes, name: str, media_type: str):
    digest = hashlib.sha256(raw).hexdigest()
    item_id = stable_id("item", "files_documents", name)
    version_id = stable_id("version", item_id, digest, str(len(raw)))
    return source_for(raw, version_id, name, digest, media_type)


class DirectSyntheticProcessor:
    processor_version = CONTRACT + "-synthetic-unit"

    def extract(
        self,
        raw: bytes,
        *,
        version_id: str,
        locator: str,
        sha256: str,
        media_type: str,
    ) -> DocumentResult:
        return extract_document(raw, source_for(raw, version_id, locator, sha256, media_type))


@pytest.mark.parametrize(
    "name,media_type,raw,marker,reason",
    [
        (
            "report.pdf",
            PDF_TYPE,
            pdf_bytes(("datacore pdf proof",)),
            "datacore pdf proof",
            "bounded_pdf_v1",
        ),
        (
            "memo.docx",
            WORD_TYPE,
            docx_bytes("datacore word proof"),
            "datacore word proof",
            "bounded_docx_v1",
        ),
        (
            "rent.xlsx",
            SHEET_TYPE,
            xlsx_bytes("Synthetic Atlas", 2450, 3, "datacoresheetproof"),
            "datacoresheetproof",
            "bounded_xlsx_v1",
        ),
    ],
)
def test_real_synthetic_documents_round_trip_closed_contract(
    name: str, media_type: str, raw: bytes, marker: str, reason: str
) -> None:
    expected = source(raw, name, media_type)
    request = encode_request(raw, expected.version_id, name, expected.sha256, media_type)
    decoded_raw, decoded_source = decode_request(request)
    assert decoded_raw == raw and decoded_source == expected
    result = decode_result(process_request(request), expected)
    assert result.status == "extracted" and result.reason == reason
    assert marker in result.text and result.scanner_status == "unscanned"


def test_contract_rejects_source_tampering_unknown_fields_and_bad_results() -> None:
    raw = docx_bytes("contract proof")
    expected = source(raw, "memo.docx", WORD_TYPE)
    request = json.loads(
        encode_request(raw, expected.version_id, expected.locator, expected.sha256, WORD_TYPE)
    )
    request["source"]["sha256"] = "0" * 64
    with pytest.raises(DocumentUnavailable):
        decode_request(json.dumps(request).encode())
    request["source"]["sha256"] = expected.sha256
    request["extra"] = True
    with pytest.raises(DocumentUnavailable):
        decode_request(json.dumps(request).encode())

    good = extract_document(raw, expected)
    result = json.loads(encode_result(good))
    result["scanner_status"] = "safe"
    with pytest.raises(DocumentUnavailable):
        decode_result(json.dumps(result).encode(), expected)
    with pytest.raises(DocumentUnavailable):
        source_for(raw, expected.version_id, "../memo.docx", expected.sha256, WORD_TYPE)


def test_mixed_text_and_image_only_pdf_defers_instead_of_claiming_complete(
    tmp_path: Path,
) -> None:
    from pypdf import PdfReader, PdfWriter

    text_page = pdf_bytes(("fictional statement total 100",))
    image_page = pdf_bytes(rgb=bytes([255, 255, 255]) * (64 * 32))
    writer = PdfWriter()
    writer.append(PdfReader(BytesIO(text_page)))
    writer.append(PdfReader(BytesIO(image_page)))
    output = BytesIO()
    writer.write(output)
    raw = output.getvalue()
    expected = source(raw, "mixed-statement.pdf", PDF_TYPE)

    result = decode_result(
        process_request(encode_request(raw, expected.version_id, expected.locator,
                                       expected.sha256, PDF_TYPE)),
        expected,
    )
    assert (result.status, result.reason, result.text) == (
        "deferred", "pages_without_text", "",
    )
    assert result.metadata.page_count == 2

    path = tmp_path / "mixed-statement.pdf"
    path.write_bytes(raw)
    item = snapshot_tree(
        tmp_path, source_id="files_documents", observed_at=datetime(2026, 10, 15, tzinfo=UTC)
    )["items"][0]
    extraction = extract_document_source_version(tmp_path, item, DirectSyntheticProcessor())
    assert (extraction.status, extraction.error_code, extraction.text) == (
        ExtractionStatus.DEFERRED, "pages_without_text", "",
    )
    assert path.read_bytes() == raw


def test_entirely_image_only_pdf_remains_deferred() -> None:
    raw = pdf_bytes(rgb=bytes([255, 255, 255]) * (64 * 32))
    result = extract_document(raw, source(raw, "scan.pdf", PDF_TYPE))
    assert (result.status, result.reason, result.text) == ("deferred", "empty_document", "")
    assert result.metadata.page_count == 1


def test_contract_accepts_deterministic_archive_member_version_identity() -> None:
    raw = docx_bytes("archive member identity")
    digest = hashlib.sha256(raw).hexdigest()
    source = source_for(raw, "archiveversion_" + digest[:32], "memo.docx", digest, WORD_TYPE)
    assert source.version_id.startswith("archiveversion_")


def hostile_ooxml(raw: bytes, name: str, payload: bytes) -> bytes:
    output = BytesIO()
    with ZipFile(BytesIO(raw)) as original, ZipFile(output, "w", compression=ZIP_DEFLATED) as new:
        for item in original.infolist():
            new.writestr(item.filename, original.read(item.filename))
        new.writestr(name, payload)
    return output.getvalue()


def test_ooxml_external_relationship_macro_bomb_and_corruption_are_explicit() -> None:
    base = docx_bytes("never silently trust package features")
    external = hostile_ooxml(
        base,
        "word/_rels/document.xml.rels",
        b'<Relationships><Relationship TargetMode="External" Target="https://example.invalid"/></Relationships>',
    )
    macro = hostile_ooxml(base, "word/vbaProject.bin", b"inert-test-marker")
    bomb = hostile_ooxml(base, "word/large.bin", b"0" * (2 * 1024 * 1024))
    assert extract_document(external, source(external, "external.docx", WORD_TYPE)).reason == (
        "unsupported_features"
    )
    assert extract_document(macro, source(macro, "macro.docx", WORD_TYPE)).reason == (
        "unsupported_features"
    )
    assert extract_document(bomb, source(bomb, "bomb.docx", WORD_TYPE)).reason == "structure_limit"
    corrupt = b"PK\x03\x04not-a-valid-office-package"
    result = extract_document(corrupt, source(corrupt, "corrupt.docx", WORD_TYPE))
    assert (result.status, result.reason) == ("failed", "invalid_document")

    corrupt_pdf = b"%PDF-1.7\nnot-a-valid-pdf"
    result = extract_document(corrupt_pdf, source(corrupt_pdf, "corrupt.pdf", PDF_TYPE))
    assert (result.status, result.reason) == ("failed", "invalid_document")


def test_source_rehash_no_mutation_change_and_processor_failure(tmp_path: Path) -> None:
    path = tmp_path / "memo.docx"
    path.write_bytes(docx_bytes("source bound document proof"))
    before = (path.read_bytes(), path.stat().st_mtime_ns)
    manifest = snapshot_tree(
        tmp_path,
        source_id="files_documents",
        observed_at=datetime(2026, 9, 22, tzinfo=UTC),
    )
    item = manifest["items"][0]
    result = extract_document_source_version(tmp_path, item, DirectSyntheticProcessor())
    assert result.status is ExtractionStatus.EXTRACTED
    assert "source bound document proof" in result.text
    assert (path.read_bytes(), path.stat().st_mtime_ns) == before

    path.write_bytes(docx_bytes("changed after snapshot"))
    changed = extract_document_source_version(tmp_path, item, DirectSyntheticProcessor())
    assert (changed.status, changed.error_code) == (ExtractionStatus.CHANGED, "source_changed")

    class Unavailable(DirectSyntheticProcessor):
        def extract(self, *args: object, **kwargs: object) -> DocumentResult:
            raise DocumentUnavailable()

    current = snapshot_tree(
        tmp_path,
        source_id="files_documents",
        observed_at=datetime(2026, 9, 22, 1, tzinfo=UTC),
    )["items"][0]
    failed = extract_document_source_version(tmp_path, current, Unavailable())
    assert (failed.status, failed.error_code) == (ExtractionStatus.FAILED, "processor_unavailable")
