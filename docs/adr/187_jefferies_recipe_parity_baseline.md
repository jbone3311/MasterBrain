# ADR-187 — Jefferies statement recipe parity baseline

Status: accepted for synthetic, nonpublishing donor comparison only.

## Context

The pinned FOS-Master Jefferies recipe has three different row granularities:
category holdings, best-effort security detail and transactions. Category
totals, including negative cash/margin values, drive reconciliation. Security
details must not be summed again; a multi-lot security uses its grand-total
line rather than a partial lot or covered subtotal. Some positions have no
numeric value, and wrapped transaction continuations are not captured. A
MasterBrain investment dossier must understand those coverage limits before
using this recipe as evidence of a holding.

## Decision

- Copy only the pure regex, parse and reconciliation behavior into the isolated
  `statement_recipe_parity.py` comparison module. Preserve ordered row kinds,
  negative category values, subtotal skipping, multi-lot flush behavior,
  transaction quantity/price splitting, confidence labels, float arithmetic
  and the donor's `total_portfolio_market_value or ending_account_value`
  fallback. The Jefferies functions have no runtime caller or path to storage,
  Brain API, review or source effects. The shared module's older Streetbeat
  regex constants are separately used by the private Streetbeat projector.
- Pin FOS-Master commit `218d5caec2f20b9047fd3eb8e027dc671acf0c15`,
  `_SYSTEM/tools/statement_extract.py`, SHA-256
  `f5b0c8bc5c0c9f01fa8decdecba36a27b81ccfd212894409472bac8526b577fe`.
  An optional local test evaluates only those exact-hash pure AST nodes; it
  never imports the donor module, opens its database or reads a real statement.
- Use fictional goldens for negative cash, multi-lot/subtotal handling,
  single-lot detail, uncaptured `N/A` value, two-date and one-date transactions,
  wrapped continuation loss, zero fallback, invalid period and empty text.
  Add a 1,000-row deterministic stress/repeatability case and compare ordered
  outputs and reconciliation to the pinned donor.
- A matched category total is not a complete portfolio or a verified amount.
  The lower-confidence detail rows can miss positions; the original donor
  comments reflect a limited sample, not a general coverage guarantee. Do not
  convert this baseline into a typed proposal or investment claim without a
  separate source-byte derivation, completeness, currency and human-review ADR.

## Verification and rollback

Exact fictional goldens, optional pinned-donor replay, full repository CI,
strict-runtime and populated-restore gates must pass. Rollback removes only
these pure comparison functions, tests and documentation. No migration or
source state changes; FOS-Master stays unchanged and cannot be cut over based
on this evidence.
