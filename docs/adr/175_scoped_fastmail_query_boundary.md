# ADR-175 — Bounded Fastmail query and metadata scope boundary

Status: accepted as a synthetic protocol primitive only. No live mailbox
enrollment, worker ingestion or private-source approval follows from this ADR.

## Context

The existing `sync-read` worker starts with an account-wide `Email/query` and
then uses account-wide `Email/changes`. Its iteration and byte limits do not
restrict which messages it may discover. A folder/date pilot cannot safely use
that worker by merely adding a filter to its first page: subsequent change
IDs, inventory reconciliation and existing cursors could escape the scope.

[RFC 8621 section 4.4.1](https://www.rfc-editor.org/rfc/rfc8621#section-4.4.1)
defines `inMailbox`, `after` (inclusive) and `before` (exclusive) filters for
`Email/query`. The server-side filter is necessary but not sufficient: returned
IDs must be checked against `Email/get` metadata before any blob download.

## Decision

- Add an immutable `ScopedMailWindow` requiring one exact opaque mailbox ID and
  whole-second UTC `after`/`before` timestamps spanning more than zero and at
  most 31 days. It builds only the three JMAP filter fields above.
- Allow `JmapReader.query_page` to take that typed scope. Every anchored page
  carries the same filter and the existing ascending `receivedAt` sort. The
  default unscoped method remains unchanged for existing synthetic callers.
- Add a fail-closed metadata predicate: `mailboxIds` must be a valid true-valued
  membership map, `receivedAt` must be a UTC timestamp, and both membership and
  the half-open time interval must match. A valid out-of-scope row returns
  false; malformed metadata raises a protocol error. A future pilot worker must
  call this before any raw message download, and must never treat false as an
  in-scope absence certificate.
- Do **not** connect this option to `ReadWorker`, its controller or CLI yet.
  The existing worker still performs account-wide reads. A follow-up must bind
  the exact window to durable account/cursor state, reject legacy/unscoped state
  for a scoped pilot, make resumed pages and reconciliation scope-safe, and
  replace or constrain account-wide changes. It must prove pause/revoke and
  no out-of-scope blob fetch with a synthetic provider and disposable database
  before a real Fastmail request is considered.

## Verification and rollback

Unit tests assert exact filtered first/anchored JMAP requests, strict window
validation, inclusive/exclusive edges, foreign mailbox rejection and malformed
metadata failure before download. Existing Fastmail/sync tests must remain
green; full CI, strict-runtime and restore gates apply before merge. Rollback
removes this unused primitive and its tests/docs; no stored state or provider
source is affected.
