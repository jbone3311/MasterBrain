# ADR-070 — Bounded current-source coverage status

Status: accepted for implementation.

## Context

`POST /v1/brain/current-search` deliberately reports partial coverage, but a client
cannot yet tell whether an empty group means no match, no activated FileOS generation
or no explicitly bridged current Email evidence. Existing per-source FileOS freshness
requires a known source ID and does not summarize active-generation readiness. Email
has no safe coverage read. Search must not guess completeness from an empty result.

## Decision

Add a separate `GET /v1/brain/current-coverage` endpoint requiring
`brain.changes.read`. It returns only DataCore sources already visible to the tenant,
ordered by opaque `source_id`, with a strict `limit` of 1–50 and an opaque existing-ID
cursor. It never enumerates provider mailboxes or filesystem paths.

Each source row contains `source_id`, `kind`, configured source `status` and a
kind-specific status:

- FileOS: `search_ready` only when the newest activation points to a ready immutable
  generation; otherwise `no_active_generation`. Include active generation ID,
  activation time, generation observation time, item/document/chunk counts and the
  latest completed-run observation/completion times when present. Report whether that
  latest completion is the run backing the active generation; do not calculate a
  policy-dependent “stale” threshold.
- Email: always label coverage `explicit_bridges_only`. Count only message,
  attachment and approved-document bridges that pass the same legacy visibility,
  deletion/quarantine and shared current-pointer fences as ADR-068. Include the newest
  current bridge time per family. Zero means no current bridged evidence, not an empty
  mailbox and not complete mailbox coverage.

The response declares `complete: false`, `generated_at`, pagination state and exact
semantics. Counts and timestamps come from one authorized database transaction, unlike
the independently read search layers. Paused sources remain visible in status but do
not gain search readiness; current search behavior remains unchanged in this tranche.

## Safety and compatibility

No locator, filename, mailbox/account identity, message metadata, content, query,
provider cursor or source discovery outside existing DataCore registration is exposed.
The endpoint performs no scan, bridge, rebuild, activation or provider/filesystem
access. Existing search, freshness and inventory routes are unchanged. Audit records
one status read without storing returned content.

## Acceptance and rollback

Unit/API tests must prove scope denial, closed limit/cursor validation, pagination and
the incomplete-coverage contract. PostgreSQL must prove FileOS no-generation and
active-generation states, latest-completion comparison, current Email family counts,
disappearance after parent update/delete/quarantine and tenant isolation. Existing
search and restore gates must remain green. Rollback removes only the new read method
and route; no schema migration or stored state is introduced.
