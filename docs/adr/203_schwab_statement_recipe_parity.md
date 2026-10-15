# ADR-203 — Charles Schwab supplied-text recipe parity

Status: accepted for synthetic-only, isolated comparison. No live statement,
reviewed financial claim, FileOS policy switch or FOS-Master change is authorized.

## Context

FOS-Master's `_SYSTEM/tools/statement_extract.py` at commit
`218d5caec2f20b9047fd3eb8e027dc671acf0c15` (file SHA-256
`f5b0c8bc5c0c9f01fa8decdecba36a27b81ccfd212894409472bac8526b577fe`)
contains a distinct `charles_schwab_brokerage` recipe. It groups old-template
Bank Sweep/Cash, security holdings and three transaction sections, with
positionally paired `SYMBOL:` lines and inline money-market tickers. Its own
comments identify scanned statements and the redesigned late-2024 template
as unsupported, and describe a six-document Cash-and-Bank-Sweep patch of
which only one was individually rechecked. Those are donor observations, not
MasterBrain acceptance evidence. Existing MasterBrain statement recipes do not
implement this one.

## Decision

Copy only the deterministic parse/reconcile semantics into the isolated
`statement_recipe_parity` module, preserving row order, donor float and
confidence behavior, accounting-parentheses signs, symbol-zip mismatch
confidence, the heading variant and zero/fallback reconciliation. Do not
connect the recipe to runtime extraction, `StatementCandidate`, KnowledgeCore
publication or Brain API. Do not claim PDF/OCR source-to-text fidelity from
supplied-text parity.

Use fictional golden inputs for each distinct row shape, boundary and failure
mode. An optional local test loads only the exact-hash donor parser functions
and constants and compares complete ordered `(summary, rows, reconciliation)`
tuples, including a 1,000-row repeatability corpus. If a source fixture
cannot exercise an era or column layout, label that coverage explicitly; do
not convert a donor silent-empty result into a false successful holding.

## Verification and rollback

Run focused fictional tests, exact-hash local donor replay, stress, full local
gate, static/docs/browser checks and hosted full CI/runtime/restore before
merge. Keep the donor checkout unchanged. Rollback removes only this isolated
candidate and its tests/docs; no stored data or source effects require undo.
