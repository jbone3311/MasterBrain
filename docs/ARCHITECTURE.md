# Architecture

## Latest executable additions

[Human-requested held-message recovery](QUARANTINE_RECOVERY.md) rechecks retained
hashes and current provider state, then atomically publishes parser-versioned
evidence and an immutable attempt. It neither advances sync nor writes mailboxes.
Current search excludes historical parser versions; same-parser output drift
fails closed rather than linking changed text to an old citation.

[Calendar MIME parts](CALENDAR_ATTACHMENTS.md), including unnamed body alternatives,
now enter the existing bounded attachment evidence/FTS path. They do not create
calendar events or obligations. [Public sample adoption](PUBLIC_EMAIL_TEST_DATA.md)
remains gated; format-faithful tests use generated synthetic bytes only.

The local control plane now supports reviewed exact-domain sender rules: immutable
tenant ruleset snapshots, bounded simulation, human activation and rollback. Search
adds read-time virtual labels without changing source mailbox/evidence state.
See [reviewed rules](REVIEWED_RULES.md). The [local model library](LOCAL_MODEL_RUNTIME.md)
is opt-in and candidate-only, not wired into the API/ingestion path. The
[logical restore drill](RESTORE_DRILL.md) exercises isolated synthetic databases;
it does not provision or validate hosted backups, encryption or point-in-time recovery.

## Style

Begin as a modular monolith plus workers. Separate deployable services only for materially different privileges or scaling: public/API ingress, mailbox connectors, inference quarantine, and mailbox action executor. Use a queue and transactional outbox, but avoid distributed-service complexity where a single process boundary suffices.

## Logical components

| Component | Responsibility | Privilege |
|---|---|---|
| API gateway | OIDC, tenant context, rate limits, request IDs | No provider secrets |
| Query/control API | Search, evidence, state, proposals, review | Tenant-scoped DB role |
| Connector workers | Incremental provider reads and reconciliation | Per-account read token |
| Raw evidence store | Encrypted MIME/attachments, content hashes | Write-once/read-scoped |
| Normalizer/indexer | Parse, dedupe, thread, FTS, queue extraction | No mailbox write |
| Rule engine | Versioned deterministic matching and decisions | No provider token |
| Inference reader | Local/remote extraction in untrusted-data quarantine | No action tools |
| Librarian | Propose temporal facts, merges, summaries | Proposal write only |
| Policy engine | Authorize proposals/actions and approvals | No provider token |
| Action executor | Execute approved mailbox command outbox | Per-account write token |
| Scheduler/reconciler | Renew watches, poll, drift checks, maintenance | Narrow job scopes |

## Main ingestion flow

1. Notification or schedule enqueues an account sync. Notifications never carry authority to mutate state.
2. Connector locks `(tenant_id, account_id)`, follows the stored opaque cursor, and writes provider events/raw evidence.
3. Changes and the new cursor commit atomically, or the cursor commits only after every covered change is durable.
4. Normalizer creates canonical messages and cleaned “new content,” retaining raw hashes and parser versions.
5. Deterministic rules classify, extract obvious fields, and decide whether a model is necessary.
6. The local model receives only bounded untrusted content and a schema; uncertainty or high consequence may escalate to an approved remote model.
7. Validated results update derived tables through versioned projectors. Candidate durable facts go to the Librarian proposal queue.
8. Proposed mailbox actions pass policy/review and enter an idempotent outbox. The executor performs them and later reconciles provider state.

Gmail describes partial sync using `history.list`, with a full sync required after an expired history ID ([guide](https://developers.google.com/workspace/gmail/api/guides/sync)). Microsoft describes delta as a local-store synchronization mechanism and recommends following opaque next/delta links ([overview](https://learn.microsoft.com/graph/delta-query-overview)).

## Query flow

```text
authenticated request
  -> resolve tenant/user/grants
  -> enforce grants within every candidate query/cache lookup
  -> parse filters and entities
  -> exact/structured SQL candidates
  -> PostgreSQL FTS candidates
  -> optional pgvector candidates
  -> reciprocal-rank/weighted fusion
  -> defense-in-depth authorization check + diversity + recency rerank
  -> bounded evidence bundle
  -> optional answer/draft model
  -> cited response
```

`pgvector` keeps vectors with transactional data and supports exact search plus HNSW/IVFFlat indexes ([project](https://github.com/pgvector/pgvector)). Start exact; add HNSW only when benchmarked latency requires it. Keep lexical retrieval first-class because names, addresses, confirmation codes, amounts, and dates are not reliably served by semantic similarity alone.

## Source of truth and replicas

- **PostgreSQL:** authoritative normalized/derived state, tenancy, rules, audit, sync cursors, jobs, and vectors.
- **Object storage:** authoritative encrypted raw MIME/large attachment blobs; PostgreSQL stores hashes and object keys.
- **SQLite edge replica (optional):** encrypted, read-mostly, user/tenant-scoped cache for offline search. It uses a signed change feed and never becomes authoritative for shared mutations.
- **Mailbox provider:** authoritative current mailbox state; reconciled with commanded effects.
- **Git:** application code, migrations, synthetic fixtures, policies/templates—not user mail or live rules containing private values.

## Reliability patterns

- Transactional outbox/inbox and idempotency keys.
- Worker leases, bounded retries with jitter, dead-letter queues, and poison-event quarantine.
- Content-addressed extraction cache keyed by normalized hash + task/schema/model/prompt version.
- Tombstones for provider deletions; retention policy determines raw/derived purge.
- Projectors rebuild derived tables from evidence/events.
- Dual-read migration checks for schema/search changes.
- Daily provider reconciliation and periodic sampled raw-hash verification.

## Rollback

Code/config deployments use normal version rollback and backward-compatible migrations. Rule versions are immutable; activating a new version records a pointer, and rollback restores the prior pointer then produces compensating mailbox actions where the provider supports them. Facts are superseded, not overwritten. Generated drafts can be removed; sent mail cannot be unsent, which is why sending remains a human decision.

## Scale assumptions

Design for tens of users, hundreds of accounts, and millions of messages without changing the logical model. Partition only when measurements require it. The likely first bottlenecks are MIME/attachment processing, embeddings, and provider quotas—not relational storage.
