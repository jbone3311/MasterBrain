# ADR-133 — Source-scoped Brain coverage and change feed

Status: accepted for synthetic/disposable implementation; hosted assistant acceptance remains open.

## Context

ADR-132 enrolls verified assistants in exact sources, but admits only current
search and evidence expansion. A client preparing a grounded answer needs to
know which *authorized* sources have current coverage and which changed. The
existing `/v1/brain/current-coverage` and `/v1/brain/changes` endpoints are
bounded but tenant-wide, so admitting assistants without filtering would leak
other source identifiers, counts, timestamps and change history.

## Decision

- Add `brain.changes.read` to the administrator-owned OIDC scope allowlist and
  all Brain-assistant eligibility fences. A status-only assistant still needs
  explicit same-tenant source enrollment. The legacy resolver continues to
  refuse these assistants during rolling upgrades; no older binary can turn
  the new scope into a tenant-wide read.
- Apply the source allowlist inside both status queries **before** ordering,
  limits and cursor construction. A cursor naming an ungranted source or event
  returns not found rather than revealing whether it exists. Pagination remains
  stable over the filtered sequence; status reads recheck binding revision and
  source grants in the same transaction.
- Expose only these two additional read routes to enrolled assistants. The
  other Brain and Knowledge routes remain denied until separately audited.
  Human owner semantics, FileOS/Email data, and FOS-Master are unchanged.
- Extend the provider-neutral read client with bounded coverage and change
  calls. Its URL and response checks are not a grant mechanism; the server is
  authoritative. Neither status route gives a model a write tool or raw
  database access.

## Threats, evidence and rollback

Test hidden-source omission, cursor probing, status-only OIDC binding, stale
saved context after partial/full revocation, wrong-tenant grants, bounded
pagination and client/API conformance on fictional Email/FileOS evidence.
Recheck the full PostgreSQL suite, migration, strict runtime, populated restore
and documentation before merge. Response caches and durable chat summaries are
not present; if later introduced, grant revision must key or invalidate them.

Rollback is forward repair: deny assistant status routes at the API, revoke
`brain.changes.read` and its grants as needed, and retain migration/audit
history. Never restore the old unfiltered assistant path. Hosted identity
enrollment, all-route review, cache revocation and a named assistant remain
[issue #88](https://github.com/jbone3311/MasterBrain/issues/88).
