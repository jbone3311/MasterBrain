# ADR-170 — Isolated statement-recipe parity seed

Status: accepted for synthetic, nonpublishing comparison only.

## Context

FOS-Master's statement recipe factory stores grouped line items and reconciliation
outcomes. MasterBrain has no equivalent investment-analysis projection yet. Porting
an entire factory or connecting live statements before a recipe-level baseline
would make discrepancies hard to explain. ADR-169 calls for deterministic code and
exact decimal amounts in the eventual product.

## Decision

- Extract only the pure Streetbeat parse and reconciliation behavior into
  `statement_recipe_parity.py`. It is not imported by runtime intake, the database,
  Brain API or the owner workspace. It has no filesystem, network or database effects.
- Pin FOS-Master commit `218d5caec2f20b9047fd3eb8e027dc671acf0c15`, path
  `_SYSTEM/tools/statement_extract.py`, SHA-256
  `f5b0c8bc5c0c9f01fa8decdecba36a27b81ccfd212894409472bac8526b577fe`.
  Four fictional golden cases capture donor output, including a mismatch and
  malformed period. An optional local test loads only the pinned pure recipe AST
  nodes and compares donor and MasterBrain outputs, without importing donor DB code.
- Preserve donor semantics for this comparison, including float arithmetic,
  `long_value or total_market_value` fallback, and regex coverage. These are
  *known limitations*, not endorsements. A zero long value may fall back to a
  different total; a row the regex misses may produce false-looking agreement.
  No output may be called a verified holding, current investment or reviewed fact.
- Do not copy donor statement data, mutate FOS-Master, widen source access or
  run this against personal documents. The next tranche must add an explicit
  typed, decimal, evidence-linked model, source-tier/hash checks, reconciliation
  status, and broader fictional corpus under a separate ADR before integration.

## Verification, observability and rollback

The focused suite asserts exact donor-golden outputs, optional exact-hash donor
replay, and a 1,000-row deterministic stress case. A mismatch fails visibly with
the case name; no production telemetry is added because this module has no runtime
callers. The full repository gates must pass before merge. Rollback removes this
isolated module and its tests/docs; it changes no stored or source state. Donor
cutover and live alpha acceptance are unaffected.
