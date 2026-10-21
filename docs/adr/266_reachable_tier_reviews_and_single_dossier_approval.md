# ADR-266 — Reachable source-tier reviews and single, bound dossier approvals

Status: **accepted; implemented on the PR #245 branch**. Synthetic-only. No
live source, mailbox, FOS-Master or current-read behavior changes.

## Context

The independent review of PR #245 left three findings after ADR-265:

1. **Buried tier reviews.** ADR-217 reviews are append-only and cannot be
   withdrawn, but the read returned the newest 25 with `truncated=true` and no
   way to reach older ones. Twenty-five newer reviews could hide an older,
   disagreeing classification from every API caller.
2. **Duplicate imports.** ADR-206/207 imports issue new fact and artifact IDs,
   so the "claim already exists" check never matched an earlier import.
   Staging the same dossier under two idempotency keys and approving both
   produced two identical reviewed rows.
3. **Unbound fact approvals.** The 0069 decision guard required only *a*
   publication receipt for that reviewer, key and fact. A direct runtime-role
   write could mark a proposal approved while naming an unrelated fact, and the
   reviewer was not tied to the current actor. The artifact guard (0070)
   already bound content but not the reviewer.

## Decision

1. `GET .../source-tier-reviews` accepts `after=<review id>` and pages by
   `(recorded_at, id)` newest first. The response adds `next_cursor` and
   `tier_counts` (T1/T2/T3 over **all** current visible reviews), so a
   disagreement is visible on the first page. An unknown or hidden cursor is
   `404`. `BrainReadClient.source_tier_reviews(after=...)` validates the closed
   response, including that counts cover the page and the cursor matches.
   Still no winning tier is computed.
2. An imported claim ID may be approved once per tenant. Staging refuses a
   claim already approved; approval takes a per-claim advisory lock and refuses
   if another proposal for the same claim was approved. Rejected claims may be
   re-staged. Migration 0095 repeats the single-approval rule in SQL.
3. Migration 0095 requires every new fact-proposal decision's reviewer to be
   the current actor, and an approval's fact to match the proposal exactly:
   project, predicate, value, type, status, derivation, confidence, quote
   citation, quote, observed time, ordered evidence IDs and measurement, with
   no supersession or validity window, published by that reviewer. Artifact
   decisions gain the same reviewer and single-approval rules. Existing rows
   are not rewritten.

## Verification

Each fix has a PostgreSQL regression test that fails on the pre-fix code:
27 reviews with an older T3 buried behind 26 T1; one dossier staged twice and
approved once; a forged approval naming an unrelated fact and a decision by
another reviewer. Results are in `docs/BUILD_RECEIPT.md`.

## Consequences

Approvals that touch several claims take one advisory lock per claim in
proposal order; two reviewers approving overlapping batches concurrently can
deadlock, which PostgreSQL resolves by aborting one retryable transaction.
