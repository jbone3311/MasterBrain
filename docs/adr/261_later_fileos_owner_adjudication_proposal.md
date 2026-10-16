# ADR-261 — Proposed owner adjudication of historical FileOS discrepancies

Status: **proposed, not implemented**. No approval or current-read authority
is added by this document.

## Problem

ADR-260 lets an authorized human inspect exact historical classifications,
but `absence_candidate` still means only that a prior hashed file was not
observed in one later scan. A mass-loss or prior-coverage flag requires more
than a global yes/no click. A decision must be durable, revisable without
erasing its audit trail, and bound to the precise immutable run and rows the
owner saw. The Brain API host must not need filesystem or donor-source
authority merely to record that decision.

## Proposed contract

1. Record append-only, idempotent human decisions in batches of at most 100
   exact prior rows. Each row names its locator, classification state and
   opaque prior version from the ADR-254 closure. Permit only controlled
   dispositions: `investigate`, `dispute_classification`, or
   `acknowledge_historical_observation`. Do not accept free-text source
   content. Repeated idempotency keys must return the same digest or fail.
2. The service and SQL independently bind every decision to tenant, human
   reviewer, source, ready later generation, completed run digest and closure
   digest. Revalidate active source, latest v1/root basis, source grant,
   exact closure membership and row state under the source lock. Reject
   stale/mismatched or cross-tenant rows. Events are immutable and tenant-RLS
   fenced; later corrections append a new decision. Reads expose the latest
   decision and its audit history without treating it as a source fact.
3. A separate run-level review would require explicit acknowledgement of
   every possible-absence and coverage-ambiguous row, plus mass-loss and
   prior-coverage flags, against the exact decision snapshot. A held,
   disputed, incomplete, or changed-source run cannot advance. Even an
   acknowledged historical observation is **not** a confirmed deletion,
   absence event, file effect, v2 activation or donor cutover.
4. Before any current-read activation proposal, a separately approved live
   shadow must produce a fresh no-follow source observation and parity
   evidence; an operator must prove rollback to the retained v1 pointer in
   a bounded synthetic drill. Hosted exact-head CI, independent review and
   owner acceptance remain mandatory. FOS-Master remains unchanged.

## Acceptance before implementation

Resolve whether `acknowledge_historical_observation` is the right owner-facing
wording; it must never look like permission to delete a file. Then test a
fictional mixture of possible absence, deferred/excluded/error coverage and
mass loss; 100-row boundaries; corrected decisions; idempotent replay;
stale-root/changed-v1 refusal; forged SQL rows and reviewer identity;
tenant/source isolation; replay after restore; and zero change to current
search, absence tables and donor files. Keep the API read-only until the
write-specific contract and SQL guards pass those tests.
