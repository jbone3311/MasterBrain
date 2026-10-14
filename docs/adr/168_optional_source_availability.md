# ADR-168 — Optional Email and FileOS source availability

Status: accepted for the read-only current-search and extractive Ask response.

## Context

MasterBrain must operate with Email only, FileOS only, both or neither. Current
search already returns empty groups without error, but its static coverage labels
do not tell a client whether an empty group means no match or no registered
source. Existing per-source coverage reports current index/bridge readiness, but
it is a separate bounded read. A source grant must not reveal hidden sources.

## Decision

- Add `coverage.source_availability` with separate `email` and `fileos` values to
  current-search and Ask. Values are `registered`, `not_registered`,
  `not_available`, or `not_searched`.
- `registered` means at least one visible source of that kind exists. It does not
  promise a query match, current Email bridge, active FileOS generation, complete
  inventory, live provider connection, or fresh source bytes. The existing
  `/v1/brain/current-coverage` route reports per-source index/bridge readiness.
- Human tenant-wide reads may receive `not_registered`. Enrolled assistants get
  `not_available` when no granted source of that kind is visible, whether none
  exists or sources exist without grants. No identifiers or counts are returned.
- A focus-excluded kind is `not_searched`; the API does not query its availability.
  The existing layer keys, scopes, bounds and partial-coverage warning remain.

## Verification and rollback

Test all four source topologies, no-match versus unregistered, source-focus exclusion,
and hidden-source non-disclosure with disposable PostgreSQL and API tests. The
change is additive, read-only and requires no migration. Older clients ignore the
new field; rollback removes it without altering source/evidence state.
