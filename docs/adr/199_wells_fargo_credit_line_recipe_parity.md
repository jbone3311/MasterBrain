# ADR-199 — Wells Fargo credit-line recipe parity baseline

Status: accepted for synthetic, nonpublishing comparison only.

## Context

FOS-Master reads Wells Fargo Advisors Priority Credit Line statements as a
loan ledger, not a bank credit limit or an investment holding. Its two text
shapes have different row order and spacing. The summary reports debt as a
positive amount, while activity rows use a debt-negative running balance.
The donor also scopes the activity table before a separate linked bank-deposit
section. Losing that scope or guessing a repayment sign can produce a plausible
but wrong reconciliation.

The donor documents PDF extraction failures for this statement family and a
later PyMuPDF-shaped fallback. Matching its parser on supplied text does not
prove that MasterBrain can obtain complete text from an actual PDF. That
source-to-text gate remains separate.

## Decision

- Pin FOS-Master commit `218d5caec2f20b9047fd3eb8e027dc671acf0c15`,
  `_SYSTEM/tools/statement_extract.py`, SHA-256
  `f5b0c8bc5c0c9f01fa8decdecba36a27b81ccfd212894409472bac8526b577fe`.
  Extract only pure parsing, fallback and reconciliation behavior into the
  isolated comparison module. Do not call it from intake, proposal publication,
  the Brain API or a file effect.
- Preserve the donor's two text shapes, signed balance conventions, optional
  summary fields, open-ended transaction labels, activity-section boundary,
  fallback trigger and confidence/extraction-method labels. Preserve known
  shortcomings as comparison outcomes rather than silently improving them.
- Compare fictional ordered summaries, rows and reconciliation against an
  optional exact-hash donor AST replay. Cover payments, draws, interest,
  overpayment, missing optional fields, linked-bank exclusion, page breaks,
  fallback rows, incomplete text and a 1,000-row repeatability stress case.

## Acceptance and rollback

Focused goldens and optional donor replay, the full repository gate, strict
runtime and populated restore must pass before merge. Rollback removes this
isolated comparison code, tests and documentation; it changes no source,
schema, API or FOS-Master file. It cannot authorize a verified loan balance,
investment claim, FileOS policy switch or donor retirement.
