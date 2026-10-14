# ADR-181 — Morgan Stanley statement recipe parity baseline

Status: accepted for synthetic, nonpublishing donor comparison only.

## Context

The pinned FileOS donor's Morgan Stanley recipe receives mostly OCR-derived
text. Its bank-deposit detail can be a sub-component of the cash/BDP/MMF
bucket; adding both rows would double-count money. OCR can also corrupt a
leading activity date, silently dropping a transaction. MasterBrain must
preserve and measure these donor behaviors before designing a better typed
extractor or an investment dossier.

## Decision

- Copy only the donor's pure regex, parse and reconciliation behavior into
  `statement_recipe_parity.py`. Preserve OCR-marker confidence, ordered cash
  bucket/detail/transaction rows, parenthesized debit sign, cash-detail
  exclusion from reconciliation and the known `or` zero-total fallback.
- Pin FOS-Master commit `218d5caec2f20b9047fd3eb8e027dc671acf0c15`,
  `_SYSTEM/tools/statement_extract.py`, SHA-256
  `f5b0c8bc5c0c9f01fa8decdecba36a27b81ccfd212894409472bac8526b577fe`.
  Optional local replay evaluates only pinned pure AST nodes; it does not
  import the donor module, access its database or read any real statement.
- Use fictional goldens for a cash bucket with bank-detail sub-component,
  parenthesized activity, OCR marker and corrupted date, missing bucket,
  unknown month, zero fallback and empty text. Always run a 1,000-row
  deterministic stress case, including in hosted CI.
- Keep this a nonpublishing comparison. It does not run OCR, establish
  source-byte-to-text proof, feed statement proposals, verify a holding or
  authorize an investment total. A better recipe must explicitly report
  uncaptured activity and avoid treating a matched bucket as complete assets.

## Verification and rollback

All fictional ordered outputs and reconciliation values must match exact-hash
donor replay locally. The full repository, strict-runtime and populated
restore gates apply before merge. No migration or source effect is involved;
rollback removes only these functions, tests and documentation. FOS-Master
remains unchanged and ineligible for cutover on this evidence alone.
