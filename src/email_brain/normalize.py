"""Bounded MIME normalization. Never fetch URLs or execute/render HTML."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from email.utils import getaddresses
from html.parser import HTMLParser

MAX_RAW_BYTES = 1_048_576
MAX_TEXT_CHARS = 100_000
PARSER_VERSION = "stdlib-mime-v3"


class _TextOnly(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.hidden = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "head"}:
            self.hidden += 1
        elif tag in {"p", "div", "br", "li", "tr"} and not self.hidden:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "head"}:
            self.hidden = max(0, self.hidden - 1)

    def handle_data(self, data: str) -> None:
        if not self.hidden:
            self.parts.append(data)


@dataclass(frozen=True)
class NormalizedMessage:
    subject: str
    sender: str
    recipients: tuple[str, ...]
    internet_message_id: str | None
    text: str
    raw_sha256: str
    truncated: bool


def normalize(raw: bytes) -> NormalizedMessage:
    if not raw or len(raw) > MAX_RAW_BYTES:
        raise ValueError("raw MIME must contain 1..1048576 bytes")
    mail = BytesParser(policy=policy.default).parsebytes(raw)
    if not isinstance(mail, EmailMessage):
        raise ValueError("invalid MIME parser result")
    # Prefer the plain body; get_body avoids text attachments and alternative duplication.
    body = mail.get_body(preferencelist=("plain", "html"))
    text = ""
    if body is not None:
        charset = body.get_content_charset() or "utf-8"
        payload = body.get_payload(decode=True)
        if isinstance(payload, bytes):
            try:
                text = payload.decode(charset, errors="replace")
            except LookupError:
                text = payload.decode("utf-8", errors="replace")
        if body.get_content_type() == "text/html":
            parser = _TextOnly()
            parser.feed(text)
            text = "".join(parser.parts)
    text = text.replace("\x00", "").strip()
    addresses = getaddresses([str(v) for v in mail.get_all("to", []) + mail.get_all("cc", [])])
    sender = getaddresses([str(mail.get("from", ""))])
    return NormalizedMessage(
        subject=str(mail.get("subject", "")).replace("\x00", "")[:2000],
        sender=(sender[0][1] if sender else "").replace("\x00", "")[:320],
        recipients=tuple(address.replace("\x00", "")[:320] for _, address in addresses[:100]),
        internet_message_id=(
            str(mail["message-id"]).replace("\x00", "")[:1000] if mail["message-id"] else None
        ),
        text=text[:MAX_TEXT_CHARS],
        raw_sha256=hashlib.sha256(raw).hexdigest(),
        truncated=len(text) > MAX_TEXT_CHARS,
    )
