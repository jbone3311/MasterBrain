# ADR-097 — Account for excluded FileOS locators before inferring absence

Status: accepted for an isolated implementation tranche; verification pending.

## Context

ADR-094 rejects incomplete scans, ADR-095 rejects donor-scale mass loss, and
ADR-096 binds consecutive runs to the same membership policy. None distinguishes a
genuinely removed file from a formerly indexed file that is still present but now
exceeds the unchanged size bound, has a newly excluded name/type, becomes a special
file, or sits under a newly excluded directory. A small such loss can pass the
mass-loss threshold and incorrectly create absence evidence. A no-follow file
symlink can cause the same mistake because its skip is an allowed scan error.

## Decision

- Every new snapshot includes a bounded, sorted `exclusions` ledger with one safe
  relative locator, `file` or `directory` kind, and closed reason for each excluded
  entry counted by `counts.excluded`. Directory entries cover their entire subtree;
  files cover only themselves. Excluded content is neither opened nor hashed.
- The completion validator requires an exact, nonduplicated ledger/count, safe
  locators, closed reasons/kinds and no overlap with indexed items or scan errors.
  A ledger overflow makes completion fail closed. Intake can still retain partial
  evidence independently; a legacy manifest without this ledger cannot complete.
- Under the existing source transaction and lock, compare prior completed item
  locators with new exclusions and allowed `symlink_skipped` errors. If any missing
  prior item is covered by an exclusion or skip, refuse the whole new completion
  before its receipt or absence events commit. A genuinely absent locator not so
  covered retains the existing absence behavior and mass-loss check.
- This is an additive snapshot contract, not a membership-policy change: retain
  `fileos-inventory-policy-v1`, existing item identities, and the donor policy
  difference. The manifest hash binds the ledger to the immutable receipt; no SQL
  migration or FOS-Master edit is needed. No force bypass or automatic cutover.

The ledger is evidence of what the trusted snapshot scanner observed, not a proof
against a forged manifest or all filesystem races. Root binding, a reviewed legacy
baseline, live-source shadow, and owner acceptance remain independent gates.

## Verification

Use synthetic files to exercise min/max size and extension exclusions, policy-path
and directory exclusions, special files where supported, no-follow symlinks,
unaffected deletion, malformed/duplicate/overlapping ledgers, and bounded overflow.
PostgreSQL regression must prove that a one-item excluded/skipped transition leaves
the previous complete receipt and absence ledger unchanged, while a real deletion
still produces one absence. Run hosted CI and populated restore before review.

## Rollback

Stop FileOS completion before deploying an older publisher that does not validate
the ledger; do not reinterpret new receipts under the older completion code. Keep
receipts and evidence append-only. Roll forward with a corrected publisher or use
the tested database restore workflow; never down-migrate or edit FOS-Master.
