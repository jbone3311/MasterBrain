# ADR-095 — Refuse unreviewed mass loss in FileOS inventory

Status: accepted for an isolated implementation tranche; hosted verification pending.

## Context

ADR-094 prevents an incomplete snapshot error ledger from becoming a complete run.
That does not catch a clean-looking but unexpectedly thin inventory: a temporarily
empty mounted directory can still produce a valid snapshot and make many previously
observed files appear absent. The pinned FOS-Master scanner has a mass-prune
tripwire, but MasterBrain's append-only completion and absence ledger needs its own
guard before any FileOS cutover.

## Decision

For a new completion of a source with a prior complete run, count identities in the
prior run's item ledger that are absent from the proposed run. Refuse completion when
at least 10 prior items are missing **and** at least half of the prior run's items
are missing. Check this under the existing tenant/source advisory lock, before
inserting the new completion receipt or any absence event. A refused run may retain
its lower-level import receipt; it must not become latest-complete or alter the
absence ledger. Return a content-free conflict. Exact replay of an already complete
run remains idempotent.

This threshold matches the pinned donor's mass-prune tripwire for comparison, not
its destructive pruning behavior. No bypass or `force` flag is authorized here.
A legitimate large removal pauses completion until a separate reviewed override
contract exists. This guard does not detect losses below the threshold, prove a
mount is healthy, or resolve policy differences between snapshots. A later
versioned-policy decision must fence policy changes across complete runs. FileOS
remains the reference implementation and is not modified or retired.

## Verification

Synthetic and PostgreSQL tests must cover threshold boundaries, a refused run with
an unchanged latest-complete receipt and no absence events, exact replay, and a
subsequent below-threshold clean run. Run hosted CI and populated restore before
review. Keep the donor pinned and unchanged.

## Rollback

Reverting the code removes this completion guard but leaves append-only receipts
intact. Do not backfill refused completions automatically. A reviewed override, if
ever needed, requires a separate decision, audit trail and explicit source scope.
