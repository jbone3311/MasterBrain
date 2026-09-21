"""Format fixtures validate bytes/packaging, not Office/PDF/OCR text extraction."""

import csv
import hashlib
import struct
import zlib
from email import policy
from email.parser import BytesParser
from io import BytesIO, StringIO
from xml.etree import ElementTree as ET
from zipfile import ZIP_STORED, ZipFile

import pytest
from attachment_samples import (
    CALENDAR_SUMMARY,
    CALENDAR_UID,
    CONTENT_NS,
    OFFICE_REL,
    PNG_PIXEL,
    REL_NS,
    SHEET_NS,
    WORD_NS,
    ZIP_TIME,
    attachment_cases,
    calendar_bytes,
    docx_bytes,
    xlsx_bytes,
)

from email_brain.attachments import receive_attachments

CASES = attachment_cases()
KNOWN_PAYLOAD_HASHES = {
    "office_docx": "ac976cbbdb7cbfbf4437ec08bbfba6c55d58e7121083ab1dd41ee05867135788",
    "office_xlsx": "d765acafb054029edf4faf2c7d03df00c9eb8d9eedd35e45cfd9d529d210660d",
    "pixel_attachment": "43739c566e26fd7cb88f69d3864ea34740372f5ee99acac169e090beffbce5c6",
    "pixel_inline": "43739c566e26fd7cb88f69d3864ea34740372f5ee99acac169e090beffbce5c6",
    "csv_utf8": "15ceca170653d92a5d9067fcaa128955caba0f8fc776a9b669e7c4a689a004bb",
    "calendar_invite": "45d587e8109d1dbd295d27d8b90f19ec2a42c112d4b0e16ad18ca87a07d594b5",
    "calendar_cancel": "dbf07b4b0a3773ecf5cdf70afbb2ec57b98f4292b7d590f600e9381a0f03a1fb",
    "nested_email": "0c7d990ba2f2b3231cb7b2bbf77735251f25085ef027e91af6c976cbcface363",
}


@pytest.mark.parametrize("name", KNOWN_PAYLOAD_HASHES)
def test_fixture_payloads_match_reviewed_known_hashes(name):
    case = next(case for case in CASES if case.name == name)
    assert case.attachments[0].sha256 == KNOWN_PAYLOAD_HASHES[name]


def test_repeated_generation_is_byte_for_byte_deterministic():
    assert attachment_cases() == attachment_cases()
    assert len(CASES) == 9
    assert len({case.name for case in CASES}) == len(CASES)


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.name)
def test_mime_structure_and_exact_attachment_bytes(case):
    root = BytesParser(policy=policy.SMTP).parsebytes(case.raw)
    assert root.get_content_type() == "multipart/mixed"
    assert not root.defects
    assert len(list(root.walk())) == case.expected_mime_parts
    assert root.get_boundary() == "email-brain-synthetic-" + case.name
    parts = list(root.iter_attachments())
    assert len(parts) == len(case.attachments)
    for part, expected in zip(parts, case.attachments, strict=True):
        assert part.get_filename() == expected.filename
        assert part.get_content_type() == expected.media_type
        assert part.get_content_disposition() == expected.disposition
        assert not part.defects
        if expected.receipt_hash_mode == "serialized_message_part":
            assert part.get_content_type() == "message/rfc822"
            assert part["Content-Transfer-Encoding"] == "8bit"
            nested = part.get_payload()
            assert isinstance(nested, list) and len(nested) == 1
            decoded = nested[0].as_bytes(policy=policy.SMTP)
        else:
            decoded = part.get_payload(decode=True)
        assert decoded == expected.payload
        assert hashlib.sha256(decoded).hexdigest() == expected.sha256


@pytest.mark.parametrize(
    "create,main_path", [(docx_bytes, "word/document.xml"), (xlsx_bytes, "xl/workbook.xml")]
)
def test_minimal_ooxml_package_structure_and_content_types(create, main_path):
    with ZipFile(BytesIO(create())) as archive:
        assert archive.testzip() is None
        names = archive.namelist()
        assert names == sorted(names)
        assert len(names) == len(set(names))
        assert "[Content_Types].xml" in names and "_rels/.rels" in names and main_path in names
        for member in archive.infolist():
            assert member.date_time == ZIP_TIME
            assert member.compress_type == ZIP_STORED
            assert member.create_system == 3
            assert not member.flag_bits & 1  # Not encrypted.
            assert not member.filename.startswith("/") and ".." not in member.filename.split("/")
            raw = archive.read(member)
            assert b"<!DOCTYPE" not in raw and b"<!ENTITY" not in raw
            ET.fromstring(raw)  # Every fixture part is well-formed XML.
        content_types = ET.fromstring(archive.read("[Content_Types].xml"))
        assert content_types.tag == f"{{{CONTENT_NS}}}Types"
        defaults = {
            node.attrib["Extension"]: node.attrib["ContentType"]
            for node in content_types.findall(f"{{{CONTENT_NS}}}Default")
        }
        assert defaults["xml"] == "application/xml"
        assert defaults["rels"] == "application/vnd.openxmlformats-package.relationships+xml"
        overrides = {
            node.attrib["PartName"]: node.attrib["ContentType"]
            for node in content_types.findall(f"{{{CONTENT_NS}}}Override")
        }
        assert "/" + main_path in overrides
        assert all(name[1:] in names for name in overrides)
        relationships = ET.fromstring(archive.read("_rels/.rels"))
        (relation,) = relationships.findall(f"{{{REL_NS}}}Relationship")
        assert relation.attrib == {
            "Id": "rId1",
            "Type": OFFICE_REL + "/officeDocument",
            "Target": main_path,
        }


def test_docx_main_story_contains_expected_synthetic_text():
    with ZipFile(BytesIO(docx_bytes())) as archive:
        root = ET.fromstring(archive.read("word/document.xml"))
    assert root.tag == f"{{{WORD_NS}}}document"
    text = root.find(f"{{{WORD_NS}}}body/{{{WORD_NS}}}p/{{{WORD_NS}}}r/{{{WORD_NS}}}t")
    assert text is not None
    assert text.text == "Melron synthetic résumé memo. No real investment."


def test_xlsx_workbook_relationship_resolves_actual_sheet_and_cells():
    with ZipFile(BytesIO(xlsx_bytes())) as archive:
        root = ET.fromstring(archive.read("xl/workbook.xml"))
        sheet = root.find(f"{{{SHEET_NS}}}sheets/{{{SHEET_NS}}}sheet")
        assert sheet is not None and sheet.attrib["sheetId"] == "1"
        identifier = sheet.attrib[f"{{{OFFICE_REL}}}id"]
        relations = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        targets = {node.attrib["Id"]: node.attrib["Target"] for node in relations}
        assert targets[identifier] == "worksheets/sheet1.xml"
        worksheet = ET.fromstring(archive.read("xl/" + targets[identifier]))
    assert worksheet.tag == f"{{{SHEET_NS}}}worksheet"
    cells = worksheet.findall(f"{{{SHEET_NS}}}sheetData/{{{SHEET_NS}}}row/{{{SHEET_NS}}}c")
    assert [cell.attrib["r"] for cell in cells] == ["A1", "B1"]
    assert cells[0].find(f"{{{SHEET_NS}}}is/{{{SHEET_NS}}}t").text == "Synthetic budget"
    assert cells[1].find(f"{{{SHEET_NS}}}v").text == "1250"
    assert not worksheet.findall(f".//{{{SHEET_NS}}}f")  # No formulas or external links.


def test_png_is_a_real_single_transparent_pixel_with_valid_chunk_crcs():
    assert PNG_PIXEL[:8] == b"\x89PNG\r\n\x1a\n"
    offset, chunks = 8, []
    while offset < len(PNG_PIXEL):
        size = struct.unpack(">I", PNG_PIXEL[offset : offset + 4])[0]
        kind = PNG_PIXEL[offset + 4 : offset + 8]
        data = PNG_PIXEL[offset + 8 : offset + 8 + size]
        crc = struct.unpack(">I", PNG_PIXEL[offset + 8 + size : offset + 12 + size])[0]
        assert zlib.crc32(kind + data) & 0xFFFFFFFF == crc
        chunks.append((kind, data))
        offset += 12 + size
    assert offset == len(PNG_PIXEL)
    assert [kind for kind, _ in chunks] == [b"IHDR", b"IDAT", b"IEND"]
    assert struct.unpack(">IIBBBBB", chunks[0][1]) == (1, 1, 8, 6, 0, 0, 0)
    assert zlib.decompress(chunks[1][1]) == b"\x00\x00\x00\x00\x00"
    assert chunks[2][1] == b""


def test_csv_contains_real_quoted_utf8_records():
    sample = next(case for case in CASES if case.name == "csv_utf8").attachments[0]
    assert list(csv.reader(StringIO(sample.payload.decode("utf-8")))) == [
        ["vendor", "amount", "note"],
        ["Café", "12.50", "Zürich, synthetic"],
    ]


@pytest.mark.parametrize("cancelled", [False, True])
def test_calendar_is_valid_bounded_utf8_with_folded_lines_and_cancellation(cancelled):
    raw = calendar_bytes(cancelled=cancelled)
    assert raw.endswith(b"\r\n") and b"\r\n " in raw
    lines = raw.split(b"\r\n")
    assert all(len(line) <= 75 for line in lines)
    for line in lines:
        line.decode("utf-8", errors="strict")
    unfolded = raw.replace(b"\r\n ", b"").decode("utf-8").split("\r\n")
    assert unfolded[:2] == ["BEGIN:VCALENDAR", "VERSION:2.0"]
    assert unfolded[-3:] == ["END:VEVENT", "END:VCALENDAR", ""]
    assert f"UID:{CALENDAR_UID}" in unfolded
    assert "DTSTAMP:20260920T120000Z" in unfolded
    assert f"SUMMARY:{CALENDAR_SUMMARY}" in unfolded
    assert "DTSTART:20260925T160000Z" in unfolded
    assert ("METHOD:CANCEL" if cancelled else "METHOD:REQUEST") in unfolded
    assert ("STATUS:CANCELLED" if cancelled else "STATUS:CONFIRMED") in unfolded
    assert ("SEQUENCE:1" if cancelled else "SEQUENCE:0") in unfolded


@pytest.mark.parametrize("name", ["office_docx", "office_xlsx", "pixel_attachment", "pixel_inline"])
def test_binary_fixtures_remain_unextracted_not_falsely_marked_as_read(name):
    case = next(case for case in CASES if case.name == name)
    (receipt,) = receive_attachments(case.raw)
    assert receipt.status == case.attachments[0].expected_status
    assert not receipt.text
    assert receipt.sha256 == case.attachments[0].sha256


def test_nested_receipt_hash_is_explicitly_wrapper_based_while_source_bytes_survive():
    case = next(case for case in CASES if case.name == "nested_email")
    (part,) = BytesParser(policy=policy.default).parsebytes(case.raw).iter_attachments()
    (receipt,) = receive_attachments(case.raw)
    assert case.attachments[0].receipt_hash_mode == "serialized_message_part"
    assert receipt.sha256 == hashlib.sha256(part.as_bytes(policy=policy.default)).hexdigest()
    assert receipt.sha256 != case.attachments[0].sha256
    assert receipt.status == "deferred" and not receipt.text
