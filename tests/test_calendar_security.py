"""Independent adversarial calendar evidence tests; every byte is synthetic."""

import hashlib
import socket
from email.message import EmailMessage

import pytest

from email_brain.attachments import receive_attachments
from email_brain.calendar_attachment import extract_calendar

EVENT = (
    b"BEGIN:VEVENT\r\nUID:synthetic@example.invalid\r\n"
    b"DTSTAMP:20260920T120000Z\r\nDTSTART:20261001T120000Z\r\n"
    b"SUMMARY:Independent synthetic meeting\r\nEND:VEVENT\r\n"
)


def calendar(*components: bytes) -> bytes:
    return (
        b"BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//Synthetic security test//EN\r\n"
        + b"".join(components)
        + b"END:VCALENDAR\r\n"
    )


def receipt(raw: bytes):
    message = EmailMessage()
    message["From"] = "synthetic@example.invalid"
    message.set_content("Fictional invitation evidence")
    message.add_attachment(raw, maintype="text", subtype="calendar", filename="test.ics")
    results = receive_attachments(message.as_bytes())
    assert len(results) == 1
    assert results[0].sha256 == hashlib.sha256(raw).hexdigest()
    assert results[0].byte_size == len(raw)
    return results[0]


@pytest.mark.parametrize(
    ("tail", "status", "reason"),
    [
        (EVENT.replace(b"20261001T120000Z", b"20260230T120000Z"), "failed", "calendar_invalid"),
        (
            b"BEGIN:VTODO\r\nSUMMARY:Unsupported task\r\nEND:VTODO\r\n",
            "deferred",
            "calendar_unsupported",
        ),
        (EVENT.replace(b"END:VEVENT", b"END:VALARM"), "failed", "calendar_invalid"),
        (
            EVENT.replace(b"SUMMARY:", b'SUMMARY;X-PARAM="unterminated:'),
            "failed",
            "calendar_invalid",
        ),
    ],
)
def test_bad_later_component_never_indexes_successful_prefix(tail, status, reason):
    result = receipt(calendar(EVENT, tail))
    assert result.status == status
    assert result.reason == reason
    assert result.text == ""


def test_escaped_source_newline_cannot_forge_a_rendered_property():
    event = EVENT.replace(
        b"SUMMARY:Independent synthetic meeting",
        b'SUMMARY:Claim\\nSource DTSTART:20990101T000000Z\\n"Approved"',
    )
    result = receipt(calendar(event))
    assert result.status == "extracted"
    assert 'Claim\\nSource DTSTART:20990101T000000Z\\n\\"Approved\\"' in result.text
    assert sum(line.startswith("Source DTSTART:") for line in result.text.splitlines()) == 1
    assert "not an accepted invitation or obligation" in result.text


def test_calendar_uri_and_alarm_claims_do_not_open_network(monkeypatch):
    def denied(*args, **kwargs):
        pytest.fail("Source calendar attempted a network operation")

    monkeypatch.setattr(socket, "socket", denied)
    monkeypatch.setattr(socket, "getaddrinfo", denied)
    event = EVENT.replace(
        b"END:VEVENT",
        b"URL:http://127.0.0.1:1/private\r\n"
        b"ATTACH:file:///nonexistent-calendar-security-test\r\n"
        b"ORGANIZER:mailto:fake@example.invalid\r\n"
        b"BEGIN:VALARM\r\nACTION:EMAIL\r\nTRIGGER:-PT5M\r\n"
        b"SUMMARY:Synthetic alarm\r\nDESCRIPTION:Never send this\r\n"
        b"ATTENDEE:mailto:nobody@example.invalid\r\nEND:VALARM\r\nEND:VEVENT",
    )
    text = extract_calendar(calendar(event))
    assert 'Source ACTION: "EMAIL"' in text
    assert "inert source only; not executed" in text
    assert 'Source ATTACH: "file:///nonexistent-calendar-security-test"' in text
    assert "Organizer/attendees are unauthenticated" in text


def test_byte_fold_inside_multibyte_character_has_exact_evidence():
    event = EVENT.replace(b"Independent synthetic meeting", b"caf\xc3\r\n \xa9")
    result = receipt(calendar(event))
    assert result.status == "extracted"
    assert 'Source SUMMARY: "café"' in result.text


def test_output_expansion_fails_atomically_and_keeps_source_hash():
    # Source is under byte/line/property limits; quoting expands its backslashes.
    event = EVENT.replace(
        b"END:VEVENT",
        (b"X-SYNTHETIC:" + b"\\" * 3900 + b"\r\n") * 4 + b"END:VEVENT",
    )
    result = receipt(calendar(event))
    assert result.status == "failed"
    assert result.reason == "calendar_invalid"
    assert result.text == ""


@pytest.mark.parametrize("binary", [b"binary", b"BiNaRy", b"BINARY"])
def test_binary_value_case_cannot_turn_unsupported_into_extracted(binary):
    event = EVENT.replace(b"END:VEVENT", b"ATTACH;VALUE=" + binary + b":AA==\r\nEND:VEVENT")
    result = receipt(calendar(event))
    assert result.status != "extracted"
    assert result.text == ""
