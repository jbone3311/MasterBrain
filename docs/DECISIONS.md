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
