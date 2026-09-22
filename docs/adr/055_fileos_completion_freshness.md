# ADR-055 — Append-only FileOS completion and freshness

Status: accepted and verified for the additive prototype tranche on 2026-09-22.
Runtime revision `1e0f87e` plus test correction `c12800f` passed hosted
[CI 35716362139](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35716362139)
and [restore 35716362094](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35716362094).

## Decision

An imported snapshot is not a completed FileOS run. DataCore writes an append-only
`brain_fileos_run_receipts` row only after every manifest item has a terminal
extraction outcome. The receipt binds tenant, actor, request UUID, source, observation
time, canonical manifest SHA-256, code revision, text extractor, optional immutable
document-processor version, item/outcome counts and published-document count.

Completion requires the exact actor/request intake receipt and manifest digest.
Outcome keys are closed; positive counts must sum to the manifest item count, and the
published count must equal `extracted`. Database constraints repeat those checks.
Receipt replay returns the original completion time; conflicting outcome or provenance
is refused. Rows use forced RLS and the common immutable-evidence trigger.

The Brain API exposes `GET /v1/brain/sources/{source_id}/freshness` under
`brain.changes.read`. It returns the latest complete receipt or an explicit
`no_completed_run`; partial prefixes are never represented as complete. The response
contains no root, locator, content, token, DSN or parser diagnostics.

## Failure and rollback

A crash before completion may leave idempotent intake/documents but no completion row.
Retrying the exact snapshot and UUID converges, then records one receipt. Rollback
stops writing/reading the additive table and endpoint; immutable evidence and donor
operation are unaffected. This does not yet provide a scheduler, source cursor,
deletion reconciliation, SLA threshold or live-shadow acceptance.
