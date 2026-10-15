"""Compatibility import for the former statement-only text replay contract."""

from masterbrain.datacore.source_text_derivation import (
    TextDerivationProof,
    prove_fileos_text_derivation,
)

__all__ = ["TextDerivationProof", "prove_fileos_text_derivation"]
