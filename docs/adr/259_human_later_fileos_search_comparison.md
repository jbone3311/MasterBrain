# ADR-259 — Human comparison of historical later FileOS search

Status: accepted for synthetic/disposable, read-only implementation.

## Context

ADR-258 builds a ready shared DataCore generation for one completed later
FileOS v2 run, but deliberately forbids activation. A reviewer needs to see
what that generation would retrieve beside the source's active v1 results
without mistaking historical text for current FileOS state or treating a
missing result as evidence that a source file is gone.

## Decision

1. A human-only, source-bound Brain API preview accepts a named ready
   `v2_later` generation, a bounded lexical query and per-generation limit.
   It requires transition-review, search and evidence-read scopes. The
   candidate is revalidated against its immutable completed run, baseline,
   latest v1 receipt, source root and active source status under the source
   lock. Source grants are checked before looking up the generation.
2. Search each generation independently with the existing lexical helper.
   Return separately ranked `active_v1` and `candidate_v2_later` layers,
   run ID and explicit possible-absence/mass-loss/coverage review flags.
   Mark candidate visibility `historical_preview`, coverage incomplete for
   current FileOS, and excerpts untrusted. A missing v1 activation yields an
   empty v1 layer, not an invented baseline.
3. No read pointer, source file, absence event or approval state changes.
   The API cannot activate either baseline or later v2. A candidate hit is
   historical evidence, not current-source authority. A non-hit says nothing
   about source absence. The pinned FOS-Master donor remains unchanged.

## Verification and next gate

Use fictional PostgreSQL lifecycle tests for a later-only file, a second
generation with possible absence, human/worker and source-grant boundaries,
closed API inputs and unchanged current search. Baseline-v2 comparison also
rejects a paused or ungranted source. The next gate is an explicit review and
rollback-ready activation policy, followed by owner-approved live shadow and
hosted exact-head checks. None is implied by this comparison.
