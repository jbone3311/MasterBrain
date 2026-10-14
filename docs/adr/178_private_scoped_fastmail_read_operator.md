# ADR-178 — Private scoped Fastmail read operator

Status: implemented for synthetic/disposable verification. This is not approval
to read a private Fastmail mailbox or enroll a live source.

## Problem

ADR-176 has a scoped library worker and ADR-177 pins its SQL lease/cursor to an
unused account, but the only private command is version-1 `sync-read`. It remains
account-wide and refuses a pinned account. A trusted operator needs a bounded,
restartable way to supply the exact mailbox/date window without exposing a
provider URL, broad token, or bypass of the database pin.

## Decision

- Keep version-1 configuration unchanged and account-wide. Add a version-2
  private configuration requiring one closed `read_scope` object with an exact
  mailbox ID and canonical whole-second UTC `after`/`before` strings. The
  31-day half-open window and SHA-256 use ADR-175's `ScopedMailWindow`; no
  scope, extra fields, coerced values or alternate timestamp spellings pass.
- The same `sync-read` command preflight opens the authenticated, tenant-bound
  database and checks the configured window's fingerprint against the
  administrator-pinned account. It performs no lease claim or provider request.
  Version 1 continues to refuse pinned accounts; version 2 refuses unpinned or
  differently pinned accounts. No runtime role gains account UPDATE.
- On each poll and before/after each HTTP request, recheck identity, account
  binding, pause, pin and token. Construct `ReadWorker` with the typed scope;
  its lease and version-4 cursor remain fenced by ADR-177. Existing request
  bounds, scrubbed outcomes, stop and retry behavior remain unchanged.
- Configuration-file changes require restart, as in version 1. SQL account
  disable, owner/credential revocation and token rotation still fail closed
  during a step. A separate reviewed enrollment workflow must pin the account
  before a real provider read; this code does not automate enrollment.

## Verification and rollback

Pure tests must reject malformed version/scope and show preflight has no client
or claim. Disposable PostgreSQL plus fictional HTTPS tests must prove exact
scope restart, no account-wide change request, no out-of-scope blob, wrong pin
before provider I/O, mid-step revocation, tenant isolation and unchanged v1
behavior. Full CI, strict-runtime and populated restore apply. Rollback stops
the scoped command but retains the pin, additive schema and version-4 cursor;
never launch an old unscoped worker on a pinned account.
