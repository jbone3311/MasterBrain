"""Bounded MIME normalization. Never fetch URLs or execute/render HTML."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from email import policy
from email.headerregistry import AddressHeader
from email.message import EmailMessage
from email.parser import BytesParser
from email.utils import getaddresses
from html.parser import HTMLParser

MAX_RAW_BYTES = 1_048_576
MAX_ISOLATED_RAW_BYTES = 16 * 1024 * 1024
MAX_TEXT_CHARS = 100_000
PARSER_VERSION = "stdlib-mime-v5"


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
    sender_rule_eligible: bool = False


def _sender(mail: EmailMessage) -> tuple[str, bool]:
    """Keep ambiguity visible as ineligibility instead of picking a first author."""
    headers = mail.get_all("from", [])
    if len(headers) != 1:
        return "", False
    header = headers[0]
    if (
        not isinstance(header, AddressHeader)
        or getattr(header, "defects", True)
        or len(header.addresses) != 1
        or any(group.display_name is not None for group in header.groups)
    ):
        return "", False
    address = header.addresses[0]
    sender = address.addr_spec
    if (
        not address.username
        or not address.domain
        or not 1 <= len(sender) <= 320
        or not sender.isprintable()
    ):
        return "", False
    sender.encode("utf-8", errors="strict")
    return sender, True


def validate_raw_budget(max_raw_bytes: int) -> None:
    if type(max_raw_bytes) is not int or not 1 <= max_raw_bytes <= MAX_ISOLATED_RAW_BYTES:
        raise ValueError("invalid bounded MIME budget")


def body_text(mail: EmailMessage) -> str:
    """Decode the selected body to inert text; preserve quoted conversation content."""
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
    return text.replace("\x00", "").strip()


def normalize(raw: bytes, *, max_raw_bytes: int = MAX_RAW_BYTES) -> NormalizedMessage:
    validate_raw_budget(max_raw_bytes)
    if not isinstance(raw, bytes) or not raw or len(raw) > max_raw_bytes:
        raise ValueError("raw MIME outside configured byte budget")
    mail = BytesParser(policy=policy.default).parsebytes(raw)
    if not isinstance(mail, EmailMessage):
        raise ValueError("invalid MIME parser result")
    text = body_text(mail)
    addresses = getaddresses([str(v) for v in mail.get_all("to", []) + mail.get_all("cc", [])])
    sender, sender_rule_eligible = _sender(mail)
    return NormalizedMessage(
        subject=str(mail.get("subject", "")).replace("\x00", "")[:2000],
        sender=sender,
        recipients=tuple(address.replace("\x00", "")[:320] for _, address in addresses[:100]),
        internet_message_id=(
            str(mail["message-id"]).replace("\x00", "")[:1000] if mail["message-id"] else None
        ),
        text=text[:MAX_TEXT_CHARS],
        raw_sha256=hashlib.sha256(raw).hexdigest(),
        truncated=len(text) > MAX_TEXT_CHARS,
        sender_rule_eligible=sender_rule_eligible,
    )
