# ADR-192 — Exact evidence quotes for proposed project aliases

Status: accepted for synthetic/disposable proposal batches only. This is not a
general certificate that historical reviewed assertions have verified quotes.

## Context

ADR-182 gives each reviewed project alias its own evidence ID and source quote.
ADR-186 checks a proposal's main quote against current, granted, nonexcluded
normalized evidence at stage, preview and review, but did not check the separate
alias quotes. A fictional alias could therefore pass the proposal queue with an
invented quote. This matters before a citation-bearing Librarian export.

## Decision

- For every proposed project alias, require its exact `source_quote` to occur in
  the normalized document of its *own* declared evidence ID. The existing
  schema already requires that ID to be in the project's evidence set. The
  main proposal check first establishes that the entire set is same-tenant,
  current, active, granted and nonexcluded; the alias check remains in the same
  transaction and is re-run during preview and human review.
- Check exact substrings in PostgreSQL; return no source text, quote excerpt or
  existence detail for an inaccessible evidence ID. A mismatch rejects the
  whole staged batch or review transaction. No model decides quote validity.
- Do not change the older direct `POST /v1/knowledge/assertions` publication
  contract in this tranche. That route checks evidence membership, not exact
  quotes. Existing reviewed history must not be described as citation-verified
  merely because newer proposals pass this gate. A full Markdown exporter must
  independently verify every displayed citation against currently authorized
  evidence and handle unavailable historical quotes explicitly.

## Verification and rollback

Use fictional normalized Email evidence in disposable PostgreSQL. Reject an
invented alias quote with no batch row; reject a quote found only in another
linked evidence item; accept a real exact span; retain the
existing stale/excluded/source-grant, atomic review and replay tests. The full
repository, strict-runtime and restore gates still apply before merge. Rollback
disables project aliases in proposal batches while retaining immutable staged
and reviewed history; do not delete source evidence or change FOS-Master.
