# ADR-062 — Additive Email evidence bridge into DataCore

Status: accepted and verified for the additive prototype tranche on 2026-09-22.
Runtime revision `0eae4c4` plus least-privilege correction `bb4b45d` passed hosted
[CI 35734147533](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35734147533)
and [restore 35734147551](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35734147551).

## Context

The Email capability already has durable, immutable raw MIME, parser-versioned
message evidence and a mature search path. Replacing that path while introducing
shared DataCore identities would combine migration risk with behavior change. At the
same time, MasterBrain cannot provide a genuinely shared evidence layer until Email
versions can be represented by the same source, item, version, evidence, normalized
document, chunk and provenance primitives used by FileOS.

## Decision

Add a one-version-at-a-time bridge from an existing **current, visible** Email
`message_version` into DataCore. The operation is worker-only and requires both
existing `brain.source.ingest` and `brain.document.publish` scopes. It accepts an
explicit legacy evidence UUID, request UUID and code revision; it never scans an
account implicitly.

The bridge:

1. reads the immutable Email snapshot and retained raw-object digest under the same
   tenant transaction;
2. refuses deleted, quarantined, historical, missing or internally inconsistent
   versions;
3. derives opaque deterministic DataCore source/item/version/evidence/document/chunk
   identifiers without exposing the mailbox address or provider message identifier;
4. publishes a deterministic `email-message-v1` normalized body containing the
   legacy search fields (subject, sender and clean text);
5. records provenance and an append-only bridge receipt binding the legacy evidence
   UUID to every shared identity; and
6. is exactly replayable and rejects idempotency or parser-output drift.

The DataCore evidence row uses `inline` plus `retained=true`: the original bytes
remain in the existing forced-RLS `raw_objects` table and the bridge receipt is the
explicit link. No bytes are copied, and no raw-content route is added.

## Safety and compatibility

The existing Email tables, ingestion, search, citations and APIs remain authoritative.
The bridge adds no mailbox read/write permission, provider token access, scheduler,
automatic backfill, deletion propagation or attachment migration. DataCore's retained
search may expose a bridged version after the Email item later changes; a separate
current-Email projection and cutover decision are required before redirecting unified
search.

All bridge receipts use forced tenant RLS and append-only triggers. A unique legacy
version constraint prevents two mappings for one evidence version. The runtime role
receives only `SELECT` and `INSERT` on the receipt table; it receives no new update or
delete authority.

## Acceptance

Synthetic PostgreSQL tests must prove exact replay, drift rejection, current-version
and visibility fencing, deterministic searchable output, raw-byte non-duplication,
receipt/provenance closure, tenant isolation, immutability and transaction rollback.
Existing Email and FileOS suites must remain green. Hosted PostgreSQL, deployment,
documentation and populated restore gates are required before this tranche is marked
verified.

## Rollback

Stop invoking the bridge. Existing Email behavior is unchanged. Retained DataCore
rows and receipts are not deleted or down-migrated; they remain auditable and can be
excluded from reads until a corrective additive migration is accepted.
