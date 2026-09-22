# ADR-067 — Private Email attachment and document bridge operator

Status: accepted for implementation; hosted verification pending.

## Context

The current private Email bridge command can publish one selected message version.
ADR-065 and ADR-066 add safe library paths for one attachment occurrence and one
approved PDF derivative, but those paths are not yet available through an explicit
operator command. A batch scan would be premature because legacy Email remains
authoritative and current/source parity is still being established.

## Decision

Extend the existing private Email bridge controller and `masterbrain email` command
family with two operations: bridge one explicit attachment-receipt UUID or bridge one
explicit approved document-extraction UUID. Both reuse the same closed versioned
configuration, owner-private credential/token files, environment-only DSN and exact
`brain.source.ingest` plus `brain.document.publish` worker scopes.

Each command authenticates before database preflight, reauthenticates before the
transaction and again after it. `--check` is non-consuming and validates configuration,
identity and database access without inspecting the target UUID or constructing the
DataCore repository. Output is content-free: operation, opaque shared IDs, bounded
counts/status and whether a receipt was newly recorded.

## Safety and compatibility

Errors remain scrubbed. The commands cannot enumerate Email, ingest mail, approve a
document, read MIME/original bytes, call a provider, schedule work or mutate a mailbox.
They add no scope, schema or source effect. The underlying ADR-065/066 transactions
retain current-version, approval, idempotency, RLS and append-only enforcement.

## Acceptance and rollback

Unit tests must prove non-consuming checks, exact dispatch, exact scopes, revocation,
closed private configuration and scrubbed errors for every operation. PostgreSQL tests
must execute the attachment and approved-document commands and prove shared search plus
unchanged legacy evidence. Existing suites and populated restore must remain green.
Rollback removes command routing; immutable receipts already created remain auditable.
