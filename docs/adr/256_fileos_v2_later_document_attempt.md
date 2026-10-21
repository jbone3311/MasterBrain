# ADR-256 — Historical later FileOS v2 document attempt and row outcomes

Status: accepted for synthetic/disposable, private, nonpublishing implementation.

## Context

ADR-255 prepares source-bound evidence for exact later donor-policy hashes,
including newly observed files, but no later document text or terminal
per-row processing result exists. A document attempt must be tied to that
preparation and account for every current row without becoming a completed
FileOS run or an authority to remove an earlier file.

## Decision

1. A worker with `brain.fileos.transition.publish`,
   `brain.document.publish` and `brain.changes.read` revalidates the exact
   ADR-255 preparation and performs a fresh, source-locked no-follow scan
   before processing. Each hashed row uses its prepared, source-bound version
   and existing confined text/isolated-document extractor. Extracted text
   goes through DataCore's normal document/chunk/provenance path. The worker
   accounts for extracted, empty, unsupported, deferred, changed or failed
   results. Current deferred and excluded inventory rows receive fixed
   `deferred_source` and `excluded_source` outcomes without fabricated bytes.
   ADR-255 refuses scan-error observations, so this first document tranche
   cannot seal a `scan_error` row; the schema reserves that outcome for a
   separately reviewed blocked-attempt path.
2. Revalidate the preparation, source root, policy and every normalized row
   in a second source-locked transaction after extraction. Migration 0090
   seals immutable attempts with one item per current observed row. A failed
   or changed hashed extraction leaves a blocked historical attempt and may
   be retried with a new attempt ID; a partial unique index allows only one
   ready attempt per preparation. Readiness means no changed, failed or
   scan-error outcome, **not** current-read or run-completion authority.
   Deferred SQL checks exact counts, closed membership, hashed-row evidence
   binding and extracted document provenance. Exact-ID replay is historical;
   a changed actor/revision is refused. A partial derivative produced before
   a failed final seal remains historical and cannot become current.
3. Forced tenant RLS/login fencing, source-lock insertion, fixed
   `publishable=false` and `absence_authorized=false`, late-item refusal,
   mutation/truncation denial and compact private inspection apply. There is
   no public mutation route or source effect. Existing v1 current pointers,
   freshness, absence events and FOS-Master remain unchanged.
4. A later decision must define completed later-run freshness, blocked
   observations, mass-loss review, rollback and owner-approved live shadow
   before v2 current activation or absence inference. This document attempt
   is not itself such a completion.

## Verification and rollback

Use fictional roots and disposable PostgreSQL to prove a later-only text file
produces a cited historical document while an excluded lock file receives an
explicit outcome; a simulated failed extraction seals a blocked attempt,
then a clean retry seals one ready attempt. Source drift, incomplete direct-
SQL attempts, mutation and truncate fail closed. Confirm v1 current
pointers/freshness and absence rows do not change. Run full local and hosted
gates. Rollback stops new attempt writes, preserves immutable history and
requires no source-file rollback.
