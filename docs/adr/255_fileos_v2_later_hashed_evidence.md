# ADR-255 — Prepare source-bound evidence for exact later FileOS v2 hashes

Status: accepted for synthetic/disposable, private, nonpublishing implementation.

## Context

ADR-254 seals every row of one later donor-policy observation but does not
prepare bytes or a DataCore source version. A later processing run needs
stable, policy-scoped evidence for each hashed row, including files that did
not exist at the completed baseline. Copying a packet hash without checking
the physical root again would allow stale evidence to be treated as current.

## Decision

1. Extract the baseline preparer's existing source-item/version/evidence
   insertion into one shared private helper. It derives a version from the
   donor candidate version and exact policy digest, verifies existing rows
   before reuse, and records `storage=source_bound, retained=false`. It never
   updates `brain_source_items.current_version_id`.
2. A worker with `brain.fileos.transition.prepare`, `brain.source.ingest`
   and `brain.changes.read` may prepare one exact ADR-254 closure. Under the
   source lock, revalidate its packet and completed baseline, physical root,
   latest v1 basis and policy; perform a fresh no-follow donor scan. Every
   normalized row must equal the sealed observation, with zero scan errors.
   Reject drift before inserting evidence. Only hashed rows get shared
   DataCore source versions/evidence; deferred, excluded and error rows do
   not invent bytes or versions.
3. Migration 0089 records an immutable preparation header and exact hashed
   row mapping. Composite FKs bind the packet and closure; a deferred SQL
   closure check requires one prepared row per sealed hash and verifies each
   DataCore version/evidence identity. Tenant RLS, tenant-login fence,
   source-lock insertion, late-row refusal and protected truncation apply.
   Private inspection rechecks the digest and every mapped row. Exact-ID
   replay is historical; it checks root identity but makes no fresh claim.
4. This preparation **does not** publish normalized text, complete a later
   run, infer absence, advance freshness, activate v2 current reads, write
   source files or alter FOS-Master. A separate terminal outcome ledger must
   process each prepared hash and account for all deferred/excluded/error
   rows. Rollback and owner-reviewed live shadow remain gates.

## Verification and rollback

Use fictional roots and disposable PostgreSQL to prove a later-only file gets
source-bound evidence while its current pointer stays null; source drift and
wrong root refuse before insertion; replay and identity/scope checks are
explicit; direct SQL cannot omit rows or mutate/truncate sealed records.
Rerun the baseline preparation, stress, full-suite and hosted gates. Rollback
stops new preparation writes and retains historical rows; no current-source
rollback is needed.
