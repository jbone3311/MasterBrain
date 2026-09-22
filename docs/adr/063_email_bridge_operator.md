# ADR-063 — Private one-version Email bridge operator

Status: accepted for implementation; hosted verification pending.

## Decision

Add `masterbrain email bridge` as a private, one-shot command for one explicitly
selected legacy Email evidence UUID. The command accepts a private closed config,
an idempotency UUID and the evidence UUID. Its worker identity must contain exactly
`brain.source.ingest` and `brain.document.publish`; it receives no `email.ingest`,
provider, mailbox-write or original-content scope.

The configuration contains only version, private credential/token paths and a bounded
code revision. The database DSN remains an environment secret. Authentication and the
least-privileged database role are checked before execution, then identity files are
re-read immediately before and after the transactional bridge call. Output is limited
to opaque shared identities, chunk count, replay state and explicit no-source-effect
flags; it never emits subject, sender, body, address, provider ID or raw MIME.

`--check` verifies closed configuration, exact worker identity and safe database
connectivity without reading the target evidence or writing data. It reports that
execution was not verified. The normal command delegates all current-version,
visibility, snapshot, race, idempotency and provenance enforcement to the verified
ADR-062 bridge transaction.

## Boundaries

This command performs no discovery, account scan, scheduling, batching, attachment
bridge, ingestion, provider call, Email search redirect or API mutation. An operator
must select each evidence UUID explicitly. Existing Email ingestion/search remains
authoritative, and DataCore retained search remains historical until a separately
accepted current-Email projection exists.

## Acceptance and rollback

Tests cover check-mode non-mutation, closed/private configuration, exact scopes,
scrubbed errors/output, replay and identity revocation. Real PostgreSQL proves command
publication and search without changing legacy rows. Rollback is to stop the command;
immutable evidence and receipts remain auditable.
