"""Known-answer and hostile-contract tests; in-process inputs are synthetic only."""

import base64
import hashlib
import json
import sys
from dataclasses import replace
from email.message import EmailMessage
from io import BytesIO
from unittest.mock import Mock

import pytest
from pdf_samples import mail_packet, variant

from email_brain import pdf_contract as contract
from email_brain import pdf_worker as worker
from email_brain.attachments import receive_attachments
from email_brain.pdf_contract import (
    PdfPage,
    PdfResult,
    PdfSource,
    PdfUnavailable,
    decode_request,
    decode_result,
    encode_request,
    encode_result,
    source_for,
)
from email_brain.synthetic_mailbox import project_events, project_facts


def result(kind="text"):
    raw, source, request = mail_packet(variant(kind))
    return raw, source, decode_result(worker.process_request(request), source)


def test_text_pages_source_hashes_and_no_scanner_claim():
    raw, source, parsed = result()
    assert parsed.source == source
    assert parsed.status == "extracted" and parsed.reason == "bounded_pdf_v1"
    assert parsed.page_count == 1 and parsed.pages[0].number == 1
    assert "pdfonlyproof known invoice USD 1234.50" in parsed.pages[0].text
    assert parsed.scanner_status == "unscanned"
    receipt = receive_attachments(raw)[0]
    assert receipt.sha256 == source.part_sha256
    assert receipt.status == "deferred" and receipt.text == ""


@pytest.mark.parametrize(
    "kind,status,reason,count",
    [
        ("image", "deferred", "no_text", 1),
        ("damaged", "failed", "invalid_pdf", None),
        ("encrypted", "deferred", "encrypted", None),
        ("empty_password", "deferred", "encrypted", None),
        ("pages", "deferred", "page_limit", None),
        ("annotation", "deferred", "unsupported_features", 1),
        ("active", "deferred", "unsupported_features", None),
        ("form", "deferred", "unsupported_features", None),
        ("names", "deferred", "unsupported_features", None),
        ("zero_pages", "failed", "invalid_pdf", None),
        ("stream", "deferred", "stream_limit", 1),
        ("text_limit", "deferred", "text_limit", 1),
    ],
)
def test_explicit_non_success_without_partial_text(kind, status, reason, count):
    _, _, parsed = result(kind)
    assert (parsed.status, parsed.reason, parsed.page_count) == (status, reason, count)
    assert parsed.pages == () and parsed.scanner_status == "unscanned"


def test_mixed_document_is_partial_with_page_order_not_silently_complete():
    _, _, parsed = result("partial")
    assert parsed.status == "partial" and parsed.reason == "pages_without_text"
    assert parsed.page_count == 2
    assert "pdfonlyproof" in parsed.pages[0].text
    assert parsed.pages[1] == PdfPage(2, "")


def test_known_answer_mailbox_pdfs_match_authored_values():
    checked = 0
    facts = project_facts(42, 0)
    for event in project_events(42, 0):
        if event.kind != "created":
            continue
        receipts = receive_attachments(event.item.raw)
        for receipt in receipts:
            if receipt.media_type != "application/pdf":
                continue
            source = source_for(event.item.raw, receipt.part_id, receipt.sha256)
            parsed = decode_result(
                worker.process_request(
                    encode_request(event.item.raw, receipt.part_id, receipt.sha256)
                ),
                source,
            )
            authored = next(
                file for file in event.attachments if file.name == receipt.original_filename
            )
            if authored.known_text:
                assert parsed.status == "extracted"
                assert authored.known_text in "\n".join(page.text for page in parsed.pages)
                assert str(facts["rent_v1_usd"]) in parsed.pages[0].text
            elif authored.name == "invoice.pdf":
                assert parsed.status == "extracted"
                amount = facts["invoice_cents"]
                assert f"Invoice USD {amount // 100}.{amount % 100:02d}" in parsed.pages[0].text
            elif authored.well_formed:
                assert parsed.reason == "no_text"
            else:
                assert parsed.reason == "invalid_pdf"
            checked += 1
    assert checked == 4


@pytest.mark.parametrize(
    "field,value",
    [
        ("part_path", "1.1"),
        ("part_path", "1.3"),
        ("part_sha256", "a" * 64),
        ("raw_sha256", "b" * 64),
        ("contract_version", "sandbox-mime-v1"),
        ("extra", "private"),
        ("raw_base64", "%%%"),
        ("raw_base64", "YQ==\n"),
        ("raw_base64", ["invalid"]),
    ],
)
def test_request_or_part_substitution_never_reaches_reader(monkeypatch, field, value):
    _, _, request = mail_packet(variant("text"))
    changed = json.loads(request)
    changed[field] = value
    extract = Mock(side_effect=AssertionError("must not parse"))
    monkeypatch.setattr(worker, "_extract", extract)
    with pytest.raises(PdfUnavailable, match="^pdf_processing_unavailable$"):
        worker.process_request(json.dumps(changed).encode())
    extract.assert_not_called()


@pytest.mark.parametrize("media,filename", [("octet-stream", "document.pdf"), ("pdf", "bad.exe")])
def test_misleading_or_active_attachment_receipt_is_not_pdf_authority(media, filename):
    _, _, request = mail_packet(variant("text"), media=media, filename=filename)
    with pytest.raises(PdfUnavailable):
        worker.process_request(request)


def test_body_pdf_and_nested_message_cannot_be_selected_as_unreceipted_attachment():
    data = variant("text")
    mail = EmailMessage()
    mail.set_content(data, maintype="application", subtype="pdf")
    raw = mail.as_bytes()
    with pytest.raises(PdfUnavailable):
        worker.process_request(encode_request(raw, "1", hashlib.sha256(data).hexdigest()))
    nested = EmailMessage()
    nested.set_content("outer body")
    nested.add_attachment(mail)
    raw = nested.as_bytes()
    with pytest.raises(PdfUnavailable):
        worker.process_request(encode_request(raw, "1.2.1", hashlib.sha256(data).hexdigest()))


@pytest.mark.parametrize(
    "raw,path,digest",
    [
        (b"", "1.2", "a" * 64),
        ("mail", "1.2", "a" * 64),
        (b"mail", "../1.2", "a" * 64),
        (b"mail", "1.0", "a" * 64),
        (b"mail", "1.02", "a" * 64),
        (b"mail", "1.2\n", "a" * 64),
        (b"mail", "1" + ".1" * 21, "a" * 64),
        (b"mail", "1.2", "A" * 64),
        (b"mail", "1.2", "a" * 64 + "\n"),
        (b"mail", True, "a" * 64),
    ],
)
def test_input_types_and_identity_bounds(raw, path, digest):
    with pytest.raises(PdfUnavailable):
        encode_request(raw, path, digest)


def test_raw_and_encoded_request_size_boundaries(monkeypatch):
    raw, _, request = mail_packet(variant("text"))
    monkeypatch.setattr(contract, "MAX_MIME_BYTES", len(raw))
    assert decode_request(request)[0] == raw
    with pytest.raises(PdfUnavailable):
        encode_request(raw + b"x", "1.2", "a" * 64)
    monkeypatch.setattr(contract, "MAX_REQUEST_BYTES", len(request) - 1)
    with pytest.raises(PdfUnavailable):
        decode_request(request)


@pytest.mark.parametrize(
    "budget",
    [
        "MAX_PDF_BYTES",
        "MAX_PAGE_CHARS",
        "MAX_TOTAL_CHARS",
        "MAX_PAGE_STREAM_BYTES",
        "MAX_TOTAL_STREAM_BYTES",
    ],
)
def test_every_document_budget_discards_partial_results(monkeypatch, budget):
    monkeypatch.setattr(worker, budget, 1)
    _, _, parsed = result()
    expected = {
        "MAX_PDF_BYTES": "pdf_byte_limit",
        "MAX_PAGE_CHARS": "text_limit",
        "MAX_TOTAL_CHARS": "text_limit",
        "MAX_PAGE_STREAM_BYTES": "stream_limit",
        "MAX_TOTAL_STREAM_BYTES": "stream_limit",
    }
    assert parsed.reason == expected[budget] and parsed.pages == ()


@pytest.mark.parametrize(
    "error",
    [
        MemoryError("private"),
        RecursionError("private"),
        RuntimeError("private"),
        OSError("private"),
    ],
)
def test_unexpected_parser_failure_is_not_cached_as_invalid_pdf(monkeypatch, error):
    import pypdf

    initialize = Mock(side_effect=error)
    monkeypatch.setattr(pypdf.PdfReader, "_initialize_stream", initialize)
    with pytest.raises(PdfUnavailable, match="^pdf_processing_unavailable$"):
        result()
    initialize.assert_called_once()


@pytest.mark.parametrize("kind", ["encrypted", "empty_password"])
def test_encrypted_pdf_never_attempts_even_an_empty_password(monkeypatch, kind):
    from pypdf._encryption import Encryption

    _, source, request = mail_packet(variant(kind))
    read_encryption = Mock(side_effect=AssertionError("must not read encryption or try passwords"))
    monkeypatch.setattr(Encryption, "read", read_encryption)
    parsed = decode_result(worker.process_request(request), source)
    assert parsed.reason == "encrypted"
    read_encryption.assert_not_called()


def test_missing_or_wrong_dependency_version_is_infrastructure_failure(monkeypatch):
    import pypdf

    monkeypatch.setattr(pypdf, "__version__", "0.0.0")
    with pytest.raises(PdfUnavailable):
        result()


@pytest.mark.parametrize(
    "mutation",
    [
        lambda v: v.update(extra="private"),
        lambda v: v.update(contract_version="wrong"),
        lambda v: v["source"].update(part_path="1.3"),
        lambda v: v["source"].update(part_sha256="c" * 64),
        lambda v: v["source"].update(raw_sha256="c" * 64),
        lambda v: v["source"].update(extra="private"),
        lambda v: v.update(scanner_status="clean"),
        lambda v: v.update(status="success"),
        lambda v: v.update(reason="unknown"),
        lambda v: v.update(page_count=True),
        lambda v: v.update(page_count=0),
        lambda v: v.update(page_count=41),
        lambda v: v.update(page_count=2),
        lambda v: v.update(page_count=None),
        lambda v: v.update(pages=[]),
        lambda v: v["pages"][0].update(number=True),
        lambda v: v["pages"][0].update(number=2),
        lambda v: v["pages"][0].update(extra="x"),
        lambda v: v["pages"][0].update(text=""),
        lambda v: v["pages"][0].update(text=" leading"),
        lambda v: v["pages"][0].update(text="nul\u0000"),
        lambda v: v["pages"][0].update(text="\ud800"),
        lambda v: v["pages"][0].update(text="x" * 20001),
        lambda v: v.update(status="deferred", reason="no_text"),
        lambda v: v.update(status="partial", reason="pages_without_text"),
    ],
)
def test_child_output_closed_schema_binding_and_consistency(mutation):
    _, source, parsed = result()
    payload = json.loads(encode_result(parsed))
    mutation(payload)
    with pytest.raises(PdfUnavailable):
        decode_result(json.dumps(payload).encode(), source)


@pytest.mark.parametrize(
    "payload",
    [b"", b"[]", b"null", b"\xff", b'{"a":1,"a":2}', b'{"a":NaN}', b"[" * 1000, b"{} trailing"],
)
def test_request_and_response_json_pressure(payload):
    source = PdfSource("a" * 64, "1.2", "b" * 64)
    with pytest.raises(PdfUnavailable):
        decode_request(payload)
    with pytest.raises(PdfUnavailable):
        decode_result(payload, source)


def test_result_total_character_and_output_byte_bounds(monkeypatch):
    _, source, parsed = result()
    pages = tuple(PdfPage(i, "x" * 20000) for i in range(1, 7))
    with pytest.raises(PdfUnavailable):
        decode_result(encode_result(replace(parsed, page_count=6, pages=pages)), source)
    payload = encode_result(parsed)
    monkeypatch.setattr(contract, "MAX_OUTPUT_BYTES", len(payload) - 1)
    with pytest.raises(PdfUnavailable):
        decode_result(payload, source)


def test_source_dataclass_cannot_accept_invalid_identity():
    with pytest.raises(PdfUnavailable):
        PdfSource("invalid", "1.2", "b" * 64)


def test_noncanonical_base64_padding_is_refused():
    payload = {
        "contract_version": contract.CONTRACT,
        "raw_sha256": hashlib.sha256(b"a").hexdigest(),
        "part_path": "1.2",
        "part_sha256": "b" * 64,
        "raw_base64": "YR==",
    }
    assert base64.b64decode("YR==") == b"a"
    with pytest.raises(PdfUnavailable):
        decode_request(json.dumps(payload).encode())


def test_child_entrypoint_applies_limits_before_read_and_returns_scrubbed_error(monkeypatch):
    events = []
    monkeypatch.setattr(worker, "_resource_limits", lambda: events.append("limits"))
    stream = Mock()
    stream.buffer.read.side_effect = lambda size: (events.append("read"), b"invalid")[1]
    monkeypatch.setattr(sys, "stdin", stream)
    monkeypatch.setattr(sys, "stdout", Mock(buffer=BytesIO()))
    monkeypatch.setattr(worker.logging, "disable", lambda value: None)
    assert worker.main() == 70
    assert events == ["limits", "read"]
    stream.buffer.read.assert_called_once_with(contract.MAX_REQUEST_BYTES + 1)


def test_worker_output_envelope_overflow_becomes_explicit_deferral(monkeypatch):
    _, source, request = mail_packet(variant("text"))
    huge = PdfResult(
        source,
        "extracted",
        "bounded_pdf_v1",
        5,
        tuple(PdfPage(i, "\U0001f600" * 20000) for i in range(1, 6)),
    )
    monkeypatch.setattr(worker, "_extract", lambda *_: huge)
    parsed = decode_result(worker.process_request(request), source)
    assert parsed.reason == "text_limit" and parsed.pages == ()
