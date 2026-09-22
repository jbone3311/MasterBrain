# MasterBrain Architecture

Updated 2026-09-21. This document defines the target boundaries and migration
constraints. [Implementation status](IMPLEMENTATION_STATUS.md) separates working code
from designs. Existing detailed Email documents describe the Email capability.

## Context and components

```text
Gmail / Graph / IMAP / JMAP             Filesystem / Dropbox / OneDrive
              │                                      │
        Email adapters                            FileOS adapter
              └──────────────────┬───────────────────┘
                                 ▼
 ┌──────────────────────────── DataCore ─────────────────────────────┐
 │ intake → digest/dedupe → evidence → extract/OCR → normalize      │
 │        → metadata/provenance → chunks → lexical/vector indexes    │
 │ common DB: tenancy, jobs, leases, audit, outbox, retention        │
 └───────────────────────────────┬───────────────────────────────────┘
                                 ▼
 ┌────────────────────────── KnowledgeCore ─────────────────────────┐
 │ entities ↔ relationships; claims/facts; events/timeline;         │
 │ projects; commitments; corrections; unified retrieval            │
 └───────────────────────────────┬───────────────────────────────────┘
                                 ▼
            Brain API → owner UI / Claude / Grok / ChatGPT / others
                                 │
                     proposal → policy → approval → executor
```

## Boundary rules

Source adapters discover changes, fetch source bytes/metadata, translate source
identities, and—later—execute separately approved source effects. They do not own
shared extraction, knowledge, or retrieval.

DataCore is deterministic-first and source-neutral. It preserves evidence before
interpretation, accounts for every input/part, publishes versioned derivatives, and
can rebuild projections. Exact-content matching is a signal; deletion authority is a
separate policy/effect concern.

High-risk formats cross a process/container boundary. The FileOS adapter verifies the
source version and sends only bounded bytes plus identity metadata to a format-specific
worker. That worker has no filesystem/source authority and returns a closed result;
DataCore independently validates identity, limits and outcome before transactionally
publishing text and chunks. Parser dependencies do not ship in the Brain API image.

The first operator boundary is a one-shot authenticated publisher, separate from the
Brain API. It binds a private config to one root/source/snapshot, requires exact worker
scopes and a request UUID, then repeatedly revalidates authority while invoking the
same adapter. It emits only counts. Scheduling, effects and Docker authority are not
part of the public API process.

Whole-run completion is separate from intake and per-document publication. Only an
append-only receipt whose terminal outcome counts cover the exact manifest advances a
source's latest-complete freshness. A crash prefix stays replayable and visible as not
complete; it cannot masquerade as a fresh source.

FileOS index rebuilds publish immutable generations from one exact completed run.
Readiness is a database-checked closure over generation items and chunks. A separate
append-only activation selects the searchable generation, and rollback reactivates a
prior ready generation. Rebuild does not reread or mutate source files.

Generation operation is a separate private one-shot command. Build-and-activate uses
an exact two-scope worker; activation-only rollback uses only the activation scope.
Check mode validates configuration, identity and database role without building or
activating. No scheduler or public mutation route owns this authority.

KnowledgeCore converts DataCore evidence into versioned, cited knowledge. A claim may
be supported, contradicted, superseded, or uncertain. Current state is a projection,
not a destructive overwrite of history.

Brain API performs authorization and progressive disclosure. Search results are
compact; expansions are explicit; original evidence requires a stronger permission.
LLM clients never receive database, object-store, provider, or filesystem authority.

## Core flows

### Intake and publication

1. Adapter emits an idempotent source observation and raw bytes/reference.
2. DataCore commits source identity, digest, evidence and receipt atomically.
3. Bounded workers extract/normalize; every part gets success, deferred, unsupported,
   quarantined, or failed status.
4. Versioned metadata, provenance, chunks and indexes publish transactionally.
5. KnowledgeCore consumes change records and publishes cited projections.
6. Cursors advance only past durable, accounted-for work.

### Query and evidence drill-down

The Brain API authorizes a bounded query, retrieves deterministic candidates, applies
optional semantic reranking, and returns compact results with evidence IDs. The client
may expand selected objects or request a verified evidence preview/original. Each step
is independently logged and budgeted.

### Proposed effects

Content or a model may suggest an effect but cannot authorize it. A typed proposal is
validated, checked against current policy and identity, previewed, approved where
required, assigned an idempotency key, executed by a narrow adapter, and reconciled
through an audit/outbox receipt.

## Storage

- PostgreSQL is the target multi-user source of truth with forced row-level security.
- Object storage holds encrypted immutable evidence when bytes are retained.
- Source files may remain in place; evidence records bind path/source ID and digest.
- Lexical indexes are required. Vector indexes are optional and rebuildable.
- Local SQLite can support bounded caches or donor parity, never authoritative hosted
  tenancy.

## Reliability

Fenced leases, idempotent commands, transactional inbox/outbox, monotonic checkpoints,
explicit freshness, reconciliation, immutable receipts, bounded retries, quarantine,
and backup/restore drills are shared primitives. Partial success is visible; it is not
reported as complete processing.

## Migration architecture

FOS-Master stays outside the runtime boundary during migration. MasterBrain runs
candidate DataCore functions against synthetic golden and read-only shadow inputs.
Only parity-proven components enter integrated paths. File effects migrate last and
retain FOS safeguards. See [FOS migration](FOS_MIGRATION.md).
