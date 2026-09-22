"""Bounded, read-only FileOS extraction with source-version revalidation."""

from __future__ import annotations

import codecs
import csv
import hashlib
import io
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath
from typing import Any
from uuid import UUID

from email_brain.domain.models import TenantContext
from masterbrain.datacore.persistence import DataCoreStore, ImportResult, PublishedDocument

EXTRACTOR_VERSION = "fileos-text-v1"
MAX_SOURCE_BYTES = 1_048_576
SUPPORTED_SUFFIXES = frozenset({".txt", ".md", ".html", ".htm", ".csv"})


class ExtractionStatus(StrEnum):
    EXTRACTED = "extracted"
    EMPTY = "empty"
    UNSUPPORTED = "unsupported"
    DEFERRED = "deferred"
    CHANGED = "changed"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class ExtractionResult:
    version_id: str
    locator: str
    status: ExtractionStatus
    text: str = ""
    error_code: str | None = None
    metadata: Mapping[str, str | int | bool] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class PublishedExtraction:
    extraction: ExtractionResult
    publication: PublishedDocument | None


@dataclass(frozen=True, slots=True)
class SnapshotPublication:
    imported: ImportResult
    results: tuple[PublishedExtraction, ...]
    counts: Mapping[str, int]


class _HTMLStripper(HTMLParser):
    """FOS-Master-compatible structural HTML text projection."""

    def __init__(self) -> None:
        super().__init__()
        self.result: list[str] = []
        self.skip_tags = {"script", "style", "head"}
        self._skip = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        if tag in self.skip_tags:
            self._skip = True
        elif tag in {"p", "div", "br", "h1", "h2", "h3", "h4", "h5", "h6", "li", "tr"}:
            self.result.append("\n")
        elif tag in {"td", "th"}:
            self.result.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if tag in self.skip_tags:
            self._skip = False

    def handle_data(self, data: str) -> None:
        if not self._skip:
            self.result.append(data)

    def text(self) -> str:
        return "".join(self.result).strip()


def _decode(raw: bytes) -> tuple[str, dict[str, str | int | bool]]:
    metadata: dict[str, str | int | bool]
    if raw.startswith(codecs.BOM_UTF32_LE) or raw.startswith(codecs.BOM_UTF32_BE):
        text, metadata = raw.decode("utf-32"), {}
    elif raw.startswith(codecs.BOM_UTF16_LE) or raw.startswith(codecs.BOM_UTF16_BE):
        text, metadata = raw.decode("utf-16"), {}
    else:
        try:
            text, metadata = raw.decode("utf-8-sig"), {}
        except UnicodeDecodeError:
            text, metadata = raw.decode("latin-1"), {"encoding_uncertain": True}
    return text.replace("\r\n", "\n").replace("\r", "\n"), metadata


def _extract_bytes(
    locator: str, version_id: str, raw: bytes
) -> tuple[ExtractionStatus, str, str | None, dict[str, str | int | bool]]:
    suffix = PurePosixPath(locator).suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        return ExtractionStatus.UNSUPPORTED, "", "unsupported_type", {"suffix": suffix or "none"}
    try:
        text, metadata = _decode(raw)
        if "\x00" in text:
            return ExtractionStatus.FAILED, "", "nul_text", metadata
        if suffix in {".html", ".htm"}:
            stripper = _HTMLStripper()
            stripper.feed(text)
            lines = [line.strip() for line in stripper.text().splitlines()]
            text = "\n".join(line for line in lines if line)
        elif suffix == ".csv":
            rows = list(csv.reader(io.StringIO(text)))
            metadata["row_count"] = max(0, len(rows) - 1)
            metadata["column_count"] = len(rows[0]) if rows else 0
        text = text.strip()
        metadata.update(
            {
                "char_count": len(text),
                "word_count": len(text.split()),
                "extractor_version": EXTRACTOR_VERSION,
            }
        )
        status = ExtractionStatus.EXTRACTED if text else ExtractionStatus.EMPTY
        return status, text, None, metadata
    except (UnicodeError, csv.Error):
        return ExtractionStatus.FAILED, "", "decode_or_parse_failed", {}


def extract_source_version(
    root: Path,
    item: Mapping[str, Any],
    *,
    max_bytes: int = MAX_SOURCE_BYTES,
) -> ExtractionResult:
    """Revalidate one source-bound version and extract without source writes."""
    locator = item.get("locator")
    version_id = item.get("version_id")
    digest = item.get("digest")
    declared_size = item.get("size_bytes")
    if (
        not isinstance(locator, str)
        or not isinstance(version_id, str)
        or not isinstance(digest, Mapping)
        or not isinstance(declared_size, int)
        or isinstance(declared_size, bool)
        or digest.get("algorithm") != "sha256"
        or not isinstance(digest.get("value"), str)
    ):
        raise ValueError("invalid source-version item")
    relative = PurePosixPath(locator)
    if not locator or relative.is_absolute() or ".." in relative.parts or "\\" in locator:
        raise ValueError("unsafe source locator")
    if max_bytes < 1 or max_bytes > MAX_SOURCE_BYTES:
        raise ValueError("invalid extraction byte bound")
    if declared_size > max_bytes:
        return ExtractionResult(
            version_id,
            locator,
            ExtractionStatus.DEFERRED,
            error_code="source_too_large",
            metadata={"size_bytes": declared_size},
        )

    authorized_root = root.resolve(strict=True)
    if not authorized_root.is_dir():
        raise ValueError("FileOS root must be a directory")
    path = authorized_root.joinpath(*relative.parts)
    try:
        if path.is_symlink():
            return ExtractionResult(
                version_id, locator, ExtractionStatus.FAILED, error_code="symlink_refused"
            )
        resolved = path.resolve(strict=True)
        resolved.relative_to(authorized_root)
        before = resolved.stat()
        if not resolved.is_file():
            raise OSError
        with resolved.open("rb") as handle:
            raw = handle.read(max_bytes + 1)
        after = resolved.stat()
    except (OSError, RuntimeError, ValueError):
        return ExtractionResult(
            version_id, locator, ExtractionStatus.FAILED, error_code="source_unavailable"
        )
    if len(raw) > max_bytes:
        return ExtractionResult(
            version_id, locator, ExtractionStatus.DEFERRED, error_code="source_too_large"
        )
    if (
        before.st_size != after.st_size
        or before.st_mtime_ns != after.st_mtime_ns
        or len(raw) != declared_size
    ):
        return ExtractionResult(
            version_id, locator, ExtractionStatus.CHANGED, error_code="source_changed"
        )
    actual = hashlib.sha256(raw).hexdigest()
    if actual != digest["value"]:
        return ExtractionResult(
            version_id, locator, ExtractionStatus.CHANGED, error_code="digest_mismatch"
        )
    status, text, error, metadata = _extract_bytes(locator, version_id, raw)
    return ExtractionResult(version_id, locator, status, text, error, metadata)


class FileOSAdapter:
    def __init__(self, store: DataCoreStore) -> None:
        self.store = store

    def publish_snapshot(
        self,
        ctx: TenantContext,
        root: Path,
        manifest: Mapping[str, Any],
        idempotency_key: UUID,
        *,
        code_revision: str,
    ) -> SnapshotPublication:
        """Import, independently extract each item, and publish successful text."""
        imported = self.store.import_fileos_snapshot(ctx, manifest, idempotency_key)
        raw_items = manifest.get("items")
        if not isinstance(raw_items, list):
            raise ValueError("invalid snapshot items")
        results: list[PublishedExtraction] = []
        counts: Counter[str] = Counter()
        for raw_item in raw_items:
            if not isinstance(raw_item, Mapping):
                raise ValueError("invalid snapshot item")
            extraction = extract_source_version(root, raw_item)
            publication = None
            if extraction.status is ExtractionStatus.EXTRACTED:
                publication = self.store.publish_text(
                    ctx,
                    extraction.version_id,
                    extraction.text,
                    code_revision=code_revision,
                    normalizer=EXTRACTOR_VERSION,
                )
            counts[extraction.status.value] += 1
            results.append(PublishedExtraction(extraction, publication))
        return SnapshotPublication(imported, tuple(results), dict(sorted(counts.items())))
