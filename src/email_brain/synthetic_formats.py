"""Small deterministic, independently test-read formats, not a document extractor.

No external input, network, macros, external relationships or production parser.
The subset is intentionally small; tests use separate PDF/Office readers.
"""

from __future__ import annotations

import struct
import zlib
from io import BytesIO
from xml.sax.saxutils import escape
from zipfile import ZIP_STORED, ZipFile, ZipInfo

WORD_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
SHEET_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
_CONTENT = "http://schemas.openxmlformats.org/package/2006/content-types"
_REL = "http://schemas.openxmlformats.org/package/2006/relationships"
_OFFICE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_WORD = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_SHEET = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"


def zip_bytes(parts: dict[str, bytes]) -> bytes:
    output = BytesIO()
    with ZipFile(output, "w", compression=ZIP_STORED) as archive:
        for name, payload in sorted(parts.items()):
            info = ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, payload)
    return output.getvalue()


def _office(parts: dict[str, str], kind: str) -> bytes:
    root = "word/document.xml" if kind == "word" else "xl/workbook.xml"
    overrides = (
        [("word/document.xml", "wordprocessingml.document.main+xml")]
        if kind == "word"
        else [
            ("xl/workbook.xml", "spreadsheetml.sheet.main+xml"),
            ("xl/worksheets/sheet1.xml", "spreadsheetml.worksheet+xml"),
        ]
    )
    parts["[Content_Types].xml"] = (
        f'<Types xmlns="{_CONTENT}"><Default Extension="rels" '
        'ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        + "".join(
            f'<Override PartName="/{name}" '
            f'ContentType="application/vnd.openxmlformats-officedocument.{media}"/>'
            for name, media in overrides
        )
        + "</Types>"
    )
    parts["_rels/.rels"] = (
        f'<Relationships xmlns="{_REL}"><Relationship Id="rId1" '
        f'Type="{_OFFICE}/officeDocument" Target="{root}"/></Relationships>'
    )
    return zip_bytes({name: value.encode("utf-8") for name, value in parts.items()})


def docx_bytes(text: str) -> bytes:
    return _office(
        {
            "word/document.xml": (
                f'<w:document xmlns:w="{_WORD}"><w:body><w:p><w:r><w:t xml:space="preserve">'
                f"{escape(text)}</w:t></w:r></w:p></w:body></w:document>"
            )
        },
        "word",
    )


def xlsx_bytes(project: str, rent: int, revision: int, marker: str) -> bytes:
    values: list[list[str | int]] = [
        ["Project", "Monthly rent USD", "Revision", "Evidence marker"],
        [project, rent, revision, marker],
    ]
    rows = []
    for row_id, values_row in enumerate(values, 1):
        cells = []
        for col_id, value in enumerate(values_row):
            address = f"{chr(65 + col_id)}{row_id}"
            if isinstance(value, int):
                cells.append(f'<c r="{address}"><v>{value}</v></c>')
            else:
                cells.append(f'<c r="{address}" t="inlineStr"><is><t>{escape(value)}</t></is></c>')
        rows.append(f'<row r="{row_id}">{"".join(cells)}</row>')
    return _office(
        {
            "xl/workbook.xml": f'<workbook xmlns="{_SHEET}" xmlns:r="{_OFFICE}">'
            '<sheets><sheet name="Rent roll" sheetId="1" r:id="rId1"/></sheets></workbook>',
            "xl/_rels/workbook.xml.rels": f'<Relationships xmlns="{_REL}">'
            f'<Relationship Id="rId1" Type="{_OFFICE}/worksheet" '
            'Target="worksheets/sheet1.xml"/></Relationships>',
            "xl/worksheets/sheet1.xml": f'<worksheet xmlns="{_SHEET}"><sheetData>'
            f"{''.join(rows)}</sheetData></worksheet>",
        },
        "sheet",
    )


def plan_rgb(tone: int) -> bytes:
    """64x32 fictional three-room floor plan, not a scanned-text/OCR fixture."""
    return bytes(
        component
        for y in range(32)
        for x in range(64)
        for component in (
            (30, 45, 60)
            if ((x in (4, 32, 60) and 4 <= y <= 28) or (y in (4, 16, 28) and 4 <= x <= 60))
            else (240, 240 - tone % 32, 240 - tone % 16)
        )
    )


def png_bytes(rgb: bytes) -> bytes:
    if len(rgb) != 64 * 32 * 3:
        raise ValueError("fixed synthetic image dimensions required")

    def chunk(kind: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
        )

    scanlines = b"".join(b"\0" + rgb[y * 192 : (y + 1) * 192] for y in range(32))
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", 64, 32, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(scanlines, level=0))
        + chunk(b"IEND", b"")
    )


def pdf_bytes(lines: tuple[str, ...] = (), *, rgb: bytes | None = None) -> bytes:
    """One fixed page, explicit xref/lengths; no JavaScript, links, files or metadata."""
    if rgb is not None and (lines or len(rgb) != 64 * 32 * 3):
        raise ValueError("fixed synthetic image-only PDF required")
    if len(lines) > 12 or any(len(line) > 100 or not line.isascii() for line in lines):
        raise ValueError("bounded synthetic ASCII PDF required")
    if rgb is None:
        escaped = [
            line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)") for line in lines
        ]
        stream = (
            "BT /F1 12 Tf 50 740 Td 18 TL "
            + " T* ".join(f"({line}) Tj" for line in escaped)
            + " ET"
        ).encode()
        resource = b"/Font << /F1 4 0 R >>"
        obj4 = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"
    else:
        stream = b"q 448 0 0 224 50 400 cm /Im1 Do Q"
        resource = b"/XObject << /Im1 4 0 R >>"
        obj4 = (
            b"<< /Type /XObject /Subtype /Image /Width 64 /Height 32 "
            b"/ColorSpace /DeviceRGB /BitsPerComponent 8 /Length "
            + str(len(rgb)).encode()
            + b" >>\nstream\n"
            + rgb
            + b"\nendstream"
        )
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << "
        + resource
        + b" >> /Contents 5 0 R >>",
        obj4,
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
    ]
    output = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for index, value in enumerate(objects, 1):
        offsets.append(len(output))
        output.extend(f"{index} 0 obj\n".encode() + value + b"\nendobj\n")
    start = len(output)
    output.extend(f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode())
    output.extend(
        f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{start}\n%%EOF\n".encode()
    )
    return bytes(output)
