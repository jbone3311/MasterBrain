# ADR-066 — Approved Email document-extraction derivative bridge

Status: accepted for implementation; hosted verification pending.

## Context

ADR-065 gives each legacy attachment occurrence its own shared source item, version,
evidence and part identity without reading attachment bytes. The existing approved PDF
channel separately records immutable `document_extractions` only after a bounded,
source-fenced job reaches completed `result_saved` state. Its extracted or partial page
text is useful to MasterBrain, but is a derivative of the attachment occurrence rather
than a new source occurrence.

## Decision

Add a one-extraction-at-a-time bridge for an explicitly selected immutable legacy
document-extraction UUID. The operation requires the existing exact shared ingest and
document-publication scopes, an idempotency UUID and code revision. It succeeds only
when the extraction has at least one completed approval job, its ADR-065 attachment
occurrence is bridged and current, and the parent Email remains current and visible.

Publish the extraction's already-bounded non-empty text as a second normalized document
on the existing attachment evidence. The normalizer identity includes the legacy PDF
processor and policy versions, so a later approved processor result cannot overwrite an
earlier derivative. Deterministic chunks, a result digest and provenance retain the
processor, policy, extraction revision and bridge revision. The operation never loads,
copies, parses, scans or executes attachment bytes.

An append-only receipt binds the legacy extraction and one immutable completed approval
job to the shared source/version/evidence/document identities, exact processor and
policy, chunk count, result digest, bridge code revision and request digest. Exact replay
is a no-op; reuse with different provenance fails closed.

## Safety and compatibility

The Email account advisory lock and shared/legacy current-version checks prevent races
with ingestion, deletion or quarantine. Tenant-scoped foreign keys, forced RLS and
append-only triggers apply to the receipt. Runtime roles receive only select/insert on
the new table. Existing approved-PDF search, citations, approval jobs, attachment bridge
receipt and attachment status remain unchanged and authoritative.

No batch enumeration, automatic approval, new file format, scanner claim, provider
access, original-content API, global ranking or search cutover is introduced. A partial
legacy extraction remains explicitly partial in the receipt and provenance even though
its available non-empty pages are searchable.

## Acceptance and rollback

Synthetic PostgreSQL tests must prove approved extracted and partial publication, exact
replay, unapproved-extraction refusal, prerequisite occurrence/current-parent fencing,
transaction rollback, tenant isolation and immutability. Existing Email/FileOS suites,
restricted containers and populated restore must remain green. Rollback stops derivative
bridge invocation; immutable shared documents and receipts remain auditable, while all
legacy behavior is unchanged.
