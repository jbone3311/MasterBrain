"""Calendar attachment extraction reaches durable evidence/search, without calendar actions."""

from datetime import UTC, datetime
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from uuid import uuid4

import pytest
from test_postgres import database as database
from test_postgres import tenant as tenant

from email_brain.attachments import receive_attachments
from email_brain.schemas import SearchRequest
from email_brain.store import IngestItem

CALENDAR = (
    b"BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//Synthetic Email Brain//EN\r\n"
    b"METHOD:REQUEST\r\nBEGIN:VEVENT\r\nUID:synthetic-event@example.invalid\r\n"
    b"DTSTAMP:20260920T120000Z\r\nDTSTART;TZID=America/Los_Angeles:20261001T093000\r\n"
    b"DTEND;TZID=America/Los_Angeles:20261001T100000\r\n"
    b"SUMMARY:calendaruniquefind planning\r\nDESCRIPTION:No real meeting\r\n"
    b"END:VEVENT\r\nEND:VCALENDAR\r\n"
)


def mime(raw=CALENDAR, *, filename=True, method="REQUEST", charset="utf-8"):
    message = EmailMessage()
    message["From"] = "sender@example.invalid"
    message["Subject"] = "Synthetic calendar envelope"
    message.set_content("Attached event evidence only")
    if filename:
        message.add_attachment(raw, maintype="text", subtype="calendar", filename="invite.ics")
        part = message.get_payload()[-1]
    else:
        message.add_alternative(raw, maintype="text", subtype="calendar")
        part = message.get_payload()[-1]
    part.set_param("method", method)
    part.set_param("charset", charset)
    return message.as_bytes()


@pytest.mark.parametrize("filename", [True, False])
def test_calendar_file_and_inline_body_are_searchable_evidence(filename):
    receipt = receive_attachments(mime(filename=filename))
    assert len(receipt) == 1 and receipt[0].status == "extracted"
    assert receipt[0].reason == "bounded_calendar_v1"
    assert receipt[0].safe_filename.endswith(".ics")
    assert "calendaruniquefind" in receipt[0].text
    assert "America/Los_Angeles" in receipt[0].text


def test_inconsistent_mime_method_is_not_successful_extraction():
    receipt = receive_attachments(mime(method="CANCEL"))[0]
    assert receipt.status == "failed" and receipt.reason == "calendar_invalid"
    assert receipt.text == ""


def test_calendar_non_utf8_declaration_is_explicitly_deferred():
    receipt = receive_attachments(mime(charset="utf-16"))[0]
    assert receipt.status == "deferred" and receipt.reason == "calendar_unsupported_charset"


def test_calendar_ascii_declaration_cannot_hide_non_ascii_source():
    raw = CALENDAR.replace(b"No real meeting", "Café meeting".encode())
    receipt = receive_attachments(mime(raw, charset="us-ascii"))[0]
    assert receipt.status == "failed" and receipt.reason == "calendar_invalid"


def test_malformed_transfer_encoding_is_not_successful_calendar_extraction():
    message = BytesParser(policy=policy.default).parsebytes(mime())
    part = message.get_payload()[-1]
    part.set_payload("!!" + part.get_payload())
    receipt = receive_attachments(message.as_bytes())[0]
    assert receipt.status == "failed" and receipt.reason == "calendar_invalid"


@pytest.mark.postgres
def test_calendar_ingestion_search_evidence_replay_and_historical_preservation(database, tenant):
    store, _ = database
    ctx, account = tenant
    raw = mime(filename=False)
    first = IngestItem(
        "calendar-1", "calendar-message", "1", datetime(2026, 9, 20, tzinfo=UTC), raw
    )
    assert store.ingest_page(ctx, account, None, "calendar-cursor-1", [first]) == 1
    assert store.ingest_page(ctx, account, None, "calendar-cursor-1", [first]) == 0
    hits = store.search(ctx, SearchRequest(query="calendaruniquefind"))
    assert len(hits) == 1 and hits[0]["result_type"] == "attachment"
    evidence = store.evidence(ctx, hits[0]["evidence_id"])
    assert evidence["parser_version"] == "stdlib-mime-v4"
    assert evidence["attachments"][0]["reason"] == "bounded_calendar_v1"
    assert "calendaruniquefind" in evidence["attachments"][0]["excerpt"]
    assert evidence["attachments"][0]["scanner_status"] == "not_scanned"
    assert evidence["attachment_accounting"]["ready"] is True
    # A malformed later invitation is preserved as failed attachment evidence,
    # not a meeting update, and cannot keep old attachment text current in search.
    broken = IngestItem(
        "calendar-2",
        "calendar-message",
        "2",
        datetime(2026, 9, 20, tzinfo=UTC),
        mime(b"BEGIN:VCALENDAR\r\nmalformed\r\n"),
    )
    store.ingest_page(ctx, account, "calendar-cursor-1", "calendar-cursor-2", [broken])
    assert not store.search(ctx, SearchRequest(query="calendaruniquefind"))
    assert store.evidence(ctx, hits[0]["evidence_id"]) == evidence
    current = store.search(ctx, SearchRequest(query="envelope", include_attachments=False))[0]
    current_evidence = store.evidence(ctx, current["evidence_id"])
    assert current_evidence["attachments"][0]["status"] == "failed"
    assert current_evidence["attachment_accounting"]["ready"] is False
    with store.transaction(ctx) as conn:
        assert conn.execute("SELECT count(*) AS n FROM raw_objects").fetchone()["n"] == 2
        assert conn.execute("SELECT count(*) AS n FROM messages WHERE deleted").fetchone()["n"] == 0


@pytest.mark.postgres
def test_realistic_fixture_corpus_preserves_bytes_and_expected_outcomes(database, tenant):
    import hashlib

    from attachment_samples import attachment_cases

    store, _ = database
    ctx, account = tenant
    cases = attachment_cases()
    items = [
        IngestItem(str(uuid4()), case.name, "1", datetime(2026, 9, 20, tzinfo=UTC), case.raw)
        for case in cases
    ]
    assert store.ingest_page(ctx, account, None, "format-corpus-1", items) == len(cases)
    with store.transaction(ctx) as conn:
        for case in cases:
            raw = conn.execute(
                "SELECT raw_mime FROM raw_objects WHERE sha256=%s",
                (hashlib.sha256(case.raw).hexdigest(),),
            ).fetchone()
            assert bytes(raw["raw_mime"]) == case.raw
            receipts = conn.execute(
                "SELECT a.* FROM attachment_receipts a JOIN message_versions v "
                "ON v.tenant_id=a.tenant_id AND v.id=a.evidence_id JOIN messages m "
                "ON m.tenant_id=v.tenant_id AND m.id=v.message_id WHERE m.provider_message_id=%s "
                "ORDER BY a.part_id",
                (case.name,),
            ).fetchall()
            assert len(receipts) == len(case.attachments)
            for expected in case.attachments:
                actual = next(r for r in receipts if r["original_filename"] == expected.filename)
                assert actual["status"] == expected.expected_status
                if expected.media_type != "message/rfc822":
                    assert actual["sha256"] == expected.sha256
                if expected.expected_status != "extracted":
                    assert actual["extracted_text"] == ""
