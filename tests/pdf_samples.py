"""Authored synthetic PDF variants; no downloads, user files or live documents."""

import hashlib
from email.message import EmailMessage
from io import BytesIO

from pypdf import PdfReader, PdfWriter
from pypdf.generic import (
    ArrayObject,
    DecodedStreamObject,
    DictionaryObject,
    NameObject,
    TextStringObject,
)

from email_brain.pdf_contract import encode_request, source_for
from email_brain.synthetic_formats import pdf_bytes, plan_rgb


def mail_packet(data, *, media="pdf", filename="document.pdf"):
    mail = EmailMessage()
    mail["From"] = "sender@example.invalid"
    mail["To"] = "owner@example.invalid"
    mail["Subject"] = "Synthetic PDF receipt"
    mail.set_content("bodyproof remains independent of document processing")
    mail.add_attachment(data, maintype="application", subtype=media, filename=filename)
    mail.set_boundary("synthetic-pdf-boundary")
    raw = mail.as_bytes()
    digest = hashlib.sha256(data).hexdigest()
    return raw, source_for(raw, "1.2", digest), encode_request(raw, "1.2", digest)


def variant(kind):
    if kind == "text":
        return pdf_bytes(("pdfonlyproof known invoice USD 1234.50", "second line"))
    if kind == "image":
        return pdf_bytes(rgb=plan_rgb(9))
    if kind == "damaged":
        return pdf_bytes(("never publish this incomplete document",))[:90]
    writer = PdfWriter()
    writer.add_page(PdfReader(BytesIO(variant("text")), strict=True).pages[0])
    if kind == "encrypted":
        writer.encrypt("synthetic-test-only")
    elif kind == "empty_password":
        writer.encrypt("")
    elif kind == "partial":
        writer.add_page(PdfReader(BytesIO(variant("image")), strict=True).pages[0])
    elif kind == "pages":
        for _ in range(40):
            writer.add_blank_page(width=612, height=792)
    elif kind in {"stream", "text_limit"}:
        stream = DecodedStreamObject()
        stream.set_data(
            b" " * (2 * 1024 * 1024 + 1)
            if kind == "stream"
            else b"BT /F1 12 Tf (" + b"x" * 20001 + b") Tj ET"
        )
        writer.pages[0][NameObject("/Contents")] = writer._add_object(stream.flate_encode())
    elif kind == "annotation":
        writer.pages[0][NameObject("/Annots")] = ArrayObject([])
    elif kind == "form":
        writer._root_object[NameObject("/AcroForm")] = DictionaryObject()
    elif kind == "active":
        # Never evaluated. Not a real URL, script, command or exploit payload.
        writer._root_object[NameObject("/OpenAction")] = TextStringObject("inert marker")
    elif kind == "names":
        writer._root_object[NameObject("/Names")] = DictionaryObject()
    elif kind == "zero_pages":
        writer = PdfWriter()
    else:
        raise AssertionError(kind)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()
