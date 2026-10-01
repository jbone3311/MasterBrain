"""Tenant-isolated persistence for shared DataCore source observations."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterator, Mapping
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import PurePosixPath
from typing import Any, Literal, cast
from uuid import UUID

from psycopg.types.json import Jsonb

from email_brain.domain.models import TenantContext
from email_brain.store import Conflict, NotFound, Store
from masterbrain.datacore.archive_contract import (
    ArchiveResult,
    ArchiveUnavailable,
)
from masterbrain.datacore.archive_contract import decode_result as decode_archive_result
from masterbrain.datacore.archive_contract import encode_result as encode_archive_result
from masterbrain.datacore.contracts import (
    Digest,
    SourceItemVersion,
    SourceKind,
    SourceRef,
    stable_id,
)
from masterbrain.datacore.fileos import (
    INVENTORY_POLICY_VERSION,
    MAX_SNAPSHOT_EXCLUSIONS,
    ROOT_BINDING_VERSION,
    SNAPSHOT_VERSION,
)

MAX_MANIFEST_ITEMS = 10_000
MAX_NORMALIZED_BYTES = 1_048_576
CHUNK_CHARACTERS = 1_000
NORMALIZER_VERSION = "plain-text-v1"
EMAIL_NORMALIZER_VERSION = "email-message-v1"
EMAIL_ATTACHMENT_NORMALIZER_VERSION = "email-attachment-text-v1"
EMAIL_DOCUMENT_NORMALIZER_PREFIX = "email-pdf-v1"
FILEOS_TEXT_EXTRACTOR_VERSION = "fileos-text-v1"
INDEX_CHUNKER_VERSION = "deterministic-chunks-v1"
MAX_GENERATION_TEXT_BYTES = 64 * 1_048_576
MAX_GENERATION_CHUNKS = 100_000
_IDENTITY = re.compile(r"^[a-z][a-z0-9_-]{0,127}$")
_ARCHIVE_PROCESSOR = re.compile(r"^sandbox-fileos-archive-v1-[a-f0-9]{64}$")
_ARCHIVE_TEXT_SUFFIXES = frozenset({".txt", ".md", ".html", ".htm", ".csv"})
_ARCHIVE_DOCUMENT_FORMATS = {".pdf": "pdf", ".docx": "docx", ".xlsx": "xlsx"}
_ARCHIVE_IMAGE_FORMATS = {
    ".jpg": "jpeg",
    ".jpeg": "jpeg",
    ".png": "png",
    ".tif": "tiff",
    ".tiff": "tiff",
    ".bmp": "bmp",
    ".gif": "gif",
    ".webp": "webp",
}
_IMAGE_OCR_PROCESSOR = re.compile(r"^sandbox-fileos-image-ocr-v1-[a-f0-9]{64}$")


@dataclass(frozen=True, slots=True)
class ImportResult:
    source_id: str
    observed_items: int
    new_versions: int
    unchanged_versions: int


@dataclass(frozen=True, slots=True)
class PublishedDocument:
    document_id: str
    evidence_id: str
    chunks: int
    changed: bool


@dataclass(frozen=True, slots=True)
class EmailBridgeResult:
    source_id: str
    item_id: str
    version_id: str
    evidence_id: str
    document_id: str
    chunks: int
    changed: bool


@dataclass(frozen=True, slots=True)
class EmailAttachmentBridgeResult:
    source_id: str
    item_id: str
    version_id: str
    evidence_id: str
    part_id: str
    document_id: str | None
    chunks: int
    outcome: str
    changed: bool


@dataclass(frozen=True, slots=True)
class EmailDocumentBridgeResult:
    source_id: str
    item_id: str
    version_id: str
    evidence_id: str
    document_id: str
    chunks: int
    extraction_status: str
    changed: bool


@dataclass(frozen=True, slots=True)
class SearchHit:
    chunk_id: str
    document_id: str
    evidence_id: str
    source_id: str
    locator: str
    excerpt: str
    rank: float


@dataclass(frozen=True, slots=True)
class EmailFamilySearch:
    messages: tuple[SearchHit, ...]
    attachments: tuple[SearchHit, ...]
    documents: tuple[SearchHit, ...]


@dataclass(frozen=True, slots=True)
class FileOSRunReceipt:
    run_id: UUID
    source_id: str
    observed_at: datetime
    completed_at: datetime
    item_count: int
    outcomes: dict[str, int]
    published_documents: int
    recorded: bool


@dataclass(frozen=True, slots=True)
class FileOSTransitionPacketRecord:
    packet_id: UUID
    source_id: str
    packet_sha256: str
    recorded_at: datetime
    recorded: bool


@dataclass(frozen=True, slots=True)
class FileOSV2StagedInventoryRecord:
    stage_id: UUID
    packet_id: UUID
    source_id: str
    candidate_sha256: str
    recorded_at: datetime
    recorded: bool


@dataclass(frozen=True, slots=True)
class IndexGeneration:
    generation_id: str
    source_id: str
    run_id: UUID
    item_count: int
    document_count: int
    chunk_count: int
    plan_sha256: str
    ready_at: datetime
    recorded: bool


@dataclass(frozen=True, slots=True)
class IndexActivation:
    source_id: str
    generation_id: str
    previous_generation_id: str | None
    activated_at: datetime
    recorded: bool


@dataclass(frozen=True, slots=True)
class ArchiveInventoryRecord:
    inventory_id: str
    source_id: str
    item_id: str
    source_version_id: str
    processor_version: str
    member_count: int
    skipped_count: int
    changed: bool


@dataclass(frozen=True, slots=True)
class ArchiveMemberTargetRecord:
    inventory_id: str
    inventory_processor_version: str
    source_id: str
    item_id: str
    source_version_id: str
    source_locator: str
    source_sha256: str
    source_size_bytes: int
    source_media_type: str
    member_locator: str
    member_sha256: str
    member_size_bytes: int
    member_media_type: str
    member_depth: int
    member_parent_locator: str | None


@dataclass(frozen=True, slots=True)
class ArchiveMemberTextRecord:
    inventory_id: str
    member_locator: str
    source_id: str
    item_id: str
    version_id: str
    evidence_id: str
    document_id: str
    chunks: int
    changed: bool


def _canonical_digest(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(encoded).hexdigest()


def fileos_manifest_sha256(manifest: Mapping[str, Any]) -> str:
    """Canonical digest shared by intake and whole-run receipts."""
    _manifest_items(manifest)
    return _canonical_digest(manifest)


def fileos_inventory_policy_sha256(manifest: Mapping[str, Any]) -> str:
    """Validate and identify the exact policy used for FileOS inventory membership."""
    policy = manifest.get("policy")
    expected_fields = {
        "policy_version",
        "hash_algorithm",
        "follow_file_symlinks",
        "min_file_size",
        "max_file_size_mb",
        "include_extensions",
        "exclude_patterns",
    }
    if not isinstance(policy, Mapping) or set(policy) != expected_fields:
        raise ValueError("invalid FileOS inventory policy")
    minimum = policy["min_file_size"]
    maximum = policy["max_file_size_mb"]
    extensions = policy["include_extensions"]
    exclusions = policy["exclude_patterns"]
    if (
        policy["policy_version"] != INVENTORY_POLICY_VERSION
        or policy["hash_algorithm"] != "sha256"
        or type(policy["follow_file_symlinks"]) is not bool
        or type(minimum) is not int
        or not 0 <= minimum <= 2048 * 1024 * 1024
        or type(maximum) is not int
        or not 1 <= maximum <= 2048
        or minimum > maximum * 1024 * 1024
        or (extensions is not None and not isinstance(extensions, list))
        or not isinstance(exclusions, list)
    ):
        raise ValueError("invalid FileOS inventory policy")
    if extensions is not None and (
        len(extensions) > 256
        or any(
            not isinstance(value, str) or len(value) > 32 or "\x00" in value for value in extensions
        )
    ):
        raise ValueError("invalid FileOS inventory policy")
    if len(exclusions) > 256 or any(
        not isinstance(value, str) or not 1 <= len(value) <= 128 or "\x00" in value
        for value in exclusions
    ):
        raise ValueError("invalid FileOS inventory policy")
    return _canonical_digest({"manifest_version": SNAPSHOT_VERSION, "policy": dict(policy)})


def fileos_manifest_root_binding_sha256(manifest: Mapping[str, Any]) -> str:
    """Validate the private local-root identity carried by a FileOS snapshot."""
    binding = manifest.get("root_binding")
    if not isinstance(binding, Mapping) or set(binding) != {"version", "sha256"}:
        raise ValueError("invalid FileOS root binding")
    digest = binding["sha256"]
    if (
        binding["version"] != ROOT_BINDING_VERSION
        or not isinstance(digest, str)
        or re.fullmatch(r"[a-f0-9]{64}", digest) is None
    ):
        raise ValueError("invalid FileOS root binding")
    return digest


def _parse_time(value: object) -> datetime:
    if not isinstance(value, str) or len(value) > 100:
        raise ValueError("invalid observed timestamp")
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("observed timestamp must be timezone-aware")
    return parsed.astimezone(UTC)


def _fileos_v2_staged_rows(
    candidate: Mapping[str, Any], source_id: str
) -> list[tuple[str, str, str | None, str | None, str | None, int | None, str | None, str | None]]:
    """Validate and project the closed donor ledger without inventing versions."""
    from masterbrain.datacore.fileos_donor_candidate import CANDIDATE_VERSION, DONOR_COMMIT
    from masterbrain.datacore.fileos_donor_shadow import (
        DONOR_HASH_LIMIT,
        MAX_SHADOW_RECORDS,
        SHADOW_PROFILE,
    )

    policy = candidate.get("policy")
    source = candidate.get("source")
    counts = candidate.get("counts")
    root = candidate.get("root_binding")
    ledgers = {
        "hashed": "hashed", "deferred": "deferred",
        "exclusions": "excluded", "errors": "error",
    }
    if (
        set(candidate) != {"candidate_version", "publishable", "source", "observed_at",
                           "root_binding", "policy", "counts", "hashed", "deferred",
                           "exclusions", "errors"}
        or candidate.get("candidate_version") != CANDIDATE_VERSION
        or candidate.get("publishable") is not False
        or not isinstance(source, Mapping)
        or source != {"source_id": source_id, "kind": "fileos"}
        or not isinstance(root, Mapping)
        or set(root) != {"version", "sha256"}
        or root.get("version") != ROOT_BINDING_VERSION
        or not isinstance(root.get("sha256"), str)
        or re.fullmatch(r"[a-f0-9]{64}", root["sha256"]) is None
        or not isinstance(policy, Mapping)
        or set(policy) != {"shadow_profile", "donor_commit", "hash_limit_bytes",
                           "follow_file_symlinks", "metadata_only"}
        or policy.get("shadow_profile") != SHADOW_PROFILE
        or policy.get("donor_commit") != DONOR_COMMIT
        or policy.get("hash_limit_bytes") != DONOR_HASH_LIMIT
        or policy.get("follow_file_symlinks") is not False
        or type(policy.get("metadata_only")) is not bool
        or not isinstance(counts, Mapping)
        or set(counts) != {"hashed", "deferred", "excluded", "errors"}
        or any(type(value) is not int or value < 0 for value in counts.values())
        or any(not isinstance(candidate.get(name), list) for name in ledgers)
        or counts != {"hashed": len(candidate["hashed"]),
                      "deferred": len(candidate["deferred"]),
                      "excluded": len(candidate["exclusions"]),
                      "errors": len(candidate["errors"])}
        or sum(counts.values()) > MAX_SHADOW_RECORDS
    ):
        raise ValueError("invalid FileOS v2 candidate ledger")
    observed = _parse_time(candidate.get("observed_at"))
    rows: list[
        tuple[str, str, str | None, str | None, str | None, int | None, str | None, str | None]
    ] = []
    occupied: set[str] = set()
    for ledger, kind in ledgers.items():
        for raw in candidate[ledger]:
            if not isinstance(raw, Mapping):
                raise ValueError("invalid FileOS v2 candidate row")
            locator = raw.get("locator")
            if (
                not isinstance(locator, str)
                or not 1 <= len(locator) <= 4000
                or locator.startswith(("/", "\\"))
                or "\\" in locator or "\x00" in locator
                or (locator == "." and kind != "error")
                or (locator != "." and any(part in {"", ".", ".."}
                                                for part in locator.split("/")))
                or locator in occupied
            ):
                raise ValueError("invalid FileOS v2 candidate locator")
            occupied.add(locator)
            if kind == "hashed":
                if set(raw) != {"item_id", "version_id", "locator", "observed_at",
                                "digest", "size_bytes", "media_type"}:
                    raise ValueError("invalid FileOS v2 hashed row")
                digest = raw["digest"]
                size = raw["size_bytes"]
                media = raw["media_type"]
                if (
                    not isinstance(digest, Mapping)
                    or set(digest) != {"algorithm", "value"}
                    or digest.get("algorithm") != "sha256"
                    or not isinstance(digest.get("value"), str)
                    or re.fullmatch(r"[a-f0-9]{64}", digest["value"]) is None
                    or type(size) is not int or not 0 <= size <= DONOR_HASH_LIMIT
                    or not isinstance(media, str) or not 1 <= len(media) <= 200
                    or _parse_time(raw["observed_at"]) != observed
                ):
                    raise ValueError("invalid FileOS v2 hashed row")
                item_id = stable_id("item", source_id, locator)
                version_id = stable_id("version", item_id, digest["value"], str(size))
                if raw["item_id"] != item_id or raw["version_id"] != version_id:
                    raise ValueError("invalid FileOS v2 hashed identity")
                rows.append(
                    (kind, locator, item_id, version_id, digest["value"], size, media, None)
                )
            elif kind == "deferred":
                if (
                    set(raw) != {"item_id", "locator", "size_bytes", "reason"}
                    or raw["item_id"] != stable_id("item", source_id, locator)
                    or type(raw["size_bytes"]) is not int or raw["size_bytes"] < 0
                    or raw["reason"] not in {"no_hash", "dataless", "oversize"}
                    or (raw["reason"] == "oversize" and raw["size_bytes"] <= DONOR_HASH_LIMIT)
                ):
                    raise ValueError("invalid FileOS v2 deferred row")
                rows.append((kind, locator, raw["item_id"], None, None,
                             raw["size_bytes"], None, raw["reason"]))
            else:
                reason_key = "reason" if kind == "excluded" else "code"
                allowed = (
                    {"donor_junk_dir", "donor_operational_dir", "donor_junk_file",
                     "symlink_directory", "not_regular"}
                    if kind == "excluded" else
                    {"directory_unreadable", "root_changed_during_scan", "symlink_skipped",
                     "changed_during_scan", "file_unreadable"}
                )
                if set(raw) != {"locator", reason_key} or raw[reason_key] not in allowed:
                    raise ValueError("invalid FileOS v2 coverage row")
                rows.append((kind, locator, None, None, None, None, None, raw[reason_key]))
    excluded_directories = {
        locator for kind, locator, *_, reason in rows
        if kind == "excluded"
        and reason in {"donor_junk_dir", "donor_operational_dir", "symlink_directory"}
    }
    for locator in occupied:
        parts = locator.split("/")
        if any("/".join(parts[:index]) in excluded_directories
               for index in range(1, len(parts))):
            raise ValueError("overlapping FileOS v2 candidate directory exclusion")
    return rows


def _fileos_transition_detail(kind: str, raw: object) -> dict[str, Any]:
    """Project only fixed, bounded private fields from an immutable packet row."""
    if not isinstance(raw, Mapping):
        raise Conflict("FileOS transition packet integrity requires review")
    locator = raw.get("locator")
    if (
        not isinstance(locator, str)
        or not 1 <= len(locator) <= 4000
        or locator.startswith(("/", "\\"))
        or "\\" in locator
        or "\x00" in locator
        or (locator != "." and any(part in {"", ".", ".."} for part in locator.split("/")))
        or (locator == "." and kind != "errors")
    ):
        raise Conflict("FileOS transition packet integrity requires review")
    detail: dict[str, Any] = {"ledger": kind, "locator": locator}
    if kind == "prior":
        state = raw.get("state")
        if not isinstance(state, str) or state not in {
            "unchanged", "changed", "deferred_prior", "excluded_prior",
            "error_covered_prior", "unobserved_prior",
        }:
            raise Conflict("FileOS transition packet integrity requires review")
        if not isinstance(raw.get("item_id"), str) or not isinstance(
            raw.get("prior_version_id"), str
        ):
            raise Conflict("FileOS transition packet integrity requires review")
        detail["state"] = state
        for key in ("item_id", "prior_version_id", "donor_version_id", "reason"):
            value = raw.get(key)
            if value is not None:
                if not isinstance(value, str) or not 1 <= len(value) <= 128:
                    raise Conflict("FileOS transition packet integrity requires review")
                detail[key] = value
    elif kind == "hashed":
        digest = raw.get("digest")
        size = raw.get("size_bytes")
        if (
            not isinstance(digest, Mapping)
            or digest.get("algorithm") != "sha256"
            or not isinstance(digest.get("value"), str)
            or re.fullmatch(r"[a-f0-9]{64}", digest["value"]) is None
            or type(size) is not int
            or not 0 <= size <= 2**63 - 1
        ):
            raise Conflict("FileOS transition packet integrity requires review")
        for key in ("item_id", "version_id"):
            value = raw.get(key)
            if not isinstance(value, str) or not 1 <= len(value) <= 128:
                raise Conflict("FileOS transition packet integrity requires review")
            detail[key] = value
        detail["sha256"] = digest["value"]
        detail["size_bytes"] = size
    elif kind == "deferred":
        item_id = raw.get("item_id")
        size = raw.get("size_bytes")
        reason = raw.get("reason")
        if (
            not isinstance(item_id, str)
            or not 1 <= len(item_id) <= 128
            or type(size) is not int
            or not 0 <= size <= 2**63 - 1
            or not isinstance(reason, str)
            or reason not in {"no_hash", "dataless", "oversize"}
            or "version_id" in raw
            or "digest" in raw
        ):
            raise Conflict("FileOS transition packet integrity requires review")
        detail.update(item_id=item_id, size_bytes=size, reason=reason)
    elif kind == "exclusions":
        reason = raw.get("reason")
        if not isinstance(reason, str) or reason not in {
            "donor_junk_dir", "donor_operational_dir", "donor_junk_file",
            "symlink_directory", "not_regular",
        }:
            raise Conflict("FileOS transition packet integrity requires review")
        detail["reason"] = reason
    elif kind == "errors":
        code = raw.get("code")
        if not isinstance(code, str) or code not in {
            "directory_unreadable", "root_changed_during_scan", "symlink_skipped",
            "changed_during_scan", "file_unreadable",
        }:
            raise Conflict("FileOS transition packet integrity requires review")
        detail["code"] = code
    else:
        raise Conflict("FileOS transition packet integrity requires review")
    return detail


def _manifest_items(
    manifest: Mapping[str, Any],
) -> tuple[SourceRef, datetime, list[SourceItemVersion]]:
    if manifest.get("manifest_version") != SNAPSHOT_VERSION:
        raise ValueError("unsupported snapshot manifest")
    fileos_manifest_root_binding_sha256(manifest)
    raw_source = manifest.get("source")
    if not isinstance(raw_source, Mapping):
        raise ValueError("missing source")
    source_id = raw_source.get("source_id")
    kind = raw_source.get("kind")
    if not isinstance(source_id, str) or kind != SourceKind.FILEOS.value:
        raise ValueError("invalid FileOS source")
    source = SourceRef(source_id, SourceKind.FILEOS, source_id)
    observed_at = _parse_time(manifest.get("observed_at"))
    raw_items = manifest.get("items")
    if not isinstance(raw_items, list) or len(raw_items) > MAX_MANIFEST_ITEMS:
        raise ValueError("snapshot item bound exceeded")
    items: list[SourceItemVersion] = []
    locators: set[str] = set()
    identities: set[str] = set()
    for raw in raw_items:
        if not isinstance(raw, Mapping):
            raise ValueError("invalid snapshot item")
        digest = raw.get("digest")
        metadata = raw.get("metadata", {})
        if not isinstance(digest, Mapping) or not isinstance(metadata, Mapping):
            raise ValueError("invalid snapshot item fields")
        item = SourceItemVersion(
            cast(str, raw.get("item_id")),
            cast(str, raw.get("version_id")),
            source,
            cast(str, raw.get("locator")),
            _parse_time(raw.get("observed_at")),
            Digest(cast(str, digest.get("algorithm")), cast(str, digest.get("value"))),
            cast(int, raw.get("size_bytes")),
            cast(str, raw.get("media_type")),
            cast(Mapping[str, Any], metadata),
        )
        expected_item = stable_id("item", source_id, item.locator)
        expected_version = stable_id(
            "version", expected_item, item.content.value, str(item.size_bytes)
        )
        if item.item_id != expected_item or item.version_id != expected_version:
            raise ValueError("snapshot identity does not match content")
        if item.observed_at != observed_at:
            raise ValueError("mixed snapshot observation times")
        if item.locator in locators or item.item_id in identities:
            raise ValueError("duplicate snapshot item")
        locators.add(item.locator)
        identities.add(item.item_id)
        items.append(item)
    counts = manifest.get("counts")
    if not isinstance(counts, Mapping) or counts.get("items") != len(items):
        raise ValueError("snapshot count does not match items")
    return source, observed_at, items


def validate_fileos_manifest(manifest: Mapping[str, Any]) -> tuple[str, int]:
    """Validate a complete snapshot without persisting it or exposing its locators."""
    source, _, items = _manifest_items(manifest)
    return source.source_id, len(items)


def validate_fileos_completion_coverage(
    manifest: Mapping[str, Any],
) -> tuple[SourceRef, datetime, list[SourceItemVersion]]:
    """Refuse a completion ledger that could mistake a scan failure for absence."""
    source, observed_at, items = _manifest_items(manifest)
    fileos_inventory_policy_sha256(manifest)
    counts = manifest["counts"]
    errors = manifest.get("errors")
    if (
        not isinstance(errors, list)
        or type(counts.get("errors")) is not int
        or counts["errors"] != len(errors)
    ):
        raise ValueError("invalid FileOS snapshot coverage")
    item_locators = {item.locator for item in items}
    error_locators: set[str] = set()
    policy = manifest.get("policy")
    no_follow = isinstance(policy, Mapping) and policy.get("follow_file_symlinks") is False
    for raw in errors:
        if not isinstance(raw, Mapping):
            raise ValueError("invalid FileOS snapshot coverage")
        locator = raw.get("locator")
        code = raw.get("code")
        if (
            not isinstance(locator, str)
            or not locator
            or locator.startswith(("/", "\\"))
            or "\x00" in locator
            or ".." in locator.replace("\\", "/").split("/")
            or locator in item_locators
            or locator in error_locators
        ):
            raise ValueError("invalid FileOS snapshot coverage")
        error_locators.add(locator)
        if code != "symlink_skipped" or not no_follow:
            raise ValueError("incomplete FileOS snapshot coverage")
    exclusions = manifest.get("exclusions")
    if (
        not isinstance(exclusions, list)
        or len(exclusions) > MAX_SNAPSHOT_EXCLUSIONS
        or type(counts.get("excluded")) is not int
        or counts["excluded"] != len(exclusions)
    ):
        raise ValueError("invalid FileOS snapshot exclusion coverage")
    exclusion_locators: set[str] = set()
    directory_exclusions: set[str] = set()
    ordered: list[tuple[str, str, str]] = []
    file_reasons = {
        "policy_path",
        "not_regular",
        "below_min_size",
        "above_max_size",
        "extension_filtered",
    }
    directory_reasons = {"policy_path", "symlink_directory"}
    for raw in exclusions:
        if not isinstance(raw, Mapping) or set(raw) != {"locator", "kind", "reason"}:
            raise ValueError("invalid FileOS snapshot exclusion coverage")
        locator, kind, reason = raw["locator"], raw["kind"], raw["reason"]
        if (
            not isinstance(locator, str)
            or not 1 <= len(locator) <= 4000
            or locator.startswith(("/", "\\"))
            or "\x00" in locator
            or any(part in {"", ".", ".."} for part in locator.replace("\\", "/").split("/"))
            or locator in item_locators
            or locator in error_locators
            or locator in exclusion_locators
            or not isinstance(kind, str)
            or not isinstance(reason, str)
            or kind not in {"file", "directory"}
            or (kind == "file" and reason not in file_reasons)
            or (kind == "directory" and reason not in directory_reasons)
        ):
            raise ValueError("invalid FileOS snapshot exclusion coverage")
        exclusion_locators.add(locator)
        if kind == "directory":
            directory_exclusions.add(locator)
        ordered.append((locator, kind, reason))
    if ordered != sorted(ordered):
        raise ValueError("invalid FileOS snapshot exclusion coverage")
    for locator in item_locators | error_locators | exclusion_locators:
        parts = locator.split("/")
        if any("/".join(parts[:index]) in directory_exclusions for index in range(1, len(parts))):
            raise ValueError("invalid FileOS snapshot exclusion coverage")
    return source, observed_at, items


def fileos_missing_locator_is_excluded(
    locator: str,
    excluded_files: set[str],
    excluded_directories: set[str],
    skipped_symlinks: set[str],
) -> bool:
    """A present-but-unindexed path must never become deletion evidence."""
    if locator in skipped_symlinks or locator in excluded_files or locator in excluded_directories:
        return True
    parts = locator.split("/")
    return any("/".join(parts[:index]) in excluded_directories for index in range(1, len(parts)))


def fileos_mass_loss_requires_review(previous_items: int, missing_items: int) -> bool:
    """Match the pinned donor's mass-prune threshold without authorizing pruning."""
    return missing_items >= 10 and missing_items * 2 >= previous_items


def deterministic_chunks(
    text: str, limit: int = CHUNK_CHARACTERS
) -> Iterator[tuple[int, int, str]]:
    """Yield exact, stable character ranges with a soft whitespace boundary."""
    if limit < 32 or limit > 2_000:
        raise ValueError("invalid chunk limit")
    start = 0
    while start < len(text):
        end = min(start + limit, len(text))
        if end < len(text):
            boundary = text.rfind(" ", start + limit // 2, end)
            if boundary > start:
                end = boundary + 1
        yield start, end, text[start:end]
        start = end


class DataCoreStore:
    """Shared DataCore repository layered on the existing secure SQL connection."""

    def __init__(self, store: Store) -> None:
        self.store = store

    def email_bridge_plan(
        self,
        ctx: TenantContext,
        account_id: UUID,
        *,
        after: UUID | None = None,
        limit: int = 25,
    ) -> dict[str, Any]:
        """Preview bounded current Email versions for explicit bridge operation."""
        self.store.require(ctx, "brain.source.ingest")
        self.store.require(ctx, "brain.document.publish")
        if not isinstance(account_id, UUID) or (after is not None and not isinstance(after, UUID)):
            raise ValueError("invalid Email bridge plan identity")
        if not 1 <= limit <= 100:
            raise ValueError("invalid Email bridge plan limit")
        with self.store.transaction(ctx) as conn:
            if not conn.execute(
                "SELECT 1 FROM mail_accounts WHERE id=%s", (account_id,)
            ).fetchone():
                raise NotFound()
            anchor = None
            if after is not None:
                anchor = conn.execute(
                    "SELECT recorded_at,id FROM message_versions WHERE account_id=%s AND id=%s",
                    (account_id, after),
                ).fetchone()
                if not anchor:
                    raise NotFound()
            rows = conn.execute(
                "SELECT v.id AS legacy_version_id,v.recorded_at,"
                "(b.legacy_version_id IS NOT NULL) AS already_bridged "
                "FROM message_versions v JOIN messages m ON m.tenant_id=v.tenant_id "
                "AND m.account_id=v.account_id AND m.id=v.message_id "
                "AND m.raw_sha256=v.raw_sha256 AND m.parser_version=v.parser_version "
                "LEFT JOIN brain_email_bridge_receipts b ON b.tenant_id=v.tenant_id "
                "AND b.legacy_version_id=v.id WHERE v.account_id=%s "
                "AND NOT m.deleted AND NOT m.quarantined "
                "AND (%s::timestamptz IS NULL OR (v.recorded_at,v.id)>(%s,%s)) "
                "ORDER BY v.recorded_at,v.id LIMIT %s",
                (
                    account_id,
                    anchor["recorded_at"] if anchor else None,
                    anchor["recorded_at"] if anchor else None,
                    after,
                    limit + 1,
                ),
            ).fetchall()
            self.store.audit(conn, ctx, "brain.email_bridge_plan", "mail_account", str(account_id))
        page = rows[:limit]
        return {
            "account_id": str(account_id),
            "results": [
                {
                    "legacy_version_id": str(row["legacy_version_id"]),
                    "recorded_at": row["recorded_at"].isoformat(),
                    "already_bridged": row["already_bridged"],
                }
                for row in page
            ],
            "next_cursor": (
                str(page[-1]["legacy_version_id"]) if len(rows) > limit and page else None
            ),
            "limit": limit,
            "source_effects": False,
            "data_effects": False,
        }

    def archive_member_text_plan(
        self,
        ctx: TenantContext,
        inventory_id: str,
        *,
        after: int | None = None,
        limit: int = 25,
    ) -> dict[str, Any]:
        """Preview eligible members in one current, sealed archive inventory."""
        self.store.require(ctx, "brain.source.ingest")
        self.store.require(ctx, "brain.document.publish")
        if (
            not isinstance(inventory_id, str)
            or not re.fullmatch(r"archive_inventory_[a-f0-9]{32}", inventory_id)
            or (after is not None and (type(after) is not int or not 0 <= after <= 1999))
            or type(limit) is not int
            or not 1 <= limit <= 100
        ):
            raise ValueError("invalid archive member text plan")
        eligible = (
            "NOT m.is_container AND m.observed_size<=%s AND ("
            "lower(m.locator) LIKE '%%.txt' OR lower(m.locator) LIKE '%%.md' OR "
            "lower(m.locator) LIKE '%%.html' OR lower(m.locator) LIKE '%%.htm' OR "
            "lower(m.locator) LIKE '%%.csv')"
        )
        with self.store.transaction(ctx) as conn:
            current = conn.execute(
                "SELECT 1 FROM brain_archive_inventories a JOIN brain_source_items p ON "
                "p.tenant_id=a.tenant_id AND p.source_id=a.source_id AND p.id=a.item_id "
                "AND p.current_version_id=a.source_version_id WHERE a.id=%s",
                (inventory_id,),
            ).fetchone()
            if not current:
                raise NotFound()
            if after is not None:
                anchor = conn.execute(
                    "SELECT 1 FROM brain_archive_members m WHERE m.inventory_id=%s "
                    f"AND m.ordinal=%s AND {eligible}",
                    (inventory_id, after, MAX_NORMALIZED_BYTES),
                ).fetchone()
                if not anchor:
                    raise NotFound()
            total = conn.execute(
                "SELECT count(*) AS n FROM brain_archive_members m WHERE m.inventory_id=%s "
                f"AND {eligible}",
                (inventory_id, MAX_NORMALIZED_BYTES),
            ).fetchone()
            assert total is not None
            rows = conn.execute(
                "SELECT m.ordinal,m.locator AS member_locator,m.observed_size AS size_bytes,"
                "m.media_hint AS media_type,m.depth,EXISTS (SELECT 1 FROM "
                "brain_archive_member_text_receipts r WHERE r.inventory_id=m.inventory_id "
                "AND r.member_locator=m.locator) AS already_published "
                "FROM brain_archive_members m WHERE m.inventory_id=%s "
                f"AND {eligible} AND (%s::integer IS NULL OR m.ordinal>%s) "
                "ORDER BY m.ordinal LIMIT %s",
                (
                    inventory_id,
                    MAX_NORMALIZED_BYTES,
                    after,
                    after,
                    limit + 1,
                ),
            ).fetchall()
            self.store.audit(
                conn,
                ctx,
                "brain.archive_member_text_plan",
                "archive_inventory",
                inventory_id,
            )
        page = rows[:limit]
        return {
            "inventory_id": inventory_id,
            "eligible_members": total["n"],
            "results": [dict(row) for row in page],
            "next_cursor": page[-1]["ordinal"] if len(rows) > limit and page else None,
            "limit": limit,
            "untrusted_metadata": True,
            "source_effects": False,
            "data_effects": False,
        }

    def archive_member_document_plan(
        self,
        ctx: TenantContext,
        inventory_id: str,
        *,
        after: int | None = None,
        limit: int = 25,
    ) -> dict[str, Any]:
        """Preview exact PDF/Office candidates in one current archive inventory."""
        self.store.require(ctx, "brain.source.ingest")
        self.store.require(ctx, "brain.document.publish")
        if (
            not isinstance(inventory_id, str)
            or not re.fullmatch(r"archive_inventory_[a-f0-9]{32}", inventory_id)
            or (after is not None and (type(after) is not int or not 0 <= after <= 1999))
            or type(limit) is not int
            or not 1 <= limit <= 100
        ):
            raise ValueError("invalid archive member document plan")
        eligible = (
            "m.observed_size<=%s AND ((NOT m.is_container "
            "AND lower(right(m.locator,4))='.pdf' AND m.media_hint='application/pdf') OR "
            "(m.is_container AND lower(right(m.locator,5))='.docx' AND m.media_hint="
            "'application/vnd.openxmlformats-officedocument.wordprocessingml.document') OR "
            "(m.is_container AND lower(right(m.locator,5))='.xlsx' AND m.media_hint="
            "'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'))"
        )
        with self.store.transaction(ctx) as conn:
            current = conn.execute(
                "SELECT 1 FROM brain_archive_inventories a JOIN brain_source_items p ON "
                "p.tenant_id=a.tenant_id AND p.source_id=a.source_id AND p.id=a.item_id "
                "AND p.current_version_id=a.source_version_id WHERE a.id=%s",
                (inventory_id,),
            ).fetchone()
            if not current:
                raise NotFound()
            if after is not None:
                anchor = conn.execute(
                    "SELECT 1 FROM brain_archive_members m WHERE m.inventory_id=%s "
                    f"AND m.ordinal=%s AND {eligible}",
                    (inventory_id, after, 8 * 1024 * 1024),
                ).fetchone()
                if not anchor:
                    raise NotFound()
            total = conn.execute(
                "SELECT count(*) AS n FROM brain_archive_members m WHERE m.inventory_id=%s "
                f"AND {eligible}",
                (inventory_id, 8 * 1024 * 1024),
            ).fetchone()
            assert total is not None
            rows = conn.execute(
                "SELECT m.ordinal,m.locator AS member_locator,m.observed_size AS size_bytes,"
                "m.media_hint AS media_type,m.depth,CASE "
                "WHEN lower(right(m.locator,4))='.pdf' THEN 'pdf' "
                "WHEN lower(right(m.locator,5))='.docx' THEN 'docx' ELSE 'xlsx' END "
                "AS document_format,EXISTS (SELECT 1 FROM "
                "brain_archive_member_document_receipts r "
                "WHERE r.inventory_id=m.inventory_id AND r.member_locator=m.locator) "
                "AS already_published FROM brain_archive_members m "
                f"WHERE m.inventory_id=%s AND {eligible} "
                "AND (%s::integer IS NULL OR m.ordinal>%s) "
                "ORDER BY m.ordinal LIMIT %s",
                (inventory_id, 8 * 1024 * 1024, after, after, limit + 1),
            ).fetchall()
            self.store.audit(
                conn,
                ctx,
                "brain.archive_member_document_plan",
                "archive_inventory",
                inventory_id,
            )
        page = rows[:limit]
        return {
            "inventory_id": inventory_id,
            "eligible_members": total["n"],
            "results": [dict(row) for row in page],
            "next_cursor": page[-1]["ordinal"] if len(rows) > limit and page else None,
            "limit": limit,
            "untrusted_metadata": True,
            "source_effects": False,
            "worker_effects": False,
            "data_effects": False,
        }

    def email_part_bridge_plan(
        self,
        ctx: TenantContext,
        account_id: UUID,
        kind: Literal["attachment", "document"],
        *,
        after: UUID | None = None,
        limit: int = 25,
    ) -> dict[str, Any]:
        """Preview bounded current Email attachment or approved-document bridges."""
        self.store.require(ctx, "brain.source.ingest")
        self.store.require(ctx, "brain.document.publish")
        if (
            not isinstance(account_id, UUID)
            or kind not in {"attachment", "document"}
            or (after is not None and not isinstance(after, UUID))
        ):
            raise ValueError("invalid Email part bridge plan identity")
        if not 1 <= limit <= 100:
            raise ValueError("invalid Email part bridge plan limit")
        with self.store.transaction(ctx) as conn:
            if not conn.execute(
                "SELECT 1 FROM mail_accounts WHERE id=%s", (account_id,)
            ).fetchone():
                raise NotFound()
            anchor = None
            if after is not None:
                table = "attachment_receipts" if kind == "attachment" else "document_extractions"
                anchor = conn.execute(
                    f"SELECT {'received_at' if kind == 'attachment' else 'created_at'} "
                    f"AS created_at,id FROM {table} WHERE account_id=%s AND id=%s",
                    (account_id, after),
                ).fetchone()
                if not anchor:
                    raise NotFound()
            if kind == "attachment":
                rows = conn.execute(
                    "SELECT a.id AS legacy_id,a.evidence_id AS legacy_parent_version_id,"
                    "a.received_at AS created_at,a.status AS state,"
                    "(ab.legacy_attachment_id IS NOT NULL) AS already_bridged "
                    "FROM attachment_receipts a JOIN message_versions mv ON "
                    "mv.tenant_id=a.tenant_id AND mv.account_id=a.account_id "
                    "AND mv.id=a.evidence_id JOIN messages m ON m.tenant_id=mv.tenant_id "
                    "AND m.account_id=mv.account_id AND m.id=mv.message_id "
                    "AND m.raw_sha256=mv.raw_sha256 AND m.parser_version=mv.parser_version "
                    "JOIN brain_email_bridge_receipts eb ON eb.tenant_id=mv.tenant_id "
                    "AND eb.account_id=mv.account_id AND eb.legacy_version_id=mv.id "
                    "JOIN brain_source_items pi ON pi.tenant_id=eb.tenant_id "
                    "AND pi.id=eb.item_id AND pi.current_version_id=eb.version_id "
                    "LEFT JOIN brain_email_attachment_bridge_receipts ab ON "
                    "ab.tenant_id=a.tenant_id AND ab.account_id=a.account_id "
                    "AND ab.legacy_attachment_id=a.id WHERE a.account_id=%s "
                    "AND NOT m.deleted AND NOT m.quarantined "
                    "AND (%s::timestamptz IS NULL OR (a.received_at,a.id)>(%s,%s)) "
                    "ORDER BY a.received_at,a.id LIMIT %s",
                    (
                        account_id,
                        anchor["created_at"] if anchor else None,
                        anchor["created_at"] if anchor else None,
                        after,
                        limit + 1,
                    ),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT d.id AS legacy_id,a.evidence_id AS legacy_parent_version_id,"
                    "d.receipt_id AS legacy_attachment_id,d.created_at,d.status AS state,"
                    "(db.legacy_extraction_id IS NOT NULL) AS already_bridged "
                    "FROM document_extractions d JOIN attachment_receipts a ON "
                    "a.tenant_id=d.tenant_id AND a.account_id=d.account_id "
                    "AND a.id=d.receipt_id JOIN message_versions mv ON "
                    "mv.tenant_id=a.tenant_id AND mv.account_id=a.account_id "
                    "AND mv.id=a.evidence_id JOIN messages m ON m.tenant_id=mv.tenant_id "
                    "AND m.account_id=mv.account_id AND m.id=mv.message_id "
                    "AND m.raw_sha256=mv.raw_sha256 AND m.parser_version=mv.parser_version "
                    "JOIN brain_email_bridge_receipts eb ON eb.tenant_id=mv.tenant_id "
                    "AND eb.account_id=mv.account_id AND eb.legacy_version_id=mv.id "
                    "JOIN brain_source_items pi ON pi.tenant_id=eb.tenant_id "
                    "AND pi.id=eb.item_id AND pi.current_version_id=eb.version_id "
                    "JOIN brain_email_attachment_bridge_receipts ab ON "
                    "ab.tenant_id=d.tenant_id AND ab.account_id=d.account_id "
                    "AND ab.legacy_attachment_id=d.receipt_id "
                    "JOIN brain_source_items ai ON ai.tenant_id=ab.tenant_id "
                    "AND ai.id=ab.item_id AND ai.current_version_id=ab.version_id "
                    "LEFT JOIN brain_email_document_bridge_receipts db ON "
                    "db.tenant_id=d.tenant_id AND db.legacy_extraction_id=d.id "
                    "WHERE d.account_id=%s AND NOT m.deleted AND NOT m.quarantined "
                    "AND d.status IN ('extracted','partial') AND EXISTS (SELECT 1 "
                    "FROM document_jobs j WHERE j.tenant_id=d.tenant_id "
                    "AND j.account_id=d.account_id AND j.receipt_id=d.receipt_id "
                    "AND j.extraction_id=d.id AND j.processor_version=d.processor_version "
                    "AND j.policy_version=d.policy_version AND j.status='completed' "
                    "AND j.outcome='result_saved') AND (%s::timestamptz IS NULL "
                    "OR (d.created_at,d.id)>(%s,%s)) ORDER BY d.created_at,d.id LIMIT %s",
                    (
                        account_id,
                        anchor["created_at"] if anchor else None,
                        anchor["created_at"] if anchor else None,
                        after,
                        limit + 1,
                    ),
                ).fetchall()
            self.store.audit(
                conn, ctx, "brain.email_part_bridge_plan", "mail_account", str(account_id)
            )
        page = rows[:limit]
        results = []
        for row in page:
            result = {
                f"legacy_{kind}_id": str(row["legacy_id"]),
                "legacy_parent_version_id": str(row["legacy_parent_version_id"]),
                "created_at": row["created_at"].isoformat(),
                "state": row["state"],
                "already_bridged": row["already_bridged"],
            }
            if kind == "document":
                result["legacy_attachment_id"] = str(row["legacy_attachment_id"])
            results.append(result)
        return {
            "account_id": str(account_id),
            "kind": kind,
            "results": results,
            "next_cursor": str(page[-1]["legacy_id"]) if len(rows) > limit and page else None,
            "limit": limit,
            "source_effects": False,
            "data_effects": False,
        }

    @staticmethod
    def _email_bridge_result(row: Mapping[str, Any], *, changed: bool) -> EmailBridgeResult:
        return EmailBridgeResult(
            source_id=row["source_id"],
            item_id=row["item_id"],
            version_id=row["version_id"],
            evidence_id=row["evidence_id"],
            document_id=row["document_id"],
            chunks=row["chunk_count"],
            changed=changed,
        )

    def bridge_current_email_version(
        self,
        ctx: TenantContext,
        legacy_version_id: UUID,
        idempotency_key: UUID,
        *,
        code_revision: str,
        expected_account_id: UUID | None = None,
    ) -> EmailBridgeResult:
        """Map one current immutable Email version into shared DataCore primitives."""
        self.store.require(ctx, "brain.source.ingest")
        self.store.require(ctx, "brain.document.publish")
        if not code_revision or len(code_revision) > 200 or "\x00" in code_revision:
            raise ValueError("invalid bridge code revision")
        request_hash = _canonical_digest(
            {
                "legacy_version_id": str(legacy_version_id),
                "normalizer": EMAIL_NORMALIZER_VERSION,
                "code_revision": code_revision,
            }
        )
        receipt_columns = (
            "source_id,item_id,version_id,evidence_id,document_id,chunk_count,request_hash"
        )
        with self.store.transaction(ctx) as conn:
            conn.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                (f"{ctx.tenant_id}:email-bridge:{legacy_version_id}",),
            )
            legacy_identity = None
            if expected_account_id is not None:
                legacy_identity = conn.execute(
                    "SELECT account_id FROM message_versions WHERE id=%s",
                    (legacy_version_id,),
                ).fetchone()
                if not legacy_identity:
                    raise NotFound()
                if legacy_identity["account_id"] != expected_account_id:
                    raise Conflict("Email evidence is outside the sealed batch account")
            receipt = conn.execute(
                f"SELECT {receipt_columns} FROM brain_email_bridge_receipts "
                "WHERE actor_id=%s AND idempotency_key=%s",
                (ctx.actor_id, idempotency_key),
            ).fetchone()
            if receipt:
                if receipt["request_hash"] != request_hash:
                    raise Conflict("idempotency key reused for a different Email bridge")
                self.store.audit(
                    conn,
                    ctx,
                    "brain.email_bridge_replayed",
                    "message_version",
                    str(legacy_version_id),
                )
                return self._email_bridge_result(receipt, changed=False)

            prior = conn.execute(
                f"SELECT {receipt_columns} FROM brain_email_bridge_receipts "
                "WHERE legacy_version_id=%s",
                (legacy_version_id,),
            ).fetchone()
            if prior:
                if prior["request_hash"] != request_hash:
                    raise Conflict("Email evidence was bridged with different provenance")
                self.store.audit(
                    conn,
                    ctx,
                    "brain.email_bridge_replayed",
                    "message_version",
                    str(legacy_version_id),
                )
                return self._email_bridge_result(prior, changed=False)

            if legacy_identity is None:
                legacy_identity = conn.execute(
                    "SELECT account_id FROM message_versions WHERE id=%s",
                    (legacy_version_id,),
                ).fetchone()
                if not legacy_identity:
                    raise NotFound()
            # Serialize against Email ingestion's account lock so a version cannot
            # become historical between the visibility check and bridge commit.
            conn.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                (f"{ctx.tenant_id}:{legacy_identity['account_id']}",),
            )
            row = conn.execute(
                "SELECT v.id AS legacy_version_id,v.account_id,v.message_id,v.raw_sha256,"
                "v.provider_version,v.snapshot,v.parser_version,v.recorded_at,"
                "m.raw_sha256 AS current_raw_sha256,m.parser_version AS current_parser_version,"
                "m.subject,m.sender,m.clean_text,m.received_at,m.deleted,m.quarantined,"
                "a.provider,octet_length(r.raw_mime) AS raw_size "
                "FROM message_versions v JOIN messages m ON m.tenant_id=v.tenant_id "
                "AND m.account_id=v.account_id AND m.id=v.message_id "
                "JOIN mail_accounts a ON a.tenant_id=v.tenant_id AND a.id=v.account_id "
                "JOIN raw_objects r ON r.tenant_id=v.tenant_id AND r.account_id=v.account_id "
                "AND r.sha256=v.raw_sha256 WHERE v.id=%s",
                (legacy_version_id,),
            ).fetchone()
            if not row:
                raise NotFound()
            if row["deleted"] or row["quarantined"]:
                raise Conflict("Email evidence is not currently visible")
            if (
                row["raw_sha256"] != row["current_raw_sha256"]
                or row["parser_version"] != row["current_parser_version"]
            ):
                raise Conflict("only the current Email evidence version can be bridged")
            snapshot = row["snapshot"]
            if not isinstance(snapshot, dict):
                raise Conflict("Email evidence snapshot is invalid")
            subject, sender, body = (
                snapshot.get("subject"),
                snapshot.get("sender"),
                snapshot.get("text"),
            )
            if (
                not all(isinstance(value, str) for value in (subject, sender, body))
                or snapshot.get("parser_version") != row["parser_version"]
                or (subject, sender, body) != (row["subject"], row["sender"], row["clean_text"])
                or any(
                    isinstance(value, str) and "\x00" in value for value in (subject, sender, body)
                )
            ):
                raise Conflict("Email projection no longer matches immutable evidence")
            subject = cast(str, subject)
            sender = cast(str, sender)
            body = cast(str, body)
            normalized = f"Subject: {subject}\nFrom: {sender}\n\n{body}"
            if len(normalized.encode()) > MAX_NORMALIZED_BYTES:
                raise ValueError("normalized Email evidence exceeds its safe bound")

            account_id = UUID(str(row["account_id"]))
            message_id = UUID(str(row["message_id"]))
            source_id = stable_id("email", str(account_id))
            item_id = stable_id("emailitem", str(message_id))
            version_id = stable_id(
                "emailversion",
                str(legacy_version_id),
                row["raw_sha256"],
                row["parser_version"],
            )
            evidence_id = stable_id("evidence", version_id)
            locator = f"message/{message_id}"
            observed_at = row["received_at"]
            metadata = {
                "legacy_version_id": str(legacy_version_id),
                "parser_version": row["parser_version"],
                "provider": row["provider"],
                "truncated": bool(snapshot.get("truncated", False)),
            }
            conn.execute(
                "INSERT INTO brain_sources(tenant_id,id,kind,display_name) "
                "VALUES (%s,%s,'email',%s) "
                "ON CONFLICT (tenant_id,id) DO NOTHING",
                (ctx.tenant_id, source_id, f"Email source {source_id[-8:]}"),
            )
            source = conn.execute(
                "SELECT kind FROM brain_sources WHERE id=%s FOR UPDATE", (source_id,)
            ).fetchone()
            if not source or source["kind"] != "email":
                raise Conflict("Email source identity has a different kind")
            conn.execute(
                "INSERT INTO brain_source_items(tenant_id,source_id,id,locator,current_version_id,"
                "first_seen_at,last_seen_at) VALUES (%s,%s,%s,%s,%s,%s,%s) "
                "ON CONFLICT (tenant_id,id) DO NOTHING",
                (
                    ctx.tenant_id,
                    source_id,
                    item_id,
                    locator,
                    version_id,
                    observed_at,
                    observed_at,
                ),
            )
            item = conn.execute(
                "SELECT source_id,locator FROM brain_source_items WHERE id=%s FOR UPDATE",
                (item_id,),
            ).fetchone()
            if not item or (item["source_id"], item["locator"]) != (source_id, locator):
                raise Conflict("Email source item identity changed")
            conn.execute(
                "INSERT INTO brain_source_versions(tenant_id,source_id,item_id,id,observed_at,"
                "sha256,size_bytes,media_type,metadata) VALUES (%s,%s,%s,%s,%s,%s,%s,"
                "'message/rfc822',%s) ON CONFLICT (tenant_id,id) DO NOTHING",
                (
                    ctx.tenant_id,
                    source_id,
                    item_id,
                    version_id,
                    observed_at,
                    row["raw_sha256"],
                    row["raw_size"],
                    Jsonb(metadata),
                ),
            )
            version = conn.execute(
                "SELECT source_id,item_id,sha256,size_bytes,media_type,metadata "
                "FROM brain_source_versions WHERE id=%s",
                (version_id,),
            ).fetchone()
            expected_version = {
                "source_id": source_id,
                "item_id": item_id,
                "sha256": row["raw_sha256"],
                "size_bytes": row["raw_size"],
                "media_type": "message/rfc822",
                "metadata": metadata,
            }
            if version != expected_version:
                raise Conflict("Email source version identity changed")
            conn.execute(
                "UPDATE brain_source_items SET first_seen_at=least(first_seen_at,%s),"
                "last_seen_at=greatest(last_seen_at,%s),current_version_id=%s WHERE id=%s",
                (observed_at, observed_at, version_id, item_id),
            )
            conn.execute(
                "INSERT INTO brain_evidence(tenant_id,id,source_version_id,sha256,"
                "storage,retained) "
                "VALUES (%s,%s,%s,%s,'inline',true) ON CONFLICT DO NOTHING",
                (ctx.tenant_id, evidence_id, version_id, row["raw_sha256"]),
            )

            body_sha = hashlib.sha256(normalized.encode()).hexdigest()
            document_id = stable_id("document", version_id, EMAIL_NORMALIZER_VERSION, body_sha)
            conn.execute(
                "INSERT INTO brain_normalized_documents(tenant_id,id,evidence_id,normalizer,"
                "body_sha256,body) VALUES (%s,%s,%s,%s,%s,%s)",
                (
                    ctx.tenant_id,
                    document_id,
                    evidence_id,
                    EMAIL_NORMALIZER_VERSION,
                    body_sha,
                    normalized,
                ),
            )
            chunks = list(deterministic_chunks(normalized))
            for ordinal, (start, end, chunk) in enumerate(chunks):
                chunk_sha = hashlib.sha256(chunk.encode()).hexdigest()
                chunk_id = stable_id("chunk", document_id, str(ordinal), chunk_sha)
                conn.execute(
                    "INSERT INTO brain_chunks(tenant_id,id,document_id,ordinal,start_offset,"
                    "end_offset,text,sha256) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                    (
                        ctx.tenant_id,
                        chunk_id,
                        document_id,
                        ordinal,
                        start,
                        end,
                        chunk,
                        chunk_sha,
                    ),
                )
            config_sha = _canonical_digest(
                {"chunk_characters": CHUNK_CHARACTERS, "fields": ["subject", "sender", "text"]}
            )
            provenance_id = stable_id("provenance", document_id, code_revision, config_sha)
            conn.execute(
                "INSERT INTO brain_provenance(tenant_id,id,output_id,transform,transform_version,"
                "code_revision,configuration_sha256,created_at) VALUES (%s,%s,%s,"
                "'bridge_email_message',%s,%s,%s,clock_timestamp())",
                (
                    ctx.tenant_id,
                    provenance_id,
                    document_id,
                    EMAIL_NORMALIZER_VERSION,
                    code_revision,
                    config_sha,
                ),
            )
            conn.execute(
                "INSERT INTO brain_provenance_inputs(tenant_id,provenance_id,input_id,ordinal) "
                "VALUES (%s,%s,%s,0)",
                (ctx.tenant_id, provenance_id, evidence_id),
            )
            for kind in ("source_version_added", "document_published"):
                changed_id = version_id if kind == "source_version_added" else document_id
                change_id = stable_id("change", kind, changed_id)
                conn.execute(
                    "INSERT INTO brain_change_events(tenant_id,id,source_id,item_id,"
                    "version_id,kind) "
                    "VALUES (%s,%s,%s,%s,%s,%s)",
                    (ctx.tenant_id, change_id, source_id, item_id, version_id, kind),
                )
            conn.execute(
                "INSERT INTO brain_email_bridge_receipts(tenant_id,actor_id,idempotency_key,"
                "account_id,legacy_version_id,source_id,item_id,version_id,evidence_id,"
                "document_id,chunk_count,normalizer,code_revision,request_hash) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    ctx.tenant_id,
                    ctx.actor_id,
                    idempotency_key,
                    account_id,
                    legacy_version_id,
                    source_id,
                    item_id,
                    version_id,
                    evidence_id,
                    document_id,
                    len(chunks),
                    EMAIL_NORMALIZER_VERSION,
                    code_revision,
                    request_hash,
                ),
            )
            self.store.audit(
                conn, ctx, "brain.email_bridge_recorded", "message_version", str(legacy_version_id)
            )
            return EmailBridgeResult(
                source_id,
                item_id,
                version_id,
                evidence_id,
                document_id,
                len(chunks),
                True,
            )

    @staticmethod
    def _email_attachment_bridge_result(
        row: Mapping[str, Any], *, changed: bool
    ) -> EmailAttachmentBridgeResult:
        return EmailAttachmentBridgeResult(
            source_id=row["source_id"],
            item_id=row["item_id"],
            version_id=row["version_id"],
            evidence_id=row["evidence_id"],
            part_id=row["part_id"],
            document_id=row["document_id"],
            chunks=row["chunk_count"],
            outcome=row["outcome"],
            changed=changed,
        )

    def bridge_email_attachment(
        self,
        ctx: TenantContext,
        legacy_attachment_id: UUID,
        idempotency_key: UUID,
        *,
        code_revision: str,
        expected_account_id: UUID | None = None,
    ) -> EmailAttachmentBridgeResult:
        """Map one immutable Email attachment occurrence without reading its bytes."""
        self.store.require(ctx, "brain.source.ingest")
        self.store.require(ctx, "brain.document.publish")
        if (
            not code_revision
            or len(code_revision) > 200
            or "\x00" in code_revision
            or (expected_account_id is not None and not isinstance(expected_account_id, UUID))
        ):
            raise ValueError("invalid attachment bridge code revision")
        request_hash = _canonical_digest(
            {
                "legacy_attachment_id": str(legacy_attachment_id),
                "normalizer": EMAIL_ATTACHMENT_NORMALIZER_VERSION,
                "code_revision": code_revision,
            }
        )
        receipt_columns = (
            "source_id,item_id,version_id,evidence_id,part_id,document_id,chunk_count,"
            "outcome,request_hash"
        )
        with self.store.transaction(ctx) as conn:
            conn.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                (f"{ctx.tenant_id}:email-attachment-bridge:{legacy_attachment_id}",),
            )
            if expected_account_id is not None:
                sealed_identity = conn.execute(
                    "SELECT account_id FROM attachment_receipts WHERE id=%s",
                    (legacy_attachment_id,),
                ).fetchone()
                if not sealed_identity:
                    raise NotFound()
                if sealed_identity["account_id"] != expected_account_id:
                    raise Conflict("attachment is outside the sealed batch account")
            receipt = conn.execute(
                f"SELECT {receipt_columns} FROM brain_email_attachment_bridge_receipts "
                "WHERE actor_id=%s AND idempotency_key=%s",
                (ctx.actor_id, idempotency_key),
            ).fetchone()
            if receipt:
                if receipt["request_hash"] != request_hash:
                    raise Conflict("idempotency key reused for a different attachment bridge")
                self.store.audit(
                    conn,
                    ctx,
                    "brain.email_attachment_bridge_replayed",
                    "attachment_receipt",
                    str(legacy_attachment_id),
                )
                return self._email_attachment_bridge_result(receipt, changed=False)
            prior = conn.execute(
                f"SELECT {receipt_columns} FROM brain_email_attachment_bridge_receipts "
                "WHERE legacy_attachment_id=%s",
                (legacy_attachment_id,),
            ).fetchone()
            if prior:
                if prior["request_hash"] != request_hash:
                    raise Conflict("Email attachment was bridged with different provenance")
                self.store.audit(
                    conn,
                    ctx,
                    "brain.email_attachment_bridge_replayed",
                    "attachment_receipt",
                    str(legacy_attachment_id),
                )
                return self._email_attachment_bridge_result(prior, changed=False)

            identity = conn.execute(
                "SELECT account_id FROM attachment_receipts WHERE id=%s",
                (legacy_attachment_id,),
            ).fetchone()
            if not identity:
                raise NotFound()
            conn.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                (f"{ctx.tenant_id}:{identity['account_id']}",),
            )
            row = conn.execute(
                "SELECT a.id AS legacy_attachment_id,a.account_id,a.evidence_id AS "
                "legacy_parent_version_id,a.part_id AS legacy_part_path,a.safe_filename,"
                "a.media_type,a.sha256,a.byte_size,a.status,a.reason,a.extracted_text,"
                "mv.message_id,mv.raw_sha256,mv.parser_version,m.received_at,m.deleted,"
                "m.quarantined,m.raw_sha256 AS current_raw_sha256,"
                "m.parser_version AS current_parser_version,b.source_id,b.item_id AS "
                "parent_item_id,b.version_id AS parent_version_id,b.evidence_id AS "
                "parent_evidence_id FROM attachment_receipts a JOIN message_versions mv "
                "ON mv.tenant_id=a.tenant_id AND mv.account_id=a.account_id "
                "AND mv.id=a.evidence_id JOIN messages m ON m.tenant_id=mv.tenant_id "
                "AND m.account_id=mv.account_id AND m.id=mv.message_id "
                "JOIN brain_email_bridge_receipts b ON b.tenant_id=mv.tenant_id "
                "AND b.account_id=mv.account_id AND b.legacy_version_id=mv.id "
                "JOIN brain_evidence pe ON pe.tenant_id=b.tenant_id "
                "AND pe.id=b.evidence_id JOIN brain_source_versions pv "
                "ON pv.tenant_id=pe.tenant_id AND pv.id=pe.source_version_id "
                "JOIN brain_source_items pi ON pi.tenant_id=pv.tenant_id "
                "AND pi.id=pv.item_id AND pi.current_version_id=pv.id WHERE a.id=%s",
                (legacy_attachment_id,),
            ).fetchone()
            if not row:
                raise Conflict("attachment parent is not bridged and current")
            if row["deleted"] or row["quarantined"]:
                raise Conflict("attachment parent is not currently visible")
            if (
                row["raw_sha256"] != row["current_raw_sha256"]
                or row["parser_version"] != row["current_parser_version"]
            ):
                raise Conflict("attachment parent evidence is historical")
            if (
                not isinstance(row["legacy_part_path"], str)
                or not 1 <= len(row["legacy_part_path"]) <= 200
                or "\x00" in row["legacy_part_path"]
                or not isinstance(row["safe_filename"], str)
                or len(row["safe_filename"]) > 120
                or "\x00" in row["safe_filename"]
            ):
                raise Conflict("attachment metadata is outside the shared contract")
            extracted_text = row["extracted_text"]
            if not isinstance(extracted_text, str) or "\x00" in extracted_text:
                raise Conflict("attachment extraction is invalid")
            if row["status"] != "extracted" and extracted_text:
                raise Conflict("attachment extraction status is inconsistent")
            if len(extracted_text.encode()) > MAX_NORMALIZED_BYTES:
                raise ValueError("attachment extraction exceeds its safe bound")

            account_id = UUID(str(row["account_id"]))
            source_id = row["source_id"]
            item_id = stable_id("attachmentitem", str(legacy_attachment_id))
            version_id = stable_id(
                "attachmentversion",
                str(legacy_attachment_id),
                row["sha256"],
                str(row["byte_size"]),
            )
            evidence_id = stable_id("evidence", version_id)
            part_id = stable_id("part", row["parent_evidence_id"], str(legacy_attachment_id))
            locator = f"attachment/{legacy_attachment_id}"
            metadata = {
                "legacy_attachment_id": str(legacy_attachment_id),
                "legacy_parent_version_id": str(row["legacy_parent_version_id"]),
                "part_path": row["legacy_part_path"],
                "safe_filename": row["safe_filename"],
                "status": row["status"],
                "reason": row["reason"],
            }
            conn.execute(
                "INSERT INTO brain_source_items(tenant_id,source_id,id,locator,"
                "current_version_id,first_seen_at,last_seen_at) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (tenant_id,id) DO NOTHING",
                (
                    ctx.tenant_id,
                    source_id,
                    item_id,
                    locator,
                    version_id,
                    row["received_at"],
                    row["received_at"],
                ),
            )
            saved_item = conn.execute(
                "SELECT source_id,locator FROM brain_source_items WHERE id=%s FOR UPDATE",
                (item_id,),
            ).fetchone()
            if not saved_item or (saved_item["source_id"], saved_item["locator"]) != (
                source_id,
                locator,
            ):
                raise Conflict("attachment item identity changed")
            conn.execute(
                "INSERT INTO brain_source_versions(tenant_id,source_id,item_id,id,observed_at,"
                "sha256,size_bytes,media_type,metadata) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) "
                "ON CONFLICT (tenant_id,id) DO NOTHING",
                (
                    ctx.tenant_id,
                    source_id,
                    item_id,
                    version_id,
                    row["received_at"],
                    row["sha256"],
                    row["byte_size"],
                    row["media_type"],
                    Jsonb(metadata),
                ),
            )
            saved_version = conn.execute(
                "SELECT source_id,item_id,sha256,size_bytes,media_type,metadata "
                "FROM brain_source_versions WHERE id=%s",
                (version_id,),
            ).fetchone()
            if saved_version != {
                "source_id": source_id,
                "item_id": item_id,
                "sha256": row["sha256"],
                "size_bytes": row["byte_size"],
                "media_type": row["media_type"],
                "metadata": metadata,
            }:
                raise Conflict("attachment version identity changed")
            conn.execute(
                "INSERT INTO brain_evidence(tenant_id,id,source_version_id,sha256,storage,"
                "retained) VALUES (%s,%s,%s,%s,'source_bound',false) ON CONFLICT DO NOTHING",
                (ctx.tenant_id, evidence_id, version_id, row["sha256"]),
            )
            saved_evidence = conn.execute(
                "SELECT source_version_id,sha256,storage,retained FROM brain_evidence WHERE id=%s",
                (evidence_id,),
            ).fetchone()
            if saved_evidence != {
                "source_version_id": version_id,
                "sha256": row["sha256"],
                "storage": "source_bound",
                "retained": False,
            }:
                raise Conflict("attachment evidence identity changed")
            conn.execute(
                "INSERT INTO brain_parts(tenant_id,id,parent_evidence_id,evidence_id,part_path,"
                "media_type,sha256,size_bytes,status,reason) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    ctx.tenant_id,
                    part_id,
                    row["parent_evidence_id"],
                    evidence_id,
                    row["legacy_part_path"],
                    row["media_type"],
                    row["sha256"],
                    row["byte_size"],
                    row["status"],
                    row["reason"],
                ),
            )

            document_id: str | None = None
            chunks: list[tuple[int, int, str]] = []
            normalizer: str | None = None
            if row["status"] == "extracted" and extracted_text:
                normalizer = EMAIL_ATTACHMENT_NORMALIZER_VERSION
                body_sha = hashlib.sha256(extracted_text.encode()).hexdigest()
                document_id = stable_id("document", version_id, normalizer, body_sha)
                conn.execute(
                    "INSERT INTO brain_normalized_documents(tenant_id,id,evidence_id,normalizer,"
                    "body_sha256,body) VALUES (%s,%s,%s,%s,%s,%s)",
                    (ctx.tenant_id, document_id, evidence_id, normalizer, body_sha, extracted_text),
                )
                chunks = list(deterministic_chunks(extracted_text))
                for ordinal, (start, end, chunk) in enumerate(chunks):
                    chunk_sha = hashlib.sha256(chunk.encode()).hexdigest()
                    chunk_id = stable_id("chunk", document_id, str(ordinal), chunk_sha)
                    conn.execute(
                        "INSERT INTO brain_chunks(tenant_id,id,document_id,ordinal,start_offset,"
                        "end_offset,text,sha256) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                        (
                            ctx.tenant_id,
                            chunk_id,
                            document_id,
                            ordinal,
                            start,
                            end,
                            chunk,
                            chunk_sha,
                        ),
                    )
                config_sha = _canonical_digest(
                    {"chunk_characters": CHUNK_CHARACTERS, "source": "attachment_receipt"}
                )
                provenance_id = stable_id("provenance", document_id, code_revision, config_sha)
                conn.execute(
                    "INSERT INTO brain_provenance(tenant_id,id,output_id,transform,"
                    "transform_version,code_revision,configuration_sha256,created_at) "
                    "VALUES (%s,%s,%s,'bridge_email_attachment_text',%s,%s,%s,"
                    "clock_timestamp())",
                    (
                        ctx.tenant_id,
                        provenance_id,
                        document_id,
                        normalizer,
                        code_revision,
                        config_sha,
                    ),
                )
                conn.execute(
                    "INSERT INTO brain_provenance_inputs(tenant_id,provenance_id,input_id,"
                    "ordinal) VALUES (%s,%s,%s,0)",
                    (ctx.tenant_id, provenance_id, evidence_id),
                )
            changes = [("source_version_added", version_id)]
            if document_id is not None:
                changes.append(("document_published", document_id))
            for kind, changed_id in changes:
                change_id = stable_id("change", kind, changed_id)
                conn.execute(
                    "INSERT INTO brain_change_events(tenant_id,id,source_id,item_id,version_id,"
                    "kind) VALUES (%s,%s,%s,%s,%s,%s)",
                    (ctx.tenant_id, change_id, source_id, item_id, version_id, kind),
                )
            conn.execute(
                "INSERT INTO brain_email_attachment_bridge_receipts(tenant_id,actor_id,"
                "idempotency_key,account_id,legacy_parent_version_id,legacy_attachment_id,"
                "parent_evidence_id,source_id,item_id,version_id,evidence_id,part_id,document_id,"
                "chunk_count,outcome,normalizer,code_revision,request_hash) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    ctx.tenant_id,
                    ctx.actor_id,
                    idempotency_key,
                    account_id,
                    row["legacy_parent_version_id"],
                    legacy_attachment_id,
                    row["parent_evidence_id"],
                    source_id,
                    item_id,
                    version_id,
                    evidence_id,
                    part_id,
                    document_id,
                    len(chunks),
                    row["status"],
                    normalizer,
                    code_revision,
                    request_hash,
                ),
            )
            self.store.audit(
                conn,
                ctx,
                "brain.email_attachment_bridge_recorded",
                "attachment_receipt",
                str(legacy_attachment_id),
            )
            return EmailAttachmentBridgeResult(
                source_id,
                item_id,
                version_id,
                evidence_id,
                part_id,
                document_id,
                len(chunks),
                row["status"],
                True,
            )

    @staticmethod
    def _email_document_bridge_result(
        row: Mapping[str, Any], *, changed: bool
    ) -> EmailDocumentBridgeResult:
        return EmailDocumentBridgeResult(
            source_id=row["source_id"],
            item_id=row["item_id"],
            version_id=row["version_id"],
            evidence_id=row["evidence_id"],
            document_id=row["document_id"],
            chunks=row["chunk_count"],
            extraction_status=row["extraction_status"],
            changed=changed,
        )

    def bridge_email_document_extraction(
        self,
        ctx: TenantContext,
        legacy_extraction_id: UUID,
        idempotency_key: UUID,
        *,
        code_revision: str,
        expected_account_id: UUID | None = None,
    ) -> EmailDocumentBridgeResult:
        """Publish one approved legacy PDF derivative on existing attachment evidence."""
        self.store.require(ctx, "brain.source.ingest")
        self.store.require(ctx, "brain.document.publish")
        if (
            not code_revision
            or len(code_revision) > 200
            or "\x00" in code_revision
            or (expected_account_id is not None and not isinstance(expected_account_id, UUID))
        ):
            raise ValueError("invalid document bridge code revision")
        request_hash = _canonical_digest(
            {
                "legacy_extraction_id": str(legacy_extraction_id),
                "bridge_contract": "email-document-bridge-v1",
                "code_revision": code_revision,
            }
        )
        receipt_columns = (
            "source_id,item_id,version_id,evidence_id,document_id,chunk_count,"
            "extraction_status,request_hash"
        )
        with self.store.transaction(ctx) as conn:
            conn.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                (f"{ctx.tenant_id}:email-document-bridge:{legacy_extraction_id}",),
            )
            if expected_account_id is not None:
                sealed_identity = conn.execute(
                    "SELECT account_id FROM document_extractions WHERE id=%s",
                    (legacy_extraction_id,),
                ).fetchone()
                if not sealed_identity:
                    raise NotFound()
                if sealed_identity["account_id"] != expected_account_id:
                    raise Conflict("document is outside the sealed batch account")
            receipt = conn.execute(
                f"SELECT {receipt_columns} FROM brain_email_document_bridge_receipts "
                "WHERE actor_id=%s AND idempotency_key=%s",
                (ctx.actor_id, idempotency_key),
            ).fetchone()
            if receipt:
                if receipt["request_hash"] != request_hash:
                    raise Conflict("idempotency key reused for a different document bridge")
                self.store.audit(
                    conn,
                    ctx,
                    "brain.email_document_bridge_replayed",
                    "document_extraction",
                    str(legacy_extraction_id),
                )
                return self._email_document_bridge_result(receipt, changed=False)
            prior = conn.execute(
                f"SELECT {receipt_columns} FROM brain_email_document_bridge_receipts "
                "WHERE legacy_extraction_id=%s",
                (legacy_extraction_id,),
            ).fetchone()
            if prior:
                if prior["request_hash"] != request_hash:
                    raise Conflict("Email document was bridged with different provenance")
                self.store.audit(
                    conn,
                    ctx,
                    "brain.email_document_bridge_replayed",
                    "document_extraction",
                    str(legacy_extraction_id),
                )
                return self._email_document_bridge_result(prior, changed=False)

            identity = conn.execute(
                "SELECT account_id FROM document_extractions WHERE id=%s",
                (legacy_extraction_id,),
            ).fetchone()
            if not identity:
                raise NotFound()
            conn.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                (f"{ctx.tenant_id}:{identity['account_id']}",),
            )
            row = conn.execute(
                "SELECT d.id AS legacy_extraction_id,d.account_id,d.receipt_id AS "
                "legacy_attachment_id,d.processor_version,d.policy_version,d.revision AS "
                "extraction_revision,d.status AS extraction_status,d.extracted_text,d.result,"
                "approval.id AS legacy_approval_job_id,a.evidence_id AS "
                "legacy_parent_version_id,mv.raw_sha256,mv.parser_version,m.deleted,"
                "m.quarantined,m.raw_sha256 AS current_raw_sha256,m.parser_version AS "
                "current_parser_version,ab.source_id,ab.item_id,ab.version_id,ab.evidence_id "
                "FROM document_extractions d JOIN attachment_receipts a ON "
                "a.tenant_id=d.tenant_id AND a.account_id=d.account_id AND a.id=d.receipt_id "
                "JOIN brain_email_attachment_bridge_receipts ab ON ab.tenant_id=d.tenant_id "
                "AND ab.account_id=d.account_id AND ab.legacy_attachment_id=d.receipt_id "
                "JOIN message_versions mv ON mv.tenant_id=a.tenant_id "
                "AND mv.account_id=a.account_id AND mv.id=a.evidence_id "
                "JOIN messages m ON m.tenant_id=mv.tenant_id AND m.account_id=mv.account_id "
                "AND m.id=mv.message_id JOIN brain_source_items ai ON "
                "ai.tenant_id=ab.tenant_id AND ai.id=ab.item_id "
                "AND ai.current_version_id=ab.version_id "
                "JOIN brain_email_bridge_receipts eb ON eb.tenant_id=mv.tenant_id "
                "AND eb.account_id=mv.account_id AND eb.legacy_version_id=mv.id "
                "JOIN brain_source_items pi ON pi.tenant_id=eb.tenant_id "
                "AND pi.id=eb.item_id AND pi.current_version_id=eb.version_id "
                "JOIN LATERAL (SELECT j.id FROM document_jobs j WHERE "
                "j.tenant_id=d.tenant_id AND j.account_id=d.account_id "
                "AND j.receipt_id=d.receipt_id AND j.extraction_id=d.id "
                "AND j.processor_version=d.processor_version "
                "AND j.policy_version=d.policy_version AND j.status='completed' "
                "AND j.outcome='result_saved' ORDER BY j.created_at,j.id LIMIT 1) approval "
                "ON true WHERE d.id=%s",
                (legacy_extraction_id,),
            ).fetchone()
            if not row:
                raise Conflict(
                    "document extraction is not approved on a bridged current attachment"
                )
            if row["deleted"] or row["quarantined"]:
                raise Conflict("document parent is not currently visible")
            if (
                row["raw_sha256"] != row["current_raw_sha256"]
                or row["parser_version"] != row["current_parser_version"]
            ):
                raise Conflict("document parent evidence is historical")
            text = row["extracted_text"]
            if (
                row["extraction_status"] not in {"extracted", "partial"}
                or not isinstance(text, str)
                or not text
                or "\x00" in text
                or len(text.encode()) > MAX_NORMALIZED_BYTES
            ):
                raise Conflict("document extraction is outside the shared text contract")
            normalizer = (
                f"{EMAIL_DOCUMENT_NORMALIZER_PREFIX}:{row['processor_version']}:"
                f"{row['policy_version']}"
            )
            if len(normalizer) > 200:
                raise Conflict("document extractor identity is outside the shared contract")
            result_sha = _canonical_digest(row["result"])
            body_sha = hashlib.sha256(text.encode()).hexdigest()
            document_id = stable_id("document", row["version_id"], normalizer, body_sha)
            conn.execute(
                "INSERT INTO brain_normalized_documents(tenant_id,id,evidence_id,normalizer,"
                "body_sha256,body) VALUES (%s,%s,%s,%s,%s,%s)",
                (ctx.tenant_id, document_id, row["evidence_id"], normalizer, body_sha, text),
            )
            chunks = list(deterministic_chunks(text))
            for ordinal, (start, end, chunk) in enumerate(chunks):
                chunk_sha = hashlib.sha256(chunk.encode()).hexdigest()
                chunk_id = stable_id("chunk", document_id, str(ordinal), chunk_sha)
                conn.execute(
                    "INSERT INTO brain_chunks(tenant_id,id,document_id,ordinal,start_offset,"
                    "end_offset,text,sha256) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                    (
                        ctx.tenant_id,
                        chunk_id,
                        document_id,
                        ordinal,
                        start,
                        end,
                        chunk,
                        chunk_sha,
                    ),
                )
            config_sha = _canonical_digest(
                {
                    "chunk_characters": CHUNK_CHARACTERS,
                    "source": "document_extractions",
                    "processor_version": row["processor_version"],
                    "policy_version": row["policy_version"],
                    "extraction_revision": row["extraction_revision"],
                    "extraction_status": row["extraction_status"],
                    "result_sha256": result_sha,
                }
            )
            provenance_id = stable_id("provenance", document_id, code_revision, config_sha)
            conn.execute(
                "INSERT INTO brain_provenance(tenant_id,id,output_id,transform,"
                "transform_version,code_revision,configuration_sha256,created_at) "
                "VALUES (%s,%s,%s,'bridge_email_document_extraction',%s,%s,%s,"
                "clock_timestamp())",
                (
                    ctx.tenant_id,
                    provenance_id,
                    document_id,
                    normalizer,
                    code_revision,
                    config_sha,
                ),
            )
            conn.execute(
                "INSERT INTO brain_provenance_inputs(tenant_id,provenance_id,input_id,ordinal) "
                "VALUES (%s,%s,%s,0)",
                (ctx.tenant_id, provenance_id, row["evidence_id"]),
            )
            change_id = stable_id("change", "document_published", document_id)
            conn.execute(
                "INSERT INTO brain_change_events(tenant_id,id,source_id,item_id,version_id,kind) "
                "VALUES (%s,%s,%s,%s,%s,'document_published')",
                (
                    ctx.tenant_id,
                    change_id,
                    row["source_id"],
                    row["item_id"],
                    row["version_id"],
                ),
            )
            conn.execute(
                "INSERT INTO brain_email_document_bridge_receipts(tenant_id,actor_id,"
                "idempotency_key,account_id,legacy_attachment_id,legacy_extraction_id,"
                "legacy_approval_job_id,source_id,item_id,version_id,evidence_id,document_id,"
                "chunk_count,extraction_status,extraction_revision,processor_version,"
                "policy_version,normalizer,result_sha256,code_revision,request_hash) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    ctx.tenant_id,
                    ctx.actor_id,
                    idempotency_key,
                    row["account_id"],
                    row["legacy_attachment_id"],
                    legacy_extraction_id,
                    row["legacy_approval_job_id"],
                    row["source_id"],
                    row["item_id"],
                    row["version_id"],
                    row["evidence_id"],
                    document_id,
                    len(chunks),
                    row["extraction_status"],
                    row["extraction_revision"],
                    row["processor_version"],
                    row["policy_version"],
                    normalizer,
                    result_sha,
                    code_revision,
                    request_hash,
                ),
            )
            self.store.audit(
                conn,
                ctx,
                "brain.email_document_bridge_recorded",
                "document_extraction",
                str(legacy_extraction_id),
            )
            return EmailDocumentBridgeResult(
                row["source_id"],
                row["item_id"],
                row["version_id"],
                row["evidence_id"],
                document_id,
                len(chunks),
                row["extraction_status"],
                True,
            )

    @staticmethod
    def _archive_inventory_record(
        row: Mapping[str, Any], *, changed: bool
    ) -> ArchiveInventoryRecord:
        return ArchiveInventoryRecord(
            row["id"],
            row["source_id"],
            row["item_id"],
            row["source_version_id"],
            row["processor_version"],
            row["member_count"],
            row["skipped_count"],
            changed,
        )

    def record_archive_inventory(
        self,
        ctx: TenantContext,
        result: ArchiveResult,
        processor_version: str,
        idempotency_key: UUID,
    ) -> ArchiveInventoryRecord:
        """Persist one accepted hash-only archive manifest; never publish child evidence."""
        self.store.require(ctx, "brain.source.ingest")
        if (
            not isinstance(result, ArchiveResult)
            or not isinstance(processor_version, str)
            or not _ARCHIVE_PROCESSOR.fullmatch(processor_version)
            or not isinstance(idempotency_key, UUID)
            or result.status not in {"complete", "partial"}
        ):
            raise ValueError("invalid accepted archive inventory")
        try:
            validated = decode_archive_result(encode_archive_result(result), result.source)
        except ArchiveUnavailable:
            raise ValueError("invalid accepted archive inventory") from None
        if validated != result or result.format not in {"zip", "tar"}:
            raise ValueError("invalid accepted archive inventory")
        result_data = asdict(result)
        result_sha = _canonical_digest(result_data)
        request_hash = _canonical_digest(
            {
                "contract": "archive-inventory-persistence-v1",
                "processor_version": processor_version,
                "result_sha256": result_sha,
            }
        )
        inventory_id = stable_id(
            "archive_inventory", result.source.version_id, processor_version, result_sha
        )
        columns = (
            "id,source_id,item_id,source_version_id,processor_version,member_count,"
            "skipped_count,result_sha256"
        )
        with self.store.transaction(ctx) as conn:
            conn.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                (f"{ctx.tenant_id}:archive:{result.source.version_id}:{processor_version}",),
            )
            receipt = conn.execute(
                "SELECT r.request_hash,i." + columns.replace(",", ",i.") + " "
                "FROM brain_archive_inventory_receipts r JOIN brain_archive_inventories i "
                "ON i.tenant_id=r.tenant_id AND i.id=r.inventory_id "
                "WHERE r.actor_id=%s AND r.idempotency_key=%s",
                (ctx.actor_id, idempotency_key),
            ).fetchone()
            if receipt:
                if receipt["request_hash"] != request_hash:
                    raise Conflict("idempotency key reused for a different archive inventory")
                self.store.audit(
                    conn,
                    ctx,
                    "brain.archive_inventory_replayed",
                    "source_version",
                    result.source.version_id,
                )
                return self._archive_inventory_record(receipt, changed=False)

            source = conn.execute(
                "SELECT v.source_id,v.item_id,v.sha256,v.size_bytes,v.media_type,i.locator,"
                "i.current_version_id,s.kind FROM brain_source_versions v "
                "JOIN brain_source_items i ON i.tenant_id=v.tenant_id AND i.source_id=v.source_id "
                "AND i.id=v.item_id JOIN brain_sources s ON s.tenant_id=v.tenant_id "
                "AND s.id=v.source_id WHERE v.id=%s FOR UPDATE OF i",
                (result.source.version_id,),
            ).fetchone()
            expected = result.source
            if not source:
                raise NotFound()
            if source["kind"] != SourceKind.FILEOS.value:
                raise Conflict("archive parent is not a FileOS source version")
            if source["current_version_id"] != expected.version_id:
                raise Conflict("archive parent source version is historical")
            if (
                source["sha256"],
                source["size_bytes"],
                source["media_type"],
                source["locator"],
            ) != (expected.sha256, expected.size_bytes, expected.media_type, expected.locator):
                raise Conflict("archive parent identity does not match immutable source")

            prior = conn.execute(
                f"SELECT {columns} FROM brain_archive_inventories "
                "WHERE source_version_id=%s AND processor_version=%s",
                (expected.version_id, processor_version),
            ).fetchone()
            if prior:
                if prior["result_sha256"] != result_sha:
                    raise Conflict("archive processor produced a different manifest")
                conn.execute(
                    "INSERT INTO brain_archive_inventory_receipts(tenant_id,actor_id,"
                    "idempotency_key,request_hash,inventory_id) VALUES (%s,%s,%s,%s,%s)",
                    (
                        ctx.tenant_id,
                        ctx.actor_id,
                        idempotency_key,
                        request_hash,
                        prior["id"],
                    ),
                )
                self.store.audit(
                    conn,
                    ctx,
                    "brain.archive_inventory_replayed",
                    "source_version",
                    expected.version_id,
                )
                return self._archive_inventory_record(prior, changed=False)

            conn.execute(
                "INSERT INTO brain_archive_inventories(tenant_id,id,source_id,item_id,"
                "source_version_id,processor_version,result_sha256,archive_format,status,"
                "reason,member_count,skipped_count,file_count,total_uncompressed_bytes) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    ctx.tenant_id,
                    inventory_id,
                    source["source_id"],
                    source["item_id"],
                    expected.version_id,
                    processor_version,
                    result_sha,
                    result.format,
                    result.status,
                    result.reason,
                    len(result.members),
                    len(result.skipped),
                    result.file_count,
                    result.total_uncompressed_bytes,
                ),
            )
            for ordinal, member in enumerate(result.members):
                conn.execute(
                    "INSERT INTO brain_archive_members(tenant_id,inventory_id,ordinal,locator,"
                    "sha256,declared_size,observed_size,media_hint,depth,parent_locator,"
                    "is_container) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (
                        ctx.tenant_id,
                        inventory_id,
                        ordinal,
                        member.locator,
                        member.sha256,
                        member.declared_size,
                        member.observed_size,
                        member.media_hint,
                        member.depth,
                        member.parent_locator,
                        member.is_container,
                    ),
                )
            for ordinal, skipped in enumerate(result.skipped):
                conn.execute(
                    "INSERT INTO brain_archive_skips(tenant_id,inventory_id,ordinal,locator,"
                    "reason,depth,parent_locator) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                    (
                        ctx.tenant_id,
                        inventory_id,
                        ordinal,
                        skipped.locator,
                        skipped.reason,
                        skipped.depth,
                        skipped.parent_locator,
                    ),
                )
            conn.execute(
                "INSERT INTO brain_archive_inventory_receipts(tenant_id,actor_id,"
                "idempotency_key,request_hash,inventory_id) VALUES (%s,%s,%s,%s,%s)",
                (ctx.tenant_id, ctx.actor_id, idempotency_key, request_hash, inventory_id),
            )
            self.store.audit(
                conn,
                ctx,
                "brain.archive_inventory_recorded",
                "source_version",
                expected.version_id,
            )
            return ArchiveInventoryRecord(
                inventory_id,
                source["source_id"],
                source["item_id"],
                expected.version_id,
                processor_version,
                len(result.members),
                len(result.skipped),
                True,
            )

    def archive_member_target(
        self, ctx: TenantContext, inventory_id: str, member_locator: str
    ) -> ArchiveMemberTargetRecord:
        """Resolve one current, accepted, non-container member through forced RLS."""
        self.store.require(ctx, "brain.source.ingest")
        if (
            not isinstance(inventory_id, str)
            or not re.fullmatch(r"archive_inventory_[a-f0-9]{32}", inventory_id)
            or not isinstance(member_locator, str)
            or not 1 <= len(member_locator) <= 1024
            or "\x00" in member_locator
            or "\\" in member_locator
        ):
            raise ValueError("invalid archive member selection")
        with self.store.transaction(ctx) as conn:
            row = conn.execute(
                "SELECT a.id AS inventory_id,a.processor_version,a.source_id,a.item_id,"
                "a.source_version_id,i.locator AS source_locator,v.sha256 AS source_sha256,"
                "v.size_bytes AS source_size_bytes,v.media_type AS source_media_type,"
                "m.locator AS member_locator,m.sha256 AS member_sha256,"
                "m.observed_size AS member_size_bytes,m.media_hint AS member_media_type,"
                "m.depth AS member_depth,"
                "m.parent_locator AS member_parent_locator "
                "FROM brain_archive_inventories a JOIN brain_archive_members m "
                "ON m.tenant_id=a.tenant_id AND m.inventory_id=a.id "
                "JOIN brain_source_versions v ON v.tenant_id=a.tenant_id "
                "AND v.id=a.source_version_id JOIN brain_source_items i "
                "ON i.tenant_id=v.tenant_id AND i.source_id=v.source_id AND i.id=v.item_id "
                "WHERE a.id=%s AND m.locator=%s AND NOT m.is_container "
                "AND a.status IN ('complete','partial') "
                "AND i.current_version_id=a.source_version_id",
                (inventory_id, member_locator),
            ).fetchone()
            if not row:
                raise NotFound()
            self.store.audit(
                conn,
                ctx,
                "brain.archive_member_selected",
                "archive_inventory",
                inventory_id,
            )
            return ArchiveMemberTargetRecord(
                row["inventory_id"],
                row["processor_version"],
                row["source_id"],
                row["item_id"],
                row["source_version_id"],
                row["source_locator"],
                row["source_sha256"],
                row["source_size_bytes"],
                row["source_media_type"],
                row["member_locator"],
                row["member_sha256"],
                row["member_size_bytes"],
                row["member_media_type"],
                row["member_depth"],
                row["member_parent_locator"],
            )

    def archive_document_member_target(
        self, ctx: TenantContext, inventory_id: str, member_locator: str
    ) -> ArchiveMemberTargetRecord:
        """Resolve one current PDF or opaque OOXML member through forced RLS."""
        self.store.require(ctx, "brain.source.ingest")
        suffix = (
            PurePosixPath(member_locator).suffix.lower() if isinstance(member_locator, str) else ""
        )
        if (
            not isinstance(inventory_id, str)
            or not re.fullmatch(r"archive_inventory_[a-f0-9]{32}", inventory_id)
            or not isinstance(member_locator, str)
            or not 1 <= len(member_locator) <= 1024
            or "\x00" in member_locator
            or "\\" in member_locator
            or suffix not in {".pdf", ".docx", ".xlsx"}
        ):
            raise ValueError("invalid archive document selection")
        expected_media = {
            ".pdf": "application/pdf",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        }[suffix]
        with self.store.transaction(ctx) as conn:
            row = conn.execute(
                "SELECT a.id AS inventory_id,a.processor_version,a.source_id,a.item_id,"
                "a.source_version_id,i.locator AS source_locator,v.sha256 AS source_sha256,"
                "v.size_bytes AS source_size_bytes,v.media_type AS source_media_type,"
                "m.locator AS member_locator,m.sha256 AS member_sha256,"
                "m.observed_size AS member_size_bytes,m.media_hint AS member_media_type,"
                "m.depth AS member_depth,m.parent_locator AS member_parent_locator "
                "FROM brain_archive_inventories a JOIN brain_archive_members m "
                "ON m.tenant_id=a.tenant_id AND m.inventory_id=a.id "
                "JOIN brain_source_versions v ON v.tenant_id=a.tenant_id "
                "AND v.id=a.source_version_id JOIN brain_source_items i "
                "ON i.tenant_id=v.tenant_id AND i.source_id=v.source_id AND i.id=v.item_id "
                "WHERE a.id=%s AND m.locator=%s AND m.media_hint=%s "
                "AND ((%s='.pdf' AND NOT m.is_container) OR "
                "(%s IN ('.docx','.xlsx') AND m.is_container)) "
                "AND a.status IN ('complete','partial') "
                "AND i.current_version_id=a.source_version_id",
                (inventory_id, member_locator, expected_media, suffix, suffix),
            ).fetchone()
            if not row:
                raise NotFound()
            self.store.audit(
                conn,
                ctx,
                "brain.archive_document_member_selected",
                "archive_inventory",
                inventory_id,
            )
            return ArchiveMemberTargetRecord(
                row["inventory_id"],
                row["processor_version"],
                row["source_id"],
                row["item_id"],
                row["source_version_id"],
                row["source_locator"],
                row["source_sha256"],
                row["source_size_bytes"],
                row["source_media_type"],
                row["member_locator"],
                row["member_sha256"],
                row["member_size_bytes"],
                row["member_media_type"],
                row["member_depth"],
                row["member_parent_locator"],
            )

    @staticmethod
    def _archive_member_text_record(
        row: Mapping[str, Any], *, changed: bool
    ) -> ArchiveMemberTextRecord:
        return ArchiveMemberTextRecord(
            row["inventory_id"],
            row["member_locator"],
            row["source_id"],
            row["item_id"],
            row["version_id"],
            row["evidence_id"],
            row["document_id"],
            row["chunk_count"],
            changed,
        )

    def publish_archive_member_text(
        self,
        ctx: TenantContext,
        target: ArchiveMemberTargetRecord,
        text: str,
        normalizer: str,
        code_revision: str,
        idempotency_key: UUID,
    ) -> ArchiveMemberTextRecord:
        """Publish one already-read archive member as distinct derived evidence."""
        self.store.require(ctx, "brain.source.ingest")
        self.store.require(ctx, "brain.document.publish")
        if (
            not isinstance(target, ArchiveMemberTargetRecord)
            or not isinstance(text, str)
            or not text
            or "\x00" in text
            or len(text.encode()) > MAX_NORMALIZED_BYTES
            or target.member_size_bytes > MAX_NORMALIZED_BYTES
            or PurePosixPath(target.member_locator).suffix.lower() not in _ARCHIVE_TEXT_SUFFIXES
            or normalizer != FILEOS_TEXT_EXTRACTOR_VERSION
            or not isinstance(code_revision, str)
            or not 1 <= len(code_revision) <= 200
            or "\x00" in code_revision
            or not isinstance(idempotency_key, UUID)
        ):
            raise ValueError("invalid archive member text publication")
        body_sha = hashlib.sha256(text.encode()).hexdigest()
        request_hash = _canonical_digest(
            {
                "contract": "archive-member-text-v1",
                "target": asdict(target),
                "body_sha256": body_sha,
                "normalizer": normalizer,
                "code_revision": code_revision,
            }
        )
        columns = (
            "inventory_id,member_locator,source_id,item_id,version_id,evidence_id,"
            "document_id,chunk_count,request_hash"
        )
        with self.store.transaction(ctx) as conn:
            conn.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                (f"{ctx.tenant_id}:archive-member:{target.inventory_id}:{target.member_locator}",),
            )
            receipt = conn.execute(
                f"SELECT {columns} FROM brain_archive_member_text_receipts "
                "WHERE actor_id=%s AND idempotency_key=%s",
                (ctx.actor_id, idempotency_key),
            ).fetchone()
            if receipt:
                if receipt["request_hash"] != request_hash:
                    raise Conflict("idempotency key reused for different archive member text")
                self.store.audit(
                    conn,
                    ctx,
                    "brain.archive_member_text_replayed",
                    "archive_inventory",
                    target.inventory_id,
                )
                return self._archive_member_text_record(receipt, changed=False)

            prior = conn.execute(
                f"SELECT actor_id,idempotency_key,{columns} "
                "FROM brain_archive_member_text_receipts "
                "WHERE inventory_id=%s AND member_locator=%s AND normalizer=%s "
                "ORDER BY created_at,actor_id,idempotency_key LIMIT 1",
                (target.inventory_id, target.member_locator, normalizer),
            ).fetchone()
            if prior:
                if prior["request_hash"] != request_hash:
                    raise Conflict("archive member text was published with different provenance")
                conn.execute(
                    "INSERT INTO brain_archive_member_text_receipts(tenant_id,actor_id,"
                    "idempotency_key,inventory_id,member_locator,parent_source_version_id,"
                    "parent_evidence_id,source_id,item_id,version_id,evidence_id,document_id,"
                    "normalizer,chunk_count,code_revision,request_hash) SELECT %s,%s,%s,"
                    "inventory_id,member_locator,parent_source_version_id,parent_evidence_id,"
                    "source_id,item_id,version_id,evidence_id,document_id,normalizer,chunk_count,"
                    "code_revision,request_hash FROM brain_archive_member_text_receipts "
                    "WHERE tenant_id=%s AND actor_id=%s AND idempotency_key=%s",
                    (
                        ctx.tenant_id,
                        ctx.actor_id,
                        idempotency_key,
                        ctx.tenant_id,
                        prior["actor_id"],
                        prior["idempotency_key"],
                    ),
                )
                self.store.audit(
                    conn,
                    ctx,
                    "brain.archive_member_text_replayed",
                    "archive_inventory",
                    target.inventory_id,
                )
                return self._archive_member_text_record(prior, changed=False)

            row = conn.execute(
                "SELECT a.id AS inventory_id,a.processor_version,a.source_id,a.item_id AS "
                "parent_item_id,a.source_version_id,v.observed_at,v.sha256 AS source_sha256,"
                "v.size_bytes AS source_size_bytes,v.media_type AS source_media_type,"
                "i.locator AS source_locator,i.current_version_id,e.id AS parent_evidence_id,"
                "m.locator AS member_locator,m.sha256 AS member_sha256,"
                "m.observed_size AS member_size_bytes,m.media_hint AS member_media_type,"
                "m.depth AS member_depth,m.parent_locator AS member_parent_locator,"
                "m.is_container FROM brain_archive_inventories a "
                "JOIN brain_archive_members m ON m.tenant_id=a.tenant_id "
                "AND m.inventory_id=a.id JOIN brain_source_versions v "
                "ON v.tenant_id=a.tenant_id AND v.id=a.source_version_id "
                "JOIN brain_source_items i ON i.tenant_id=v.tenant_id "
                "AND i.source_id=v.source_id AND i.id=v.item_id "
                "JOIN brain_evidence e ON e.tenant_id=v.tenant_id "
                "AND e.source_version_id=v.id WHERE a.id=%s AND m.locator=%s "
                "FOR UPDATE OF i",
                (target.inventory_id, target.member_locator),
            ).fetchone()
            if not row or row["is_container"]:
                raise NotFound()
            actual = ArchiveMemberTargetRecord(
                row["inventory_id"],
                row["processor_version"],
                row["source_id"],
                row["parent_item_id"],
                row["source_version_id"],
                row["source_locator"],
                row["source_sha256"],
                row["source_size_bytes"],
                row["source_media_type"],
                row["member_locator"],
                row["member_sha256"],
                row["member_size_bytes"],
                row["member_media_type"],
                row["member_depth"],
                row["member_parent_locator"],
            )
            if row["current_version_id"] != target.source_version_id or actual != target:
                raise Conflict("archive member parent or identity is no longer current")

            item_id = stable_id("archiveitem", target.inventory_id, target.member_locator)
            version_id = stable_id(
                "archiveversion",
                target.inventory_id,
                target.inventory_processor_version,
                target.member_locator,
                target.member_sha256,
                str(target.member_size_bytes),
            )
            evidence_id = stable_id("evidence", version_id)
            document_id = stable_id("document", version_id, normalizer, body_sha)
            locator = f"archive-member/{item_id}"
            metadata = {
                "derived_from": target.source_version_id,
                "inventory_id": target.inventory_id,
                "member_locator": target.member_locator,
                "inventory_processor": target.inventory_processor_version,
            }
            conn.execute(
                "INSERT INTO brain_source_items(tenant_id,source_id,id,locator,"
                "current_version_id,first_seen_at,last_seen_at) VALUES (%s,%s,%s,%s,%s,%s,%s) "
                "ON CONFLICT (tenant_id,id) DO NOTHING",
                (
                    ctx.tenant_id,
                    target.source_id,
                    item_id,
                    locator,
                    version_id,
                    row["observed_at"],
                    row["observed_at"],
                ),
            )
            saved_item = conn.execute(
                "SELECT source_id,locator,current_version_id FROM brain_source_items "
                "WHERE id=%s FOR UPDATE",
                (item_id,),
            ).fetchone()
            if saved_item != {
                "source_id": target.source_id,
                "locator": locator,
                "current_version_id": version_id,
            }:
                raise Conflict("archive member child item identity changed")
            conn.execute(
                "INSERT INTO brain_source_versions(tenant_id,source_id,item_id,id,observed_at,"
                "sha256,size_bytes,media_type,metadata) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) "
                "ON CONFLICT (tenant_id,id) DO NOTHING",
                (
                    ctx.tenant_id,
                    target.source_id,
                    item_id,
                    version_id,
                    row["observed_at"],
                    target.member_sha256,
                    target.member_size_bytes,
                    target.member_media_type,
                    Jsonb(metadata),
                ),
            )
            saved_version = conn.execute(
                "SELECT source_id,item_id,sha256,size_bytes,media_type,metadata "
                "FROM brain_source_versions WHERE id=%s",
                (version_id,),
            ).fetchone()
            if saved_version != {
                "source_id": target.source_id,
                "item_id": item_id,
                "sha256": target.member_sha256,
                "size_bytes": target.member_size_bytes,
                "media_type": target.member_media_type,
                "metadata": metadata,
            }:
                raise Conflict("archive member child version identity changed")
            conn.execute(
                "INSERT INTO brain_evidence(tenant_id,id,source_version_id,sha256,storage,"
                "retained) VALUES (%s,%s,%s,%s,'source_bound',false) "
                "ON CONFLICT DO NOTHING",
                (ctx.tenant_id, evidence_id, version_id, target.member_sha256),
            )
            saved_evidence = conn.execute(
                "SELECT source_version_id,sha256,storage,retained FROM brain_evidence WHERE id=%s",
                (evidence_id,),
            ).fetchone()
            if saved_evidence != {
                "source_version_id": version_id,
                "sha256": target.member_sha256,
                "storage": "source_bound",
                "retained": False,
            }:
                raise Conflict("archive member child evidence identity changed")
            conn.execute(
                "INSERT INTO brain_normalized_documents(tenant_id,id,evidence_id,normalizer,"
                "body_sha256,body) VALUES (%s,%s,%s,%s,%s,%s)",
                (ctx.tenant_id, document_id, evidence_id, normalizer, body_sha, text),
            )
            chunks = list(deterministic_chunks(text))
            for ordinal, (start, end, chunk) in enumerate(chunks):
                chunk_sha = hashlib.sha256(chunk.encode()).hexdigest()
                conn.execute(
                    "INSERT INTO brain_chunks(tenant_id,id,document_id,ordinal,start_offset,"
                    "end_offset,text,sha256) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                    (
                        ctx.tenant_id,
                        stable_id("chunk", document_id, str(ordinal), chunk_sha),
                        document_id,
                        ordinal,
                        start,
                        end,
                        chunk,
                        chunk_sha,
                    ),
                )
            config_sha = _canonical_digest(
                {
                    "contract": "archive-member-text-v1",
                    "inventory_processor": target.inventory_processor_version,
                    "member_read_contract": "sandbox-fileos-archive-member-v1",
                    "normalizer": normalizer,
                    "chunk_characters": CHUNK_CHARACTERS,
                }
            )
            provenance_id = stable_id("provenance", document_id, code_revision, config_sha)
            conn.execute(
                "INSERT INTO brain_provenance(tenant_id,id,output_id,transform,"
                "transform_version,code_revision,configuration_sha256,created_at) "
                "VALUES (%s,%s,%s,'archive_member_text',%s,%s,%s,clock_timestamp())",
                (
                    ctx.tenant_id,
                    provenance_id,
                    document_id,
                    normalizer,
                    code_revision,
                    config_sha,
                ),
            )
            for ordinal, input_id in enumerate((row["parent_evidence_id"], target.inventory_id)):
                conn.execute(
                    "INSERT INTO brain_provenance_inputs(tenant_id,provenance_id,input_id,"
                    "ordinal) VALUES (%s,%s,%s,%s)",
                    (ctx.tenant_id, provenance_id, input_id, ordinal),
                )
            conn.execute(
                "INSERT INTO brain_change_events(tenant_id,id,source_id,item_id,version_id,kind) "
                "VALUES (%s,%s,%s,%s,%s,'document_published')",
                (
                    ctx.tenant_id,
                    stable_id("change", "document_published", document_id),
                    target.source_id,
                    item_id,
                    version_id,
                ),
            )
            conn.execute(
                "INSERT INTO brain_archive_member_text_receipts(tenant_id,actor_id,"
                "idempotency_key,inventory_id,member_locator,parent_source_version_id,"
                "parent_evidence_id,source_id,item_id,version_id,evidence_id,document_id,"
                "normalizer,chunk_count,code_revision,request_hash) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    ctx.tenant_id,
                    ctx.actor_id,
                    idempotency_key,
                    target.inventory_id,
                    target.member_locator,
                    target.source_version_id,
                    row["parent_evidence_id"],
                    target.source_id,
                    item_id,
                    version_id,
                    evidence_id,
                    document_id,
                    normalizer,
                    len(chunks),
                    code_revision,
                    request_hash,
                ),
            )
            self.store.audit(
                conn,
                ctx,
                "brain.archive_member_text_published",
                "archive_inventory",
                target.inventory_id,
            )
            return ArchiveMemberTextRecord(
                target.inventory_id,
                target.member_locator,
                target.source_id,
                item_id,
                version_id,
                evidence_id,
                document_id,
                len(chunks),
                True,
            )

    def publish_archive_member_document(
        self,
        ctx: TenantContext,
        target: ArchiveMemberTargetRecord,
        text: str,
        document_processor: str,
        document_format: str,
        code_revision: str,
        idempotency_key: UUID,
    ) -> ArchiveMemberTextRecord:
        """Publish one isolated archive-member PDF/Office extraction."""
        self.store.require(ctx, "brain.source.ingest")
        self.store.require(ctx, "brain.document.publish")
        suffix = (
            PurePosixPath(target.member_locator).suffix.lower()
            if isinstance(target, ArchiveMemberTargetRecord)
            else ""
        )
        if (
            not isinstance(target, ArchiveMemberTargetRecord)
            or not isinstance(text, str)
            or not text
            or "\x00" in text
            or len(text.encode()) > MAX_NORMALIZED_BYTES
            or target.member_size_bytes > 8 * 1024 * 1024
            or _ARCHIVE_DOCUMENT_FORMATS.get(suffix) != document_format
            or not isinstance(document_processor, str)
            or not 1 <= len(document_processor) <= 200
            or "\x00" in document_processor
            or not isinstance(code_revision, str)
            or not 1 <= len(code_revision) <= 200
            or "\x00" in code_revision
            or not isinstance(idempotency_key, UUID)
        ):
            raise ValueError("invalid archive member document publication")
        body_sha = hashlib.sha256(text.encode()).hexdigest()
        request_hash = _canonical_digest(
            {
                "contract": "archive-member-document-v1",
                "target": asdict(target),
                "body_sha256": body_sha,
                "document_processor": document_processor,
                "document_format": document_format,
                "code_revision": code_revision,
            }
        )
        columns = (
            "inventory_id,member_locator,source_id,item_id,version_id,evidence_id,"
            "document_id,chunk_count,request_hash"
        )
        with self.store.transaction(ctx) as conn:
            conn.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                (f"{ctx.tenant_id}:archive-member:{target.inventory_id}:{target.member_locator}",),
            )
            receipt = conn.execute(
                f"SELECT {columns} FROM brain_archive_member_document_receipts "
                "WHERE actor_id=%s AND idempotency_key=%s",
                (ctx.actor_id, idempotency_key),
            ).fetchone()
            if receipt:
                if receipt["request_hash"] != request_hash:
                    raise Conflict("idempotency key reused for different archive member document")
                self.store.audit(
                    conn,
                    ctx,
                    "brain.archive_member_document_replayed",
                    "archive_inventory",
                    target.inventory_id,
                )
                return self._archive_member_text_record(receipt, changed=False)

            prior = conn.execute(
                f"SELECT actor_id,idempotency_key,{columns} "
                "FROM brain_archive_member_document_receipts "
                "WHERE inventory_id=%s AND member_locator=%s AND document_processor=%s "
                "ORDER BY created_at,actor_id,idempotency_key LIMIT 1",
                (target.inventory_id, target.member_locator, document_processor),
            ).fetchone()
            if prior:
                if prior["request_hash"] != request_hash:
                    raise Conflict("archive member document has different provenance")
                conn.execute(
                    "INSERT INTO brain_archive_member_document_receipts(tenant_id,actor_id,"
                    "idempotency_key,inventory_id,member_locator,parent_source_version_id,"
                    "parent_evidence_id,source_id,item_id,version_id,evidence_id,document_id,"
                    "document_processor,document_format,chunk_count,code_revision,request_hash) "
                    "SELECT %s,%s,%s,inventory_id,member_locator,parent_source_version_id,"
                    "parent_evidence_id,source_id,item_id,version_id,evidence_id,document_id,"
                    "document_processor,document_format,chunk_count,code_revision,request_hash "
                    "FROM brain_archive_member_document_receipts WHERE tenant_id=%s "
                    "AND actor_id=%s AND idempotency_key=%s",
                    (
                        ctx.tenant_id,
                        ctx.actor_id,
                        idempotency_key,
                        ctx.tenant_id,
                        prior["actor_id"],
                        prior["idempotency_key"],
                    ),
                )
                self.store.audit(
                    conn,
                    ctx,
                    "brain.archive_member_document_replayed",
                    "archive_inventory",
                    target.inventory_id,
                )
                return self._archive_member_text_record(prior, changed=False)

            row = conn.execute(
                "SELECT a.id AS inventory_id,a.processor_version,a.source_id,a.item_id AS "
                "parent_item_id,a.source_version_id,v.observed_at,v.sha256 AS source_sha256,"
                "v.size_bytes AS source_size_bytes,v.media_type AS source_media_type,"
                "i.locator AS source_locator,i.current_version_id,e.id AS parent_evidence_id,"
                "m.locator AS member_locator,m.sha256 AS member_sha256,"
                "m.observed_size AS member_size_bytes,m.media_hint AS member_media_type,"
                "m.depth AS member_depth,m.parent_locator AS member_parent_locator,"
                "m.is_container FROM brain_archive_inventories a "
                "JOIN brain_archive_members m ON m.tenant_id=a.tenant_id "
                "AND m.inventory_id=a.id JOIN brain_source_versions v "
                "ON v.tenant_id=a.tenant_id AND v.id=a.source_version_id "
                "JOIN brain_source_items i ON i.tenant_id=v.tenant_id "
                "AND i.source_id=v.source_id AND i.id=v.item_id "
                "JOIN brain_evidence e ON e.tenant_id=v.tenant_id "
                "AND e.source_version_id=v.id WHERE a.id=%s AND m.locator=%s "
                "FOR UPDATE OF i",
                (target.inventory_id, target.member_locator),
            ).fetchone()
            if not row:
                raise NotFound()
            actual = ArchiveMemberTargetRecord(
                row["inventory_id"],
                row["processor_version"],
                row["source_id"],
                row["parent_item_id"],
                row["source_version_id"],
                row["source_locator"],
                row["source_sha256"],
                row["source_size_bytes"],
                row["source_media_type"],
                row["member_locator"],
                row["member_sha256"],
                row["member_size_bytes"],
                row["member_media_type"],
                row["member_depth"],
                row["member_parent_locator"],
            )
            should_be_container = suffix in {".docx", ".xlsx"}
            if (
                row["current_version_id"] != target.source_version_id
                or actual != target
                or row["is_container"] is not should_be_container
            ):
                raise Conflict("archive document parent or identity is no longer current")

            item_id = stable_id("archiveitem", target.inventory_id, target.member_locator)
            version_id = stable_id(
                "archiveversion",
                target.inventory_id,
                target.inventory_processor_version,
                target.member_locator,
                target.member_sha256,
                str(target.member_size_bytes),
            )
            evidence_id = stable_id("evidence", version_id)
            document_id = stable_id("document", version_id, document_processor, body_sha)
            locator = f"archive-member/{item_id}"
            metadata = {
                "derived_from": target.source_version_id,
                "inventory_id": target.inventory_id,
                "member_locator": target.member_locator,
                "inventory_processor": target.inventory_processor_version,
                "document_format": document_format,
            }
            conn.execute(
                "INSERT INTO brain_source_items(tenant_id,source_id,id,locator,"
                "current_version_id,first_seen_at,last_seen_at) VALUES (%s,%s,%s,%s,%s,%s,%s) "
                "ON CONFLICT (tenant_id,id) DO NOTHING",
                (
                    ctx.tenant_id,
                    target.source_id,
                    item_id,
                    locator,
                    version_id,
                    row["observed_at"],
                    row["observed_at"],
                ),
            )
            saved_item = conn.execute(
                "SELECT source_id,locator,current_version_id FROM brain_source_items "
                "WHERE id=%s FOR UPDATE",
                (item_id,),
            ).fetchone()
            if saved_item != {
                "source_id": target.source_id,
                "locator": locator,
                "current_version_id": version_id,
            }:
                raise Conflict("archive document child item identity changed")
            conn.execute(
                "INSERT INTO brain_source_versions(tenant_id,source_id,item_id,id,observed_at,"
                "sha256,size_bytes,media_type,metadata) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) "
                "ON CONFLICT (tenant_id,id) DO NOTHING",
                (
                    ctx.tenant_id,
                    target.source_id,
                    item_id,
                    version_id,
                    row["observed_at"],
                    target.member_sha256,
                    target.member_size_bytes,
                    target.member_media_type,
                    Jsonb(metadata),
                ),
            )
            saved_version = conn.execute(
                "SELECT source_id,item_id,sha256,size_bytes,media_type,metadata "
                "FROM brain_source_versions WHERE id=%s",
                (version_id,),
            ).fetchone()
            if saved_version != {
                "source_id": target.source_id,
                "item_id": item_id,
                "sha256": target.member_sha256,
                "size_bytes": target.member_size_bytes,
                "media_type": target.member_media_type,
                "metadata": metadata,
            }:
                raise Conflict("archive document child version identity changed")
            conn.execute(
                "INSERT INTO brain_evidence(tenant_id,id,source_version_id,sha256,storage,"
                "retained) VALUES (%s,%s,%s,%s,'source_bound',false) ON CONFLICT DO NOTHING",
                (ctx.tenant_id, evidence_id, version_id, target.member_sha256),
            )
            saved_evidence = conn.execute(
                "SELECT source_version_id,sha256,storage,retained FROM brain_evidence WHERE id=%s",
                (evidence_id,),
            ).fetchone()
            if saved_evidence != {
                "source_version_id": version_id,
                "sha256": target.member_sha256,
                "storage": "source_bound",
                "retained": False,
            }:
                raise Conflict("archive document child evidence identity changed")
            conn.execute(
                "INSERT INTO brain_normalized_documents(tenant_id,id,evidence_id,normalizer,"
                "body_sha256,body) VALUES (%s,%s,%s,%s,%s,%s)",
                (ctx.tenant_id, document_id, evidence_id, document_processor, body_sha, text),
            )
            chunks = list(deterministic_chunks(text))
            for ordinal, (start, end, chunk) in enumerate(chunks):
                chunk_sha = hashlib.sha256(chunk.encode()).hexdigest()
                conn.execute(
                    "INSERT INTO brain_chunks(tenant_id,id,document_id,ordinal,start_offset,"
                    "end_offset,text,sha256) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                    (
                        ctx.tenant_id,
                        stable_id("chunk", document_id, str(ordinal), chunk_sha),
                        document_id,
                        ordinal,
                        start,
                        end,
                        chunk,
                        chunk_sha,
                    ),
                )
            config_sha = _canonical_digest(
                {
                    "contract": "archive-member-document-v1",
                    "inventory_processor": target.inventory_processor_version,
                    "member_read_contract": "sandbox-fileos-archive-member-v1",
                    "document_processor": document_processor,
                    "document_format": document_format,
                    "chunk_characters": CHUNK_CHARACTERS,
                }
            )
            provenance_id = stable_id("provenance", document_id, code_revision, config_sha)
            conn.execute(
                "INSERT INTO brain_provenance(tenant_id,id,output_id,transform,"
                "transform_version,code_revision,configuration_sha256,created_at) "
                "VALUES (%s,%s,%s,'archive_member_document',%s,%s,%s,clock_timestamp())",
                (
                    ctx.tenant_id,
                    provenance_id,
                    document_id,
                    document_processor,
                    code_revision,
                    config_sha,
                ),
            )
            for ordinal, input_id in enumerate((row["parent_evidence_id"], target.inventory_id)):
                conn.execute(
                    "INSERT INTO brain_provenance_inputs(tenant_id,provenance_id,input_id,"
                    "ordinal) VALUES (%s,%s,%s,%s)",
                    (ctx.tenant_id, provenance_id, input_id, ordinal),
                )
            conn.execute(
                "INSERT INTO brain_change_events(tenant_id,id,source_id,item_id,version_id,kind) "
                "VALUES (%s,%s,%s,%s,%s,'document_published')",
                (
                    ctx.tenant_id,
                    stable_id("change", "document_published", document_id),
                    target.source_id,
                    item_id,
                    version_id,
                ),
            )
            conn.execute(
                "INSERT INTO brain_archive_member_document_receipts(tenant_id,actor_id,"
                "idempotency_key,inventory_id,member_locator,parent_source_version_id,"
                "parent_evidence_id,source_id,item_id,version_id,evidence_id,document_id,"
                "document_processor,document_format,chunk_count,code_revision,request_hash) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    ctx.tenant_id,
                    ctx.actor_id,
                    idempotency_key,
                    target.inventory_id,
                    target.member_locator,
                    target.source_version_id,
                    row["parent_evidence_id"],
                    target.source_id,
                    item_id,
                    version_id,
                    evidence_id,
                    document_id,
                    document_processor,
                    document_format,
                    len(chunks),
                    code_revision,
                    request_hash,
                ),
            )
            self.store.audit(
                conn,
                ctx,
                "brain.archive_member_document_published",
                "archive_inventory",
                target.inventory_id,
            )
            return ArchiveMemberTextRecord(
                target.inventory_id,
                target.member_locator,
                target.source_id,
                item_id,
                version_id,
                evidence_id,
                document_id,
                len(chunks),
                True,
            )

    def publish_archive_member_image_ocr(
        self,
        ctx: TenantContext,
        target: ArchiveMemberTargetRecord,
        text: str,
        image_processor: str,
        image_format: str,
        detected_format: str,
        width: int,
        height: int,
        mode: str,
        frame_count: int,
        truncated: bool,
        code_revision: str,
        idempotency_key: UUID,
    ) -> ArchiveMemberTextRecord:
        """Publish one complete nonempty archive-member image OCR derivative."""
        self.store.require(ctx, "brain.source.ingest")
        self.store.require(ctx, "brain.document.publish")
        suffix = (
            PurePosixPath(target.member_locator).suffix.lower()
            if isinstance(target, ArchiveMemberTargetRecord)
            else ""
        )
        text_bytes = text.encode() if isinstance(text, str) else b""
        if (
            not isinstance(target, ArchiveMemberTargetRecord)
            or not isinstance(text, str)
            or not text
            or text != text.strip()
            or "\x00" in text
            or len(text) > 5_000
            or len(text_bytes) > 20_000
            or not 0 < target.member_size_bytes <= 8 * 1024 * 1024
            or _ARCHIVE_IMAGE_FORMATS.get(suffix) != image_format
            or detected_format != image_format
            or not isinstance(image_processor, str)
            or not _IMAGE_OCR_PROCESSOR.fullmatch(image_processor)
            or type(width) is not int
            or type(height) is not int
            or not 1 <= width <= 25_000_000
            or not 1 <= height <= 25_000_000
            or width * height > 25_000_000
            or not isinstance(mode, str)
            or not 1 <= len(mode) <= 16
            or "\x00" in mode
            or type(frame_count) is not int
            or frame_count != 1
            or type(truncated) is not bool
            or not isinstance(code_revision, str)
            or not 1 <= len(code_revision) <= 200
            or "\x00" in code_revision
            or not isinstance(idempotency_key, UUID)
        ):
            raise ValueError("invalid archive member image OCR publication")
        body_sha = hashlib.sha256(text_bytes).hexdigest()
        request_hash = _canonical_digest(
            {
                "contract": "archive-member-image-ocr-v1",
                "target": asdict(target),
                "body_sha256": body_sha,
                "image_processor": image_processor,
                "image_format": image_format,
                "detected_format": detected_format,
                "width": width,
                "height": height,
                "mode": mode,
                "frame_count": frame_count,
                "truncated": truncated,
                "code_revision": code_revision,
            }
        )
        columns = (
            "inventory_id,member_locator,source_id,item_id,version_id,evidence_id,"
            "document_id,chunk_count,request_hash"
        )
        with self.store.transaction(ctx) as conn:
            conn.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                (f"{ctx.tenant_id}:archive-member:{target.inventory_id}:{target.member_locator}",),
            )
            receipt = conn.execute(
                f"SELECT {columns} FROM brain_archive_member_image_receipts "
                "WHERE actor_id=%s AND idempotency_key=%s",
                (ctx.actor_id, idempotency_key),
            ).fetchone()
            if receipt:
                if receipt["request_hash"] != request_hash:
                    raise Conflict("idempotency key reused for different archive member image OCR")
                self.store.audit(
                    conn,
                    ctx,
                    "brain.archive_member_image_ocr_replayed",
                    "archive_inventory",
                    target.inventory_id,
                )
                return self._archive_member_text_record(receipt, changed=False)

            row = conn.execute(
                "SELECT a.id AS inventory_id,a.processor_version,a.source_id,a.item_id AS "
                "parent_item_id,a.source_version_id,v.observed_at,v.sha256 AS source_sha256,"
                "v.size_bytes AS source_size_bytes,v.media_type AS source_media_type,"
                "i.locator AS source_locator,i.current_version_id,e.id AS parent_evidence_id,"
                "m.locator AS member_locator,m.sha256 AS member_sha256,"
                "m.observed_size AS member_size_bytes,m.media_hint AS member_media_type,"
                "m.depth AS member_depth,m.parent_locator AS member_parent_locator,"
                "m.is_container FROM brain_archive_inventories a "
                "JOIN brain_archive_members m ON m.tenant_id=a.tenant_id "
                "AND m.inventory_id=a.id JOIN brain_source_versions v "
                "ON v.tenant_id=a.tenant_id AND v.id=a.source_version_id "
                "JOIN brain_source_items i ON i.tenant_id=v.tenant_id "
                "AND i.source_id=v.source_id AND i.id=v.item_id "
                "JOIN brain_evidence e ON e.tenant_id=v.tenant_id "
                "AND e.source_version_id=v.id WHERE a.id=%s AND m.locator=%s "
                "FOR UPDATE OF i",
                (target.inventory_id, target.member_locator),
            ).fetchone()
            if not row:
                raise NotFound()
            actual = ArchiveMemberTargetRecord(
                row["inventory_id"],
                row["processor_version"],
                row["source_id"],
                row["parent_item_id"],
                row["source_version_id"],
                row["source_locator"],
                row["source_sha256"],
                row["source_size_bytes"],
                row["source_media_type"],
                row["member_locator"],
                row["member_sha256"],
                row["member_size_bytes"],
                row["member_media_type"],
                row["member_depth"],
                row["member_parent_locator"],
            )
            if (
                row["current_version_id"] != target.source_version_id
                or actual != target
                or row["is_container"]
            ):
                raise Conflict("archive image parent or identity is no longer current")

            prior = conn.execute(
                f"SELECT actor_id,idempotency_key,{columns} "
                "FROM brain_archive_member_image_receipts "
                "WHERE inventory_id=%s AND member_locator=%s AND image_processor=%s "
                "ORDER BY created_at,actor_id,idempotency_key LIMIT 1",
                (target.inventory_id, target.member_locator, image_processor),
            ).fetchone()
            if prior:
                if prior["request_hash"] != request_hash:
                    raise Conflict("archive member image OCR has different provenance")
                conn.execute(
                    "INSERT INTO brain_archive_member_image_receipts(tenant_id,actor_id,"
                    "idempotency_key,inventory_id,member_locator,parent_source_version_id,"
                    "parent_evidence_id,source_id,item_id,version_id,evidence_id,document_id,"
                    "image_processor,image_format,detected_format,width,height,mode,frame_count,"
                    "truncated,chunk_count,code_revision,request_hash) SELECT %s,%s,%s,"
                    "inventory_id,member_locator,parent_source_version_id,parent_evidence_id,"
                    "source_id,item_id,version_id,evidence_id,document_id,image_processor,"
                    "image_format,detected_format,width,height,mode,frame_count,truncated,"
                    "chunk_count,code_revision,request_hash FROM "
                    "brain_archive_member_image_receipts WHERE tenant_id=%s AND actor_id=%s "
                    "AND idempotency_key=%s",
                    (
                        ctx.tenant_id,
                        ctx.actor_id,
                        idempotency_key,
                        ctx.tenant_id,
                        prior["actor_id"],
                        prior["idempotency_key"],
                    ),
                )
                self.store.audit(
                    conn,
                    ctx,
                    "brain.archive_member_image_ocr_replayed",
                    "archive_inventory",
                    target.inventory_id,
                )
                return self._archive_member_text_record(prior, changed=False)

            item_id = stable_id("archiveitem", target.inventory_id, target.member_locator)
            version_id = stable_id(
                "archiveversion",
                target.inventory_id,
                target.inventory_processor_version,
                target.member_locator,
                target.member_sha256,
                str(target.member_size_bytes),
            )
            evidence_id = stable_id("evidence", version_id)
            document_id = stable_id("document", version_id, image_processor, body_sha)
            locator = f"archive-member/{item_id}"
            metadata = {
                "derived_from": target.source_version_id,
                "inventory_id": target.inventory_id,
                "member_locator": target.member_locator,
                "inventory_processor": target.inventory_processor_version,
                "image_format": image_format,
            }
            conn.execute(
                "INSERT INTO brain_source_items(tenant_id,source_id,id,locator,"
                "current_version_id,first_seen_at,last_seen_at) VALUES (%s,%s,%s,%s,%s,%s,%s) "
                "ON CONFLICT (tenant_id,id) DO NOTHING",
                (
                    ctx.tenant_id,
                    target.source_id,
                    item_id,
                    locator,
                    version_id,
                    row["observed_at"],
                    row["observed_at"],
                ),
            )
            saved_item = conn.execute(
                "SELECT source_id,locator,current_version_id FROM brain_source_items "
                "WHERE id=%s FOR UPDATE",
                (item_id,),
            ).fetchone()
            if saved_item != {
                "source_id": target.source_id,
                "locator": locator,
                "current_version_id": version_id,
            }:
                raise Conflict("archive image child item identity changed")
            conn.execute(
                "INSERT INTO brain_source_versions(tenant_id,source_id,item_id,id,observed_at,"
                "sha256,size_bytes,media_type,metadata) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) "
                "ON CONFLICT (tenant_id,id) DO NOTHING",
                (
                    ctx.tenant_id,
                    target.source_id,
                    item_id,
                    version_id,
                    row["observed_at"],
                    target.member_sha256,
                    target.member_size_bytes,
                    target.member_media_type,
                    Jsonb(metadata),
                ),
            )
            saved_version = conn.execute(
                "SELECT source_id,item_id,sha256,size_bytes,media_type,metadata "
                "FROM brain_source_versions WHERE id=%s",
                (version_id,),
            ).fetchone()
            if saved_version != {
                "source_id": target.source_id,
                "item_id": item_id,
                "sha256": target.member_sha256,
                "size_bytes": target.member_size_bytes,
                "media_type": target.member_media_type,
                "metadata": metadata,
            }:
                raise Conflict("archive image child version identity changed")
            conn.execute(
                "INSERT INTO brain_evidence(tenant_id,id,source_version_id,sha256,storage,"
                "retained) VALUES (%s,%s,%s,%s,'source_bound',false) ON CONFLICT DO NOTHING",
                (ctx.tenant_id, evidence_id, version_id, target.member_sha256),
            )
            saved_evidence = conn.execute(
                "SELECT source_version_id,sha256,storage,retained FROM brain_evidence WHERE id=%s",
                (evidence_id,),
            ).fetchone()
            if saved_evidence != {
                "source_version_id": version_id,
                "sha256": target.member_sha256,
                "storage": "source_bound",
                "retained": False,
            }:
                raise Conflict("archive image child evidence identity changed")
            conn.execute(
                "INSERT INTO brain_normalized_documents(tenant_id,id,evidence_id,normalizer,"
                "body_sha256,body) VALUES (%s,%s,%s,%s,%s,%s)",
                (ctx.tenant_id, document_id, evidence_id, image_processor, body_sha, text),
            )
            chunks = list(deterministic_chunks(text))
            for ordinal, (start, end, chunk) in enumerate(chunks):
                chunk_sha = hashlib.sha256(chunk.encode()).hexdigest()
                conn.execute(
                    "INSERT INTO brain_chunks(tenant_id,id,document_id,ordinal,start_offset,"
                    "end_offset,text,sha256) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                    (
                        ctx.tenant_id,
                        stable_id("chunk", document_id, str(ordinal), chunk_sha),
                        document_id,
                        ordinal,
                        start,
                        end,
                        chunk,
                        chunk_sha,
                    ),
                )
            config_sha = _canonical_digest(
                {
                    "contract": "archive-member-image-ocr-v1",
                    "inventory_processor": target.inventory_processor_version,
                    "member_read_contract": "sandbox-fileos-archive-member-v1",
                    "image_contract": "sandbox-fileos-image-ocr-v1",
                    "image_policy": "bounded_image_ocr_v1",
                    "image_processor": image_processor,
                    "image_format": image_format,
                    "detected_format": detected_format,
                    "width": width,
                    "height": height,
                    "mode": mode,
                    "frame_count": frame_count,
                    "truncated": truncated,
                    "chunk_characters": CHUNK_CHARACTERS,
                }
            )
            provenance_id = stable_id("provenance", document_id, code_revision, config_sha)
            conn.execute(
                "INSERT INTO brain_provenance(tenant_id,id,output_id,transform,"
                "transform_version,code_revision,configuration_sha256,created_at) "
                "VALUES (%s,%s,%s,'archive_member_image_ocr',%s,%s,%s,clock_timestamp())",
                (
                    ctx.tenant_id,
                    provenance_id,
                    document_id,
                    image_processor,
                    code_revision,
                    config_sha,
                ),
            )
            for ordinal, input_id in enumerate((row["parent_evidence_id"], target.inventory_id)):
                conn.execute(
                    "INSERT INTO brain_provenance_inputs(tenant_id,provenance_id,input_id,"
                    "ordinal) VALUES (%s,%s,%s,%s)",
                    (ctx.tenant_id, provenance_id, input_id, ordinal),
                )
            conn.execute(
                "INSERT INTO brain_change_events(tenant_id,id,source_id,item_id,version_id,kind) "
                "VALUES (%s,%s,%s,%s,%s,'document_published')",
                (
                    ctx.tenant_id,
                    stable_id("change", "document_published", document_id),
                    target.source_id,
                    item_id,
                    version_id,
                ),
            )
            conn.execute(
                "INSERT INTO brain_archive_member_image_receipts(tenant_id,actor_id,"
                "idempotency_key,inventory_id,member_locator,parent_source_version_id,"
                "parent_evidence_id,source_id,item_id,version_id,evidence_id,document_id,"
                "image_processor,image_format,detected_format,width,height,mode,frame_count,"
                "truncated,chunk_count,code_revision,request_hash) VALUES (%s,%s,%s,%s,%s,"
                "%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    ctx.tenant_id,
                    ctx.actor_id,
                    idempotency_key,
                    target.inventory_id,
                    target.member_locator,
                    target.source_version_id,
                    row["parent_evidence_id"],
                    target.source_id,
                    item_id,
                    version_id,
                    evidence_id,
                    document_id,
                    image_processor,
                    image_format,
                    detected_format,
                    width,
                    height,
                    mode,
                    frame_count,
                    truncated,
                    len(chunks),
                    code_revision,
                    request_hash,
                ),
            )
            self.store.audit(
                conn,
                ctx,
                "brain.archive_member_image_ocr_published",
                "archive_inventory",
                target.inventory_id,
            )
            return ArchiveMemberTextRecord(
                target.inventory_id,
                target.member_locator,
                target.source_id,
                item_id,
                version_id,
                evidence_id,
                document_id,
                len(chunks),
                True,
            )

    def import_fileos_snapshot(
        self,
        ctx: TenantContext,
        manifest: Mapping[str, Any],
        idempotency_key: UUID,
    ) -> ImportResult:
        self.store.require(ctx, "brain.source.ingest")
        source, observed_at, items = _manifest_items(manifest)
        root_binding_hash = fileos_manifest_root_binding_sha256(manifest)
        request_hash = _canonical_digest(manifest)
        with self.store.transaction(ctx) as conn:
            conn.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                (f"{ctx.tenant_id}:{ctx.actor_id}:{idempotency_key}",),
            )
            receipt = conn.execute(
                "SELECT request_hash,result FROM brain_import_receipts "
                "WHERE actor_id=%s AND idempotency_key=%s",
                (ctx.actor_id, idempotency_key),
            ).fetchone()
            if receipt:
                if receipt["request_hash"] != request_hash:
                    raise Conflict("idempotency key reused for a different snapshot")
                return ImportResult(**receipt["result"])
            conn.execute(
                "INSERT INTO brain_sources(tenant_id,id,kind,display_name,root_binding_sha256) "
                "VALUES (%s,%s,%s,%s,%s) "
                "ON CONFLICT (tenant_id,id) DO NOTHING",
                (
                    ctx.tenant_id,
                    source.source_id,
                    source.kind.value,
                    source.display_name,
                    root_binding_hash,
                ),
            )
            saved_source = conn.execute(
                "SELECT kind,root_binding_sha256 FROM brain_sources WHERE id=%s FOR UPDATE",
                (source.source_id,),
            ).fetchone()
            if not saved_source or saved_source["kind"] != source.kind.value:
                raise Conflict("source identity has a different kind")
            if saved_source["root_binding_sha256"] is None:
                existing_evidence = conn.execute(
                    "SELECT EXISTS(SELECT 1 FROM brain_source_items WHERE source_id=%s) "
                    "OR EXISTS(SELECT 1 FROM brain_fileos_run_receipts WHERE source_id=%s) "
                    "AS present",
                    (source.source_id, source.source_id),
                ).fetchone()
                if existing_evidence and existing_evidence["present"]:
                    raise Conflict("FileOS legacy root binding requires review")
                conn.execute(
                    "UPDATE brain_sources SET root_binding_sha256=%s WHERE id=%s",
                    (root_binding_hash, source.source_id),
                )
            elif saved_source["root_binding_sha256"] != root_binding_hash:
                raise Conflict("FileOS source root binding changed")

            new_versions = 0
            for item in items:
                conn.execute(
                    "INSERT INTO brain_source_items(tenant_id,source_id,id,locator,"
                    "current_version_id,"
                    "first_seen_at,last_seen_at) VALUES (%s,%s,%s,%s,%s,%s,%s) "
                    "ON CONFLICT (tenant_id,id) DO NOTHING",
                    (
                        ctx.tenant_id,
                        source.source_id,
                        item.item_id,
                        item.locator,
                        item.version_id,
                        observed_at,
                        observed_at,
                    ),
                )
                saved_item = conn.execute(
                    "SELECT source_id,locator FROM brain_source_items WHERE id=%s FOR UPDATE",
                    (item.item_id,),
                ).fetchone()
                if not saved_item or (saved_item["source_id"], saved_item["locator"]) != (
                    source.source_id,
                    item.locator,
                ):
                    raise Conflict("source item identity changed")
                inserted = conn.execute(
                    "INSERT INTO brain_source_versions(tenant_id,source_id,item_id,id,observed_at,"
                    "sha256,size_bytes,media_type,metadata) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) "
                    "ON CONFLICT (tenant_id,id) DO NOTHING RETURNING id",
                    (
                        ctx.tenant_id,
                        source.source_id,
                        item.item_id,
                        item.version_id,
                        item.observed_at,
                        item.content.value,
                        item.size_bytes,
                        item.media_type,
                        Jsonb(dict(item.metadata)),
                    ),
                ).fetchone()
                saved_version = conn.execute(
                    "SELECT source_id,item_id,sha256,size_bytes,media_type,metadata "
                    "FROM brain_source_versions WHERE id=%s",
                    (item.version_id,),
                ).fetchone()
                if not saved_version or saved_version != {
                    "source_id": source.source_id,
                    "item_id": item.item_id,
                    "sha256": item.content.value,
                    "size_bytes": item.size_bytes,
                    "media_type": item.media_type,
                    "metadata": dict(item.metadata),
                }:
                    raise Conflict("source version identity changed")
                conn.execute(
                    "UPDATE brain_source_items SET first_seen_at=least(first_seen_at,%s),"
                    "last_seen_at=greatest(last_seen_at,%s),"
                    "current_version_id=CASE WHEN %s>=last_seen_at THEN %s "
                    "ELSE current_version_id END "
                    "WHERE id=%s",
                    (observed_at, observed_at, observed_at, item.version_id, item.item_id),
                )
                evidence_id = stable_id("evidence", item.version_id)
                conn.execute(
                    "INSERT INTO brain_evidence(tenant_id,id,source_version_id,sha256,"
                    "storage,retained) "
                    "VALUES (%s,%s,%s,%s,'source_bound',false) ON CONFLICT DO NOTHING",
                    (ctx.tenant_id, evidence_id, item.version_id, item.content.value),
                )
                if inserted:
                    new_versions += 1
                    change_id = stable_id("change", "source_version_added", item.version_id)
                    conn.execute(
                        "INSERT INTO brain_change_events(tenant_id,id,source_id,item_id,"
                        "version_id,kind) "
                        "VALUES (%s,%s,%s,%s,%s,'source_version_added')",
                        (
                            ctx.tenant_id,
                            change_id,
                            source.source_id,
                            item.item_id,
                            item.version_id,
                        ),
                    )
            result = ImportResult(
                source.source_id, len(items), new_versions, len(items) - new_versions
            )
            conn.execute(
                "INSERT INTO brain_import_receipts(tenant_id,actor_id,idempotency_key,"
                "request_hash,result) "
                "VALUES (%s,%s,%s,%s,%s)",
                (ctx.tenant_id, ctx.actor_id, idempotency_key, request_hash, Jsonb(asdict(result))),
            )
            return result

    def complete_fileos_run(
        self,
        ctx: TenantContext,
        manifest: Mapping[str, Any],
        run_id: UUID,
        *,
        outcomes: Mapping[str, int],
        item_outcomes: Mapping[str, str],
        published_documents: int,
        code_revision: str,
        document_processor_version: str | None,
    ) -> FileOSRunReceipt:
        """Append a completion receipt only after every snapshot item is accounted."""
        self.store.require(ctx, "brain.document.publish")
        source, observed_at, items = validate_fileos_completion_coverage(manifest)
        policy_hash = fileos_inventory_policy_sha256(manifest)
        root_binding_hash = fileos_manifest_root_binding_sha256(manifest)
        allowed = {"extracted", "empty", "unsupported", "deferred", "changed", "failed"}
        counts = dict(sorted(outcomes.items()))
        items_by_id = {item.item_id: item for item in items}
        item_results = dict(sorted(item_outcomes.items()))
        calculated: dict[str, int] = {}
        for outcome in item_results.values():
            calculated[outcome] = calculated.get(outcome, 0) + 1
        if (
            not isinstance(run_id, UUID)
            or (not counts and bool(items))
            or not set(counts) <= allowed
            or any(type(value) is not int or value <= 0 for value in counts.values())
            or set(item_results) != set(items_by_id)
            or not set(item_results.values()) <= allowed
            or dict(sorted(calculated.items())) != counts
            or sum(counts.values()) != len(items)
            or type(published_documents) is not int
            or not 0 <= published_documents <= len(items)
            or published_documents != counts.get("extracted", 0)
        ):
            raise ValueError("invalid FileOS completion counts")
        for descriptor in (code_revision, FILEOS_TEXT_EXTRACTOR_VERSION):
            if not descriptor or len(descriptor) > 200 or "\x00" in descriptor:
                raise ValueError("invalid FileOS completion provenance")
        if document_processor_version is not None and (
            not document_processor_version
            or len(document_processor_version) > 200
            or "\x00" in document_processor_version
        ):
            raise ValueError("invalid document processor provenance")
        manifest_hash = _canonical_digest(manifest)
        expected = {
            "source_id": source.source_id,
            "observed_at": observed_at,
            "manifest_sha256": manifest_hash,
            "policy_sha256": policy_hash,
            "root_binding_sha256": root_binding_hash,
            "code_revision": code_revision,
            "text_extractor_version": FILEOS_TEXT_EXTRACTOR_VERSION,
            "document_processor_version": document_processor_version,
            "item_count": len(items),
            "outcomes": counts,
            "published_documents": published_documents,
        }
        with self.store.transaction(ctx) as conn:
            conn.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                (f"{ctx.tenant_id}:fileos-source:{source.source_id}",),
            )
            imported = conn.execute(
                "SELECT request_hash,result FROM brain_import_receipts "
                "WHERE actor_id=%s AND idempotency_key=%s",
                (ctx.actor_id, run_id),
            ).fetchone()
            if (
                not imported
                or imported["request_hash"] != manifest_hash
                or imported["result"].get("source_id") != source.source_id
                or imported["result"].get("observed_items") != len(items)
            ):
                raise Conflict("FileOS completion is not bound to its intake")
            existing = conn.execute(
                "SELECT source_id,observed_at,manifest_sha256,policy_sha256,"
                "root_binding_sha256,code_revision,"
                "text_extractor_version,document_processor_version,item_count,outcomes,"
                "published_documents,completed_at "
                "FROM brain_fileos_run_receipts WHERE actor_id=%s AND run_id=%s",
                (ctx.actor_id, run_id),
            ).fetchone()
            previous = conn.execute(
                "SELECT actor_id,run_id,observed_at,manifest_sha256,policy_sha256,"
                "root_binding_sha256,item_count "
                "FROM brain_fileos_run_receipts WHERE source_id=%s "
                "AND NOT (actor_id=%s AND run_id=%s) "
                "ORDER BY observed_at DESC,completed_at DESC,run_id DESC LIMIT 1",
                (source.source_id, ctx.actor_id, run_id),
            ).fetchone()
            bound_source = conn.execute(
                "SELECT root_binding_sha256 FROM brain_sources WHERE id=%s FOR UPDATE",
                (source.source_id,),
            ).fetchone()
            if not bound_source or bound_source["root_binding_sha256"] != root_binding_hash:
                raise Conflict("FileOS source root binding changed")
            if previous and observed_at <= previous["observed_at"]:
                raise Conflict("FileOS completion observation is not newer")
            recorded = existing is None
            if existing:
                completed_at = existing.pop("completed_at")
                if existing["policy_sha256"] is None or existing["root_binding_sha256"] is None:
                    raise Conflict("FileOS inventory policy requires review")
                if existing != expected:
                    raise Conflict("FileOS completion receipt changed")
            else:
                if previous and previous["policy_sha256"] != policy_hash:
                    raise Conflict("FileOS inventory policy requires review")
                if previous and previous["root_binding_sha256"] != root_binding_hash:
                    raise Conflict("FileOS root binding requires review")
                row = conn.execute(
                    "INSERT INTO brain_fileos_run_receipts(tenant_id,actor_id,run_id,source_id,"
                    "observed_at,manifest_sha256,policy_sha256,root_binding_sha256,"
                    "code_revision,text_extractor_version,document_processor_version,item_count,"
                    "outcomes,published_documents) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
                    "RETURNING completed_at",
                    (
                        ctx.tenant_id,
                        ctx.actor_id,
                        run_id,
                        source.source_id,
                        observed_at,
                        manifest_hash,
                        policy_hash,
                        root_binding_hash,
                        code_revision,
                        FILEOS_TEXT_EXTRACTOR_VERSION,
                        document_processor_version,
                        len(items),
                        Jsonb(counts),
                        published_documents,
                    ),
                ).fetchone()
                assert row is not None
                completed_at = row["completed_at"]
            for item_id, outcome in item_results.items():
                item = items_by_id[item_id]
                conn.execute(
                    "INSERT INTO brain_fileos_run_items(tenant_id,actor_id,run_id,source_id,"
                    "observed_at,item_id,version_id,outcome) VALUES (%s,%s,%s,%s,%s,%s,%s,%s) "
                    "ON CONFLICT DO NOTHING",
                    (
                        ctx.tenant_id,
                        ctx.actor_id,
                        run_id,
                        source.source_id,
                        observed_at,
                        item_id,
                        item.version_id,
                        outcome,
                    ),
                )
            saved_items = conn.execute(
                "SELECT item_id,version_id,outcome FROM brain_fileos_run_items "
                "WHERE actor_id=%s AND run_id=%s ORDER BY item_id",
                (ctx.actor_id, run_id),
            ).fetchall()
            expected_items = [
                {
                    "item_id": item_id,
                    "version_id": items_by_id[item_id].version_id,
                    "outcome": outcome,
                }
                for item_id, outcome in item_results.items()
            ]
            if saved_items != expected_items:
                raise Conflict("FileOS run item ledger changed")
            if previous:
                missing = conn.execute(
                    "SELECT old.item_id,old.version_id,prior.locator "
                    "FROM brain_fileos_run_items old "
                    "JOIN brain_source_items prior ON prior.tenant_id=old.tenant_id "
                    "AND prior.source_id=old.source_id AND prior.id=old.item_id "
                    "LEFT JOIN brain_fileos_run_items current ON current.tenant_id=old.tenant_id "
                    "AND current.actor_id=%s AND current.run_id=%s "
                    "AND current.item_id=old.item_id "
                    "WHERE old.actor_id=%s AND old.run_id=%s AND current.item_id IS NULL "
                    "ORDER BY old.item_id",
                    (ctx.actor_id, run_id, previous["actor_id"], previous["run_id"]),
                ).fetchall()
                excluded_files = {
                    entry["locator"] for entry in manifest["exclusions"] if entry["kind"] == "file"
                }
                excluded_directories = {
                    entry["locator"]
                    for entry in manifest["exclusions"]
                    if entry["kind"] == "directory"
                }
                skipped_symlinks = {error["locator"] for error in manifest["errors"]}
                if recorded and any(
                    fileos_missing_locator_is_excluded(
                        row["locator"], excluded_files, excluded_directories, skipped_symlinks
                    )
                    for row in missing
                ):
                    raise Conflict("FileOS excluded prior item requires review")
                if recorded and fileos_mass_loss_requires_review(
                    previous["item_count"], len(missing)
                ):
                    raise Conflict("FileOS inventory mass loss requires review")
                for missing_item in missing:
                    event_id = stable_id(
                        "absence", str(run_id), missing_item["item_id"], missing_item["version_id"]
                    )
                    conn.execute(
                        "INSERT INTO brain_fileos_absence_events(tenant_id,id,source_id,item_id,"
                        "version_id,previous_actor_id,previous_run_id,observed_actor_id,"
                        "observed_run_id,observed_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
                        "ON CONFLICT DO NOTHING",
                        (
                            ctx.tenant_id,
                            event_id,
                            source.source_id,
                            missing_item["item_id"],
                            missing_item["version_id"],
                            previous["actor_id"],
                            previous["run_id"],
                            ctx.actor_id,
                            run_id,
                            observed_at,
                        ),
                    )
            return FileOSRunReceipt(
                run_id,
                source.source_id,
                observed_at,
                completed_at,
                len(items),
                counts,
                published_documents,
                recorded,
            )

    def verify_fileos_completed_baseline(
        self, ctx: TenantContext, manifest: Mapping[str, Any], run_id: UUID
    ) -> datetime:
        """Bind a private v1 manifest to the latest completed, exact-item run.

        This is a read-only transition precondition, not publication authority.
        The caller must recheck after any potentially long donor scan.
        """
        self.store.require(ctx, "brain.changes.read")
        if not isinstance(run_id, UUID):
            raise ValueError("invalid FileOS baseline run")
        source, observed_at, items = validate_fileos_completion_coverage(manifest)
        manifest_hash = fileos_manifest_sha256(manifest)
        policy_hash = fileos_inventory_policy_sha256(manifest)
        root_hash = fileos_manifest_root_binding_sha256(manifest)
        expected_items = sorted((item.item_id, item.version_id) for item in items)
        with self.store.transaction(ctx) as conn:
            latest = conn.execute(
                "SELECT actor_id,run_id,observed_at,completed_at,manifest_sha256,"
                "policy_sha256,root_binding_sha256,item_count,outcomes,published_documents "
                "FROM brain_fileos_run_receipts WHERE source_id=%s "
                "ORDER BY observed_at DESC,completed_at DESC,run_id DESC LIMIT 1",
                (source.source_id,),
            ).fetchone()
            if (
                latest is None
                or latest["run_id"] != run_id
                or latest["observed_at"] != observed_at
                or latest["manifest_sha256"] != manifest_hash
                or latest["policy_sha256"] != policy_hash
                or latest["root_binding_sha256"] != root_hash
                or latest["item_count"] != len(items)
            ):
                raise Conflict("FileOS completed baseline requires review")
            bound_source = conn.execute(
                "SELECT root_binding_sha256 FROM brain_sources WHERE id=%s",
                (source.source_id,),
            ).fetchone()
            if bound_source is None or bound_source["root_binding_sha256"] != root_hash:
                raise Conflict("FileOS completed baseline requires review")
            imported = conn.execute(
                "SELECT request_hash,result FROM brain_import_receipts "
                "WHERE actor_id=%s AND idempotency_key=%s",
                (latest["actor_id"], run_id),
            ).fetchone()
            if (
                imported is None
                or imported["request_hash"] != manifest_hash
                or not isinstance(imported["result"], Mapping)
                or imported["result"].get("source_id") != source.source_id
                or imported["result"].get("observed_items") != len(items)
            ):
                raise Conflict("FileOS completed baseline requires review")
            recorded_items = conn.execute(
                "SELECT item_id,version_id,outcome FROM brain_fileos_run_items "
                "WHERE actor_id=%s AND run_id=%s ORDER BY item_id",
                (latest["actor_id"], run_id),
            ).fetchall()
            if [(row["item_id"], row["version_id"]) for row in recorded_items] != expected_items:
                raise Conflict("FileOS completed baseline requires review")
            actual_outcomes: dict[str, int] = {}
            for row in recorded_items:
                outcome = row["outcome"]
                actual_outcomes[outcome] = actual_outcomes.get(outcome, 0) + 1
            if (
                actual_outcomes != latest["outcomes"]
                or latest["published_documents"] != actual_outcomes.get("extracted", 0)
            ):
                raise Conflict("FileOS completed baseline requires review")
            return cast(datetime, latest["completed_at"])

    def stage_fileos_transition_review(
        self,
        ctx: TenantContext,
        prior_manifest: Mapping[str, Any],
        prior_run_id: UUID,
        packet_id: UUID,
        packet: Mapping[str, Any],
    ) -> FileOSTransitionPacketRecord:
        """Seal one nonpublishing donor-policy packet against a completed v1 run.

        The source advisory lock closes the gap between the caller's scan and
        insertion. This table is never read by freshness, absence or search.
        """
        self.store.require(ctx, "brain.source.ingest")
        self.store.require(ctx, "brain.changes.read")
        if not isinstance(prior_run_id, UUID) or not isinstance(packet_id, UUID):
            raise ValueError("invalid FileOS transition packet identity")
        source, prior_observed, items = validate_fileos_completion_coverage(prior_manifest)
        prior_hash = fileos_manifest_sha256(prior_manifest)
        policy_hash = fileos_inventory_policy_sha256(prior_manifest)
        root_hash = fileos_manifest_root_binding_sha256(prior_manifest)
        if not isinstance(packet, Mapping) or set(packet) != {
            "packet_version", "publishable", "requires_review", "source_id",
            "prior_run_id", "prior_manifest_sha256", "candidate", "preview",
        }:
            raise ValueError("invalid FileOS transition packet")
        candidate = packet["candidate"]
        preview = packet["preview"]
        if not isinstance(candidate, Mapping) or not isinstance(preview, Mapping):
            raise ValueError("invalid FileOS transition packet")
        baseline = preview.get("completed_baseline")
        candidate_source = candidate.get("source")
        candidate_root = candidate.get("root_binding")
        preview_root = preview.get("root_binding")
        if (
            packet["packet_version"] != "masterbrain-fileos-transition-review-packet-v1"
            or packet["publishable"] is not False
            or packet["requires_review"] is not True
            or packet["source_id"] != source.source_id
            or packet["prior_run_id"] != str(prior_run_id)
            or packet["prior_manifest_sha256"] != prior_hash
            or candidate.get("candidate_version") != "masterbrain-fileos-donor-candidate-v1"
            or candidate.get("publishable") is not False
            or not isinstance(candidate_source, Mapping)
            or candidate_source.get("source_id") != source.source_id
            or candidate_source.get("kind") != "fileos"
            or not isinstance(candidate_root, Mapping)
            or candidate_root.get("sha256") != root_hash
            or not isinstance(preview_root, Mapping)
            or preview_root != candidate_root
            or preview.get("publishable") is not False
            or preview.get("requires_review") is not True
            or preview.get("source_id") != source.source_id
            or preview.get("prior_observed_at") != prior_observed.isoformat()
            or preview.get("donor_observed_at") != candidate.get("observed_at")
            or preview.get("prior_policy_sha256") != policy_hash
            or preview.get("candidate_counts") != candidate.get("counts")
            or not isinstance(baseline, Mapping)
            or baseline.get("run_id") != str(prior_run_id)
            or baseline.get("manifest_sha256") != prior_hash
        ):
            raise ValueError("invalid FileOS transition packet binding")
        ledgers = ("hashed", "deferred", "exclusions", "errors")
        candidate_counts = candidate.get("counts")
        preview_counts = preview.get("counts")
        prior_states = (
            "unchanged", "changed", "deferred_prior", "excluded_prior",
            "error_covered_prior", "unobserved_prior",
        )
        if (
            not isinstance(candidate_counts, Mapping)
            or set(candidate_counts) != {"hashed", "deferred", "excluded", "errors"}
            or any(not isinstance(candidate.get(name), list) for name in ledgers)
            or candidate_counts != {
                "hashed": len(candidate["hashed"]),
                "deferred": len(candidate["deferred"]),
                "excluded": len(candidate["exclusions"]),
                "errors": len(candidate["errors"]),
            }
            or not isinstance(preview.get("prior_items"), list)
            or len(preview["prior_items"]) != len(items)
            or not isinstance(preview_counts, Mapping)
            or set(preview_counts) != {*prior_states, "donor_only_hashed"}
            or any(type(preview_counts[state]) is not int or preview_counts[state] < 0
                   for state in preview_counts)
            or sum(preview_counts[state] for state in prior_states) != len(items)
            or not isinstance(preview.get("donor_only_hashed"), list)
            or preview_counts["donor_only_hashed"] != len(preview["donor_only_hashed"])
            or any(
                not isinstance(row, Mapping)
                or "version_id" in row
                or "digest" in row
                for row in candidate["deferred"]
            )
        ):
            raise ValueError("invalid FileOS transition packet ledger")
        donor_observed = _parse_time(candidate.get("observed_at"))
        if donor_observed <= prior_observed:
            raise ValueError("FileOS transition observation is not newer")
        try:
            encoded = json.dumps(
                packet, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                allow_nan=False,
            ).encode()
        except (TypeError, ValueError) as exc:
            raise ValueError("invalid FileOS transition packet encoding") from exc
        if len(encoded) > 16 * 1024 * 1024:
            raise ValueError("FileOS transition packet byte bound exceeded")
        packet_hash = hashlib.sha256(encoded).hexdigest()
        with self.store.transaction(ctx) as conn:
            conn.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                (f"{ctx.tenant_id}:fileos-source:{source.source_id}",),
            )
            latest = conn.execute(
                "SELECT actor_id,run_id,observed_at,completed_at,manifest_sha256,"
                "policy_sha256,root_binding_sha256,item_count "
                "FROM brain_fileos_run_receipts WHERE source_id=%s "
                "ORDER BY observed_at DESC,completed_at DESC,run_id DESC LIMIT 1",
                (source.source_id,),
            ).fetchone()
            bound_source = conn.execute(
                "SELECT root_binding_sha256 FROM brain_sources WHERE id=%s",
                (source.source_id,),
            ).fetchone()
            if (
                latest is None
                or latest["run_id"] != prior_run_id
                or latest["observed_at"] != prior_observed
                or latest["manifest_sha256"] != prior_hash
                or latest["policy_sha256"] != policy_hash
                or latest["root_binding_sha256"] != root_hash
                or latest["item_count"] != len(items)
                or not isinstance(baseline.get("completed_at"), str)
                or baseline["completed_at"] != latest["completed_at"].isoformat()
                or bound_source is None
                or bound_source["root_binding_sha256"] != root_hash
            ):
                raise Conflict("FileOS transition baseline requires review")
            existing = conn.execute(
                "SELECT source_id,prior_actor_id,prior_run_id,prior_manifest_sha256,"
                "packet_sha256,recorded_at FROM brain_fileos_transition_packets WHERE id=%s",
                (packet_id,),
            ).fetchone()
            if existing:
                if (
                    existing["source_id"] != source.source_id
                    or existing["prior_actor_id"] != latest["actor_id"]
                    or existing["prior_run_id"] != prior_run_id
                    or existing["prior_manifest_sha256"] != prior_hash
                    or existing["packet_sha256"] != packet_hash
                ):
                    raise Conflict("FileOS transition packet identity changed")
                return FileOSTransitionPacketRecord(
                    packet_id, source.source_id, packet_hash, existing["recorded_at"], False
                )
            if conn.execute(
                "SELECT 1 FROM brain_fileos_transition_packets WHERE source_id=%s "
                "AND prior_actor_id=%s AND prior_run_id=%s AND packet_sha256=%s",
                (source.source_id, latest["actor_id"], prior_run_id, packet_hash),
            ).fetchone():
                raise Conflict("FileOS transition packet already recorded")
            inserted = conn.execute(
                "INSERT INTO brain_fileos_transition_packets(tenant_id,id,actor_id,source_id,"
                "prior_actor_id,prior_run_id,prior_observed_at,donor_observed_at,"
                "root_binding_sha256,prior_manifest_sha256,packet_sha256,packet) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING recorded_at",
                (
                    ctx.tenant_id, packet_id, ctx.actor_id, source.source_id,
                    latest["actor_id"], prior_run_id, prior_observed, donor_observed,
                    root_hash, prior_hash, packet_hash, Jsonb(dict(packet)),
                ),
            ).fetchone()
            assert inserted is not None
            return FileOSTransitionPacketRecord(
                packet_id, source.source_id, packet_hash, inserted["recorded_at"], True
            )

    def stage_fileos_v2_inventory(
        self, ctx: TenantContext, packet_id: UUID, stage_id: UUID
    ) -> FileOSV2StagedInventoryRecord:
        """Persist a donor-shape inventory without publishing or inferring absence."""
        self.store.require(ctx, "brain.source.ingest")
        self.store.require(ctx, "brain.changes.read")
        if not isinstance(packet_id, UUID) or not isinstance(stage_id, UUID):
            raise ValueError("invalid FileOS v2 stage identity")
        with self.store.transaction(ctx) as conn:
            packet_row = conn.execute(
                "SELECT id,source_id,prior_actor_id,prior_run_id,prior_observed_at,"
                "donor_observed_at,root_binding_sha256,prior_manifest_sha256,"
                "packet_sha256,packet FROM brain_fileos_transition_packets WHERE id=%s",
                (packet_id,),
            ).fetchone()
            if packet_row is None:
                raise NotFound()
            packet = packet_row["packet"]
            if (
                not isinstance(packet, Mapping)
                or _canonical_digest(packet) != packet_row["packet_sha256"]
                or packet.get("packet_version") != "masterbrain-fileos-transition-review-packet-v1"
                or packet.get("publishable") is not False
                or packet.get("requires_review") is not True
                or packet.get("source_id") != packet_row["source_id"]
                or packet.get("prior_run_id") != str(packet_row["prior_run_id"])
                or packet.get("prior_manifest_sha256") != packet_row["prior_manifest_sha256"]
            ):
                raise Conflict("FileOS v2 staging packet integrity requires review")
            source_id = packet_row["source_id"]
            candidate = packet.get("candidate")
            preview = packet.get("preview")
            if not isinstance(candidate, Mapping) or not isinstance(preview, Mapping):
                raise Conflict("FileOS v2 staging packet integrity requires review")
            try:
                rows = _fileos_v2_staged_rows(candidate, source_id)
                donor_observed = _parse_time(candidate.get("observed_at"))
            except (TypeError, ValueError) as exc:
                raise Conflict("FileOS v2 staging candidate requires review") from exc
            root = candidate.get("root_binding")
            baseline = preview.get("completed_baseline")
            if (
                not isinstance(root, Mapping)
                or root.get("sha256") != packet_row["root_binding_sha256"]
                or donor_observed != packet_row["donor_observed_at"]
                or not isinstance(baseline, Mapping)
                or baseline.get("run_id") != str(packet_row["prior_run_id"])
                or baseline.get("manifest_sha256") != packet_row["prior_manifest_sha256"]
                or preview.get("candidate_counts") != candidate["counts"]
            ):
                raise Conflict("FileOS v2 staging packet binding requires review")
            candidate_sha = _canonical_digest(candidate)
            conn.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                (f"{ctx.tenant_id}:fileos-source:{source_id}",),
            )
            latest = conn.execute(
                "SELECT actor_id,run_id,observed_at,completed_at,manifest_sha256,"
                "root_binding_sha256 FROM brain_fileos_run_receipts WHERE source_id=%s "
                "ORDER BY observed_at DESC,completed_at DESC,run_id DESC LIMIT 1",
                (source_id,),
            ).fetchone()
            source = conn.execute(
                "SELECT root_binding_sha256 FROM brain_sources WHERE id=%s AND kind='fileos'",
                (source_id,),
            ).fetchone()
            if (
                latest is None or source is None
                or latest["actor_id"] != packet_row["prior_actor_id"]
                or latest["run_id"] != packet_row["prior_run_id"]
                or latest["observed_at"] != packet_row["prior_observed_at"]
                or latest["manifest_sha256"] != packet_row["prior_manifest_sha256"]
                or latest["root_binding_sha256"] != packet_row["root_binding_sha256"]
                or source["root_binding_sha256"] != packet_row["root_binding_sha256"]
                or baseline.get("completed_at") != latest["completed_at"].isoformat()
            ):
                raise Conflict("FileOS v2 staging baseline requires review")
            existing = conn.execute(
                "SELECT id,packet_id,source_id,candidate_sha256,recorded_at "
                "FROM brain_fileos_v2_staged_inventories WHERE id=%s OR packet_id=%s",
                (stage_id, packet_id),
            ).fetchone()
            if existing:
                if (
                    existing["id"] != stage_id
                    or existing["packet_id"] != packet_id
                    or existing["source_id"] != source_id
                    or existing["candidate_sha256"] != candidate_sha
                ):
                    raise Conflict("FileOS v2 stage identity changed")
                self.store.audit(
                    conn, ctx, "brain.fileos_v2_inventory_stage_replay",
                    "fileos_v2_stage", str(stage_id),
                )
                return FileOSV2StagedInventoryRecord(
                    stage_id, packet_id, source_id, candidate_sha, existing["recorded_at"], False
                )
            conn.execute(
                "INSERT INTO brain_fileos_v2_staged_inventories(tenant_id,id,actor_id,"
                "packet_id,source_id,prior_actor_id,prior_run_id,prior_observed_at,"
                "donor_observed_at,root_binding_sha256,packet_sha256,candidate_sha256,counts) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (ctx.tenant_id, stage_id, ctx.actor_id, packet_id, source_id,
                 packet_row["prior_actor_id"], packet_row["prior_run_id"],
                 packet_row["prior_observed_at"], donor_observed,
                 packet_row["root_binding_sha256"], packet_row["packet_sha256"],
                 candidate_sha, Jsonb(dict(candidate["counts"]))),
            )
            for kind, locator, item_id, version_id, sha256, size, media, reason in rows:
                conn.execute(
                    "INSERT INTO brain_fileos_v2_staged_rows(tenant_id,stage_id,source_id,"
                    "kind,locator,item_id,version_id,sha256,size_bytes,media_type,reason) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (ctx.tenant_id, stage_id, source_id, kind, locator, item_id,
                     version_id, sha256, size, media, reason),
                )
            recorded = conn.execute(
                "SELECT recorded_at FROM brain_fileos_v2_staged_inventories WHERE id=%s",
                (stage_id,),
            ).fetchone()
            assert recorded is not None
            self.store.audit(
                conn, ctx, "brain.fileos_v2_inventory_staged",
                "fileos_v2_stage", str(stage_id),
            )
            return FileOSV2StagedInventoryRecord(
                stage_id, packet_id, source_id, candidate_sha, recorded["recorded_at"], True
            )

    def fileos_transition_review(
        self,
        ctx: TenantContext,
        packet_id: UUID,
        *,
        include_details: bool = False,
        offset: int = 0,
        limit: int = 25,
    ) -> dict[str, Any]:
        """Read a sealed packet without making it a publishable FileOS run.

        The summary omits locators. Detail requires a separate evidence scope
        and uses stable ordinal pages over the immutable packet.
        """
        self.store.require(ctx, "brain.changes.read")
        if include_details:
            self.store.require(ctx, "brain.evidence.read")
        if (
            not isinstance(packet_id, UUID)
            or type(include_details) is not bool
            or type(offset) is not int
            or offset < 0
            or type(limit) is not int
            or not 1 <= limit <= 50
            or (not include_details and offset != 0)
        ):
            raise ValueError("invalid FileOS transition review request")
        with self.store.transaction(ctx) as conn:
            saved = conn.execute(
                "SELECT id,source_id,prior_actor_id,prior_run_id,prior_observed_at,"
                "donor_observed_at,root_binding_sha256,prior_manifest_sha256,"
                "packet_sha256,packet,recorded_at FROM brain_fileos_transition_packets "
                "WHERE id=%s",
                (packet_id,),
            ).fetchone()
            if saved is None:
                raise NotFound()
            packet = saved["packet"]
            try:
                encoded = json.dumps(
                    packet, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                    allow_nan=False,
                ).encode()
                actual_hash = hashlib.sha256(encoded).hexdigest()
            except (TypeError, ValueError) as exc:
                raise Conflict("FileOS transition packet integrity requires review") from exc
            if actual_hash != saved["packet_sha256"] or len(encoded) > 16 * 1024 * 1024:
                raise Conflict("FileOS transition packet integrity requires review")
            if not isinstance(packet, Mapping):
                raise Conflict("FileOS transition packet integrity requires review")
            candidate = packet.get("candidate")
            preview = packet.get("preview")
            if not isinstance(candidate, Mapping) or not isinstance(preview, Mapping):
                raise Conflict("FileOS transition packet integrity requires review")
            try:
                donor_observed = _parse_time(candidate.get("observed_at"))
            except ValueError as exc:
                raise Conflict("FileOS transition packet integrity requires review") from exc
            counts = candidate.get("counts")
            classifications = preview.get("counts")
            blockers = preview.get("blockers")
            ledgers = ("hashed", "deferred", "exclusions", "errors")
            prior_rows = preview.get("prior_items")
            allowed_blockers = {
                "prior_snapshot_errors", "donor_scan_errors",
                "prior_item_not_hashed_under_donor_policy",
            }
            if (
                packet.get("packet_version") != "masterbrain-fileos-transition-review-packet-v1"
                or packet.get("publishable") is not False
                or packet.get("requires_review") is not True
                or packet.get("source_id") != saved["source_id"]
                or packet.get("prior_run_id") != str(saved["prior_run_id"])
                or packet.get("prior_manifest_sha256") != saved["prior_manifest_sha256"]
                or donor_observed != saved["donor_observed_at"]
                or not isinstance(counts, Mapping)
                or not isinstance(classifications, Mapping)
                or set(counts) != {"hashed", "deferred", "excluded", "errors"}
                or set(classifications) != {
                    "unchanged", "changed", "deferred_prior", "excluded_prior",
                    "error_covered_prior", "unobserved_prior", "donor_only_hashed",
                }
                or not isinstance(blockers, list)
                or any(not isinstance(value, str) or value not in allowed_blockers
                       for value in blockers)
                or not isinstance(prior_rows, list)
                or any(not isinstance(candidate.get(ledger), list) for ledger in ledgers)
                or counts != {
                    "hashed": len(candidate["hashed"]),
                    "deferred": len(candidate["deferred"]),
                    "excluded": len(candidate["exclusions"]),
                    "errors": len(candidate["errors"]),
                }
                or not all(type(value) is int and value >= 0
                           for value in classifications.values())
            ):
                raise Conflict("FileOS transition packet integrity requires review")
            conn.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                (f"{ctx.tenant_id}:fileos-source:{saved['source_id']}",),
            )
            latest = conn.execute(
                "SELECT actor_id,run_id,observed_at,manifest_sha256,"
                "root_binding_sha256,policy_sha256 FROM brain_fileos_run_receipts "
                "WHERE source_id=%s ORDER BY observed_at DESC,completed_at DESC,run_id DESC "
                "LIMIT 1",
                (saved["source_id"],),
            ).fetchone()
            source = conn.execute(
                "SELECT root_binding_sha256 FROM brain_sources WHERE id=%s AND kind='fileos'",
                (saved["source_id"],),
            ).fetchone()
            latest_matches = bool(
                latest
                and source
                and latest["actor_id"] == saved["prior_actor_id"]
                and latest["run_id"] == saved["prior_run_id"]
                and latest["observed_at"] == saved["prior_observed_at"]
                and latest["manifest_sha256"] == saved["prior_manifest_sha256"]
                and latest["root_binding_sha256"] == saved["root_binding_sha256"]
                and source["root_binding_sha256"] == saved["root_binding_sha256"]
                and latest["policy_sha256"] == preview.get("prior_policy_sha256")
            )
            total = len(prior_rows) + sum(len(candidate[ledger]) for ledger in ledgers)
            result: dict[str, Any] = {
                "review_version": "masterbrain-fileos-transition-review-v1",
                "packet_id": packet_id,
                "source_id": saved["source_id"],
                "prior_run_id": saved["prior_run_id"],
                "packet_sha256": saved["packet_sha256"],
                "recorded_at": saved["recorded_at"],
                "donor_observed_at": saved["donor_observed_at"],
                "latest_receipt_matches_packet": latest_matches,
                "publishable": False,
                "requires_review": True,
                "candidate_counts": dict(counts),
                "classification_counts": dict(classifications),
                "blockers": list(blockers),
                "detail_total": total,
            }
            if include_details:
                ordered = [
                    *(("prior", row) for row in prior_rows),
                    *((ledger, row) for ledger in ledgers for row in candidate[ledger]),
                ]
                page = ordered[offset:offset + limit]
                result["details"] = [_fileos_transition_detail(kind, row) for kind, row in page]
                result["next_offset"] = offset + len(page) if offset + len(page) < total else None
            self.store.audit(
                conn, ctx, "brain.fileos_transition_review_read",
                "fileos_transition_packet", str(packet_id),
            )
            return result

    def fileos_freshness(self, ctx: TenantContext, source_id: str) -> dict[str, Any]:
        """Return the latest complete run, never an in-progress or partial prefix."""
        self.store.require(ctx, "brain.changes.read")
        if not _IDENTITY.fullmatch(source_id):
            raise NotFound()
        with self.store.transaction(ctx) as conn:
            if not conn.execute("SELECT 1 FROM brain_sources WHERE id=%s", (source_id,)).fetchone():
                raise NotFound()
            row = conn.execute(
                "SELECT run_id,observed_at,completed_at,item_count,outcomes,"
                "published_documents,code_revision,"
                "text_extractor_version,document_processor_version "
                "FROM brain_fileos_run_receipts WHERE source_id=%s "
                "ORDER BY observed_at DESC,completed_at DESC,run_id DESC LIMIT 1",
                (source_id,),
            ).fetchone()
            self.store.audit(conn, ctx, "brain.fileos_freshness_read", "brain_source", source_id)
        return {
            "source_id": source_id,
            "status": "complete" if row else "no_completed_run",
            "latest_complete_run": row,
            "partial_runs_included": False,
        }

    def current_coverage(
        self,
        ctx: TenantContext,
        *,
        after: str | None = None,
        limit: int = 25,
    ) -> dict[str, Any]:
        """Summarize bounded current-search coverage for registered sources."""
        self.store.require(ctx, "brain.changes.read")
        if after is not None and not _IDENTITY.fullmatch(after):
            raise NotFound()
        if not 1 <= limit <= 50:
            raise ValueError("invalid coverage limit")
        with self.store.transaction(ctx) as conn:
            generated = conn.execute("SELECT clock_timestamp() AS generated_at").fetchone()
            assert generated is not None
            if (
                after is not None
                and not conn.execute("SELECT 1 FROM brain_sources WHERE id=%s", (after,)).fetchone()
            ):
                raise NotFound()
            rows = conn.execute(
                "WITH current_parents AS ("
                "SELECT eb.tenant_id,eb.source_id,eb.evidence_id,eb.created_at "
                "FROM brain_email_bridge_receipts eb JOIN message_versions mv ON "
                "mv.tenant_id=eb.tenant_id AND mv.account_id=eb.account_id "
                "AND mv.id=eb.legacy_version_id JOIN messages m ON "
                "m.tenant_id=mv.tenant_id AND m.account_id=mv.account_id "
                "AND m.id=mv.message_id AND m.raw_sha256=mv.raw_sha256 "
                "AND m.parser_version=mv.parser_version JOIN brain_source_items pi ON "
                "pi.tenant_id=eb.tenant_id AND pi.id=eb.item_id "
                "AND pi.current_version_id=eb.version_id "
                "WHERE NOT m.deleted AND NOT m.quarantined), current_attachments AS ("
                "SELECT ab.tenant_id,ab.source_id,ab.legacy_attachment_id,ab.item_id,"
                "ab.version_id,ab.evidence_id,ab.created_at FROM current_parents p "
                "JOIN brain_email_attachment_bridge_receipts ab ON "
                "ab.tenant_id=p.tenant_id AND ab.parent_evidence_id=p.evidence_id "
                "JOIN brain_source_items ai ON ai.tenant_id=ab.tenant_id "
                "AND ai.id=ab.item_id AND ai.current_version_id=ab.version_id), "
                "current_documents AS (SELECT db.tenant_id,db.source_id,db.created_at "
                "FROM current_attachments a JOIN brain_email_document_bridge_receipts db ON "
                "db.tenant_id=a.tenant_id "
                "AND db.legacy_attachment_id=a.legacy_attachment_id "
                "AND db.source_id=a.source_id AND db.item_id=a.item_id "
                "AND db.version_id=a.version_id AND db.evidence_id=a.evidence_id), "
                "selected AS (SELECT id,kind,status,created_at FROM brain_sources "
                "WHERE (%s::text IS NULL OR id>%s) ORDER BY id LIMIT %s) "
                "SELECT s.id AS source_id,s.kind,s.status AS configured_status,"
                "s.created_at AS registered_at,a.generation_id,a.activated_at,"
                "g.run_actor_id,g.run_id,g.observed_at AS generation_observed_at,"
                "g.item_count,g.document_count,g.chunk_count,lr.actor_id AS latest_run_actor_id,"
                "lr.run_id AS latest_run_id,lr.observed_at AS latest_run_observed_at,"
                "lr.completed_at AS latest_run_completed_at,"
                "COALESCE((SELECT count(*) FROM current_parents p "
                "WHERE p.source_id=s.id),0)::integer AS email_message_count,"
                "(SELECT max(p.created_at) FROM current_parents p "
                "WHERE p.source_id=s.id) AS latest_message_bridge_at,"
                "COALESCE((SELECT count(*) FROM current_attachments ea "
                "WHERE ea.source_id=s.id),0)::integer AS email_attachment_count,"
                "(SELECT max(ea.created_at) FROM current_attachments ea "
                "WHERE ea.source_id=s.id) AS latest_attachment_bridge_at,"
                "COALESCE((SELECT count(*) FROM current_documents ed "
                "WHERE ed.source_id=s.id),0)::integer AS email_document_count,"
                "(SELECT max(ed.created_at) FROM current_documents ed "
                "WHERE ed.source_id=s.id) AS latest_document_bridge_at "
                "FROM selected s LEFT JOIN LATERAL (SELECT generation_id,activated_at "
                "FROM brain_index_activations WHERE source_id=s.id "
                "ORDER BY activated_at DESC,idempotency_key DESC LIMIT 1) a "
                "ON s.kind='fileos' LEFT JOIN brain_index_generations g "
                "ON g.id=a.generation_id AND g.source_id=s.id LEFT JOIN LATERAL ("
                "SELECT actor_id,run_id,observed_at,completed_at "
                "FROM brain_fileos_run_receipts WHERE source_id=s.id "
                "ORDER BY observed_at DESC,completed_at DESC,run_id DESC LIMIT 1) lr "
                "ON s.kind='fileos' ORDER BY s.id",
                (after, after, limit + 1),
            ).fetchall()
            self.store.audit(conn, ctx, "brain.current_coverage_read", "brain_source", "registered")
        page = rows[:limit]
        results: list[dict[str, Any]] = []
        for row in page:
            common = {
                "source_id": row["source_id"],
                "kind": row["kind"],
                "configured_status": row["configured_status"],
                "registered_at": row["registered_at"],
            }
            if row["kind"] == "fileos":
                generation = None
                if row["generation_id"] is not None:
                    generation = {
                        "generation_id": row["generation_id"],
                        "activated_at": row["activated_at"],
                        "observed_at": row["generation_observed_at"],
                        "item_count": row["item_count"],
                        "document_count": row["document_count"],
                        "chunk_count": row["chunk_count"],
                    }
                latest_run = None
                if row["latest_run_id"] is not None:
                    latest_run = {
                        "run_id": row["latest_run_id"],
                        "observed_at": row["latest_run_observed_at"],
                        "completed_at": row["latest_run_completed_at"],
                    }
                results.append(
                    {
                        **common,
                        "coverage": "active_generation_only",
                        "status": ("search_ready" if generation else "no_active_generation"),
                        "active_generation": generation,
                        "latest_complete_run": latest_run,
                        "latest_completion_is_active": bool(
                            generation
                            and row["latest_run_id"] == row["run_id"]
                            and row["latest_run_actor_id"] == row["run_actor_id"]
                        ),
                    }
                )
            else:
                counts = {
                    "messages": row["email_message_count"],
                    "attachments": row["email_attachment_count"],
                    "documents": row["email_document_count"],
                }
                results.append(
                    {
                        **common,
                        "coverage": "explicit_bridges_only",
                        "status": (
                            "current_evidence_available"
                            if any(counts.values())
                            else "no_current_bridged_evidence"
                        ),
                        "current_counts": counts,
                        "latest_current_bridge_at": {
                            "messages": row["latest_message_bridge_at"],
                            "attachments": row["latest_attachment_bridge_at"],
                            "documents": row["latest_document_bridge_at"],
                        },
                    }
                )
        return {
            "generated_at": generated["generated_at"],
            "complete": False,
            "semantics": "registered_sources_and_explicit_bridges_only",
            "results": results,
            "next_cursor": page[-1]["source_id"] if len(rows) > limit and page else None,
            "limit": limit,
        }

    def fileos_inventory(self, ctx: TenantContext, source_id: str) -> dict[str, Any]:
        """Summarize membership and newly observed absence for the latest complete run."""
        self.store.require(ctx, "brain.changes.read")
        if not _IDENTITY.fullmatch(source_id):
            raise NotFound()
        with self.store.transaction(ctx) as conn:
            source = conn.execute(
                "SELECT 1 FROM brain_sources WHERE id=%s AND kind='fileos'", (source_id,)
            ).fetchone()
            if not source:
                raise NotFound()
            latest = conn.execute(
                "SELECT actor_id,run_id,observed_at,completed_at,item_count "
                "FROM brain_fileos_run_receipts WHERE source_id=%s "
                "ORDER BY observed_at DESC,completed_at DESC,run_id DESC LIMIT 1",
                (source_id,),
            ).fetchone()
            if latest:
                absence = conn.execute(
                    "SELECT count(*) AS n FROM brain_fileos_absence_events "
                    "WHERE source_id=%s AND observed_actor_id=%s AND observed_run_id=%s",
                    (source_id, latest["actor_id"], latest["run_id"]),
                ).fetchone()
                assert absence is not None
                result = {
                    "source_id": source_id,
                    "status": "complete",
                    "run_id": latest["run_id"],
                    "observed_at": latest["observed_at"],
                    "completed_at": latest["completed_at"],
                    "present_items": latest["item_count"],
                    "newly_absent_items": absence["n"],
                    "absent_evidence_retained": True,
                    "search_visibility_changed": False,
                }
            else:
                result = {
                    "source_id": source_id,
                    "status": "no_completed_run",
                    "run_id": None,
                    "observed_at": None,
                    "completed_at": None,
                    "present_items": None,
                    "newly_absent_items": None,
                    "absent_evidence_retained": True,
                    "search_visibility_changed": False,
                }
            self.store.audit(conn, ctx, "brain.fileos_inventory_read", "brain_source", source_id)
            return result

    def fileos_rebuild_preview(
        self,
        ctx: TenantContext,
        source_id: str,
        *,
        after: str | None = None,
        limit: int = 25,
    ) -> dict[str, Any]:
        """Verify a bounded page of current deterministic index artifacts without writes."""
        self.store.require(ctx, "brain.changes.read")
        if (
            not _IDENTITY.fullmatch(source_id)
            or (after is not None and not _IDENTITY.fullmatch(after))
            or not 1 <= limit <= 50
        ):
            raise ValueError("invalid FileOS rebuild preview request")
        with self.store.transaction(ctx) as conn:
            source = conn.execute(
                "SELECT 1 FROM brain_sources WHERE id=%s AND kind='fileos'", (source_id,)
            ).fetchone()
            if not source:
                raise NotFound()
            conn.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                (f"{ctx.tenant_id}:fileos-source:{source_id}",),
            )
            latest = conn.execute(
                "SELECT actor_id,run_id,observed_at,item_count "
                "FROM brain_fileos_run_receipts WHERE source_id=%s "
                "ORDER BY observed_at DESC,completed_at DESC,run_id DESC LIMIT 1",
                (source_id,),
            ).fetchone()
            if not latest:
                self.store.audit(
                    conn, ctx, "brain.fileos_rebuild_preview", "brain_source", source_id
                )
                return {
                    "source_id": source_id,
                    "status": "no_completed_run",
                    "run_id": None,
                    "observed_at": None,
                    "total_items": None,
                    "results": [],
                    "next_cursor": None,
                    "source_effects": False,
                    "data_effects": False,
                }
            if (
                after is not None
                and not conn.execute(
                    "SELECT 1 FROM brain_fileos_run_items "
                    "WHERE actor_id=%s AND run_id=%s AND item_id=%s",
                    (latest["actor_id"], latest["run_id"], after),
                ).fetchone()
            ):
                raise NotFound()
            rows = conn.execute(
                "SELECT ri.item_id,ri.version_id,ri.outcome,e.id AS evidence_id,"
                "d.id AS document_id,d.normalizer,d.body_sha256,d.body "
                "FROM brain_fileos_run_items ri "
                "JOIN brain_evidence e ON e.tenant_id=ri.tenant_id "
                "AND e.source_version_id=ri.version_id "
                "LEFT JOIN LATERAL (SELECT nd.id,nd.normalizer,nd.body_sha256,nd.body "
                "FROM brain_normalized_documents nd WHERE nd.tenant_id=ri.tenant_id "
                "AND nd.evidence_id=e.id ORDER BY nd.created_at DESC,nd.id DESC LIMIT 1) d "
                "ON true WHERE ri.actor_id=%s AND ri.run_id=%s AND ri.item_id>%s "
                "ORDER BY ri.item_id LIMIT %s",
                (latest["actor_id"], latest["run_id"], after or "", limit + 1),
            ).fetchall()
            has_more = len(rows) > limit
            page = rows[:limit]
            document_ids = [row["document_id"] for row in page if row["document_id"]]
            chunk_rows = (
                conn.execute(
                    "SELECT document_id,id,ordinal,start_offset,end_offset,text,sha256 "
                    "FROM brain_chunks WHERE document_id=ANY(%s) "
                    "ORDER BY document_id,ordinal",
                    (document_ids,),
                ).fetchall()
                if document_ids
                else []
            )
            chunks_by_document: dict[str, list[dict[str, Any]]] = {}
            for chunk in chunk_rows:
                chunks_by_document.setdefault(chunk["document_id"], []).append(chunk)
            results: list[dict[str, Any]] = []
            for row in page:
                document_id = row["document_id"]
                if document_id is None:
                    disposition = "source_reprocess_required"
                    expected_chunks = None
                    stored_chunks = 0
                else:
                    body = row["body"]
                    body_sha = hashlib.sha256(body.encode()).hexdigest()
                    expected_document_id = stable_id(
                        "document", row["version_id"], row["normalizer"], body_sha
                    )
                    expected = [
                        {
                            "document_id": document_id,
                            "id": stable_id(
                                "chunk",
                                document_id,
                                str(ordinal),
                                hashlib.sha256(text.encode()).hexdigest(),
                            ),
                            "ordinal": ordinal,
                            "start_offset": start,
                            "end_offset": end,
                            "text": text,
                            "sha256": hashlib.sha256(text.encode()).hexdigest(),
                        }
                        for ordinal, (start, end, text) in enumerate(deterministic_chunks(body))
                    ]
                    stored = chunks_by_document.get(document_id, [])
                    valid = (
                        row["body_sha256"] == body_sha
                        and document_id == expected_document_id
                        and stored == expected
                    )
                    disposition = "verified" if valid else "rebuild_required"
                    expected_chunks = len(expected)
                    stored_chunks = len(stored)
                results.append(
                    {
                        "item_id": row["item_id"],
                        "version_id": row["version_id"],
                        "evidence_id": row["evidence_id"],
                        "document_id": document_id,
                        "source_outcome": row["outcome"],
                        "disposition": disposition,
                        "expected_chunks": expected_chunks,
                        "stored_chunks": stored_chunks,
                    }
                )
            self.store.audit(conn, ctx, "brain.fileos_rebuild_preview", "brain_source", source_id)
            return {
                "source_id": source_id,
                "status": "complete",
                "run_id": latest["run_id"],
                "observed_at": latest["observed_at"],
                "total_items": latest["item_count"],
                "results": results,
                "next_cursor": page[-1]["item_id"] if has_more else None,
                "source_effects": False,
                "data_effects": False,
            }

    def build_fileos_index_generation(
        self,
        ctx: TenantContext,
        source_id: str,
        expected_run_id: UUID,
        *,
        code_revision: str,
    ) -> IndexGeneration:
        """Build one immutable lexical generation from normalized evidence."""
        self.store.require(ctx, "brain.document.publish")
        if (
            not _IDENTITY.fullmatch(source_id)
            or not isinstance(expected_run_id, UUID)
            or not code_revision
            or len(code_revision) > 200
            or "\x00" in code_revision
        ):
            raise ValueError("invalid index generation request")
        with self.store.transaction(ctx) as conn:
            conn.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                (f"{ctx.tenant_id}:fileos-source:{source_id}",),
            )
            run = conn.execute(
                "SELECT actor_id,run_id,observed_at,item_count "
                "FROM brain_fileos_run_receipts WHERE source_id=%s "
                "ORDER BY observed_at DESC,completed_at DESC,run_id DESC LIMIT 1",
                (source_id,),
            ).fetchone()
            if not run:
                raise NotFound()
            if run["run_id"] != expected_run_id:
                raise Conflict("index generation is not bound to the latest complete run")
            rows = conn.execute(
                "SELECT ri.item_id,ri.version_id,ri.outcome,e.id AS evidence_id,"
                "d.id AS document_id,d.normalizer,d.body_sha256,d.body "
                "FROM brain_fileos_run_items ri JOIN brain_evidence e "
                "ON e.tenant_id=ri.tenant_id AND e.source_version_id=ri.version_id "
                "LEFT JOIN LATERAL (SELECT nd.id,nd.normalizer,nd.body_sha256,nd.body "
                "FROM brain_normalized_documents nd WHERE nd.tenant_id=ri.tenant_id "
                "AND nd.evidence_id=e.id ORDER BY nd.created_at DESC,nd.id DESC LIMIT 1) d "
                "ON true WHERE ri.actor_id=%s AND ri.run_id=%s ORDER BY ri.item_id",
                (run["actor_id"], expected_run_id),
            ).fetchall()
            if len(rows) != run["item_count"]:
                raise Conflict("completed inventory ledger is incomplete")
            plan_items: list[dict[str, Any]] = []
            generated_chunks: list[dict[str, Any]] = []
            total_text_bytes = 0
            document_count = 0
            for row in rows:
                if row["evidence_id"] != stable_id("evidence", row["version_id"]):
                    raise Conflict("evidence identity changed")
                document_id = row["document_id"]
                disposition = "not_indexed"
                body_sha: str | None = None
                if document_id is not None:
                    body = row["body"]
                    encoded = body.encode()
                    total_text_bytes += len(encoded)
                    if total_text_bytes > MAX_GENERATION_TEXT_BYTES:
                        raise ValueError("index generation text bound exceeded")
                    body_sha = hashlib.sha256(encoded).hexdigest()
                    if row["body_sha256"] != body_sha or document_id != stable_id(
                        "document", row["version_id"], row["normalizer"], body_sha
                    ):
                        raise Conflict("normalized document identity changed")
                    disposition = "indexed"
                    document_count += 1
                    for ordinal, (start, end, text) in enumerate(deterministic_chunks(body)):
                        chunk_sha = hashlib.sha256(text.encode()).hexdigest()
                        generated_chunks.append(
                            {
                                "document_id": document_id,
                                "id": stable_id("chunk", document_id, str(ordinal), chunk_sha),
                                "ordinal": ordinal,
                                "start_offset": start,
                                "end_offset": end,
                                "text": text,
                                "sha256": chunk_sha,
                            }
                        )
                        if len(generated_chunks) > MAX_GENERATION_CHUNKS:
                            raise ValueError("index generation chunk bound exceeded")
                elif row["outcome"] == "extracted":
                    raise Conflict("completed extraction is missing its document")
                plan_items.append(
                    {
                        "item_id": row["item_id"],
                        "version_id": row["version_id"],
                        "outcome": row["outcome"],
                        "evidence_id": row["evidence_id"],
                        "document_id": document_id,
                        "body_sha256": body_sha,
                        "disposition": disposition,
                    }
                )
            plan_sha = _canonical_digest(
                {
                    "source_id": source_id,
                    "run_actor_id": str(run["actor_id"]),
                    "run_id": str(expected_run_id),
                    "observed_at": run["observed_at"].isoformat(),
                    "code_revision": code_revision,
                    "chunker_version": INDEX_CHUNKER_VERSION,
                    "items": plan_items,
                }
            )
            generation_id = stable_id(
                "index_generation",
                source_id,
                str(expected_run_id),
                INDEX_CHUNKER_VERSION,
                plan_sha,
            )
            existing = conn.execute(
                "SELECT g.run_id,g.item_count,g.document_count,g.chunk_count,g.plan_sha256,"
                "r.ready_at FROM brain_index_generations g "
                "LEFT JOIN brain_index_generation_receipts r ON r.generation_id=g.id "
                "WHERE g.id=%s",
                (generation_id,),
            ).fetchone()
            expected = {
                "run_id": expected_run_id,
                "item_count": len(rows),
                "document_count": document_count,
                "chunk_count": len(generated_chunks),
                "plan_sha256": plan_sha,
            }
            if existing:
                ready_at = existing.pop("ready_at")
                if ready_at is None or existing != expected:
                    raise Conflict("index generation identity changed")
                return IndexGeneration(
                    generation_id,
                    source_id,
                    expected_run_id,
                    len(rows),
                    document_count,
                    len(generated_chunks),
                    plan_sha,
                    ready_at,
                    False,
                )
            conn.execute(
                "INSERT INTO brain_index_generations(tenant_id,id,source_id,run_actor_id,"
                "run_id,observed_at,plan_sha256,code_revision,chunker_version,item_count,"
                "document_count,chunk_count) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    ctx.tenant_id,
                    generation_id,
                    source_id,
                    run["actor_id"],
                    expected_run_id,
                    run["observed_at"],
                    plan_sha,
                    code_revision,
                    INDEX_CHUNKER_VERSION,
                    len(rows),
                    document_count,
                    len(generated_chunks),
                ),
            )
            for item in plan_items:
                conn.execute(
                    "INSERT INTO brain_index_generation_items(tenant_id,generation_id,"
                    "source_id,item_id,version_id,outcome,disposition,evidence_id,document_id) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (
                        ctx.tenant_id,
                        generation_id,
                        source_id,
                        item["item_id"],
                        item["version_id"],
                        item["outcome"],
                        item["disposition"],
                        item["evidence_id"],
                        item["document_id"],
                    ),
                )
            for chunk in generated_chunks:
                conn.execute(
                    "INSERT INTO brain_index_generation_chunks(tenant_id,generation_id,"
                    "source_id,document_id,id,ordinal,start_offset,end_offset,text,sha256) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (
                        ctx.tenant_id,
                        generation_id,
                        source_id,
                        chunk["document_id"],
                        chunk["id"],
                        chunk["ordinal"],
                        chunk["start_offset"],
                        chunk["end_offset"],
                        chunk["text"],
                        chunk["sha256"],
                    ),
                )
            receipt = conn.execute(
                "INSERT INTO brain_index_generation_receipts(tenant_id,generation_id,source_id) "
                "VALUES (%s,%s,%s) RETURNING ready_at",
                (ctx.tenant_id, generation_id, source_id),
            ).fetchone()
            assert receipt is not None
            return IndexGeneration(
                generation_id,
                source_id,
                expected_run_id,
                len(rows),
                document_count,
                len(generated_chunks),
                plan_sha,
                receipt["ready_at"],
                True,
            )

    def activate_fileos_index_generation(
        self,
        ctx: TenantContext,
        source_id: str,
        generation_id: str,
        idempotency_key: UUID,
    ) -> IndexActivation:
        """Append an activation receipt; reactivating an older generation is rollback."""
        self.store.require(ctx, "brain.index.activate")
        if (
            not _IDENTITY.fullmatch(source_id)
            or not _IDENTITY.fullmatch(generation_id)
            or not isinstance(idempotency_key, UUID)
        ):
            raise ValueError("invalid index activation request")
        request_hash = _canonical_digest({"source_id": source_id, "generation_id": generation_id})
        with self.store.transaction(ctx) as conn:
            conn.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                (f"{ctx.tenant_id}:fileos-source:{source_id}",),
            )
            existing = conn.execute(
                "SELECT source_id,generation_id,previous_generation_id,request_hash,"
                "activated_at FROM brain_index_activations "
                "WHERE actor_id=%s AND idempotency_key=%s",
                (ctx.actor_id, idempotency_key),
            ).fetchone()
            if existing:
                if (
                    existing["request_hash"] != request_hash
                    or existing["source_id"] != source_id
                    or existing["generation_id"] != generation_id
                ):
                    raise Conflict("index activation key reused")
                return IndexActivation(
                    source_id,
                    generation_id,
                    existing["previous_generation_id"],
                    existing["activated_at"],
                    False,
                )
            ready = conn.execute(
                "SELECT 1 FROM brain_index_generation_receipts "
                "WHERE generation_id=%s AND source_id=%s",
                (generation_id, source_id),
            ).fetchone()
            if not ready:
                raise NotFound()
            previous = conn.execute(
                "SELECT generation_id FROM brain_index_activations WHERE source_id=%s "
                "ORDER BY activated_at DESC,idempotency_key DESC LIMIT 1",
                (source_id,),
            ).fetchone()
            previous_id = previous["generation_id"] if previous else None
            row = conn.execute(
                "INSERT INTO brain_index_activations(tenant_id,actor_id,idempotency_key,"
                "source_id,generation_id,previous_generation_id,request_hash) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING activated_at",
                (
                    ctx.tenant_id,
                    ctx.actor_id,
                    idempotency_key,
                    source_id,
                    generation_id,
                    previous_id,
                    request_hash,
                ),
            ).fetchone()
            assert row is not None
            return IndexActivation(source_id, generation_id, previous_id, row["activated_at"], True)

    def fileos_index_status(self, ctx: TenantContext, source_id: str) -> dict[str, Any]:
        """Return the active immutable index generation without exposing content."""
        self.store.require(ctx, "brain.changes.read")
        if not _IDENTITY.fullmatch(source_id):
            raise NotFound()
        with self.store.transaction(ctx) as conn:
            if not conn.execute(
                "SELECT 1 FROM brain_sources WHERE id=%s AND kind='fileos'", (source_id,)
            ).fetchone():
                raise NotFound()
            row = conn.execute(
                "SELECT a.generation_id,a.previous_generation_id,a.activated_at,g.run_id,"
                "g.observed_at,g.item_count,g.document_count,g.chunk_count,g.plan_sha256,"
                "g.chunker_version FROM brain_index_activations a "
                "JOIN brain_index_generations g ON g.id=a.generation_id "
                "WHERE a.source_id=%s ORDER BY a.activated_at DESC,a.idempotency_key DESC LIMIT 1",
                (source_id,),
            ).fetchone()
            self.store.audit(conn, ctx, "brain.fileos_index_status", "brain_source", source_id)
            return {
                "source_id": source_id,
                "status": "active" if row else "no_active_generation",
                "active_generation": row,
            }

    def search_fileos_active(
        self, ctx: TenantContext, source_id: str, query: str, *, limit: int = 10
    ) -> list[SearchHit]:
        """Search only the source's append-only active index generation."""
        self.store.require(ctx, "brain.search")
        if (
            not _IDENTITY.fullmatch(source_id)
            or not query.strip()
            or len(query) > 500
            or "\x00" in query
            or not 1 <= limit <= 50
        ):
            raise ValueError("invalid active FileOS search")
        with self.store.transaction(ctx) as conn:
            active = conn.execute(
                "SELECT generation_id FROM brain_index_activations WHERE source_id=%s "
                "ORDER BY activated_at DESC,idempotency_key DESC LIMIT 1",
                (source_id,),
            ).fetchone()
            if not active:
                raise NotFound()
            rows = conn.execute(
                "SELECT c.id AS chunk_id,c.document_id,i.evidence_id,i.source_id,si.locator,"
                "ts_headline('simple',c.text,plainto_tsquery('simple',%s),"
                "'MaxWords=35,MinWords=10') AS excerpt,"
                "ts_rank_cd(c.search_vector,plainto_tsquery('simple',%s)) AS rank "
                "FROM brain_index_generation_chunks c "
                "JOIN brain_index_generation_items i ON i.tenant_id=c.tenant_id "
                "AND i.generation_id=c.generation_id AND i.document_id=c.document_id "
                "JOIN brain_source_items si ON si.tenant_id=i.tenant_id "
                "AND si.source_id=i.source_id AND si.id=i.item_id "
                "WHERE c.generation_id=%s "
                "AND c.search_vector @@ plainto_tsquery('simple',%s) "
                "ORDER BY rank DESC,c.id LIMIT %s",
                (query, query, active["generation_id"], query, limit),
            ).fetchall()
            self.store.audit(conn, ctx, "brain.fileos_active_search", "brain_source", source_id)
            return [SearchHit(**row) for row in rows]

    def search_current_fileos(
        self, ctx: TenantContext, query: str, *, limit: int = 10
    ) -> list[SearchHit]:
        """Search the newest activated generation of every authorized FileOS source."""
        self.store.require(ctx, "brain.search")
        if not query.strip() or len(query) > 500 or "\x00" in query or not 1 <= limit <= 50:
            raise ValueError("invalid current FileOS search")
        with self.store.transaction(ctx) as conn:
            rows = conn.execute(
                "WITH active AS (SELECT DISTINCT ON (source_id) source_id,generation_id "
                "FROM brain_index_activations ORDER BY source_id,activated_at DESC,"
                "idempotency_key DESC) "
                "SELECT c.id AS chunk_id,c.document_id,i.evidence_id,i.source_id,si.locator,"
                "ts_headline('simple',c.text,plainto_tsquery('simple',%s),"
                "'MaxWords=35,MinWords=10') AS excerpt,"
                "ts_rank_cd(c.search_vector,plainto_tsquery('simple',%s)) AS rank "
                "FROM active a JOIN brain_index_generation_chunks c "
                "ON c.source_id=a.source_id AND c.generation_id=a.generation_id "
                "JOIN brain_index_generation_items i ON i.tenant_id=c.tenant_id "
                "AND i.generation_id=c.generation_id AND i.document_id=c.document_id "
                "JOIN brain_source_items si ON si.tenant_id=i.tenant_id "
                "AND si.source_id=i.source_id AND si.id=i.item_id "
                "WHERE c.search_vector @@ plainto_tsquery('simple',%s) "
                "ORDER BY rank DESC,c.id LIMIT %s",
                (query, query, query, limit),
            ).fetchall()
            self.store.audit(
                conn, ctx, "brain.current_fileos_search", "brain_index", "fileos_active"
            )
            return [SearchHit(**row) for row in rows]

    def search_current_email(
        self, ctx: TenantContext, query: str, *, limit: int = 10
    ) -> list[SearchHit]:
        """Search explicitly bridged Email evidence still current in both layers."""
        self.store.require(ctx, "brain.search")
        if not query.strip() or len(query) > 500 or "\x00" in query or not 1 <= limit <= 50:
            raise ValueError("invalid current Email search")
        with self.store.transaction(ctx) as conn:
            rows = conn.execute(
                "SELECT c.id AS chunk_id,c.document_id,e.id AS evidence_id,v.source_id,"
                "i.locator,ts_headline('simple',c.text,plainto_tsquery('simple',%s),"
                "'MaxWords=35,MinWords=10') AS excerpt,"
                "ts_rank_cd(c.search_vector,plainto_tsquery('simple',%s)) AS rank "
                "FROM brain_chunks c JOIN brain_normalized_documents d "
                "ON d.tenant_id=c.tenant_id AND d.id=c.document_id "
                "JOIN brain_evidence e ON e.tenant_id=d.tenant_id AND e.id=d.evidence_id "
                "JOIN brain_source_versions v ON v.tenant_id=e.tenant_id "
                "AND v.id=e.source_version_id JOIN brain_source_items i "
                "ON i.tenant_id=v.tenant_id AND i.id=v.item_id "
                "AND i.current_version_id=v.id JOIN brain_sources s "
                "ON s.tenant_id=v.tenant_id AND s.id=v.source_id AND s.kind='email' "
                "JOIN brain_email_bridge_receipts b ON b.tenant_id=v.tenant_id "
                "AND b.version_id=v.id AND b.evidence_id=e.id AND b.document_id=d.id "
                "JOIN message_versions mv ON mv.tenant_id=b.tenant_id "
                "AND mv.account_id=b.account_id AND mv.id=b.legacy_version_id "
                "JOIN messages m ON m.tenant_id=mv.tenant_id AND m.account_id=mv.account_id "
                "AND m.id=mv.message_id AND m.raw_sha256=mv.raw_sha256 "
                "AND m.parser_version=mv.parser_version "
                "WHERE NOT m.deleted AND NOT m.quarantined "
                "AND c.search_vector @@ plainto_tsquery('simple',%s) "
                "ORDER BY rank DESC,c.id LIMIT %s",
                (query, query, query, limit),
            ).fetchall()
            self.store.audit(
                conn, ctx, "brain.current_email_search", "brain_index", "email_bridged"
            )
            return [SearchHit(**row) for row in rows]

    def search_current_archive_members(
        self, ctx: TenantContext, query: str, *, limit: int = 10
    ) -> list[SearchHit]:
        """Search explicit archive text derivatives whose parent archive is current."""
        self.store.require(ctx, "brain.search")
        if not query.strip() or len(query) > 500 or "\x00" in query or not 1 <= limit <= 20:
            raise ValueError("invalid current archive-member search")
        with self.store.transaction(ctx) as conn:
            rows = conn.execute(
                "SELECT c.id AS chunk_id,c.document_id,e.id AS evidence_id,v.source_id,"
                "i.locator,ts_headline('simple',c.text,plainto_tsquery('simple',%s),"
                "'MaxWords=35,MinWords=10') AS excerpt,"
                "ts_rank_cd(c.search_vector,plainto_tsquery('simple',%s)) AS rank "
                "FROM brain_chunks c JOIN brain_normalized_documents d ON "
                "d.tenant_id=c.tenant_id AND d.id=c.document_id "
                "JOIN brain_evidence e ON e.tenant_id=d.tenant_id AND e.id=d.evidence_id "
                "JOIN brain_source_versions v ON v.tenant_id=e.tenant_id "
                "AND v.id=e.source_version_id JOIN brain_source_items i ON "
                "i.tenant_id=v.tenant_id AND i.source_id=v.source_id AND i.id=v.item_id "
                "AND i.current_version_id=v.id WHERE EXISTS (SELECT 1 FROM "
                "brain_archive_member_text_receipts r JOIN brain_archive_inventories a ON "
                "a.tenant_id=r.tenant_id AND a.id=r.inventory_id "
                "JOIN brain_archive_members m ON m.tenant_id=a.tenant_id "
                "AND m.inventory_id=a.id AND m.locator=r.member_locator "
                "JOIN brain_source_items p ON p.tenant_id=a.tenant_id "
                "AND p.source_id=a.source_id AND p.id=a.item_id "
                "AND p.current_version_id=a.source_version_id "
                "JOIN brain_evidence pe ON pe.tenant_id=a.tenant_id "
                "AND pe.id=r.parent_evidence_id AND pe.source_version_id=a.source_version_id "
                "WHERE r.tenant_id=d.tenant_id AND r.document_id=d.id "
                "AND r.evidence_id=e.id AND r.source_id=v.source_id "
                "AND r.item_id=v.item_id AND r.version_id=v.id "
                "AND r.parent_source_version_id=a.source_version_id "
                "AND a.source_id=r.source_id AND NOT m.is_container "
                "AND v.sha256=m.sha256 AND v.size_bytes=m.observed_size "
                "AND v.media_type=m.media_hint) AND "
                "c.search_vector @@ plainto_tsquery('simple',%s) "
                "ORDER BY rank DESC,c.id LIMIT %s",
                (query, query, query, limit),
            ).fetchall()
            self.store.audit(
                conn,
                ctx,
                "brain.current_archive_member_search",
                "brain_index",
                "archive_member_derivatives",
            )
            return [SearchHit(**row) for row in rows]

    def search_current_archive_documents(
        self, ctx: TenantContext, query: str, *, limit: int = 10
    ) -> list[SearchHit]:
        """Search archive documents whose exact parent/member receipt is current."""
        self.store.require(ctx, "brain.search")
        if not query.strip() or len(query) > 500 or "\x00" in query or not 1 <= limit <= 20:
            raise ValueError("invalid current archive-document search")
        with self.store.transaction(ctx) as conn:
            rows = conn.execute(
                "SELECT c.id AS chunk_id,c.document_id,e.id AS evidence_id,v.source_id,"
                "i.locator,ts_headline('simple',c.text,plainto_tsquery('simple',%s),"
                "'MaxWords=35,MinWords=10') AS excerpt,"
                "ts_rank_cd(c.search_vector,plainto_tsquery('simple',%s)) AS rank "
                "FROM brain_chunks c JOIN brain_normalized_documents d ON "
                "d.tenant_id=c.tenant_id AND d.id=c.document_id "
                "JOIN brain_evidence e ON e.tenant_id=d.tenant_id AND e.id=d.evidence_id "
                "JOIN brain_source_versions v ON v.tenant_id=e.tenant_id "
                "AND v.id=e.source_version_id JOIN brain_source_items i ON "
                "i.tenant_id=v.tenant_id AND i.source_id=v.source_id AND i.id=v.item_id "
                "AND i.current_version_id=v.id WHERE EXISTS (SELECT 1 FROM "
                "brain_archive_member_document_receipts r "
                "JOIN brain_archive_inventories a ON "
                "a.tenant_id=r.tenant_id AND a.id=r.inventory_id "
                "JOIN brain_archive_members m ON m.tenant_id=a.tenant_id "
                "AND m.inventory_id=a.id AND m.locator=r.member_locator "
                "JOIN brain_source_items p ON p.tenant_id=a.tenant_id "
                "AND p.source_id=a.source_id AND p.id=a.item_id "
                "AND p.current_version_id=a.source_version_id "
                "JOIN brain_evidence pe ON pe.tenant_id=a.tenant_id "
                "AND pe.id=r.parent_evidence_id AND pe.source_version_id=a.source_version_id "
                "WHERE r.tenant_id=d.tenant_id AND r.document_id=d.id "
                "AND r.evidence_id=e.id AND r.source_id=v.source_id "
                "AND r.item_id=v.item_id AND r.version_id=v.id "
                "AND r.parent_source_version_id=a.source_version_id "
                "AND a.source_id=r.source_id "
                "AND v.sha256=m.sha256 AND v.size_bytes=m.observed_size "
                "AND v.media_type=m.media_hint AND ("
                "(r.document_format='pdf' AND NOT m.is_container "
                "AND lower(right(m.locator,4))='.pdf' "
                "AND m.media_hint='application/pdf') OR "
                "(r.document_format='docx' AND m.is_container "
                "AND lower(right(m.locator,5))='.docx' AND m.media_hint="
                "'application/vnd.openxmlformats-officedocument.wordprocessingml.document') OR "
                "(r.document_format='xlsx' AND m.is_container "
                "AND lower(right(m.locator,5))='.xlsx' AND m.media_hint="
                "'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'))) AND "
                "c.search_vector @@ plainto_tsquery('simple',%s) "
                "ORDER BY rank DESC,c.id LIMIT %s",
                (query, query, query, limit),
            ).fetchall()
            self.store.audit(
                conn,
                ctx,
                "brain.current_archive_document_search",
                "brain_index",
                "archive_document_derivatives",
            )
            return [SearchHit(**row) for row in rows]

    def search_current_archive_images(
        self, ctx: TenantContext, query: str, *, limit: int = 10
    ) -> list[SearchHit]:
        """Search OCR only while its exact archive parent and member are current."""
        self.store.require(ctx, "brain.search")
        if not query.strip() or len(query) > 500 or "\x00" in query or not 1 <= limit <= 20:
            raise ValueError("invalid current archive-image search")
        with self.store.transaction(ctx) as conn:
            rows = conn.execute(
                "SELECT c.id AS chunk_id,c.document_id,e.id AS evidence_id,v.source_id,"
                "i.locator,ts_headline('simple',c.text,plainto_tsquery('simple',%s),"
                "'MaxWords=35,MinWords=10') AS excerpt,"
                "ts_rank_cd(c.search_vector,plainto_tsquery('simple',%s)) AS rank "
                "FROM brain_chunks c JOIN brain_normalized_documents d ON "
                "d.tenant_id=c.tenant_id AND d.id=c.document_id "
                "JOIN brain_evidence e ON e.tenant_id=d.tenant_id AND e.id=d.evidence_id "
                "JOIN brain_source_versions v ON v.tenant_id=e.tenant_id "
                "AND v.id=e.source_version_id JOIN brain_source_items i ON "
                "i.tenant_id=v.tenant_id AND i.source_id=v.source_id AND i.id=v.item_id "
                "AND i.current_version_id=v.id WHERE EXISTS (SELECT 1 FROM "
                "brain_archive_member_image_receipts r "
                "JOIN brain_archive_inventories a ON "
                "a.tenant_id=r.tenant_id AND a.id=r.inventory_id "
                "JOIN brain_archive_members m ON m.tenant_id=a.tenant_id "
                "AND m.inventory_id=a.id AND m.locator=r.member_locator "
                "JOIN brain_source_items p ON p.tenant_id=a.tenant_id "
                "AND p.source_id=a.source_id AND p.id=a.item_id "
                "AND p.current_version_id=a.source_version_id "
                "JOIN brain_evidence pe ON pe.tenant_id=a.tenant_id "
                "AND pe.id=r.parent_evidence_id AND pe.source_version_id=a.source_version_id "
                "WHERE r.tenant_id=d.tenant_id AND r.document_id=d.id "
                "AND r.evidence_id=e.id AND r.source_id=v.source_id "
                "AND r.item_id=v.item_id AND r.version_id=v.id "
                "AND r.parent_source_version_id=a.source_version_id "
                "AND a.source_id=r.source_id AND NOT m.is_container "
                "AND v.sha256=m.sha256 AND v.size_bytes=m.observed_size "
                "AND v.media_type=m.media_hint "
                "AND m.media_hint='application/octet-stream' "
                "AND r.detected_format=r.image_format AND ("
                "(r.image_format='jpeg' AND (right(lower(m.locator),4)='.jpg' "
                "OR right(lower(m.locator),5)='.jpeg')) OR "
                "(r.image_format='png' AND right(lower(m.locator),4)='.png') OR "
                "(r.image_format='tiff' AND (right(lower(m.locator),4)='.tif' "
                "OR right(lower(m.locator),5)='.tiff')) OR "
                "(r.image_format='bmp' AND right(lower(m.locator),4)='.bmp') OR "
                "(r.image_format='gif' AND right(lower(m.locator),4)='.gif') OR "
                "(r.image_format='webp' AND right(lower(m.locator),5)='.webp'))) "
                "AND c.search_vector @@ plainto_tsquery('simple',%s) "
                "ORDER BY rank DESC,c.id LIMIT %s",
                (query, query, query, limit),
            ).fetchall()
            self.store.audit(
                conn,
                ctx,
                "brain.current_archive_image_search",
                "brain_index",
                "archive_image_derivatives",
            )
            return [SearchHit(**row) for row in rows]

    def search_current_email_family(
        self,
        ctx: TenantContext,
        query: str,
        *,
        message_limit: int = 10,
        attachment_limit: int = 10,
        document_limit: int = 10,
    ) -> EmailFamilySearch:
        """Search current bridged Email representations with independent ranks."""
        self.store.require(ctx, "brain.search")
        limits = (message_limit, attachment_limit, document_limit)
        if (
            not query.strip()
            or len(query) > 500
            or "\x00" in query
            or any(not 1 <= limit <= 25 for limit in limits)
        ):
            raise ValueError("invalid current Email family search")
        with self.store.transaction(ctx) as conn:
            rows = conn.execute(
                "WITH current_parents AS ("
                "SELECT eb.tenant_id,eb.account_id,eb.legacy_version_id,eb.source_id,"
                "eb.item_id,eb.version_id,eb.evidence_id,eb.document_id,pi.locator "
                "FROM brain_email_bridge_receipts eb JOIN message_versions mv ON "
                "mv.tenant_id=eb.tenant_id AND mv.account_id=eb.account_id "
                "AND mv.id=eb.legacy_version_id JOIN messages m ON "
                "m.tenant_id=mv.tenant_id AND m.account_id=mv.account_id "
                "AND m.id=mv.message_id AND m.raw_sha256=mv.raw_sha256 "
                "AND m.parser_version=mv.parser_version JOIN brain_source_items pi ON "
                "pi.tenant_id=eb.tenant_id AND pi.id=eb.item_id "
                "AND pi.current_version_id=eb.version_id "
                "WHERE NOT m.deleted AND NOT m.quarantined), family AS ("
                "SELECT 'message'::text AS result_kind,c.id AS chunk_id,c.document_id,"
                "p.evidence_id,p.source_id,p.locator,c.text,c.search_vector "
                "FROM current_parents p JOIN brain_normalized_documents d ON "
                "d.tenant_id=p.tenant_id AND d.id=p.document_id "
                "JOIN brain_chunks c ON c.tenant_id=d.tenant_id AND c.document_id=d.id "
                "UNION ALL SELECT 'attachment',c.id,c.document_id,ab.evidence_id,"
                "ab.source_id,ai.locator,c.text,c.search_vector FROM current_parents p "
                "JOIN brain_email_attachment_bridge_receipts ab ON "
                "ab.tenant_id=p.tenant_id AND ab.parent_evidence_id=p.evidence_id "
                "JOIN brain_source_items ai ON ai.tenant_id=ab.tenant_id "
                "AND ai.id=ab.item_id AND ai.current_version_id=ab.version_id "
                "JOIN brain_normalized_documents d ON d.tenant_id=ab.tenant_id "
                "AND d.id=ab.document_id JOIN brain_chunks c ON c.tenant_id=d.tenant_id "
                "AND c.document_id=d.id UNION ALL SELECT 'document',c.id,c.document_id,"
                "db.evidence_id,db.source_id,ai.locator,c.text,c.search_vector "
                "FROM current_parents p JOIN brain_email_attachment_bridge_receipts ab "
                "ON ab.tenant_id=p.tenant_id AND ab.parent_evidence_id=p.evidence_id "
                "JOIN brain_email_document_bridge_receipts db ON db.tenant_id=ab.tenant_id "
                "AND db.legacy_attachment_id=ab.legacy_attachment_id "
                "AND db.source_id=ab.source_id AND db.item_id=ab.item_id "
                "AND db.version_id=ab.version_id AND db.evidence_id=ab.evidence_id "
                "JOIN brain_source_items ai ON ai.tenant_id=db.tenant_id "
                "AND ai.id=db.item_id AND ai.current_version_id=db.version_id "
                "JOIN brain_normalized_documents d ON d.tenant_id=db.tenant_id "
                "AND d.id=db.document_id JOIN brain_chunks c ON c.tenant_id=d.tenant_id "
                "AND c.document_id=d.id), matches AS (SELECT result_kind,chunk_id,"
                "document_id,evidence_id,source_id,locator,"
                "ts_headline('simple',text,plainto_tsquery('simple',%s),"
                "'MaxWords=35,MinWords=10') AS excerpt,"
                "ts_rank_cd(search_vector,plainto_tsquery('simple',%s)) AS rank "
                "FROM family WHERE search_vector @@ plainto_tsquery('simple',%s)), "
                "ranked AS (SELECT *,row_number() OVER (PARTITION BY result_kind "
                "ORDER BY rank DESC,chunk_id) AS result_ordinal FROM matches) "
                "SELECT result_kind,chunk_id,document_id,evidence_id,source_id,locator,"
                "excerpt,rank FROM ranked WHERE "
                "(result_kind='message' AND result_ordinal<=%s) OR "
                "(result_kind='attachment' AND result_ordinal<=%s) OR "
                "(result_kind='document' AND result_ordinal<=%s) "
                "ORDER BY CASE result_kind WHEN 'message' THEN 1 WHEN 'attachment' THEN 2 "
                "ELSE 3 END,rank DESC,chunk_id",
                (query, query, query, message_limit, attachment_limit, document_limit),
            ).fetchall()
            self.store.audit(
                conn, ctx, "brain.current_email_family_search", "brain_index", "email_family"
            )
        buckets: dict[str, list[SearchHit]] = {
            "message": [],
            "attachment": [],
            "document": [],
        }
        for row in rows:
            kind = row.pop("result_kind")
            buckets[kind].append(SearchHit(**row))
        return EmailFamilySearch(
            tuple(buckets["message"]),
            tuple(buckets["attachment"]),
            tuple(buckets["document"]),
        )

    def publish_text(
        self,
        ctx: TenantContext,
        source_version_id: str,
        text: str,
        *,
        code_revision: str,
        normalizer: str = NORMALIZER_VERSION,
    ) -> PublishedDocument:
        self.store.require(ctx, "brain.document.publish")
        if not text or "\x00" in text or len(text.encode()) > MAX_NORMALIZED_BYTES:
            raise ValueError("normalized text is empty or exceeds its safe bound")
        for descriptor in (normalizer, code_revision):
            if not descriptor or len(descriptor) > 200 or "\x00" in descriptor:
                raise ValueError("invalid publication descriptor")
        body_sha = hashlib.sha256(text.encode()).hexdigest()
        document_id = stable_id("document", source_version_id, normalizer, body_sha)
        evidence_id = stable_id("evidence", source_version_id)
        with self.store.transaction(ctx) as conn:
            conn.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                (f"{ctx.tenant_id}:publish:{document_id}",),
            )
            version = conn.execute(
                "SELECT source_id,item_id FROM brain_source_versions WHERE id=%s",
                (source_version_id,),
            ).fetchone()
            if not version:
                raise NotFound()
            existing = conn.execute(
                "SELECT id FROM brain_normalized_documents WHERE id=%s", (document_id,)
            ).fetchone()
            if existing:
                count = conn.execute(
                    "SELECT count(*) AS n FROM brain_chunks WHERE document_id=%s", (document_id,)
                ).fetchone()
                assert count is not None
                return PublishedDocument(document_id, evidence_id, count["n"], False)
            conn.execute(
                "INSERT INTO brain_normalized_documents(tenant_id,id,evidence_id,normalizer,"
                "body_sha256,body) VALUES (%s,%s,%s,%s,%s,%s)",
                (ctx.tenant_id, document_id, evidence_id, normalizer, body_sha, text),
            )
            chunks = list(deterministic_chunks(text))
            for ordinal, (start, end, chunk) in enumerate(chunks):
                chunk_sha = hashlib.sha256(chunk.encode()).hexdigest()
                chunk_id = stable_id("chunk", document_id, str(ordinal), chunk_sha)
                conn.execute(
                    "INSERT INTO brain_chunks(tenant_id,id,document_id,ordinal,start_offset,"
                    "end_offset,"
                    "text,sha256) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                    (ctx.tenant_id, chunk_id, document_id, ordinal, start, end, chunk, chunk_sha),
                )
            config_sha = _canonical_digest({"chunk_characters": CHUNK_CHARACTERS})
            provenance_id = stable_id("provenance", document_id, code_revision, config_sha)
            conn.execute(
                "INSERT INTO brain_provenance(tenant_id,id,output_id,transform,transform_version,"
                "code_revision,configuration_sha256,created_at) "
                "VALUES (%s,%s,%s,'normalize_text',%s,%s,%s,clock_timestamp())",
                (
                    ctx.tenant_id,
                    provenance_id,
                    document_id,
                    normalizer,
                    code_revision,
                    config_sha,
                ),
            )
            conn.execute(
                "INSERT INTO brain_provenance_inputs(tenant_id,provenance_id,input_id,ordinal) "
                "VALUES (%s,%s,%s,0)",
                (ctx.tenant_id, provenance_id, evidence_id),
            )
            change_id = stable_id("change", "document_published", document_id)
            conn.execute(
                "INSERT INTO brain_change_events(tenant_id,id,source_id,item_id,version_id,kind) "
                "VALUES (%s,%s,%s,%s,%s,'document_published')",
                (
                    ctx.tenant_id,
                    change_id,
                    version["source_id"],
                    version["item_id"],
                    source_version_id,
                ),
            )
            return PublishedDocument(document_id, evidence_id, len(chunks), True)

    def search(self, ctx: TenantContext, query: str, *, limit: int = 10) -> list[SearchHit]:
        self.store.require(ctx, "brain.search")
        if not query.strip() or len(query) > 500 or not 1 <= limit <= 50 or "\x00" in query:
            raise ValueError("invalid search request")
        with self.store.transaction(ctx) as conn:
            rows = conn.execute(
                "SELECT c.id AS chunk_id,c.document_id,d.evidence_id,v.source_id,i.locator,"
                "ts_headline('simple',c.text,plainto_tsquery('simple',%s),"
                "'MaxWords=35,MinWords=10') AS excerpt,"
                "ts_rank_cd(c.search_vector,plainto_tsquery('simple',%s)) AS rank "
                "FROM brain_chunks c JOIN brain_normalized_documents d ON "
                "d.tenant_id=c.tenant_id AND d.id=c.document_id "
                "JOIN brain_evidence e ON e.tenant_id=d.tenant_id AND e.id=d.evidence_id "
                "JOIN brain_source_versions v ON v.tenant_id=e.tenant_id "
                "AND v.id=e.source_version_id JOIN brain_source_items i ON "
                "i.tenant_id=v.tenant_id AND i.id=v.item_id "
                "WHERE c.search_vector @@ plainto_tsquery('simple',%s) "
                "ORDER BY rank DESC,c.id LIMIT %s",
                (query, query, query, limit),
            ).fetchall()
            self.store.audit(conn, ctx, "brain.search", "query")
        return [SearchHit(**row) for row in rows]

    def evidence(self, ctx: TenantContext, evidence_id: str) -> dict[str, Any]:
        self.store.require(ctx, "brain.evidence.read")
        if not _IDENTITY.fullmatch(evidence_id):
            raise NotFound()
        with self.store.transaction(ctx) as conn:
            row = conn.execute(
                "SELECT e.id,e.sha256,e.storage,e.retained,e.created_at,"
                "v.id AS source_version_id,v.observed_at,v.size_bytes,v.media_type,"
                "v.source_id,i.id AS source_item_id,i.locator,s.kind AS source_kind,"
                "d.id AS document_id,d.normalizer,d.created_at AS indexed_at,"
                "(SELECT count(*) FROM brain_chunks c WHERE c.tenant_id=e.tenant_id "
                "AND c.document_id=d.id) AS chunk_count "
                "FROM brain_evidence e JOIN brain_source_versions v ON "
                "v.tenant_id=e.tenant_id AND v.id=e.source_version_id "
                "JOIN brain_source_items i ON i.tenant_id=v.tenant_id AND i.id=v.item_id "
                "JOIN brain_sources s ON s.tenant_id=v.tenant_id AND s.id=v.source_id "
                "LEFT JOIN LATERAL (SELECT nd.id,nd.normalizer,nd.created_at "
                "FROM brain_normalized_documents nd WHERE nd.tenant_id=e.tenant_id "
                "AND nd.evidence_id=e.id ORDER BY nd.created_at DESC,nd.id DESC LIMIT 1) d "
                "ON true WHERE e.id=%s",
                (evidence_id,),
            ).fetchone()
            if not row:
                raise NotFound()
            self.store.audit(conn, ctx, "brain.evidence_read", "brain_evidence", evidence_id)
            return {**row, "original_content_available": False, "untrusted_content": True}

    def evidence_content(
        self, ctx: TenantContext, evidence_id: str, *, max_chars: int = 4000
    ) -> dict[str, Any]:
        self.store.require(ctx, "brain.content.read")
        if not _IDENTITY.fullmatch(evidence_id) or not 1 <= max_chars <= 16_000:
            raise ValueError("invalid evidence content request")
        with self.store.transaction(ctx) as conn:
            row = conn.execute(
                "SELECT d.id AS document_id,d.body,d.body_sha256,d.normalizer,d.created_at "
                "FROM brain_normalized_documents d WHERE d.evidence_id=%s "
                "ORDER BY d.created_at DESC,d.id DESC LIMIT 1",
                (evidence_id,),
            ).fetchone()
            if not row:
                raise NotFound()
            body = row.pop("body")
            self.store.audit(conn, ctx, "brain.content_read", "brain_evidence", evidence_id)
            return {
                **row,
                "evidence_id": evidence_id,
                "content": body[:max_chars],
                "truncated": len(body) > max_chars,
                "returned_chars": min(len(body), max_chars),
                "untrusted_content": True,
            }

    def changes(
        self,
        ctx: TenantContext,
        *,
        after: str | None = None,
        limit: int = 25,
    ) -> dict[str, Any]:
        self.store.require(ctx, "brain.changes.read")
        if after is not None and not _IDENTITY.fullmatch(after):
            raise NotFound()
        if not 1 <= limit <= 50:
            raise ValueError("invalid change limit")
        with self.store.transaction(ctx) as conn:
            anchor = None
            if after is not None:
                anchor = conn.execute(
                    "SELECT recorded_at,id FROM brain_change_events WHERE id=%s", (after,)
                ).fetchone()
                if not anchor:
                    raise NotFound()
            rows = conn.execute(
                "SELECT id,source_id,item_id,version_id,kind,recorded_at "
                "FROM brain_change_events WHERE (%s::timestamptz IS NULL OR "
                "(recorded_at,id)>(%s,%s)) ORDER BY recorded_at,id LIMIT %s",
                (
                    anchor["recorded_at"] if anchor else None,
                    anchor["recorded_at"] if anchor else None,
                    after,
                    limit + 1,
                ),
            ).fetchall()
            self.store.audit(conn, ctx, "brain.changes_read", "change_feed")
        page = rows[:limit]
        return {
            "results": page,
            "next_cursor": page[-1]["id"] if len(rows) > limit and page else None,
            "limit": limit,
        }
