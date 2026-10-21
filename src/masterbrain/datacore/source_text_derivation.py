"""Bounded FileOS source-byte to normalized-text derivation proof.

This proves supplied bytes reproduce the exact DataCore text projection. The
caller must separately obtain them from an authorized current source version.
It does not classify document authority or publish Knowledge claims.
"""

from __future__ import annotations

import hashlib
import hmac
import re
from dataclasses import dataclass
from pathlib import PurePosixPath

from masterbrain.datacore.extraction import (
    EXTRACTOR_VERSION,
    MAX_SOURCE_BYTES,
    ExtractionStatus,
    _extract_bytes,
)

_SHA256 = re.compile(r"^[a-f0-9]{64}$")


@dataclass(frozen=True, slots=True)
class TextDerivationProof:
    source_sha256: str
    source_size_bytes: int
    text_sha256: str
    normalizer: str


def prove_fileos_text_derivation(
    raw: bytes,
    *,
    locator: str,
    source_sha256: str,
    source_size_bytes: int,
    text: str,
    text_sha256: str,
    normalizer: str,
) -> TextDerivationProof:
    """Replay the exact built-in text transform; refuse unsupported transforms."""
    if type(raw) is not bytes or not 0 < len(raw) <= MAX_SOURCE_BYTES:
        raise ValueError("invalid_source_bytes")
    if type(source_size_bytes) is not int or source_size_bytes != len(raw):
        raise ValueError("source_size_mismatch")
    if (
        type(locator) is not str
        or not 1 <= len(locator) <= 1024
        or "\\" in locator
        or "\x00" in locator
        or PurePosixPath(locator).is_absolute()
        or ".." in PurePosixPath(locator).parts
    ):
        raise ValueError("invalid_source_locator")
    if type(normalizer) is not str or normalizer != EXTRACTOR_VERSION:
        raise ValueError("unsupported_text_transform")
    if type(text) is not str:
        raise ValueError("invalid_normalized_text")
    try:
        encoded_text = text.encode("utf-8")
    except UnicodeError:
        raise ValueError("invalid_normalized_text") from None
    if len(encoded_text) > MAX_SOURCE_BYTES:
        raise ValueError("invalid_normalized_text")
    if (
        type(source_sha256) is not str
        or _SHA256.fullmatch(source_sha256) is None
        or not hmac.compare_digest(hashlib.sha256(raw).hexdigest(), source_sha256)
    ):
        raise ValueError("source_digest_mismatch")
    if (
        type(text_sha256) is not str
        or _SHA256.fullmatch(text_sha256) is None
        or not hmac.compare_digest(hashlib.sha256(encoded_text).hexdigest(), text_sha256)
    ):
        raise ValueError("text_digest_mismatch")
    status, extracted, _, metadata = _extract_bytes(locator, "", raw)
    if status is not ExtractionStatus.EXTRACTED or metadata.get("encoding_uncertain"):
        raise ValueError("unsupported_or_ambiguous_extraction")
    if extracted != text:
        raise ValueError("text_derivation_mismatch")
    return TextDerivationProof(source_sha256, source_size_bytes, text_sha256, normalizer)
