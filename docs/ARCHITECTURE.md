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
ADR-100 strengthens the source side of this boundary: snapshot and text/document
reads open every path component beneath the authorized root with no-follow
descriptors, then recheck the same locator after bounded reading. A pathname
precheck is not the authority to open bytes.

The first operator boundary is a one-shot authenticated publisher, separate from the
Brain API. It binds a private config to one root/source/snapshot, requires exact worker
scopes and a request UUID, then repeatedly revalidates authority while invoking the
same adapter. It emits only counts. Scheduling, effects and Docker authority are not
part of the public API process.
ADR-135 lets this one publisher require a database login bound to its
authenticated worker tenant. The opt-in check uses the existing transaction
fence; it does not route other private workers or authorize hosted operation.

Whole-run completion is separate from intake and per-document publication. Only an
append-only receipt whose terminal outcome counts cover the exact manifest advances a
source's latest-complete freshness. A crash prefix stays replayable and visible as not
complete; it cannot masquerade as a fresh source.
ADR-122 inserts new v1 run items before the receipt in one transaction. The
deferred receipt check validates the final ledger once, while an immediate
source-locked guard bars late item inserts. The completed-run and absence
contracts are unchanged.
The completion boundary also validates snapshot coverage. An unreadable directory,
failed file read or hash-time change cannot be promoted to a complete run and
therefore cannot create an absence event; partial imports remain separate. A
second guard refuses a new complete run with at least 10 missing prior items and
at least 50% loss, even if its scan reports no errors. It retains the previous
complete inventory until a separately reviewed recovery path exists.
Each new completion also records an immutable digest of its explicit inventory
policy. Comparing consecutive completed runs with an unknown or different policy
is refused before absence inference. Legacy policy cannot be recovered from a
whole-manifest hash, so it is not silently backfilled.
FileOS root identity is a separate versioned boundary: the private publisher
rechecks its physical root, source intake records an immutable digest, and
completion requires it to match the source and prior receipt. Old sources with
evidence and unknown roots need a reviewed baseline transition. The digest is
private metadata, not a Brain API field (ADR-098).
The donor-policy v2 transition is separate from v1 completion. After exact
owner review and historical verification, ADR-121 permits a worker-only,
locked fresh rescan to prepare policy-scoped source versions and source-bound
evidence. A sealed mapping retains each donor candidate identity; the v1
current pointer and completed-run ledger remain unchanged. Preparation is not
v2 completion, current visibility or cutover.
ADR-123 adds a separately scoped owner authorization for the exact prepared
stage. Completion must still be a distinct fresh, source-locked transaction;
the authorization receipt changes no current FileOS state.
ADR-124 implements that private completion transaction: another exact,
no-follow donor scan seals a receipt over the immutable staged membership and
prepared hashed evidence. It is a historical baseline, not an activation;
v1 current pointers, freshness, absence and active search remain authoritative.
ADR-125 then reuses the confined text and isolated document processors to
publish normalized derivatives on prepared v2 versions. An exact rescan and
source-locked outcome ledger seal a ready or blocked historical attempt; a
crash cannot create partial readiness. Retained-history search may see those
derivatives, but no v2 current index/activation, absence or cutover follows.
ADR-126 defines a shared-table v2 generation over one ready document attempt;
its first implementation must remain private and SQL-fenced against activation.
ADR-147 exposes only the existing human-scoped historical search comparison of
one ready v2 generation with active v1 through a bounded Brain API route. That
read path neither activates v2 nor changes FileOS current-state authority.
Each new snapshot also accounts for excluded file and directory locators. Before
absence inference, completion refuses any missing prior item covered by an
exclusion or allowed no-follow symlink skip. Genuine removals remain eligible for
absence evidence under the existing mass-loss guard. This ledger does not change
membership policy or authorize FileOS cutover.

FileOS index rebuilds publish immutable generations from one exact completed run.
Readiness is a database-checked closure over generation items and chunks. A separate
append-only activation selects the searchable generation, and rollback reactivates a
prior ready generation. Rebuild does not reread or mutate source files.

Generation operation is a separate private one-shot command. Build-and-activate uses
an exact two-scope worker; activation-only rollback uses only the activation scope.
Check mode validates configuration, identity and database role without building or
activating. No scheduler or public mutation route owns this authority.
ADR-138 lets both modes opt into a database login bound to that authenticated
worker's tenant. Shared, owner and wrong-tenant logins fail before check mode
can succeed. This does not route other private workers or approve hosting.
ADR-139 applies that opt-in bound-login rule through a shared DataCore helper to
all database-backed private `masterbrain` Email bridge and FileOS archive
operators, including previews and batches. Every item in a batch uses the same
authenticated worker tenant; a plan cannot select a route. ADR-141 extends
the same opt-in DataCore store rule to `email-brain sync-read`, `process-jobs`
and `process-documents`; their preflight and execution use the authenticated
worker tenant, not a provider or job field. The read worker reopens the bound
store between polls. Hosted credential lifecycle remains separate.

Current FileOS retrieval is an explicit cross-source read over each source's newest
activation. Existing compatibility and unified search remain unchanged and may expose
retained historical derivatives; clients choose the current-only route deliberately.

Grouped retrieval exposes the same choice: retained-history evidence is the backward-
compatible default, while `current_fileos` composes active FileOS evidence with
reviewed KnowledgeCore results. Ranks and limits remain separate by layer.

Bridged Email retrieval checks current state in both layers at query time: the shared
item must point to the indexed version, and the immutable bridge receipt must still
identify the legacy Email message's current visible raw/parser version. Updates hide
old shared hits until explicitly re-bridged; delete/quarantine hides them without
erasing retained evidence. Legacy Email search remains authoritative.

KnowledgeCore converts DataCore evidence into versioned, cited knowledge. A claim may
be supported, contradicted, superseded, or uncertain. Current state is a projection,
not a destructive overwrite of history.
ADR-158's first optional `unsuperseded` query is a source-grant-aware leaf of
the reviewed supersession/correction graph. It does not compare valid times,
collapse conflicting leaves or change the grouped Brain current-search's
retained KnowledgeCore layer. That later composition needs its own evaluation.

Brain API performs authorization and progressive disclosure. Search results are
compact; expansions are explicit; original evidence requires a stronger permission.
LLM clients never receive database, object-store, provider, or filesystem authority.
The opt-in service path resolves a verified identity through a table-blind lookup
login, then routes its tenant to a separately bound database login. The route is
private server configuration, never request-controlled. This synthetic API path
does not yet route separate worker commands or prove hosted containment (ADR-109).

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
