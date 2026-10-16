# ADR-261 — Historical FileOS row decisions and proposed run adjudication

Status: **partially implemented**. Append-only historical row decisions are
implemented in migration 0093 and the Brain API. Run-level signoff, absence
approval, live shadow and current-read authority remain **proposed and
unimplemented**. A row disposition is never file or deletion authority.

## Problem

ADR-260 lets an authorized human inspect exact historical classifications,
but `absence_candidate` still means only that a prior hashed file was not
observed in one later scan. A mass-loss or prior-coverage flag requires more
than a global yes/no click. A decision must be durable, revisable without
erasing its audit trail, and bound to the precise immutable run and rows the
owner saw. The Brain API host must not need filesystem or donor-source
authority merely to record that decision.

## Contract and implementation boundary

1. Record append-only, idempotent human decisions in batches of at most 100
   exact prior rows. Each row names its locator, classification state and
   opaque prior version from the ADR-254 closure. Permit only controlled
   dispositions: `investigate`, `dispute_classification`, or
   `acknowledge_historical_observation`. Do not accept free-text source
   content. Repeated idempotency keys replay only the exact stored decision;
   changed payloads fail. **Implemented.** HTTP requests also obey the
   existing 32 KiB body limit, so the effective batch may be below 100 rows.
2. The service and SQL independently bind every decision to tenant, human
   reviewer, source, ready later generation, completed run digest and closure
   digest. Revalidate active source, latest v1/root basis, source grant,
   exact closure membership and row state under the source lock. Reject
   stale/mismatched or cross-tenant rows. Events are immutable and tenant-RLS
   fenced; later corrections append a new decision. Reads expose the latest
   decision and its audit history without treating it as a source fact.
   **Implemented** by `FileOSV2LaterRowDecisions`, bounded history readback,
   `v2-later-review-rows` latest-decision metadata and migration 0093. The
   service requires a human principal; SQL independently checks the actor,
   tenant, exact run/closure/row and current source/v1/root basis, but the
   database does not itself store a client-kind claim.
3. **Not implemented.** A separate run-level review would require explicit acknowledgement of
   every possible-absence and coverage-ambiguous row, plus mass-loss and
   prior-coverage flags, against the exact decision snapshot. A held,
   disputed, incomplete, or changed-source run cannot advance. Even an
   acknowledged historical observation is **not** a confirmed deletion,
   absence event, file effect, v2 activation or donor cutover.
4. **Not implemented.** Before any current-read activation proposal, a separately approved live
   shadow must produce a fresh no-follow source observation and parity
   evidence; an operator must prove rollback to the retained v1 pointer in
   a bounded synthetic drill. Hosted exact-head CI, independent review and
   owner acceptance remain mandatory. FOS-Master remains unchanged.

## Acceptance and remaining gates

The first row-decision tranche tests fictional atomic batches, corrections,
idempotent replay, historical possible absence, bounded history, stale v1,
source-grant and worker denial, forged SQL row/reviewer, immutable storage,
and unchanged current search. The 100-row service boundary and a populated
two-cluster synthetic restore now pass. Mixed-coverage/mass-loss,
tenant-login isolation after restore and hosted exact-head stress remain
before run-level signoff. The owner-facing
`acknowledge_historical_observation` wording still needs acceptance; it does
**not** authorize deletion or absence. No live data
or donor modification is part of this tranche.
