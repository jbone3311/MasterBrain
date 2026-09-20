# Architecture Decisions

This is a concise ADR index. Each decision should become an individual immutable ADR during implementation when detail or alternatives expand.

## Accepted

### ADR-001 — Hosted PostgreSQL is authoritative

**Decision:** managed PostgreSQL + `pgvector`; encrypted object storage for raw blobs.  
**Why:** multi-user concurrency, transactions, RLS, PITR, full-text and vector retrieval in one system.  
**Consequence:** higher operations/cost than local SQLite; requires strict runtime roles and restore testing.

### ADR-002 — SQLite is optional edge/cache only

**Decision:** use encrypted SQLite FTS5/optional vector extension for offline tenant-scoped replicas, never shared authority.  
**Why:** local speed/privacy without multi-writer/synchronization ambiguity.

### ADR-003 — Modular monolith first

**Decision:** one codebase with clear modules; separate deployment boundaries only for ingress, untrusted inference, and mailbox executor where privileges differ.  
**Why:** simpler delivery with enforceable security boundaries.

### ADR-004 — Provider-native incremental sync

**Decision:** Fastmail JMAP, Gmail History/Pub/Sub hint, Graph delta/change-notification hint, iCloud IMAP UID/UIDVALIDITY/IDLE hint.  
**Why:** less polling and correct change semantics. Notifications are hints; cursors/reconciliation are truth.

### ADR-005 — Evidence/events immutable; projections rebuildable

**Decision:** preserve raw versions/hashes, event/action audit, and evidence links.  
**Why:** replay, correction, provenance, rollback, and debugging.

### ADR-006 — Code → local → remote → human ladder

**Decision:** deterministic rules first, local constrained model second, remote escalation only by policy, human review by consequence.  
**Why:** privacy, cost, latency, and reliability.

### ADR-007 — Control-plane proposals, not self-modification

**Decision:** assistants propose typed changes; safe config/knowledge follows review policy; software changes go to Factory.  
**Why:** prevent silent behavioral drift and preserve governance.

### ADR-008 — Draft-only and staged deletion initially

**Decision:** no auto-send or permanent auto-delete in v1; use `_GrokBot/Review Delete` and provider drafts.  
**Why:** irreversible consequences exceed early classifier confidence.

### ADR-009 — Hybrid retrieval without vector dependence

**Decision:** exact/structured + PostgreSQL FTS first; vectors/reranking added by measured benefit.  
**Why:** email identifiers and numbers favor lexical retrieval; degraded mode remains useful.

### ADR-010 — Relational temporal facts before graph database

**Decision:** entities/relations/facts with bitemporal fields in PostgreSQL. Use Graphiti as a pattern/reference and possible later pilot.  
**Why:** reduce infrastructure and keep authorization/transactions unified.

### ADR-011 — REST authority, MCP adapter

**Decision:** stable REST/JSON service contract; MCP exposes narrow typed tools/resources over it.  
**Why:** clients remain replaceable and MCP security/evolution are isolated.

### ADR-012 — Isolation in API and RLS

**Decision:** API authorization plus forced RLS and tenant-aware object/cache keys.  
**Why:** defense in depth. PostgreSQL documents RLS behavior and bypass cases ([docs](https://www.postgresql.org/docs/17/ddl-rowsecurity.html)).

## Deferred decisions

### ADR-013 — Executable foundation and bounded bootstrap (2026-09-19)

**Decision:** ship a loopback-only developer service with synthetic ingestion,
PostgreSQL FTS/evidence, atomic cursor checkpoints, idempotent reviewed proposals,
and a read-only Fastmail protocol adapter. Do not connect real accounts, provision
paid hosting, execute mailbox writes, or enable remote inference during bootstrap.
The user authorized private repository creation, publication, and implementation.

**Auth boundary:** bootstrap credentials are random bearer tokens mapped by their
SHA-256 digests to server-configured tenant/actor/scopes, with an expiry. Only
existing owner memberships are supported; invited members and resource sharing
remain disabled until grant-aware authorization and OIDC are implemented. This
is not production authentication. Tenant/actor never come from request bodies.
Runtime DB credentials must be non-owner, non-superuser, and non-BYPASSRLS.

**Evidence boundary:** bounded raw MIME is retained in a tenant-isolated PostgreSQL
table for this synthetic prototype, atomically with its projection and checkpoint.
Encrypted object storage is still the production target. No public raw-byte API.
Raw objects are immutable while retained, not exempt from authorized retention/purge.

**Review boundary:** proposals are immutable requests. A human owner can mark them
approved/rejected with optimistic version checks; approval does not apply a rule
or execute an action. Feature requests stay data until Factory explicitly adopts
them. This avoids mistaking a review queue for a completed action executor.

**Factory boundary:** a sibling Dropbox source checkout is the desired final local
layout; live databases, venvs, secrets, indexes, and worker state must live outside
Dropbox. Prepare registration artifacts but do not modify Factory itself or claim
its bind/audit passed. Email Brain runtime never imports Factory.

**Verification:** pure unit/API tests plus a real PostgreSQL CI service test RLS,
composite tenant/account foreign keys, replay, transaction rollback, stale cursors,
idempotency conflicts, proposal transitions, and least-privileged runtime roles.

**Rollback:** API is additive; stop it and restore the database from backup if
required. Do not down-migrate/delete retained evidence. No mailbox compensation
is needed because no provider write path exists.

Sources: [Psycopg transactions](https://www.psycopg.org/psycopg3/docs/basic/transactions.html),
[PostgreSQL RLS and bypass behavior](https://www.postgresql.org/docs/17/ddl-rowsecurity.html),
[FastAPI test client](https://fastapi.tiangolo.com/tutorial/testing/).

## Deferred decisions (tracked without blocking bootstrap)

### ADR-014 — Factory-shaped attachment receipts, bounded extraction (2026-09-19)

**Decision:** extend the transactional ingestion slice with per-MIME-part attachment
receipts and append-only intake events; keep every occurrence, link duplicates
within an account, and retain original bytes in the raw MIME evidence. Extract
bounded plain-text attachments without models. PDFs, Office files, images, archives,
executables, and nested emails receive explicit deferred/skipped status. They are
not executed, unpacked, OCRed, or marked safe by the API process. No raw download
or outbound SMTP capability is introduced.

**Rationale:** Factory's intake standards require receipt accounting, provenance,
per-document outcomes, and no filename-only embeddings. Its document/archive
tools are valuable but currently path/config/CLI-oriented, with optional imports
and some logging that can contain private paths. A long-running multi-tenant
service needs an isolated, deterministic worker contract first. Do not make the
hosted service import a sibling Factory checkout or copy its governance runtime.
See [Factory intake review](FACTORY_INTAKE_REVIEW.md).

**Limit:** complete MIME is currently capped at 1 MiB; attachments at 256 KiB for
plain-text extraction, 64 recorded attachment parts per message, MIME depth 20.
These are prototype limits, not final product limits. Oversized/over-complex MIME
aborts the page without advancing its cursor. Durable poison-message quarantine
and larger encrypted object storage must precede real mailbox backfill.

**Retention:** preserving evidence does not grant infinite retention. A separately
authorized purge workflow must remove message bodies, attachment projections,
objects, vectors, and cache copies; no such destructive workflow runs in v0.1.

**Tests:** path traversal filenames, executable signatures under misleading names,
binary disguised as text, duplicate receipts, archive/nested handling, MIME limits,
attachment FTS, RLS, immutable receipt-event history, and reconciliation counts.

## Owner decisions pending

### ADR-015 — Fastmail read-only HTTP transport (2026-09-19)

**Decision:** implement and mock-test a Fastmail-specific HTTPS transport with a
fixed `api.fastmail.com` host boundary, no redirects/environment proxy inheritance,
timeouts, bounded streamed responses, and JMAP read-method allowlist. Session
discovery, metadata fetch and raw-blob reads are available as a library. Tokens are
supplied by the caller; no token is discovered or stored by the adapter.

**Boundary:** no live account is contacted during the build; no write/submission
methods or SMTP exist. This is not yet a backfill scheduler or credential enrollment
flow. State/checkpoint policy remains in the ingestion worker design, not HTTP code.
Provider errors are typed and scrubbed, with explicit throttling/auth/expired-state
outcomes. Disposable-account authorization is still required for live acceptance.

Sources: [Fastmail JMAP](https://www.fastmail.com/dev/),
[JMAP blob download](https://jmap.io/spec-core.html#downloading-binary-data).

## Pending owner choices

### ADR-016 — Resumable read worker with fenced leases (2026-09-19)

**Decision:** add a bounded, one-page-at-a-time Fastmail worker. Persist a versioned
checkpoint containing the import generation, baseline Email state, query state,
position and total. Restart listing when query state changes; do not infer deletion
from an incomplete listing. Replay changes from the baseline after listing finishes.
Keep the original Email baseline when restarting a changed query. An expired change
cursor pauses with `resync_required`: a complete inventory-diff reconciler is still
needed before safely replacing the baseline. Explicit provider tombstones hide
current search while retained evidence remains available.

**Concurrency:** acquire a database-clock lease before network work, renew between
bounded requests, and fence commits with the exact lease token. Network requests
never run inside a database transaction. Checkpoint and evidence commit together;
an expired/replaced lease cannot commit. A configured provider-account binding is
required and checked against session discovery before reading messages.

**Failure:** persist bounded, content-free run outcomes, retry deadlines and auth/
protocol pauses. No sleeping retry loop in the worker. MIME failures and oversized
messages still stop the page without advancing: durable byte-preserving quarantine
and larger object storage are separate gates, not simulated as successful imports.
Partial full imports are searchable but never advertised as a complete mailbox.

**Boundary:** library orchestration and synthetic/provider-mock tests only initially;
no automatic discovery of credentials, enrollment, real mailbox contact or mailbox
writes. Operator enrollment, scheduler and disposable-account acceptance remain gates.
No inference or binary extraction is enabled by synchronization.

**Rollback:** stop workers; leases expire. Preserve new tables/checkpoints and deploy
forward-compatible code. Older code must not interpret the worker's JSON checkpoints
as provider state. No destructive down migration or provider compensation is required.

Sources: [JMAP query-state contract](https://www.rfc-editor.org/rfc/rfc8620#section-5.5),
[JMAP mail changes](https://www.rfc-editor.org/rfc/rfc8621#section-4.2).

- Cloud/managed Postgres vendor and region.
- OIDC/Zero Trust vendor.
- First provider and exact backfill window.
- Tenant sharing granularity and household/team UX.
- Raw body/attachment retention and compliance obligations.
- Local model/embedding/reranker selected by benchmark.
- Talon vs alternative quote/signature parser after corpus test.
- Whether an edge replica is worth device/key/revocation complexity.
- Search index partitioning and HNSW threshold.
- Remote-model providers and data-retention contractual mode.
- UI framework; architecture does not require one.

## Explicitly rejected for initial build

SQLite as multi-user source of truth; public database/model/MCP endpoints; vector-only retrieval; automatic send/delete; direct assistant SQL; direct model provider credentials; rules as executable code; graph database by default; whole-mailbox prompts; Git storage of email/live secrets.
