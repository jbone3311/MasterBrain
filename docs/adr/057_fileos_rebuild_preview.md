# ADR-057 — Read-only deterministic rebuild preview

Status: accepted and verified for the additive prototype tranche on 2026-09-22.
Revision `0653a35` passed hosted
[CI 35720358559](https://github.com/jbone3311/MasterBrain/actions/runs/35720358559)
and [restore 35720358811](https://github.com/jbone3311/MasterBrain/actions/runs/35720358811).

## Decision

Before DataCore gains any rebuild executor, it exposes a bounded, read-only preview
over the latest completed FileOS inventory. The preview takes the same per-source
transaction lock as completion, so one response cannot mix two inventory runs. Its
cursor must belong to that exact latest run.

For each requested item, DataCore resolves the evidence and newest normalized
document, recomputes the body digest, deterministic document identity, chunk
boundaries, chunk digests and chunk identities, and compares them with stored rows.
The compact result is `verified`, `rebuild_required`, or
`source_reprocess_required`. It returns opaque identities and counts only—never source
paths, normalized text or chunk text.

The endpoint is `GET /v1/brain/sources/{source_id}/rebuild-preview`, requires
`brain.changes.read`, limits pages to 50 items and audits access. The response states
that both source and DataCore effects are false. It neither creates jobs nor changes
documents, chunks, visibility, receipts, cursors, evidence or source files.

## Failure and next boundary

Unknown, stale or cross-source page cursors fail closed. A source without a completed
run returns an explicit empty state. A later execution tranche requires a separate
ADR, idempotent generation identity, failure/rollback contract and parity tests; this
preview is not authorization to mutate an index.
