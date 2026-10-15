"""Fictional retained-MIME proof without a database or mailbox."""

from __future__ import annotations

import hashlib

import pytest

from email_brain.normalize import PARSER_VERSION, normalize
from email_brain.synthetic import fake_email
from masterbrain.datacore.email_text_derivation import prove_email_text_derivation
from masterbrain.datacore.persistence import EMAIL_NORMALIZER_VERSION


def _basis(raw: bytes) -> dict[str, object]:
    message = normalize(raw)
    text = f"Subject: {message.subject}\nFrom: {message.sender}\n\n{message.text}"
    return {
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "source_size_bytes": len(raw),
        "text": text,
        "text_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "normalizer": EMAIL_NORMALIZER_VERSION,
        "parser_version": PARSER_VERSION,
    }


def test_retained_mime_reproduces_exact_bridged_text() -> None:
    raw = fake_email(0)
    proof = prove_email_text_derivation(raw, **_basis(raw))  # type: ignore[arg-type]
    assert proof.source_size_bytes == len(raw)
    assert proof.source_sha256 == hashlib.sha256(raw).hexdigest()
    assert proof.text_sha256 != proof.source_sha256


@pytest.mark.parametrize(
    "change",
    [
        {"source_size_bytes": 1},
        {"source_sha256": "0" * 64},
        {"text_sha256": "0" * 64},
        {"normalizer": "unknown"},
        {"parser_version": "other-parser"},
        {"text": "Subject: forged"},
    ],
)
def test_retained_mime_rejects_changed_basis(change: dict[str, object]) -> None:
    raw = fake_email(0)
    basis = _basis(raw) | change
    with pytest.raises(ValueError, match="^email_derivation_|^invalid_email_derivation_basis"):
        prove_email_text_derivation(raw, **basis)  # type: ignore[arg-type]


def test_retained_mime_rejects_changed_bytes_even_if_original_digest_supplied() -> None:
    raw = fake_email(0)
    with pytest.raises(ValueError, match="email_derivation_failed"):
        prove_email_text_derivation(raw[:-1] + b"X", **_basis(raw))  # type: ignore[arg-type]
