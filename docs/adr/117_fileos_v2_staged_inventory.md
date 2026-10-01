# ADR-117 — Persist a nonpublishing FileOS v2 inventory shape

Status: accepted for synthetic/disposable staging only.

## Context

Snapshot v1 and its completed-run ledger require a source version and SHA-256 for
every item. The pinned FOS-Master scanner can instead report a metadata-only
observation (`no_hash`, `dataless`, or `oversize`). Giving such an observation a
fabricated source version would make it eligible for evidence, indexing or absence
logic that its bytes cannot support. ADR-115/116 retain a reviewed candidate, but
that JSON packet is not a relational inventory model.

## Decision

- Add a separate, immutable v2 **staging** inventory and row ledger. A staged
  inventory references one sealed transition packet and its exact completed-v1
  receipt. It is always nonpublishing and requires review. No current-source,
  freshness, absence, index or search query may consume it.
- Store hashed observations with their real digest and deterministic candidate
  version ID. Store deferred observations with size and reason, but with **NULL**
  version, digest and media type. Store exclusions and scan errors separately in
  the same closed row ledger. Never turn an unobserved or excluded prior v1 item
  into absence evidence during staging.
- Validate the packet's canonical digest, candidate counts and row shapes before
  insertion. Under the source completion advisory lock, require the packet's v1
  receipt and source root binding still to be latest and exact. One packet can be
  staged once; same-ID replay is idempotent, alternate-ID replay is refused.
- Force tenant RLS and tenant-login fencing. Deny row mutation and truncation.
  Insert rows before the header in one transaction; a source-locked trigger
  refuses inserts after the header exists. One deferred header constraint
  checks all four ledger counts at commit, avoiding a full recount per row.
  Grant only
  the existing private runtime SELECT/INSERT surface; no CLI, Brain API or
  assistant route is added. Record only opaque stage IDs in create/replay audit
  events; no locator or source content enters routine telemetry.
- Keep snapshot v1 publication, FOS-Master and source files unchanged. A later
  ADR must define owner approval, the v1-to-v2 transaction, v2 freshness and
  absence semantics, rollback, live shadow and cohort cutover.

## Verification and rollback

Disposable PostgreSQL tests cover hashed/deferred/exclusion/error rows, replay,
3,000 hashless rows, stale receipt, wrong tenant, row-shape constraints, ledger
balance, late-insert refusal, immutability and nonpublication. Full CI, strict runtime, populated restore and pinned donor
parity gate merge. Rollback stops staging; immutable staged evidence remains for
provenance and v1 behavior is unchanged.
