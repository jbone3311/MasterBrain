# ADR-079 — Require a private one-member operator before archive text publication

Status: accepted and implemented in `257ab30`, with operator-specific negative and
PostgreSQL acceptance coverage completed in `d66de6e`.

## Context

Checkpoint 4Q deliberately provides an internal persistence primitive, not unattended
authority. A public route, directory scan or automatic manifest loop would convert a
one-member safety boundary into archive-wide fan-out and would expose source bytes to a
long-lived service.

## Decision

Add one owner-private command using the established local worker identity and runtime
database preflight. Bind it to one immutable archive image, one configured FileOS root,
one inventory ID, one member locator and one idempotency key. Reauthenticate before
source access, before publication and before returning. Keep `--check` non-consuming
and content-free.

The operator composes existing checkpoint 4P read and 4Q publication contracts; it
does not duplicate their path, hash, RLS, currency, normalization or replay logic.

## Alternatives rejected

- Public Brain API mutation: expands the network attack surface and service authority.
- Archive-wide batch: defeats explicit member selection and complicates partial
  failure/retry semantics.
- Host-side directory extraction: introduces writable staging and path cleanup risk.
- Returning text or bytes from the command: leaks content into terminals and logs.

## Rollback

Remove the command/controller. Existing inventories, member reads and already-published
append-only derivatives remain valid and searchable as retained history. No source or
FOS-Master state is changed.
