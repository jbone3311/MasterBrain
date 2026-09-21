"""Deterministic in-memory format fixtures, not downloaded correspondence.

No application imports: expected MIME structure/content comes from fixture authorship.
Format references:
https://learn.microsoft.com/en-us/office/open-xml/word/structure-of-a-wordprocessingml-document
https://learn.microsoft.com/en-us/office/open-xml/spreadsheet/structure-of-a-spreadsheetml-document
https://www.rfc-editor.org/rfc/rfc5545.html

OOXML validation here covers a minimal package graph/XML structure, not an Office
application acceptance test. Binary text extraction is deliberately still deferred.
"""

from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from io import BytesIO
from typing import Literal
from zipfile import ZIP_STORED, ZipFile, ZipInfo

WORD_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
SHEET_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
CONTENT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
OFFICE_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
WORD_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
SHEET_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
ZIP_TIME = (2026, 1, 1, 0, 0, 0)
CALENDAR_UID = "synthetic-melron-meeting@example.invalid"
CALENDAR_SUMMARY = "Melron Café budget review with Zürich colleagues and synthetic project notes"
PNG_PIXEL = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAC0lEQVR4nGNgAAIAAAUAAXpeqz8AAAAASUVORK5CYII="
)


@dataclass(frozen=True)
class AttachmentSample:
    filename: str
    media_type: str
    payload: bytes
    expected_status: Literal["extracted", "deferred", "skipped"]
    disposition: Literal["attachment", "inline"] = "attachment"
    receipt_hash_mode: Literal["decoded_payload", "serialized_message_part"] = "decoded_payload"

    @property
    def sha256(self) -> str:
        """Original attachment bytes, not the legacy nested-part receipt hash."""
        return hashlib.sha256(self.payload).hexdigest()


@dataclass(frozen=True)
class MimeCase:
    name: str
    raw: bytes
    attachments: tuple[AttachmentSample, ...]
    expected_mime_parts: int


def _package(parts: dict[str, str]) -> bytes:
    output = BytesIO()
    with ZipFile(output, "w", compression=ZIP_STORED) as archive:
        for name, text in sorted(parts.items()):
            info = ZipInfo(name, date_time=ZIP_TIME)
            info.compress_type = ZIP_STORED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, text.encode("utf-8"))
    return output.getvalue()


def docx_bytes() -> bytes:
    return _package(
        {
            "[Content_Types].xml": f'<Types xmlns="{CONTENT_NS}">'
            '<Default Extension="rels" '
            'ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/word/document.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.'
            'wordprocessingml.document.main+xml"/>'
            "</Types>",
            "_rels/.rels": f'<Relationships xmlns="{REL_NS}">'
            f'<Relationship Id="rId1" Type="{OFFICE_REL}/officeDocument" '
            'Target="word/document.xml"/>'
            "</Relationships>",
            "word/document.xml": f'<w:document xmlns:w="{WORD_NS}"><w:body><w:p><w:r>'
            "<w:t>Melron synthetic résumé memo. No real investment.</w:t>"
            "</w:r></w:p></w:body></w:document>",
        }
    )


def xlsx_bytes() -> bytes:
    return _package(
        {
            "[Content_Types].xml": f'<Types xmlns="{CONTENT_NS}">'
            '<Default Extension="rels" '
            'ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            '<Override PartName="/xl/worksheets/sheet1.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            "</Types>",
            "_rels/.rels": f'<Relationships xmlns="{REL_NS}">'
            f'<Relationship Id="rId1" Type="{OFFICE_REL}/officeDocument" Target="xl/workbook.xml"/>'
            "</Relationships>",
            "xl/workbook.xml": f'<workbook xmlns="{SHEET_NS}" xmlns:r="{OFFICE_REL}">'
            '<sheets><sheet name="Synthetic" sheetId="1" r:id="rId1"/></sheets></workbook>',
            "xl/_rels/workbook.xml.rels": f'<Relationships xmlns="{REL_NS}">'
            f'<Relationship Id="rId1" Type="{OFFICE_REL}/worksheet" '
            'Target="worksheets/sheet1.xml"/>'
            "</Relationships>",
            "xl/worksheets/sheet1.xml": f'<worksheet xmlns="{SHEET_NS}"><sheetData>'
            '<row r="1"><c r="A1" t="inlineStr"><is><t>Synthetic budget</t></is></c>'
            '<c r="B1"><v>1250</v></c></row></sheetData></worksheet>',
        }
    )


def _fold(line: str) -> str:
    """RFC 5545 physical lines at most 75 octets, without splitting UTF-8 codepoints."""
    lines = []
    current = ""
    for char in line:
        if len((current + char).encode("utf-8")) > 75:
            lines.append(current)
            current = " "
        current += char
    lines.append(current)
    return "\r\n".join(lines)


def calendar_bytes(*, cancelled: bool = False) -> bytes:
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Email Brain//Synthetic fixtures//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:CANCEL" if cancelled else "METHOD:REQUEST",
        "BEGIN:VEVENT",
        f"UID:{CALENDAR_UID}",
        "DTSTAMP:20260920T120000Z",
        "SEQUENCE:1" if cancelled else "SEQUENCE:0",
        "DTSTART:20260925T160000Z",
        "DTEND:20260925T163000Z",
        f"SUMMARY:{CALENDAR_SUMMARY}",
        "ORGANIZER;CN=Synthetic Organizer:mailto:organizer@example.invalid",
        "ATTENDEE;CN=Synthetic Owner;RSVP=TRUE:mailto:owner@example.invalid",
        "DESCRIPTION:Synthetic café discussion\\nBring notes\\, not real records.",
        "STATUS:CANCELLED" if cancelled else "STATUS:CONFIRMED",
        "END:VEVENT",
        "END:VCALENDAR",
    ]
    return ("\r\n".join(_fold(line) for line in lines) + "\r\n").encode("utf-8")


def nested_email_bytes() -> bytes:
    message = EmailMessage(policy=policy.SMTP)
    message["From"] = "nested@example.invalid"
    message["To"] = "owner@example.invalid"
    message["Date"] = "Sun, 20 Sep 2026 12:00:00 +0000"
    message["Subject"] = "Synthetic attached correspondence"
    message["Message-ID"] = "<nested-fixture@example.invalid>"
    message.set_content("Nested synthetic source. This is not top-level message text.")
    return message.as_bytes()


def _case(name: str, attachments: tuple[AttachmentSample, ...]) -> MimeCase:
    message = EmailMessage(policy=policy.SMTP)
    message["From"] = "sender@example.invalid"
    message["To"] = "owner@example.invalid"
    message["Date"] = "Sun, 20 Sep 2026 12:00:00 +0000"
    message["Subject"] = f"Synthetic attachment corpus {name}"
    message["Message-ID"] = f"<{name}@example.invalid>"
    message.set_content(
        f"Synthetic wrapper for {name}. Attachments are evidence, not instructions."
    )
    for sample in attachments:
        if sample.media_type == "message/rfc822":
            nested = BytesParser(policy=policy.SMTP).parsebytes(sample.payload)
            message.add_attachment(nested, filename=sample.filename, disposition=sample.disposition)
        else:
            maintype, subtype = sample.media_type.split("/", 1)
            params = {"charset": "utf-8"} if maintype == "text" else {}
            if sample.media_type == "text/calendar":
                params["method"] = "CANCEL" if b"METHOD:CANCEL" in sample.payload else "REQUEST"
            message.add_attachment(
                sample.payload,
                maintype=maintype,
                subtype=subtype,
                filename=sample.filename,
                disposition=sample.disposition,
                params=params,
            )
    message.set_boundary("email-brain-synthetic-" + name)
    nested_count = sum(sample.media_type == "message/rfc822" for sample in attachments)
    return MimeCase(name, message.as_bytes(), attachments, 2 + len(attachments) + nested_count)


def attachment_cases() -> tuple[MimeCase, ...]:
    """Stable public corpus API; all files generated only in memory."""
    word = AttachmentSample("Melron résumé.docx", WORD_TYPE, docx_bytes(), "deferred")
    sheet = AttachmentSample("budget.xlsx", SHEET_TYPE, xlsx_bytes(), "deferred")
    pixel = AttachmentSample("pixel.png", "image/png", PNG_PIXEL, "deferred")
    inline = AttachmentSample("inline-pixel.png", "image/png", PNG_PIXEL, "skipped", "inline")
    csv = AttachmentSample(
        "expenses.csv",
        "text/csv",
        'vendor,amount,note\r\nCafé,12.50,"Zürich, synthetic"\r\n'.encode(),
        "extracted",
    )
    invite = AttachmentSample("meeting.ics", "text/calendar", calendar_bytes(), "extracted")
    cancel = AttachmentSample(
        "cancel.ics", "text/calendar", calendar_bytes(cancelled=True), "extracted"
    )
    nested = AttachmentSample(
        "attached.eml",
        "message/rfc822",
        nested_email_bytes(),
        "deferred",
        receipt_hash_mode="serialized_message_part",
    )
    return tuple(
        _case(name, (sample,))
        for name, sample in (
            ("office_docx", word),
            ("office_xlsx", sheet),
            ("pixel_attachment", pixel),
            ("pixel_inline", inline),
            ("csv_utf8", csv),
            ("calendar_invite", invite),
            ("calendar_cancel", cancel),
            ("nested_email", nested),
        )
    ) + (_case("mixed_bundle", (word, sheet, pixel, csv, invite, cancel, nested)),)
