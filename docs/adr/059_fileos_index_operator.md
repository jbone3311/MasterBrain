# ADR-059 — Explicit private FileOS index generation operator

Status: accepted for implementation; hosted verification pending.

## Decision

MasterBrain adds a private `fileos index` operator command with two explicit modes:
build-and-activate one generation for an exact completed run, or activate an existing
ready generation for rollback. It uses a closed, owner-private configuration, a
runtime-only least-privileged PostgreSQL DSN, an expiring worker credential and an
actor-scoped UUID idempotency key for activation.

Build mode requires exactly `brain.document.publish` and `brain.index.activate`.
Activation-only mode requires exactly `brain.index.activate`. The controller checks
the database role and local identity without consuming the request in `--check` mode,
then reauthenticates between build and activation and after completion. A crash after
build but before activation leaves an immutable ready generation that the same command
can safely reuse.

The command returns only the source and generation identity, bounded counts, receipt
times and replay flags. It never returns normalized text, source paths, credentials,
database diagnostics or original bytes. Both modes state `source_effects: false`.

## Boundary and rollback

This is an explicit one-shot operator, not a scheduler, public API mutation or global
search switch. The completed run must already exist; build does not scan or reprocess
source files. Rollback is activation-only selection of a prior ready generation using
a fresh idempotency key.

Acceptance requires closed-config, exact-scope, check-mode, revocation, privileged-DSN,
build replay, activation replay/conflict and prior-generation rollback tests on hosted
PostgreSQL. Removing the private configuration or credential disables the operator;
existing immutable records remain.
