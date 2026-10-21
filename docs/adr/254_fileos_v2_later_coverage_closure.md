# ADR-254 — Exact historical FileOS v2 later-observation coverage closure

Status: accepted for synthetic/disposable, private, nonpublishing implementation.

## Context

ADR-253 retains a later donor-policy observation against an exact completed
v2 baseline. Its candidate and ADR-251 comparison include every scanned row
and every prior present-row classification, but there is no independently
sealed row-by-row input for a future later-run processor. A preview count is
not a terminal processing outcome or authority to infer absence.

## Decision

1. Deterministically project one immutable ADR-253 packet into a closed
   coverage document. It lists each current hashed, deferred, excluded and
   error row once, with the validated source identity, candidate version,
   digest, size and reason as applicable. It separately lists each prior
   present-row classification once. The count maps must exactly cover both
   lists. Sort by locator and bind the document to the packet's canonical
   SHA-256, source, root and observation. Cap canonical UTF-8 at 16 MiB.
2. A private worker with `brain.fileos.transition.verify` and
   `brain.changes.read` may seal exactly one closure per packet. There is no
   source read: this operation is historical, and exact-ID replay never
   claims fresh observation. An alternate closure ID or actor is refused.
   A private reader recomputes the complete projection from the validated
   packet, compares the stored JSON and digest, and returns only IDs, count
   maps, blocker codes and a digest—not paths or content.
3. Migration 0088 enforces exact packet identity by composite FK, one
   closure per packet, forced tenant RLS and tenant-login fence, immutable
   rows, truncation refusal, bounded JSON and fixed
   `publishable=false`/`absence_authorized=false`/`requires_review=true`.
   No current-search or absence-event consumer reads the table.
4. This closure is **not a completed later run**. It has no document/evidence
   processing outcomes, readiness, source freshness, absence authority,
   current-read activation or FOS-Master cutover. The next tranche must
   process exact current hashed versions and account for every row in a
   terminal outcome ledger, with rollback and reviewed activation separate.

## Verification and rollback

Use fictional roots and disposable PostgreSQL to prove exact row coverage,
record/read/replay, changed identity refusal, direct-SQL forged authority and
content detection, mutation/truncate denial, and no current/absence effect.
Run full local and hosted gates before merge. Rollback stops closure writes
and retains historical rows; it does not alter source or current FileOS state.
