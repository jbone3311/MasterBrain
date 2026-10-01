# ADR-121 — Prepare FileOS v2 evidence without changing current FileOS

Status: accepted for synthetic/disposable preparation only.

## Context

ADR-119 records a historical match between an owner-reviewed FileOS v2 stage and
one fresh donor-policy scan. That receipt does not reserve the filesystem, import
shared evidence, or authorize v2 publication. The current v1 importer also cannot
represent hashless donor observations and must not be reused with a policy change.

## Decision

- Add a private, worker-only `brain.fileos.transition.prepare` operation. It also
  requires `brain.source.ingest` and `brain.changes.read`. No REST, assistant,
  general filesystem-browsing, or scheduling route is added.
- Under the same per-source completion lock, revalidate the exact current v1
  receipt, sealed stage, human review, and historical verification. Perform a
  **new** bounded, no-follow, source-bound donor-policy scan inside that locked
  transaction. Reject root, row, count, policy, error, or latest-v1 drift.
- Materialize only genuinely hashed rows as shared source items, immutable
  source versions and source-bound evidence. V1 and donor candidate version IDs
  both use item/content/size, but v1's immutable version metadata includes an
  mtime that the donor candidate does not capture. Reusing that ID would poison
  a later v1 import. Therefore a v2 prepared version ID is deterministically
  namespaced by the candidate version and policy digest. A separate immutable
  mapping preserves the exact donor candidate ID and links it to the prepared
  DataCore version/evidence; matching v2 identities replay, while conflicts
  refuse. Hashless deferred, excluded and error rows remain in the staged
  ledger without fabricated versions or evidence.
- Record a separate immutable, forced-RLS, tenant-login-fenced preparation
  receipt, bound to the exact approval, verification, stage, source, prior v1 run,
  candidate/plan and fresh row digest. A database constraint checks that every
  hashed stage row has one exact candidate-to-prepared mapping and matching
  item, version and evidence at commit. Exact-ID
  replay is idempotent and still rechecks the source; alternate identity refuses.
- Do **not** update `brain_source_items.current_version_id`, v1 run receipts,
  active index generations, current search, freshness, absence, change feed or
  source effects. A prepared source-bound evidence row is not a completed v2
  baseline or a retained original byte copy. No publication/cutover is authorized
  by the earlier review or this receipt. A later decision must specify explicit
  owner publication authority, v2 completion, visibility, absence suppression,
  rollback and live-source acceptance.

## Verification and rollback

Use synthetic/disposable PostgreSQL tests for new/unchanged/changed hashed rows,
hashless rows, exact replay, wrong scope/client/tenant, stale v1, source mutation,
root drift, immutability, RLS and absence of current-state effects. Run full CI,
strict runtime, populated restore and pinned-donor parity. Rollback stops the
private preparer; historical evidence and receipts remain immutable, while v1
read and FOS-Master operation remain unchanged. Live use requires a measured
scan/lock budget and separate owner authorization.
