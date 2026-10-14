"""Fictional-only checks for exact source-byte to normalized-text replay."""

from __future__ import annotations

import hashlib

import pytest

from masterbrain.datacore.extraction import EXTRACTOR_VERSION, MAX_SOURCE_BYTES
from masterbrain.statement_derivation import prove_fileos_text_derivation


def _prove(raw: bytes, *, text: str, locator: str = "fictional.txt", **overrides: object):
    fields: dict[str, object] = {
        "locator": locator,
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "source_size_bytes": len(raw),
        "text": text,
        "text_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "normalizer": EXTRACTOR_VERSION,
    }
    fields.update(overrides)
    return prove_fileos_text_derivation(raw, **fields)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("locator", "raw", "text"),
    [
        ("fictional.txt", b"\xef\xbb\xbf Alpha\r\nBeta \n", "Alpha\nBeta"),
        ("fictional.md", b" # Fictional\n", "# Fictional"),
        ("fictional.txt", " Café\n".encode(), "Café"),
        ("fictional.html", b"<p>Alpha</p><p>Beta</p>", "Alpha\nBeta"),
        ("fictional.csv", b"name,amount\nFictional,12.00\n", "name,amount\nFictional,12.00"),
    ],
)
def test_exact_source_text_derivation(locator: str, raw: bytes, text: str) -> None:
    proof = _prove(raw, text=text, locator=locator)
    assert proof.source_sha256 == hashlib.sha256(raw).hexdigest()
    assert proof.text_sha256 == hashlib.sha256(text.encode()).hexdigest()
    assert proof.normalizer == EXTRACTOR_VERSION
    assert proof.source_size_bytes == len(raw)
    assert not hasattr(proof, "raw") and not hasattr(proof, "text")


@pytest.mark.parametrize(
    ("override", "code"),
    [
        ({"source_sha256": "0" * 64}, "source_digest_mismatch"),
        ({"source_size_bytes": 99}, "source_size_mismatch"),
        ({"text_sha256": "0" * 64}, "text_digest_mismatch"),
        (
            {
                "text": "Fictional changed",
                "text_sha256": hashlib.sha256(b"Fictional changed").hexdigest(),
            },
            "text_derivation_mismatch",
        ),
        ({"normalizer": "fictional-untrusted-v1"}, "unsupported_text_transform"),
        ({"locator": "../fictional.txt"}, "invalid_source_locator"),
        ({"locator": "fictional.pdf"}, "unsupported_or_ambiguous_extraction"),
    ],
)
def test_mismatch_and_unapproved_transform_fail_closed(
    override: dict[str, object], code: str,
) -> None:
    fields: dict[str, object] = {"text": "Fictional"}
    fields.update(override)
    with pytest.raises(ValueError, match=f"^{code}$"):
        _prove(b"Fictional", **fields)  # type: ignore[arg-type]


def test_ambiguous_encoding_nul_empty_and_bounds_fail_closed() -> None:
    for raw, text in ((b"\xffFictional", "ÿFictional"), (b"A\x00B", "A\x00B"),
                      (b"  ", "")):
        with pytest.raises(ValueError, match="unsupported_or_ambiguous_extraction"):
            _prove(raw, text=text)
    with pytest.raises(ValueError, match="invalid_source_bytes"):
        _prove(b"A" * (MAX_SOURCE_BYTES + 1), text="A")
    with pytest.raises(ValueError, match="invalid_source_bytes"):
        _prove(b"", text="")


def test_same_digest_does_not_make_unrelated_text_a_derivation() -> None:
    # Mirrors the current statement-ledger fixture: stored hashes can both be
    # internally valid even when the stored text did not come from source bytes.
    with pytest.raises(ValueError, match="text_derivation_mismatch"):
        _prove(b"fictional immutable statement bytes", text="Fictional holding 2 $50")
