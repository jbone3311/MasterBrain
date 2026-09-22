"""Source-neutral intake, evidence, extraction, normalization, and indexing primitives."""

from masterbrain.datacore.dedup import (
    DEFAULT_CONFIG,
    compare_files,
    file_hash,
    find_duplicates,
    should_include,
)

__all__ = [
    "DEFAULT_CONFIG",
    "compare_files",
    "file_hash",
    "find_duplicates",
    "should_include",
]
