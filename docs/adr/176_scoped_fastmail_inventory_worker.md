# ADR-176 — Scoped Fastmail inventory worker, before enrollment

Status: accepted as a synthetic-only worker tranche. It does not authorize a
private Fastmail request, account enrollment, or a scoped `sync-read` command.

## Context

ADR-175 can issue a typed mailbox/date `Email/query` and check `Email/get`
metadata, but the existing worker uses an account-wide `Email/changes` cursor.
Applying only the query filter would permit later account-wide IDs to reach the
download path. The existing account and SQL cursor are not yet bound to a scope.

## Decision

- A worker explicitly constructed with one `ScopedMailWindow` uses version-4
  checkpoints carrying the SHA-256 of the exact canonical query filter.
  It refuses legacy, unscoped, or differently scoped checkpoints before a JMAP
  request; the account-wide worker refuses version-4 checkpoints.
- The scoped worker does not call `Email/changes` or capture an account-wide
  `Email/get` state. It repeatedly makes only filtered, anchored inventories.
  A completed inventory is durably sealed before reconciliation. After the
  bounded reconciliation pass, a new generation starts; `caught_up` means one
  observed pass completed, not a point-in-time snapshot or continuous freshness.
- Every returned metadata row must independently satisfy the exact mailbox and
  half-open UTC date window before a blob download or retained-blob reuse.
  Malformed or out-of-scope rows pause with a protocol error; no page commits.
  Provider `notFound` remains an accounted tombstone, not an out-of-scope claim.
- The scoped worker is intentionally **not** connected to the operator
  configuration or a live enrolled account. A later migration and controller
  change must bind the exact scope to the account/lease/cursor in PostgreSQL,
  prevent old workers from reading a scoped account, refuse preexisting
  unscoped evidence, and prove pause/revoke and restart against a disposable
  database and fictional HTTPS provider. Until then `sync-read` is account-wide.

## Tradeoff, verification, rollback

Repeated filtered inventories cost more query work than query-state deltas and
may observe a moving mailbox. They avoid account-wide change IDs for the bounded
pilot; a separate queryChanges design could follow after measuring load and
correctness. Synthetic tests cover filter propagation on repeated scans, cursor
identity, no account-wide protocol call and pre-download metadata refusal.
The existing unscoped suite must remain green. Rollback stops the unused scoped
library caller and retains any version-4 cursor; old workers cannot interpret it.
No source effect, SQL migration, or donor FileOS change is part of this tranche.
