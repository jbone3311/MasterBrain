# ADR-198 — Wells Fargo brokerage recipe parity baseline

Status: accepted for synthetic, nonpublishing comparison only.

## Context

The pinned FOS-Master brokerage recipe reads a statement family with wrapped
security identities, multi-lot totals, single acquired lots, more-than-six-lot
summary rows, cash and activity. Some files sharing its filename family are
scanned, bank statements or incomplete tail fragments. A matching total in one
synthetic case cannot establish that all positions in a real account were read.
The known fixed-income description weakness is preserved as donor behavior.

## Decision

- Extract only the donor's pure regex, lookback, parse and reconciliation
  behavior into an isolated comparison module. Preserve row order, symbol/name
  lookback, page-break lot deduplication, missing-value behavior, confidence
  labels and the donor's `closing_value or asset_value` fallback. No runtime
  intake, proposal publication, Brain API or file effect may call it.
- Pin FOS-Master commit `218d5caec2f20b9047fd3eb8e027dc671acf0c15`,
  `_SYSTEM/tools/statement_extract.py`, SHA-256
  `f5b0c8bc5c0c9f01fa8decdecba36a27b81ccfd212894409472bac8526b577fe`.
  Optional local parity evaluates only exact-hash pure AST nodes, never the
  donor module, its database or a real statement.
- Use fictional goldens for cash, single and multi-lot holdings, page-break
  deduplication, more-than-six-lot rows, activity, incomplete/empty documents,
  zero-value fallback and mismatch. Compare ordered rows and reconciliation
  exactly against the pinned donor; add a 1,000-row repeatability stress case.

## Acceptance and rollback

Run fictional goldens, optional pinned-donor replay, full repository CI,
strict-runtime and populated-restore gates. Rollback removes the isolated
comparison code, tests and documentation only. No source, schema, API or
FOS-Master file changes. This baseline cannot authorize investment claims,
FileOS policy switching or donor retirement.
