# ADR-094 — Refuse FileOS completion after incomplete snapshot coverage

Status: implemented and verified in an isolated tranche. Hosted
[CI 35863559605](https://github.com/jbone3311/MasterBrain/actions/runs/35863559605)
and [restore 35863559359](https://github.com/jbone3311/MasterBrain/actions/runs/35863559359)
passed on PR #18's runtime head `d7e698e`; review remains pending. This is not an
inventory-policy switch or cutover.

## Context

`snapshot_tree` v1 reports errors separately from its hashable `items`. The current
manifest parser checks item count, but `complete_fileos_run` can append a completion
receipt and infer absence from the item list without checking snapshot errors. A
temporary directory read failure can therefore make a previously observed item
look absent. The pinned FOS-Master scanner also silently omitted an unreadable
synthetic directory and pruned its one old row in DC-002E; the donor's mass-prune
tripwire does not protect small losses. Neither behavior is acceptable evidence of
a complete inventory.

## Decision

Before any FileOS run completion, validate the manifest's exact error ledger:

- `errors` must be a list of unique, nonempty relative locators with known codes;
  `counts.errors` must equal its length. Malformed or contradictory coverage is
  refused without disclosing locators in the error message.
- `directory_unreadable`, `file_unreadable`, `changed_during_scan`,
  `symlink_outside_root` and unknown codes block completion. A failed read or
  uncertain boundary is not an observed absence.
- `symlink_skipped` is the sole tolerated error, and only when the manifest policy
  explicitly has `follow_file_symlinks: false`. This records the current v1
  intentional no-follow behavior; it does not authorize a policy change between
  completed runs.
- The private FileOS publisher checks coverage before importing or extracting.
  The storage completion method independently checks it again, so callers cannot
  bypass the guard. Incomplete intake may still be retained through the lower-level
  import API, but it cannot advance freshness or create absence events.

No existing receipt or evidence is rewritten. No schema, donor scanner, snapshot
exclusion, search, activation or effect behavior changes in this tranche. The later
versioned-policy decision must compare policy identities across complete runs and
add a mass-loss/coverage guard, including a safe approval and rollback path.

## Verification

Use synthetic manifests and PostgreSQL to prove: each blocking error fails before
completion; a missing/invalid error ledger fails; deliberate no-follow symlink
skips remain accepted; a failed second run retains the prior latest-complete run
and writes no absence event; a later clean run can complete and infer a genuine
absence. Test direct storage access as well as publisher preflight. Run hosted CI
and populated restore before review. FOS-Master stays unchanged.

## Rollback

Revert the completion guard code only if it causes an unacceptable regression;
previous append-only receipts and evidence remain intact. Do not backfill a
completion receipt for a previously incomplete scan. A paused source can retry
with a new clean snapshot after its underlying read failure is resolved.
