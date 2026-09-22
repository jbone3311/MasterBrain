# ADR-065 — Additive Email attachment-occurrence bridge

Status: accepted for implementation; hosted verification pending.

## Context

Email attachment receipts are immutable occurrences tied to one parser-versioned
message evidence record. Duplicate hashes link occurrences but do not collapse them.
Receipts already account for extracted, failed, skipped, deferred and pending states;
approved PDF extraction revisions are a separate immutable workflow. DataCore needs a
shared part/evidence representation without re-parsing MIME, copying unsafe bytes or
mistaking a content duplicate for the same occurrence.

## Decision

Add a one-occurrence-at-a-time bridge for an existing attachment receipt whose parent
message has already passed the ADR-062 Email bridge and remains current and visible.
The operation requires the existing exact shared ingest and document-publication
scopes, an explicit attachment UUID, idempotency UUID and code revision.

Every accepted receipt creates deterministic opaque child source-item/version/evidence
identities and a `brain_parts` row linking the parent shared message evidence to the
child attachment evidence. Occurrence identity derives from the receipt UUID, not the
content hash. The child version carries bounded MIME part metadata and the receipt's
status/reason. Its evidence is `source_bound` and not claimed retained because bytes
remain embedded in the retained parent MIME rather than copied into a separate object.

For `attachment_receipts.status='extracted'` with non-empty text, the bridge publishes
the existing bounded `extracted_text` through `email-attachment-text-v1`, deterministic
chunks and explicit provenance. Empty extracted receipts and failed, skipped, deferred
or pending receipts publish accounting and evidence identity with zero documents/chunks.
The bridge never executes, decodes, extracts, scans or downloads attachment bytes.

An append-only receipt binds the legacy attachment UUID, parent legacy/shared evidence,
all child identities, outcome, code revision and request digest. A later approved PDF
or other isolated extraction is a distinct derivative bridge keyed by its immutable
extraction revision; it does not rewrite this occurrence receipt.

## Safety and compatibility

The parent/current Email account advisory lock prevents an update or deletion race.
The bridge rejects unbridged, historical, deleted, quarantined or inconsistent parent
messages. Existing Email attachment/document search and citations remain authoritative.
No automatic enumeration, batch, provider access, MIME parsing, original-content API,
dedupe deletion or search cutover is introduced.

`brain_parts` and bridge receipts use forced tenant RLS and append-only triggers.
Runtime roles receive only required select/insert grants. Filenames and part paths are
stored as bounded untrusted metadata and are not returned by the compact bridge result.

## Acceptance and rollback

Synthetic PostgreSQL tests must prove occurrence preservation for duplicate hashes,
searchable extracted text, zero-document deferred accounting, exact replay, current-
parent fencing, transaction rollback, tenant isolation and immutability. All existing
Email/FileOS suites and populated restore must remain green. Rollback stops bridge
invocation; immutable shared rows remain auditable and existing Email behavior is
unchanged.
