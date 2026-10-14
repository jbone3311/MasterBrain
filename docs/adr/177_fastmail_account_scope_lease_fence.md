# ADR-177 — Account-bound Fastmail scope and lease fence

Status: implemented for synthetic/disposable PostgreSQL verification. No live
enrollment or private provider read is authorized by this record.

## Problem

ADR-176's version-4 cursor prevents an opted-in worker from resuming a different
scope, but an empty account has no cursor yet. An old `sync-read` binary can
acquire that account and run account-wide. A scoped worker's crashed, expired
lease is also vulnerable if an old binary can take it over without presenting
the selected scope. The database needs to reject that path before provider I/O.

## Decision

- The enrollment administrator may pin one SHA-256 of the exact ADR-175
  canonical mailbox/date filter on a previously unused Fastmail account.
  Changing that pin is refused once an Email worker, cursor, message state,
  provider event or raw evidence exists. Runtime roles have no account UPDATE.
- `SyncStore.acquire` compares the requested typed window fingerprint with the
  account pin before creating a worker row or lease. It writes the pin into the
  worker and a new `scope_claim_token` equal to each fresh lease token.
- A database trigger requires the worker pin to equal the account pin and, for
  a live scoped lease, the claim token to equal the lease token. An old worker
  that omits the new fields fails both on first insert and on takeover after a
  crashed lease. An unscoped account continues to use NULL scope fields.
- Cursor writes for a pinned account must carry a version-4 checkpoint with
  the exact pin. A version-4 cursor is refused on an unpinned account. Evidence
  and cursor still commit in one transaction. The existing unscoped operator
  refuses a pinned account during preflight, before client construction; the
  database acquisition independently denies it.
- Controller configuration and owner-reviewed enrollment/revocation are separate
  gates. This tranche does not make a real Fastmail pilot safe or available.

## Proof and rollback

Disposable PostgreSQL tests cover fresh pinning, prior-state refusal,
unscoped/changed-scope acquisition before provider I/O, old-binary insert and
crash takeover refusal, exact scoped lease/cursor success, direct-SQL cursor
drift refusal, tenant isolation and unscoped regression. Restore and full CI
remain required. Roll back by stopping scoped workers; keep the additive
columns, triggers and any version-4 cursors. Never down-migrate or discard
evidence to re-enable an old worker.
