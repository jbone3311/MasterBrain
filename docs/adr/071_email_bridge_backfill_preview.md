# ADR-071 — Private Email bridge backfill preview

Status: implemented and hosted-verified in runtime revision `4c3347c`; current-version
transition assertion corrected in `e9cf62f`.

## Context

The private bridge command safely migrates one explicitly selected current Email
version, but selecting many versions is currently manual. An automatic executor would
be unsafe before selection order, paging, replay and current-state races are observable.
Ordinary Brain clients must not gain mailbox enumeration merely to support migration.

## Decision

Add `masterbrain email bridge-plan` as a private operator command. It requires the
existing closed Email bridge config, the existing exact worker scopes, one explicit
account UUID, a limit of 1–100 and an optional cursor naming an existing version in
that account. `--check` remains non-consuming and does not inspect the account.

Normal execution performs one read-only tenant transaction. It selects only versions
that are current by raw hash/parser version and whose parent message is neither deleted
nor quarantined. Results are ordered by `(recorded_at, version_id)` and contain only the
legacy version UUID, recorded time and `already_bridged` boolean. The page returns an
opaque next cursor, requested limit, `source_effects: false` and `data_effects: false`.
It exposes no subject, sender, recipients, message body, provider identifier, folder,
attachment metadata or shared locator.

An absent account or cursor fails closed. The preview never reserves work and is not
execution authority: every later single-item or batch bridge must reauthenticate and
recheck current legacy/shared state inside its own transaction. A later executor may
consume only an explicit immutable plan contract introduced by a separate ADR; this
tranche adds no looping writes or scheduler.

## Safety and compatibility

The command is not an HTTP/Brain API route. It contacts no provider, changes no
mailbox, creates no DataCore row and advances no cursor. Existing one-item bridge
commands and their idempotency behavior remain unchanged. Errors and output remain
content-free.

## Acceptance and rollback

Tests must prove exact scopes, non-consuming `--check`, closed account/cursor/limit
validation, stable pagination, already-bridged labeling, update/delete/quarantine
exclusion, revocation checks, tenant isolation and content-free output. Hosted
PostgreSQL and restore must remain green. Rollback removes only the read method and
operator subcommand; no schema or evidence changes are involved.
