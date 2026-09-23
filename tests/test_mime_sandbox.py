"""Synthetic pure worker/schema tests; real process isolation is verified in CI."""

import hashlib
import io
import json
from dataclasses import replace
from email.message import EmailMessage
from types import SimpleNamespace

import pytest
from attachment_samples import attachment_cases

from email_brain import mime_sandbox as sandbox
from email_brain.attachments import receive_attachments
from email_brain.mime_sandbox import (
    CONTRACT_VERSION,
    MAX_INPUT_BYTES,
    MAX_OUTPUT_BYTES,
    MimeUnavailable,
    decode_response,
    process_raw,
    validate_prepared,
)
from email_brain.normalize import MAX_RAW_BYTES, normalize

RAW = (
    b"From: fixture@example.invalid\r\nTo: owner@example.invalid\r\nSubject: Synthetic\r\n\r\nProof"
)


def attachment_raw():
    mail = EmailMessage()
    mail["From"] = "fixture@example.invalid"
    mail["Subject"] = "Synthetic receipt"
    mail.set_content("Body evidence")
    mail.add_attachment("Attachment evidence", subtype="plain", filename="notes.txt")
    return mail.as_bytes()


def encoded(value):
    return json.dumps(value, separators=(",", ":")).encode("ascii")


def test_normalization_equivalent_to_existing_small_message_path():
    result, attachments, rejected = decode_response(process_raw(RAW), RAW)
    assert result == normalize(RAW)
    assert attachments == receive_attachments(RAW) == []
    assert rejected is False


@pytest.mark.parametrize("case", attachment_cases(), ids=lambda case: case.name)
def test_existing_format_fixtures_preserved(case):
    result, attachments, rejected = decode_response(process_raw(case.raw), case.raw)
    assert result == normalize(case.raw)
    assert attachments == receive_attachments(case.raw)
    assert rejected is False


def test_large_attachment_body_is_normalized_but_binary_remains_deferred():
    mail = EmailMessage()
    mail["Subject"] = "Large synthetic fixture"
    mail.set_content("searchable isolated body proof")
    mail.add_attachment(
        b"%PDF synthetic " + b"x" * MAX_RAW_BYTES,
        maintype="application",
        subtype="pdf",
        filename="large.pdf",
    )
    raw = mail.as_bytes()
    assert MAX_RAW_BYTES < len(raw) < MAX_INPUT_BYTES
    with pytest.raises(ValueError):
        normalize(raw)
    with pytest.raises(ValueError):
        receive_attachments(raw)
    result, attachments, rejected = decode_response(process_raw(raw), raw)
    assert not rejected
    assert "searchable isolated body proof" in result.text
    assert len(attachments) == 1
    assert attachments[0].status == "deferred"
    assert attachments[0].text == ""


def test_max_input_and_output_text_bounds():
    raw = b"x" * MAX_INPUT_BYTES
    result, attachments, rejected = decode_response(process_raw(raw), raw)
    assert not rejected and attachments == []
    assert result.truncated and len(result.text) == 100000
    with pytest.raises(MimeUnavailable):
        process_raw(raw + b"x")


@pytest.mark.parametrize("budget", [0, -1, True, 1.0, "16", MAX_INPUT_BYTES + 1])
def test_explicit_parser_budget_is_bounded(budget):
    for parser in (normalize, receive_attachments):
        with pytest.raises(ValueError):
            parser(RAW, max_raw_bytes=budget)


def test_empty_and_over_complex_mime_are_deterministic_rejections():
    assert decode_response(process_raw(b""), b"") == (None, [], True)
    mail = EmailMessage()
    mail.set_content("Body")
    for index in range(65):
        mail.add_attachment("Synthetic", filename=f"part-{index}.txt")
    raw = mail.as_bytes()
    assert decode_response(process_raw(raw), raw) == (None, [], True)


def test_active_payload_not_executed_or_extracted():
    mail = EmailMessage()
    mail.set_content("Body")
    mail.add_attachment(
        b"#!/bin/sh\ncurl https://example.invalid/private\n",
        maintype="text",
        subtype="plain",
        filename="notes.txt",
    )
    raw = mail.as_bytes()
    _, attachments, rejected = decode_response(process_raw(raw), raw)
    assert not rejected
    assert attachments[0].status == "deferred"
    assert attachments[0].reason == "active_content_quarantined"
    assert attachments[0].text == ""


@pytest.mark.parametrize(
    "mutation",
    [
        {"contract_version": "untrusted-v2"},
        {"raw_sha256": "0" * 64},
        {"outcome": "success"},
        {"outcome": "rejected"},
        {"normalized": None},
        {"attachments": None},
        {"arbitrary_command": "send"},
    ],
)
def test_envelope_mutations_rejected(mutation):
    value = {**json.loads(process_raw(RAW)), **mutation}
    with pytest.raises(MimeUnavailable):
        decode_response(encoded(value), RAW)


@pytest.mark.parametrize(
    "payload",
    [
        b"",
        b"null",
        b"[]",
        b"{}",
        b"garbage",
        b"\xff",
        b"[" * 1200,
        b"{} trailing",
        b"x" * (MAX_OUTPUT_BYTES + 1),
    ],
)
def test_invalid_output_is_scrubbed_infrastructure_failure(payload):
    with pytest.raises(MimeUnavailable, match="^isolated MIME processing unavailable$"):
        decode_response(payload, RAW)


@pytest.mark.parametrize(
    "field,value",
    [
        ("subject", "x" * 2001),
        ("sender", "x" * 321),
        ("text", "x" * 100001),
        ("subject", "private\x00value"),
        ("text", "\ud800"),
        ("internet_message_id", "x" * 1001),
        ("recipients", ["a"] * 101),
        ("recipients", [None]),
        ("recipients", "wrong type"),
        ("raw_sha256", "0" * 64),
        ("truncated", 1),
        ("truncated", True),
        ("subject", None),
    ],
)
def test_normalized_fields_strict(field, value):
    output = json.loads(process_raw(RAW))
    output["normalized"][field] = value
    with pytest.raises(MimeUnavailable):
        decode_response(encoded(output), RAW)


@pytest.mark.parametrize(
    "field,value",
    [
        ("part_id", "../file"),
        ("part_id", "1.0"),
        ("part_id", "1.1001"),
        ("part_id", "1" + ".1" * 21),
        ("original_filename", "x" * 1001),
        ("safe_filename", "../../notes.txt"),
        ("media_type", "text/plain\r\nBad: yes"),
        ("sha256", "x" * 64),
        ("byte_size", True),
        ("byte_size", -1),
        ("byte_size", MAX_INPUT_BYTES + 1),
        ("byte_size", 1.0),
        ("status", "pending"),
        ("reason", "received"),
        ("text", "x" * 20001),
        ("text", "\udfff"),
        ("text", "private\x00value"),
        ("reason", "bounded_calendar_v1"),
    ],
)
def test_attachment_fields_strict(field, value):
    raw = attachment_raw()
    output = json.loads(process_raw(raw))
    output["attachments"][0][field] = value
    with pytest.raises(MimeUnavailable):
        decode_response(encoded(output), raw)


@pytest.mark.parametrize("mutation", ["duplicate", "ancestor", "many", "extra", "wrong_reason"])
def test_attachment_collection_and_semantics(mutation):
    raw = attachment_raw()
    output = json.loads(process_raw(raw))
    attachment = output["attachments"][0]
    if mutation == "duplicate":
        output["attachments"].append(dict(attachment))
    elif mutation == "ancestor":
        output["attachments"].append({**attachment, "part_id": "1"})
    elif mutation == "many":
        output["attachments"] = [attachment] * 65
    elif mutation == "extra":
        attachment["execute"] = "never"
    else:
        attachment["status"] = "deferred"
        attachment["reason"] = "extraction_byte_limit"
        # Unextracted receipts must not smuggle searchable text.
    with pytest.raises(MimeUnavailable):
        decode_response(encoded(output), raw)


@pytest.mark.parametrize("nested", [False, True])
def test_duplicate_json_keys_rejected(nested):
    payload = process_raw(RAW)
    if nested:
        payload = payload.replace(b'"subject":', b'"subject":"forged","subject":', 1)
    else:
        payload = b'{"outcome":"rejected",' + payload[1:]
    with pytest.raises(MimeUnavailable):
        decode_response(payload, RAW)


def test_json_nan_rejected():
    raw = attachment_raw()
    output = json.loads(process_raw(raw))
    output["attachments"][0]["byte_size"] = float("nan")
    with pytest.raises(MimeUnavailable):
        decode_response(encoded(output), raw)


def test_rejected_contract_cannot_include_partial_output():
    output = {
        "contract_version": CONTRACT_VERSION,
        "raw_sha256": hashlib.sha256(RAW).hexdigest(),
        "outcome": "rejected",
        "normalized": None,
        "attachments": [None],
    }
    with pytest.raises(MimeUnavailable):
        decode_response(encoded(output), RAW)


def test_unexpected_parser_failure_is_not_cached_rejection(monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError("SYNTHETIC_PRIVATE_SOURCE_MARKER")

    monkeypatch.setattr(sandbox, "normalize", fail)
    with pytest.raises(MimeUnavailable) as caught:
        process_raw(RAW)
    assert "PRIVATE" not in str(caught.value)


def test_malformed_worker_implementation_result_is_not_rejection(monkeypatch):
    raw = attachment_raw()
    attachments = receive_attachments(raw)
    monkeypatch.setattr(
        sandbox,
        "receive_attachments",
        lambda *a, **k: [replace(attachments[0], status="unexpected")],
    )
    with pytest.raises(MimeUnavailable):
        process_raw(raw)


@pytest.mark.parametrize("bad", ["\ud800", "\x00"])
def test_unpublishable_source_unicode_is_deterministic_rejection(monkeypatch, bad):
    normalized = replace(normalize(RAW), subject=bad)
    monkeypatch.setattr(sandbox, "normalize", lambda *a, **k: normalized)
    assert decode_response(process_raw(RAW), RAW) == (None, [], True)


def test_output_budget_is_infrastructure_failure(monkeypatch):
    monkeypatch.setattr(sandbox, "MAX_OUTPUT_BYTES", 50)
    with pytest.raises(MimeUnavailable):
        process_raw(RAW)


def test_worker_resource_limits_are_hard_and_linux_only(monkeypatch):
    import resource

    calls = []
    monkeypatch.setattr(sandbox.sys, "platform", "linux")
    monkeypatch.setattr(resource, "setrlimit", lambda limit, values: calls.append((limit, values)))
    sandbox._resource_limits()
    assert calls == [
        (resource.RLIMIT_CPU, (10, 10)),
        (resource.RLIMIT_AS, (512 * 1024 * 1024, 512 * 1024 * 1024)),
        (resource.RLIMIT_FSIZE, (0, 0)),
        (resource.RLIMIT_CORE, (0, 0)),
        (resource.RLIMIT_NOFILE, (64, 64)),
    ]
    calls.clear()
    sandbox._resource_limits(max_file_bytes=32 * 1024 * 1024)
    assert calls[2] == (
        resource.RLIMIT_FSIZE,
        (32 * 1024 * 1024, 32 * 1024 * 1024),
    )
    with pytest.raises(MimeUnavailable):
        sandbox._resource_limits(max_file_bytes=32 * 1024 * 1024 + 1)
    monkeypatch.setattr(sandbox.sys, "platform", "darwin")
    with pytest.raises(MimeUnavailable):
        sandbox._resource_limits()


def test_worker_limits_precede_input_and_success_writes_only_json(monkeypatch):
    limited = False

    class Input(io.BytesIO):
        def read(self, size=-1):
            assert limited
            assert size == MAX_INPUT_BYTES + 1
            return super().read(size)

    def limits():
        nonlocal limited
        limited = True

    output = io.BytesIO()
    monkeypatch.setattr(sandbox, "_resource_limits", limits)
    monkeypatch.setattr(sandbox.sys, "stdin", SimpleNamespace(buffer=Input(RAW)))
    monkeypatch.setattr(sandbox.sys, "stdout", SimpleNamespace(buffer=output))
    assert sandbox.main() == 0
    assert decode_response(output.getvalue(), RAW)[0] == normalize(RAW)


def test_worker_failure_emits_no_content(monkeypatch):
    output = io.BytesIO()
    monkeypatch.setattr(sandbox, "_resource_limits", lambda: None)
    monkeypatch.setattr(sandbox.sys, "stdin", SimpleNamespace(buffer=io.BytesIO(RAW)))
    monkeypatch.setattr(sandbox.sys, "stdout", SimpleNamespace(buffer=output))

    def fail(raw):
        raise RuntimeError("SYNTHETIC_PRIVATE_MARKER")

    monkeypatch.setattr(sandbox, "process_raw", fail)
    assert sandbox.main() == 70
    assert output.getvalue() == b""


@pytest.mark.parametrize(
    "payload",
    [
        b"[" * 9 + b"0" + b"]" * 9,
        b"[" + b"{}," * 256 + b"{}]",
        b"[" + b"0," * 4097 + b"0]",
    ],
)
def test_json_structure_budget_precedes_allocation(payload, monkeypatch):
    monkeypatch.setattr(sandbox.json, "loads", lambda *a, **k: pytest.fail("unbounded JSON parse"))
    with pytest.raises(MimeUnavailable):
        decode_response(payload, RAW)


def test_quoted_punctuation_is_not_structural_budget():
    raw = b"Subject: Quoted punctuation\r\n\r\n" + b'[{\\"}]:' * 10000
    normalized, _, rejected = decode_response(process_raw(raw), raw)
    assert not rejected
    assert normalized == normalize(raw)


@pytest.mark.parametrize(
    "changes",
    [
        {"status": "failed", "reason": "calendar_invalid", "text": ""},
        {"status": "skipped", "reason": "inline_image_not_ocr_enabled", "text": ""},
        {"status": "deferred", "reason": "extraction_byte_limit", "text": ""},
        {"byte_size": 262145},
    ],
)
def test_receipt_reason_agrees_with_type_and_budget(changes):
    raw = attachment_raw()
    output = json.loads(process_raw(raw))
    output["attachments"][0].update(changes)
    with pytest.raises(MimeUnavailable):
        decode_response(encoded(output), raw)


def test_prepared_contract_accepts_valid_parsed_and_rejected_values():
    raw = attachment_raw()
    prepared = decode_response(process_raw(raw), raw)
    assert validate_prepared(prepared, raw) == prepared
    assert validate_prepared((None, [], True), b"") == (None, [], True)


@pytest.mark.parametrize(
    "result",
    [
        None,
        [],
        [None, [], True],
        (None, []),
        (None, [], True, None),
        (None, [], False),
        (None, [], 1),
        (None, (), True),
        (None, [None], True),
        ({}, [], False),
        (None, [], None),
    ],
)
def test_prepared_shape_cannot_be_cached_as_rejection(result):
    with pytest.raises(MimeUnavailable):
        validate_prepared(result, RAW)


@pytest.mark.parametrize(
    "case",
    [
        "normal_with_rejected",
        "wrong_hash",
        "null_text",
        "surrogate",
        "many_recipients",
        "recipient_list",
        "bad_recipient",
        "huge_subject",
        "too_many_attachments",
        "non_attachment",
        "duplicate_part",
        "ancestor_part",
        "invalid_status",
    ],
)
def test_prepared_fields_rejected_before_serialization(case, monkeypatch):
    raw = attachment_raw()
    normalized, attachments, rejected = decode_response(process_raw(raw), raw)
    if case == "normal_with_rejected":
        rejected = True
    elif case == "wrong_hash":
        normalized = replace(normalized, raw_sha256="0" * 64)
    elif case == "null_text":
        normalized = replace(normalized, text=None)
    elif case == "surrogate":
        normalized = replace(normalized, text="\ud800")
    elif case == "many_recipients":
        normalized = replace(normalized, recipients=("synthetic",) * 101)
    elif case == "recipient_list":
        normalized = replace(normalized, recipients=["synthetic"])
    elif case == "bad_recipient":
        normalized = replace(normalized, recipients=(None,))
    elif case == "huge_subject":
        normalized = replace(normalized, subject="x" * 1_000_000)
    elif case == "too_many_attachments":
        attachments = attachments * 65
    elif case == "non_attachment":
        attachments = [{}]
    elif case == "duplicate_part":
        attachments = attachments * 2
    elif case == "ancestor_part":
        attachments.append(replace(attachments[0], part_id="1"))
    else:
        attachments = [replace(attachments[0], status="unexpected")]
    monkeypatch.setattr(
        sandbox, "_encode", lambda *args: pytest.fail("serialized malformed output")
    )
    with pytest.raises(MimeUnavailable):
        validate_prepared((normalized, attachments, rejected), raw)


def test_prepared_canonical_output_still_has_byte_budget(monkeypatch):
    prepared = decode_response(process_raw(RAW), RAW)
    monkeypatch.setattr(sandbox, "MAX_OUTPUT_BYTES", 50)
    with pytest.raises(MimeUnavailable):
        validate_prepared(prepared, RAW)


def test_prepared_uninitialized_dataclass_is_scrubbed():
    normalized = object.__new__(sandbox.NormalizedMessage)
    with pytest.raises(MimeUnavailable, match="^isolated MIME processing unavailable$"):
        validate_prepared((normalized, [], False), RAW)
