# ADR-048 — Shared DataCore persistence and lexical index

Status: accepted for the additive prototype tranche on 2026-09-22.

## Decision

MasterBrain adds tenant-isolated `brain_*` PostgreSQL tables for sources, stable
source items and immutable versions, evidence references, normalized documents,
deterministic chunks, provenance, changes and import receipts. FileOS snapshot
manifests enter through a dedicated DataCore repository using the existing verified
owner context and least-privileged runtime role. Existing EmailBrain tables and
behavior are untouched.

Snapshot import is bounded, validated before publication, idempotent per actor and
key, serialized per source and atomic. A changed hash creates a new immutable version;
an unchanged replay does not. File evidence is source-bound in this tranche: the
database stores hashes and locators, never file bytes. Normalized text publication is
a distinct scoped operation and records immutable provenance before PostgreSQL lexical
indexing. Search returns compact excerpts with evidence identities.

## Security and failure boundaries

- Forced row-level security applies to every new table.
- Runtime roles receive explicit table grants only; immutable records reject update
  and delete even for ordinary runtime callers.
- Locators are relative, NUL-free and cannot contain parent traversal. Metadata is
  scalar and size-bounded; manifests, item counts and text bytes are bounded.
- A manifest is validated completely before its transaction. Any identity/content
  contradiction rolls back the whole import.
- Concurrent imports lock a tenant/source pair and cannot fork current state.
- No source writes, FileOS cutover, file deletion, OCR, remote inference or Email
  schema migration is authorized by this decision.

## Verification and rollback

Unit tests cover validation and deterministic chunking. PostgreSQL tests cover replay,
drift, concurrency, rollback, RLS, immutable evidence, lexical retrieval and grants.
The synthetic logical restore hashes every public table, so these records are included
in backup/restore parity automatically. Rollback is to stop using the additive path;
retained records are not destructively down-migrated.
