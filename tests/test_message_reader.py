"""Synthetic owner-reader boundaries; no real messages or provider calls."""

import hashlib
from dataclasses import asdict
from email.message import EmailMessage
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from test_service import TOKEN, registry

from email_brain.api import create_app
from email_brain.attachments import receive_attachments
from email_brain.auth import Principal
from email_brain.blobs import BlobError
from email_brain.message_reader import (
    MessageReader,
    ReaderUnavailable,
    attachment_bytes,
    decoded_body,
    header_view,
    parse_small,
)
from email_brain.normalize import MAX_RAW_BYTES, normalize
from email_brain.store import AccessDenied, Conflict, NotFound, Store


def mail_bytes(body="Readerproof body", html=None, attachments=()):
    mail = EmailMessage()
    mail["From"] = "Alice <alice@example.invalid>"
    mail["To"] = "Owner <owner@example.invalid>"
    mail["Subject"] = "Readerproof synthetic email"
    mail.set_content(body)
    if html is not None:
        mail.add_alternative(html, subtype="html")
    for filename, content, media in attachments:
        main, sub = media.split("/")
        mail.add_attachment(content, maintype=main, subtype=sub, filename=filename)
    return mail.as_bytes()


@pytest.mark.parametrize("length", [0, 4000, 4001, 100000, 130000, 400000])
def test_complete_body_not_search_excerpt(length):
    text = "Readerproof " + "x" * length + " ENDPROOF"
    raw = mail_bytes(text)
    assert len(raw) < MAX_RAW_BYTES
    assert decoded_body(parse_small(raw)) == text
    assert len(normalize(raw).text) <= 100000


@pytest.mark.parametrize("charset", ["utf-8", "iso-8859-1", "utf-16", "unknown123"])
def test_reader_decodes_bounded_text_and_keeps_quotes(charset):
    text = "Quoted conversation\n> Previous reply\n\nFinal line"
    codec = "utf-8" if charset == "unknown123" else charset
    raw = f"Content-Type: text/plain; charset={charset}\r\n\r\n".encode() + text.encode(codec)
    assert decoded_body(parse_small(raw)) == text


def test_html_is_never_rendered_or_fetched_and_plain_is_preferred():
    html = (
        '<script>exfiltrate()</script><style>secret</style><p>Hello 😀</p>'
        '<img src="https://bad.invalid/x"><iframe src="https://bad.invalid/i"></iframe>'
    )
    raw = b"Content-Type: text/html; charset=utf-8\r\n\r\n" + html.encode()
    assert decoded_body(parse_small(raw)) == "Hello 😀"
    assert decoded_body(parse_small(mail_bytes("Prefer plain", html))) == "Prefer plain"


@pytest.mark.parametrize("raw", [b"", b"x" * (MAX_RAW_BYTES + 1), "not bytes", None])
def test_reader_does_not_expand_api_parser_budget(raw):
    with pytest.raises(ReaderUnavailable):
        parse_small(raw)


@pytest.mark.parametrize("case", ["count", "single", "total"])
def test_header_metadata_is_bounded_but_source_unchanged(case):
    if case == "count":
        headers = "X-Item: value\r\n" * 110
    elif case == "single":
        headers = "Subject: " + "x" * 6000 + "\r\n"
    else:
        headers = ("X-Item: " + "x" * 4000 + "\r\n") * 20
    raw = (headers + "\r\nBody").encode()
    before = hashlib.sha256(raw).hexdigest()
    result, truncated = header_view(parse_small(raw))
    assert truncated and len(result) <= 100
    assert all(len(row["value"]) <= 4000 for row in result)
    assert sum(len(row["value"]) for row in result) <= 65536
    assert hashlib.sha256(raw).hexdigest() == before


@pytest.mark.parametrize(
    "filename,content,media",
    [
        ("../report.csv", b"name,value\nA,12", "text/csv"),
        ("evil.html", b"<script>alert(1)</script>", "text/html"),
        ("pretend.pdf", b"MZnot a PDF", "application/pdf"),
        ("report.pdf", b"%PDF-synthetic-only", "application/pdf"),
        ("empty.txt", b"", "text/plain"),
        (
            "file.xlsx",
            b"PK\x03\x04synthetic",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ),
    ],
)
def test_attachment_is_exact_decoded_bytes_never_executed(filename, content, media):
    raw = mail_bytes(attachments=[(filename, content, media)])
    receipt = asdict(receive_attachments(raw)[0])
    assert attachment_bytes(parse_small(raw), receipt) == content


@pytest.mark.parametrize(
    "change",
    [
        {"sha256": "0" * 64},
        {"byte_size": 999},
        {"part_id": "1.99"},
        {"part_id": "1.0"},
        {"part_id": "1.-1"},
        {"part_id": "2.1"},
        {"part_id": "1.99999"},
        {"part_id": "1.x"},
        {"part_id": "1.١"},
    ],
)
def test_part_integrity_and_path_fail_closed(change):
    raw = mail_bytes(attachments=[("text.txt", b"part", "text/plain")])
    receipt = asdict(receive_attachments(raw)[0]) | change
    with pytest.raises(ReaderUnavailable):
        attachment_bytes(parse_small(raw), receipt)


def test_nested_part_requires_original_download():
    outer, inner = EmailMessage(), EmailMessage()
    outer.set_content("Outer")
    inner.set_content("Nested")
    outer.add_attachment(inner)
    raw = outer.as_bytes()
    receipt = asdict(receive_attachments(raw)[0])
    with pytest.raises(Conflict):
        attachment_bytes(parse_small(raw), receipt)


@pytest.mark.parametrize("kind", ["assistant", "worker"])
def test_library_requires_human_before_any_storage(kind):
    store = MagicMock(spec=Store)
    ctx = registry().authenticate(TOKEN).context
    reader = MessageReader(store)
    for call in (reader.read, reader.download):
        with pytest.raises(AccessDenied):
            call(Principal(ctx, kind), uuid4())
    store.transaction.assert_not_called()


def reader_client(monkeypatch, kind="human", scopes=None):
    reader = MagicMock(spec=MessageReader)
    reader.read.return_value = {"synthetic": True}
    identifier = uuid4()
    reader.download.return_value = (b"source bytes", f"message-{identifier}.eml")
    monkeypatch.setattr("email_brain.api.MessageReader", lambda _: reader)
    client = TestClient(
        create_app(MagicMock(spec=Store), registry(scopes or {"email.evidence.read"}, kind))
    )
    return client, reader, f"/v1/reader/{identifier}"


@pytest.mark.parametrize(
    "suffix,method",
    [
        ("", "get"),
        ("/original", "post"),
        ("/attachments/00000000-0000-4000-8000-000000000001", "post"),
    ],
)
@pytest.mark.parametrize(
    "mode,expected",
    [("missing", 401), ("assistant", 403), ("worker", 403), ("scope", 403), ("human", 200)],
)
def test_reader_api_access_all_routes(monkeypatch, suffix, method, mode, expected):
    client, reader, path = reader_client(
        monkeypatch,
        mode if mode in {"assistant", "worker"} else "human",
        {"email.search"} if mode == "scope" else None,
    )
    kwargs = {} if mode == "missing" else {"headers": {"Authorization": f"Bearer {TOKEN}"}}
    if method == "post":
        kwargs["json"] = {"acknowledge_unscanned": True}
    result = getattr(client, method)(path + suffix, **kwargs)
    assert result.status_code == expected
    if expected != 200:
        reader.read.assert_not_called()
        reader.download.assert_not_called()


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"acknowledge_unscanned": False},
        {"acknowledge_unscanned": 1},
        {"acknowledge_unscanned": "true"},
        {"acknowledge_unscanned": True, "path": "/secret"},
        {"acknowledge_unscanned": True, "tenant_id": str(uuid4())},
    ],
)
def test_download_requires_closed_explicit_consent(monkeypatch, payload):
    client, reader, path = reader_client(monkeypatch)
    result = client.post(
        path + "/original", json=payload, headers={"Authorization": f"Bearer {TOKEN}"}
    )
    assert result.status_code == 422
    assert "/secret" not in result.text
    reader.download.assert_not_called()


def test_download_has_safe_headers_and_is_not_get_or_generic_object_access(monkeypatch):
    client, _, path = reader_client(monkeypatch)
    headers = {"Authorization": f"Bearer {TOKEN}"}
    result = client.post(path + "/original", json={"acknowledge_unscanned": True}, headers=headers)
    assert result.content == b"source bytes"
    assert result.headers["content-type"] == "application/octet-stream"
    assert result.headers["content-disposition"].startswith('attachment; filename="message-')
    assert "sandbox" in result.headers["content-security-policy"]
    assert "default-src 'none'" in result.headers["content-security-policy"]
    assert result.headers["cache-control"] == "no-store"
    assert result.headers["x-content-type-options"] == "nosniff"
    assert result.headers["x-content-sha256"] == hashlib.sha256(result.content).hexdigest()
    assert client.get(path + "/original", headers=headers).status_code == 405
    assert client.get("/v1/reader/not-a-uuid", headers=headers).status_code == 422
    assert client.get("/v1/raw/" + "a" * 64, headers=headers).status_code == 404


@pytest.mark.parametrize(
    "error,code",
    [
        (BlobError(), 503),
        (ReaderUnavailable(), 503),
        (NotFound(), 404),
        (AccessDenied("private content"), 403),
        (Conflict("private content"), 409),
    ],
)
def test_reader_failures_are_scrubbed(monkeypatch, error, code):
    client, reader, path = reader_client(monkeypatch)
    reader.read.side_effect = error
    response = client.get(path, headers={"Authorization": f"Bearer {TOKEN}"})
    assert response.status_code == code and "private content" not in response.text


def test_reader_asset_is_fixed_same_origin(monkeypatch):
    client, _, _ = reader_client(monkeypatch)
    response = client.get("/message_reader.js")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert 'src="/message_reader.js"' in client.get("/").text
