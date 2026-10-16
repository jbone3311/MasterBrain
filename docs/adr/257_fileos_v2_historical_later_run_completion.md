# ADR-257 — Historical completion of one later FileOS v2 processing run

Status: accepted for synthetic/disposable, private, nonactivating implementation.

## Context

ADR-256 can seal all later-observation row outcomes, but a document attempt
alone does not attest that the exact source still matches after processing.
One attempt may be blocked and retried. A later run needs an explicit,
immutable completion boundary before any future generation or current-read
decision. This boundary must not make possible missing files into absence
events or imply that the FOS-Master donor can be retired.

## Decision

1. A separately scoped worker selects one **ready** ADR-256 attempt. Under
   the tenant/source lock, it revalidates the packet, closure, preparation,
   complete outcome ledger, latest v1 baseline and root binding, then makes a
   fresh no-follow donor-policy scan. The exact current rows, source policy
   and root must still match. The fresh observation must postdate the attempt.
   Blocked attempts cannot complete.
2. Migration 0091 appends one historical completion per observation packet.
   Composite foreign keys bind the exact ready attempt, preparation, closure
   and packet. A database trigger independently checks the current v1/root
   lock, ready outcome counts, packet classification counts and computed
   review flags. Fixed SQL checks preserve `publishable=false`,
   `current_read_active=false`, `absence_authorized=false` and
   `requires_review=true`. RLS, tenant-login fencing, immutable rows and
   truncate denial apply. Exact-ID replay returns only the old receipt.
3. The receipt explicitly flags possible absence, donor mass-loss threshold
   and prior-coverage ambiguity. Even a zero-flag run still requires a
   separate owner-reviewed current-generation/rollback policy. This table
   is historical evidence only; current FileOS search, v1 freshness and
   absence events do not consume it.
4. A later ADR must define generation assembly over this completion, then
   an owner-approved live shadow, bounded activation, rollback and absence
   review. Source effects and FOS-Master retirement remain separately gated.

## Verification and rollback

Fictional PostgreSQL tests cover blocked-attempt refusal, source drift,
forged SQL flags, clean and possible-absence runs, exact replay, one run per
packet, scope and mutation/truncation denial. Assert current search and
absence rows do not change. Run the full local and hosted gates. Rollback
stops new completion writes and preserves immutable history; no source-file
or current-index rollback is required because this tranche changes neither.
