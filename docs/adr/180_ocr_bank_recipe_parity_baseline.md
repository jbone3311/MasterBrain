# ADR-180 — OCR bank-statement recipe parity baseline

Status: accepted for synthetic, nonpublishing donor comparison only.

## Context

Streetbeat and Fidelity parity cover brokerage text, but the FOS-Master donor
also parses image-only bank statements after OCR. The OCR bank recipe
groups debit and credit rows by date anchor because OCR can wrap an amount onto
a separate line. A line-only extractor would silently lose such a transaction.
The donor also assigns transaction years from statement boundary dates, so a
December-to-January rollover must not become a January-year debit.

## Decision

- Copy only the donor's pure section splitting, row grouping, date assignment,
  parsing and reconciliation semantics into the isolated comparison module.
  Preserve row order, optional/invalid date behavior, category recognition,
  float arithmetic and reconciliation mismatch. The only intentional syntactic
  difference is `zip(..., strict=True)`: Python's regex split always yields one
  chunk per captured date, so this is equivalent for all inputs.
- Pin FOS-Master commit `218d5caec2f20b9047fd3eb8e027dc671acf0c15`,
  `_SYSTEM/tools/statement_extract.py`, SHA-256
  `f5b0c8bc5c0c9f01fa8decdecba36a27b81ccfd212894409472bac8526b577fe`.
  Optional local replay loads only the pure, pinned AST nodes; it does not
  import the donor module, scan files, use a database, or access real statements.
- Use fictional golden cases for wrapped OCR amounts, year rollover, mismatch,
  empty text and invalid dates. Compare all ordered rows, summary and
  reconciliation with the pinned donor; add a 1,000-row deterministic stress
  case. No real account number or statement content belongs in Git.
- Do not connect this baseline to runtime OCR, statement proposals, KnowledgeCore
  or Brain API. OCR text correctness, source-byte derivation, bank-account
  review and statement coverage require separate acceptance before publication.

## Verification and rollback

The fictional goldens and exact-hash donor replay must pass before merge, then
the full repository, strict-runtime and restore gates apply. Removing these
pure functions and tests changes no persisted or source data. FOS-Master
remains unchanged; this comparison does not authorize cutover.
