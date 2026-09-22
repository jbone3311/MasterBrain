# ADR-056 — Completed-inventory reconciliation evidence

Status: accepted for an additive prototype tranche on 2026-09-22, pending hosted
PostgreSQL and populated-restore gates.

## Decision

DataCore records every item/outcome in a completed FileOS run in the immutable,
forced-RLS `brain_fileos_run_items` ledger. A deferred database constraint requires
the ledger's item total and grouped outcomes to equal the parent completion receipt;
an application-only aggregate is not sufficient.

Completion is serialized per tenant/source and must be newer than the preceding
completed observation. This prevents a delayed older snapshot from becoming the
fresh inventory. Between consecutive completed runs, an item present in the prior
ledger and absent from the new ledger creates an immutable
`brain_fileos_absence_events` record. Partial imports and failed/crashed publication
prefixes cannot create absence events because they have no completion receipt.

`GET /v1/brain/sources/{source_id}/inventory` returns bounded counts for the latest
complete run. It does not expose paths or content. Absence preserves all versions,
evidence, normalized documents, chunks and provenance, and does not yet alter search
visibility. A later policy tranche may define current-versus-historical retrieval only
after rebuild and reappearance behavior is evaluated.

## Donor and safety boundary

FOS-Master's `corpus_reconcile.py` reinforces hash-based, read-only coverage reporting,
but it does not supply MasterBrain's tenant/run consistency model. This implementation
therefore records donor provenance while using the stricter shared DataCore receipt
boundary. No donor file, source file or FileOS database is modified.

Rollback stops writing/reading the additive ledgers and endpoint. It does not delete
their immutable rows. This tranche is not a scheduler, source cursor, automatic
rebuild, deletion policy, file effect, cutover or retirement decision.
