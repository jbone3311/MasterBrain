# ADR-096 — Bind FileOS completion to an immutable inventory policy

Status: accepted and implemented in isolated PR #20; hosted CI and populated restore passed on runtime head `26fd5b2`. Review and integration remain pending.

## Context

A completed FileOS run stores the canonical hash of its entire snapshot, but the
snapshot itself is not retained in the completion ledger. Consecutive-run absence
inference therefore cannot tell whether the scanner's size, exclusion, extension or
symlink rules changed. A clean scan under a narrower policy could create false
absence events despite the coverage and mass-loss guards in ADR-094/095.

## Decision

- Give the current snapshot policy an explicit `fileos-inventory-policy-v1`
  contract marker in each new manifest. Validate the exact policy fields and bounded
  values before completion. Compute a SHA-256 of the canonical manifest version and
  policy object, not of paths, file content or observation time.
- Migration 0031 adds `policy_sha256` to the append-only FileOS completion receipt.
  New inserts must have a lowercase 64-hex digest; old receipts stay null and
  immutable because their policy cannot be reconstructed from the whole-manifest
  hash. The database enforces the new-insert requirement without falsely
  backfilling legacy history.
- Under the existing tenant/source lock, a new completion requires the previous
  latest-complete receipt to have the same policy digest. Unknown legacy policy or
  drift refuses completion before any new receipt or absence event commits. Exact
  replay of a newly policy-bound run remains idempotent. Historical receipts remain
  readable, but cannot be completed again under an invented policy identity.
- No silent rebaseline, force flag, file effect, source-policy switch or donor edit
  is authorized. Existing sources with a legacy completion pause at this boundary
  until a separate reviewed baseline/transition contract exists. That path must
  preserve old evidence and explain search visibility and rollback.

The digest identifies a policy contract, not scanner parity. A code change that
changes membership semantics must bump the policy marker and pass donor shadow and
consecutive-run gates. This decision does not adopt the donor junk classifier,
increase size bounds, follow external symlinks or prove live cloud behavior.
An individual file crossing the unchanged size/exclusion boundary can still drop
out of `items` without a per-locator exclusion record; policy identity alone does
not prove that disappearance is a real deletion. An explicit exclusion/metadata-
only ledger and small-loss acceptance gate remain necessary before cutover.

## Verification

Unit tests cover exact policy validation and stable/different digests. PostgreSQL
tests prove equal-policy consecutive runs and genuine absence; a changed exclusion,
size or symlink rule refuses completion and writes no absence; replay remains
idempotent; new direct SQL inserts without a digest fail. Run full hosted CI and
populated restore before review. Keep FOS-Master pinned and unchanged.

## Rollback

The migration is additive and does not rewrite historical receipts. Stop FileOS
completion before deploying older code that cannot supply the new digest; do not
drop the constraint or backfill unknown policy automatically. Roll forward with a
corrected publisher, or use the tested database restore workflow if necessary.
