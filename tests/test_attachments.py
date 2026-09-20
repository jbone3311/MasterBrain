from email.message import EmailMessage

import pytest

from email_brain.attachments import receive_attachments, reconcile, safe_name


def mail_with_file(data: bytes, filename: str = "notes.txt", mime: str = "text/plain") -> bytes:
    mail = EmailMessage()
    mail["Subject"] = "Synthetic attachment test"
    mail.set_content("See the attached file.")
    main, sub = mime.split("/")
    mail.add_attachment(data, maintype=main, subtype=sub, filename=filename)
    return mail.as_bytes()


def test_text_extraction_and_accounting() -> None:
    result = receive_attachments(mail_with_file(b"Synthetic spreadsheet overview"))
    assert len(result) == 1 and result[0].status == "extracted"
    assert result[0].text == "Synthetic spreadsheet overview"
    assert reconcile([r.status for r in result])["unaccounted"] == 0


@pytest.mark.parametrize(
    "data,name,mime",
    [
        (b"MZpayload", "innocent.txt", "text/plain"),
        (b"%PDF-1.4", "innocent.txt", "text/plain"),
        (b"PK\x03\x04", "files.zip", "application/zip"),
        (b"pdf", "terms.pdf", "application/pdf"),
        (b"office", "report.xlsm", "application/vnd.ms-excel"),
        (b"binary\x00", "notes.txt", "text/plain"),
    ],
)
def test_binary_or_active_content_is_deferred(data: bytes, name: str, mime: str) -> None:
    result = receive_attachments(mail_with_file(data, name, mime))[0]
    assert result.status == "deferred"
    assert result.text == ""


def test_hostile_filename_has_no_path_authority() -> None:
    assert safe_name("../../hidden/steal.txt") == "steal.txt"
    assert safe_name("C:\\secret\\steal.txt") == "steal.txt"
    assert safe_name(".../") == "attachment"


def test_failed_decode_is_explicit() -> None:
    assert receive_attachments(mail_with_file(b"\xff\xfe"))[0].status == "failed"


def test_reconciliation_cannot_hide_unknown_outcomes() -> None:
    assert reconcile(["extracted", "deferred"])["ready"] is False
    assert reconcile(["imaginary-success"])["unaccounted"] == 1


def test_attachment_limit_aborts_instead_of_silently_dropping_files() -> None:
    mail = EmailMessage()
    mail.set_content("Synthetic")
    for index in range(65):
        mail.add_attachment(b"x", maintype="text", subtype="plain", filename=f"{index}.txt")
    with pytest.raises(ValueError, match="count limit"):
        receive_attachments(mail.as_bytes())
