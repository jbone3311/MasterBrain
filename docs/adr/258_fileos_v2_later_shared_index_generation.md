# ADR-258 — Shared DataCore generation for a historical later FileOS v2 run

Status: accepted for synthetic/disposable, private, nonactivating implementation.

## Context

ADR-257 completes historical processing of one later donor-policy observation.
Its normalized documents and exact per-row outcomes need an index generation
on the same DataCore substrate as v1 and the v2 baseline before a bounded
comparison or eventual rollback-ready activation can be considered. The
historical run still provides no current-read or absence authority.

## Decision

1. Migration 0092 extends `brain_index_generations` with a distinct
   `v2_later` basis and exact run/attempt digest binding. Existing `v1` and
   baseline `v2` rows retain their prior shapes and behavior. The shared
   item/chunk/ready-receipt tables are reused; no parallel search database
   or current pointer is introduced.
2. A scoped private worker verifies the immutable ADR-257 receipt, latest
   v1/source-root basis and complete ready attempt. It indexes only hashed
   rows, matching each prepared source version/evidence and extracted
   normalized document; deferred, excluded and possible-absence rows remain
   explicitly accounted in the run packet, not fabricated as index items.
   It validates bounded text, deterministic chunks and document identity,
   then seals one content-addressed ready generation. Exact replay is inert.
3. SQL independently rejects a forged/stale parent, missing or altered hashed
   item membership, altered/missing/extra chunks and activation of any
   `v2_later` generation. Forced tenant RLS and the existing source-lock and
   immutable generation machinery remain in force.
4. A later decision must add a human-only, scoped comparison of this named
   historical generation against the active v1 view. Generation readiness
   alone is not an approval to activate, infer absence or change FOS-Master.
   Owner-approved live shadow, rollback and hosted gates remain open.

## Verification and rollback

Use a fictional mixed FileOS root to prove exact indexed text, historical
replay, unchanged current search, blocked/stale/scope refusal, direct-SQL
forged membership and activation denial. Stress the whole path on 3,000
fictional hashes, run the full local and hosted gates, and preserve the donor
checkout. Rollback stops new generation builds and retains immutable history;
no active pointer or source file changes in this tranche.
