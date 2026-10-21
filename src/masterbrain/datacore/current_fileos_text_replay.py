"""Bounded confined FileOS read plus exact source-byte/text derivation replay.

Caller must first authorize and pin the current source/version/document basis,
then recheck that basis under lock before persisting any receipt. This helper
never edits the file or publishes a Knowledge claim.
"""

from __future__ import annotations

from pathlib import Path

from masterbrain.datacore.confined_files import (
    ConfinedFileChanged,
    ConfinedFileTooLarge,
    ConfinedFileUnavailable,
    read_confined_file,
)
from masterbrain.datacore.extraction import MAX_SOURCE_BYTES
from masterbrain.datacore.fileos import fileos_root_binding_sha256
from masterbrain.datacore.source_text_derivation import (
    TextDerivationProof,
    prove_fileos_text_derivation,
)


class CurrentFileOSFileUnavailable(ValueError):
    """Pinned confined file could not be read unchanged and within bounds."""


def replay_current_fileos_text(
    root: Path, *, locator: str, root_binding_sha256: str,
    source_sha256: str, source_size_bytes: int,
    text: str, text_sha256: str, normalizer: str,
) -> TextDerivationProof:
    """Replay one currently authorized file; return only fixed-size digests."""
    try:
        opened = read_confined_file(
            root, locator, max_bytes=MAX_SOURCE_BYTES, capture_bytes=True,
        )
    except (ConfinedFileUnavailable, ConfinedFileChanged, ConfinedFileTooLarge):
        raise CurrentFileOSFileUnavailable("confined_file_unavailable") from None
    if opened.raw is None:
        raise CurrentFileOSFileUnavailable("confined_file_unavailable")
    proof = prove_fileos_text_derivation(
        opened.raw, locator=locator, source_sha256=source_sha256,
        source_size_bytes=source_size_bytes, text=text,
        text_sha256=text_sha256, normalizer=normalizer,
    )
    if fileos_root_binding_sha256(root) != root_binding_sha256:
        raise ValueError("root_changed")
    return proof
