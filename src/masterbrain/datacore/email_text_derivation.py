"""Point-in-time retained-MIME to bridged Email text proof, without effects."""

from __future__ import annotations

import hashlib
import hmac
import re

from email_brain.normalize import MAX_RAW_BYTES, PARSER_VERSION, normalize
from masterbrain.datacore.persistence import EMAIL_NORMALIZER_VERSION
from masterbrain.datacore.source_text_derivation import TextDerivationProof

_SHA256 = re.compile(r"^[a-f0-9]{64}$")


def prove_email_text_derivation(
    raw: bytes, *, source_sha256: str, source_size_bytes: int,
    text: str, text_sha256: str, normalizer: str, parser_version: str,
) -> TextDerivationProof:
    """Recompute the exact direct-MIME bridge projection from retained bytes."""
    if (
        type(raw) is not bytes
        or not 0 < len(raw) <= MAX_RAW_BYTES
        or type(source_size_bytes) is not int
        or source_size_bytes != len(raw)
        or normalizer != EMAIL_NORMALIZER_VERSION
        or parser_version != PARSER_VERSION
        or type(text) is not str
        or type(source_sha256) is not str
        or _SHA256.fullmatch(source_sha256) is None
        or type(text_sha256) is not str
        or _SHA256.fullmatch(text_sha256) is None
    ):
        raise ValueError("invalid_email_derivation_basis")
    try:
        encoded = text.encode("utf-8", errors="strict")
        if (
            not hmac.compare_digest(hashlib.sha256(raw).hexdigest(), source_sha256)
            or not hmac.compare_digest(hashlib.sha256(encoded).hexdigest(), text_sha256)
        ):
            raise ValueError("email_derivation_digest_mismatch")
        message = normalize(raw)
        if message.truncated or message.raw_sha256 != source_sha256:
            raise ValueError("email_derivation_incomplete")
        reproduced = f"Subject: {message.subject}\nFrom: {message.sender}\n\n{message.text}"
        if reproduced != text:
            raise ValueError("email_derivation_mismatch")
    except (UnicodeError, ValueError, RecursionError):
        raise ValueError("email_derivation_failed") from None
    return TextDerivationProof(source_sha256, source_size_bytes, text_sha256, normalizer)
