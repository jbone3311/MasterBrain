# ADR-174 — Fidelity statement recipe parity baseline

Status: accepted for synthetic, nonpublishing donor comparison only.

## Context

ADR-170 pinned one clean, single-column Streetbeat recipe. The donor also has a
Fidelity brokerage recipe for flattened two-column PDF text. Its own comments
warn that interleaved rows can be missed; the resulting reconciliation mismatch
is a coverage signal, not evidence that the remaining rows are complete. A
second recipe baseline is needed before changing extraction or building a
cross-source investment dossier.

## Decision

- Copy only the donor's pure Fidelity parse and reconciliation semantics into
  the isolated `statement_recipe_parity.py` module. Preserve regexes, row order,
  duplicate key, float arithmetic, percentage label, confidence values, and
  `total_holdings or ending_account_value` fallback. This module still has no
  runtime intake, database, Brain API, workspace or source-effect caller.
- Pin FOS-Master commit `218d5caec2f20b9047fd3eb8e027dc671acf0c15`, path
  `_SYSTEM/tools/statement_extract.py`, SHA-256
  `f5b0c8bc5c0c9f01fa8decdecba36a27b81ccfd212894409472bac8526b577fe`.
  The optional local test loads only the pinned pure AST nodes, never donor
  imports, filesystem scanning, database writes or real statements.
- Use fictional goldens for a balanced statement, duplicate detail row,
  interleaved missed row, zero-total fallback, invalid period and empty text.
  A 1,000-distinct-row deterministic case tests bounded corpus scale. The
  baseline intentionally retains missed rows, weak confidence, and the zero
  fallback oddity. These are documented donor behavior, not correctness claims.
- Do not let this low-confidence recipe feed ADR-171/172's Streetbeat-only typed
  candidate or proposal ledger. A later separate decision must define typed
  Fidelity rows, source-byte-to-text proof, explicit incomplete-coverage
  handling, review policy and owner acceptance before any publication.

## Verification and rollback

Exact fictional golden outputs and optional exact-hash donor replay must match
summary, ordered rows and reconciliation, including the known missed-row case.
The full repository, strict-runtime and restore gates apply before merge. No
real account or source document is read by the tests. Rollback removes the
Fidelity functions, tests and this decision; it changes no stored or source
state. FOS-Master remains unchanged and is not eligible for cutover.
