# ADR-058 — Immutable FileOS index generations and activation rollback

Status: accepted and verified for the additive prototype tranche on 2026-09-22.
Revision `b715bf1` passed hosted
[CI 35725616036](https://github.com/jbone3311/MasterBrain/actions/runs/35725616036)
and [restore 35725615886](https://github.com/jbone3311/MasterBrain/actions/runs/35725615886).

## Decision

DataCore may rebuild lexical derivatives only from the latest completed FileOS run.
The build takes the same per-source transaction lock as completion, verifies the exact
run ledger, evidence identity, normalized body digest and deterministic document
identity, then regenerates chunks from normalized text. It never rereads or changes a
source file.

Each build creates an immutable generation whose identity binds the tenant-scoped
source, completion run, observation, exact item plan, code revision and chunker
version. The generation contains one disposition for every completed-run item plus a
closed set of generated chunks. PostgreSQL accepts a readiness receipt only when the
declared item, document and chunk counts match the stored children. Ready generations
cannot accept more items or chunks.

Activation is a separate append-only receipt requiring `brain.index.activate`, a
current tenant actor and an actor-scoped UUID idempotency key. Search follows only the
latest activation for that source. Rollback is therefore a new activation of a prior
ready generation; no generation, evidence, document or receipt is deleted or edited.
The same key and request replays, while changed reuse conflicts.

The Brain API initially exposes only active-generation status and bounded lexical
search. Generation build and activation remain trusted library operations until a
separate, narrow operator command can verify its private configuration and authority.
Existing global DataCore search remains unchanged, so this tranche proves the new
retrieval path without silently changing compatibility behavior.

## Safety and failure contract

Generation construction is one database transaction. A crash before readiness leaves
no committed partial generation. Builds are bounded to 10,000 run items, 64 MiB of
normalized text and 100,000 chunks. An `extracted` ledger item without its normalized
document, any changed deterministic identity, a stale requested run, or an incomplete
ledger fails closed.

All generation, item, chunk, readiness and activation tables carry forced RLS,
least-privilege grants and immutable update/delete triggers. Read endpoints return
opaque IDs, counts, digests, bounded excerpts and source-relative locators; they do
not return source roots, credentials or original bytes. Restoration must preserve the
same active generation and query result.

## Acceptance and rollback

PostgreSQL integration must prove deterministic replay, generation changes across
completed runs, activation replay/conflict, active-only query behavior, reactivation
rollback, post-ready append rejection, RLS, API authorization and populated logical
restore. Hosted tests are authoritative because local PostgreSQL skips are not passes.

Operational rollback stops building or reading generations, or appends an activation
of the last accepted generation. This decision adds no source reprocessing,
incremental scheduler, file effect, FOS-Master cutover, rename or retirement.
