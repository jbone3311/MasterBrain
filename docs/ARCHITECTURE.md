# Architecture

Updated 2026-09-21. [CODE_MAP.md](CODE_MAP.md) maps executable modules;
[FEATURES_AND_METHODS.md](FEATURES_AND_METHODS.md) explains the owner workflows.
Sections titled logical components, flows and reliability patterns describe the
target architecture; not every component is implemented. Current boundaries are
explicit in [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md).

The [worked product walkthrough](PRODUCT_WALKTHROUGH.md) follows the same boundaries
from the owner's perspective. Keep evidence, interpretation, approval and external
execution distinct in both diagrams and implementation.

## Latest executable additions

[Structured memory](STRUCTURED_MEMORY.md), ADR-046, adds typed owner-reviewed
travel/bill records, source-bound full revisions and a commit-ordered, non-consuming
change feed. Candidate extraction is a narrow labelled-format parser, not an LLM
or automatic ingestion stage. Freshness explicitly separates sync from interpretation.

[Owner message reading](MESSAGE_READER.md), ADR-045, resolves immutable evidence
to verified retained bytes under current human/owner/account authority. Small
messages are read beyond search-excerpt limits, with inert text and bounded
headers. Larger originals retain an explicit projection-only screen plus original
export. Separate consented download POSTs serve verified bytes, never arbitrary
objects. No migration, worker privilege or assistant evidence change.

[ADR-044 review fixes](adr/044_review_fixes.md) separate key-refresh network I/O
from cached-key access and carry source sender eligibility through versioned MIME
results into search/rule simulation. Legacy evidence remains immutable and readable;
missing sender provenance denies rule matching until explicit reprocessing.

[Browser authorization sessions](BROWSER_AUTH.md), ADR-042, implement an optional
code/PKCE exchange and process-local session/CSRF backend over ADR-040's current
human mapping boundary. No new table/grant. ADR-043 adds explicitly selected
private TLS/operator startup. Default startup/UI are unchanged; owner UI wiring
and actual browser acceptance are the next integration.

[Access-token identity](IDENTITY_AUTH.md), ADR-040/migration 0013, joins fixed-profile
JWT verification to administrator-owned identity mappings and fresh Store-transaction
checks. Discovery/JWKS trust is configured, never chosen by token content. Mapping
RLS precedes tenant resolution; ordinary tenant RLS and owner checks remain.
The API can explicitly select this mode but remains loopback-only. Browser login,
MFA, identity enrollment, service identities and team sharing are not implemented.

[Read-worker operation](READ_CONTROLLER.md), ADR-039, adds a private-configured
bounded CLI over the existing Fastmail worker. Preflight performs no provider
requests/lease claims. Execution reuses checkpoint/retry/lease logic and adds
per-request/step authority checks. No enrollment, scheduler service or hosted
identity is created; MIME/PDF controllers remain separate.

[Owner PDF review](DOCUMENT_REVIEW_SCREEN.md), ADR-038, uses existing document
APIs for explicit selection/approval, bounded history/status/cancel and cited page
evidence. A separate static script owns this channel and generation-fenced search;
MIME controls/credentials remain separate. Document search is opt-in, text-only
and unscanned. No schema, extraction or mailbox authority is added to the browser.

[Document operator execution](DOCUMENT_CONTROLLER.md), ADR-036, adds a separate
fixed-purpose/configured PDF command and exact document-worker identity. Shared
private-file/key/polling primitives preserve separate MIME/PDF queues and processors.
The loopback server can explicitly declare the PDF approval channel; no Docker
privilege enters the API. Demo owner provisioning uses human scopes only.

[Approved document processing](DOCUMENT_PROCESSING.md), ADR-035/migration 0012,
connects the PDF worker to synthetic-only source-bound approvals, separate worker
scope, immutable result revisions, opt-in document FTS and bounded page citations.
The ADR-034 groundwork paragraph below describes that earlier increment only.
No source/body mutation, default PDF parsing, UI controls or hosted service is added.

[Source-bound PDF worker groundwork](PDF_WORKER.md) adds a separate closed pipe
contract and optional restricted image. The child verifies retained MIME and part
hashes before bounded extraction; the parent validates page-level outcomes. The
ordinary parser and quarantine jobs remain unchanged. ADR-035 adds separate durable
approval/extraction publication, not a hidden reuse of MIME recovery permissions.

[Known-answer synthetic mail](TEST_MAILBOX_PLAN.md) now exports coherent MIME and
documents and replays them through the existing synthetic-only ingestion boundary.
Manifest-hash cursors bind seed/version/bytes; per-event transactions preserve
restart and duplicate-delivery semantics. Independent PDF/Office readers validate
fixtures in development; only the separately opted-in PDF worker now adds pypdf
outside dev. The default API/MIME image still excludes it. The generator itself
adds no table or API endpoint; the independent document channel does.

[Operator processing](PROCESSING_CONTROLLER.md) turns the approved-job library
into a bounded CLI with private identity/key configuration, non-claiming preflight,
fixed result counts and graceful stop. API and worker still deploy separately;
no service, provider enrollment or cloud resources are automatically created.

[Owner processing review](PROCESSING_REVIEW_SCREEN.md) exposes durable history,
explicit isolated approvals and cancellation through the existing scoped API.
All-state history is indexed by immutable time/ID; UI controls are bound to
session/account/view and parser. No background browser polling or automatic approval.

[Durable recovery jobs](RECOVERY_JOBS.md) connect an opt-in approval/status API to
the restricted worker. One-hour grants, leased bounded retries, cancellation and
fresh authorization/source fences make evidence publication and completion atomic.
The API holds no Docker authority; hosted identity/supervision remain gates.

[Isolated large-MIME recovery](ISOLATED_MIME_RECOVERY.md) lets a trusted worker
inject an exact-image processor into human-authorized Recovery. Existing SQL fences
and immutable parser versions publish bounded body/text-attachment evidence from
retained messages up to 16 MiB. This does not give the public API Docker privileges
or enable binary extraction; hosted deployment of the job channel is still required.

[Encrypted large-email storage](LARGE_EVIDENCE_STORAGE.md) stages verified external
objects before atomic SQL manifest/event/checkpoint publication. The explicit
local backend preserves up to 16 MiB; mail above the 1 MiB parser budget is held,
not indexed. Failed transactions may leave encrypted orphans, never automatically
deleted. Restore checks now require SQL, ciphertext and independently supplied keys.

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

### Separate message-recovery and document-processing boundaries

Current `RecoveryJobs` and `Recovery` select evidence through a quarantine
receipt. Ready status is accepted there only for a recorded same-parser recovery
attempt, not as a general attachment-processing entry point. A ready message may
have deferred binary attachments and no quarantine receipt at all.

ADR-035 represents approved processing of such a part with source/event identity,
independent result revisions and fenced publication. Never manufacture quarantine
or drop a valid body projection to fit the old queue. The synthetic API/library
integration, ADR-036's operator command and ADR-038's owner screen remain distinct
from pending browser/live acceptance. See
[document processing](DOCUMENT_PROCESSING.md) and [EB-006](BACKLOG.md#eb-006-next-source-bound-document-processing).

### Deployment style

Begin as a modular monolith plus workers. Separate deployable services only for
materially different privileges or scaling: API ingress, mailbox connectors,
restricted document readers, inference quarantine and the future action executor.
Current processing queues are PostgreSQL job tables; no separate broker is required.
Add the transactional mailbox-action outbox with the separately approved executor,
not as an implied existing component.

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
6. The local model receives only bounded untrusted content and a schema. Uncertainty
   or high consequence can request escalation, but disclosure permission and budget
   must also permit a remote call; otherwise defer or request human review.
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

The list below is the target ownership model. Currently, small raw MIME can be
stored inline in PostgreSQL and larger evidence uses an explicitly configured
encrypted local backend. Hosted Blob, vector indexes, entity/state projectors,
local replicas and action outboxes are not implemented storage components.

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

Current rule rollback appends a new immutable revision containing the prior rules;
it does not edit historical rows or move mail. Current migrations are forward-only
and checksum-verified: stop incompatible workers and use documented forward repair
or an explicitly tested restore, not an assumed downgrade. Future provider effects
need separately approved compensating commands where supported. Facts will be
superseded rather than overwritten; sending is not reliably reversible.

## Scale assumptions

Design for tens of users, hundreds of accounts, and millions of messages without changing the logical model. Partition only when measurements require it. The likely first bottlenecks are MIME/attachment processing, embeddings, and provider quotas—not relational storage.
