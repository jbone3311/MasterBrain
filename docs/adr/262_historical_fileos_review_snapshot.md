# ADR-262 — Exact historical FileOS review snapshot

Status: **accepted for synthetic-only implementation**. This is a read-only
prerequisite for a separately designed run-level signoff, not signoff itself.

## Context

ADR-261 stores append-only decisions on exact prior rows of a ready historical
FileOS v2 later generation. A future run-level review must bind to one
deterministic snapshot of those decisions. Counting only the `absence_candidate`
state is insufficient: deferred, excluded, error-covered and unobserved prior
rows also make coverage ambiguous. A later correction must change the snapshot
identity, and an unreviewed or disputed row must remain visibly unresolved.

## Decision

Expose a human-only, source-granted Brain API summary for one named ready
historical generation. Reuse ADR-259/260 source, active-v1/root, completed-run
and immutable-closure checks under the source lock. Read the latest immutable
decision for each exact prior locator. A controlled pure function validates
decision/closure membership and computes a canonical SHA-256 over the exact
run/closure/generation identity, review flags, prior-row classifications and
latest decision identities. It returns only the digest and compact counts,
not a bulk locator dump or source content.

Required row decisions are those classified `absence_candidate`,
`deferred_prior`, `excluded_prior`, `error_covered_prior`, `unobserved_prior`
or `unobserved_hashless_prior`. Only the current latest
`acknowledge_historical_observation` disposition counts as acknowledged;
`investigate`, `dispute_classification` and missing decisions are held. The
summary separately lists true `possible_absence`, `mass_loss` and
`prior_coverage` run flags requiring future explicit acknowledgement. It may
say `row_decisions_complete=true` when every required row is acknowledged,
but never says the run is approved or current. Corrections change the digest
and can move a row from acknowledged back to held.

The route requires a human principal, `brain.fileos.transition.review`,
`brain.search` and `brain.evidence.read`, plus the exact source grant. It is
read-only apart from its standard audit event. SQL and API response flags
remain `absence_authorized=false`, `current_read_active=false` and
`source_effect_authorized=false`. No automatic run-level signoff, deletion,
absence event, donor cutover or live-source enrollment is added.

## Acceptance

- Pure synthetic cases cover clean, possible-absence, mixed ambiguous
  coverage, mass-loss/prior-coverage flags, missing/disputed/corrected
  decisions, forged extra/mismatched decisions, stable digest and changed
  digest after correction.
- A disposable PostgreSQL lifecycle proves source/worker denial, exact ready
  generation and closure binding, API shape and unchanged current search.
- The existing 100-row/3,000-file and two-cluster restore gates remain
  separate. Hosted exact-head CI, owner wording, run-level signoff,
  fresh live shadow, rollback and independent review remain required.
