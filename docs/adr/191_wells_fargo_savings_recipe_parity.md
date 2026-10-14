# ADR-191 — Wells Fargo savings recipe parity baseline

Status: accepted for synthetic, nonpublishing donor comparison only.

## Context

The pinned FOS-Master savings recipe infers transaction direction from printed
daily-balance changes, not from an unsigned amount or a guessed description.
Same-day groups can mix deposits and withdrawals; the donor first uses clear
direction words, then a bounded subset-sum residual. Ambiguous or missing
balance cases deliberately yield low-confidence defaults that may fail
reconciliation. MasterBrain must preserve those behaviors before considering
this statement family for typed intake or financial answers.

## Decision

- Copy only the pure regex, keyword, daily-group sign resolution, parse and
  reconciliation semantics into the isolated `statement_recipe_parity.py`
  comparison module. Preserve ordered transaction rows, donor confidence
  levels, the twelve-unknown subset-search cap, missing-balance defaults,
  summary fields and floating-point reconciliation behavior. Do not call this
  recipe from runtime ingestion, KnowledgeCore, Brain API or effects.
- Pin FOS-Master commit `218d5caec2f20b9047fd3eb8e027dc671acf0c15`,
  `_SYSTEM/tools/statement_extract.py`, SHA-256
  `f5b0c8bc5c0c9f01fa8decdecba36a27b81ccfd212894409472bac8526b577fe`.
  Optional local parity evaluates only exact-hash pure AST nodes; it never
  imports the donor module, opens its database or reads a real statement.
- Use fictional goldens for single-row balance deltas, same-direction groups,
  mixed keyword/residual resolution (including misleading transfer wording
  and wire originator/beneficiary tags), uniquely forced and ambiguous subset
  cases, missing daily balance, absent beginning balance, malformed period,
  and 1,000-row repeatability. Preserve a mismatch visibly; do not coerce it
  into a verified account balance or holding.

## Verification and rollback

Run fictional goldens, optional pinned-donor replay, full repository CI,
strict-runtime and populated-restore gates. Rollback removes only the isolated
comparison functions, tests and documentation. No schema, API, source state or
FOS-Master file changes; this baseline cannot authorize FileOS cutover.
