# Architecture Decisions

This is an ADR index plus historical decision summaries. New detailed decisions
live in [adr/](adr/). Later explicit decisions supersede earlier limitations without
rewriting their history. The current status is in [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md).
The documentation refresh changes explanations/navigation, not runtime privileges.

ADR-035 now defines the separate approved PDF source-to-search channel for ready
mail. ADR-029/030 remain bounded MIME recovery; no implicit permission expansion.

## Accepted

[ADR-071](adr/071_email_bridge_backfill_preview.md) defines a private, bounded and
non-consuming current-Email bridge plan for one explicit account. It establishes safe
selection and paging without adding batch writes, provider access or a Brain API
mailbox-enumeration surface; hosted PostgreSQL and restore verification are green.

[ADR-070](adr/070_current_source_coverage.md) defines a bounded, separately authorized
status view for active FileOS generation readiness and explicitly bridged current Email
coverage. It exposes only registered opaque sources and existing facts; hosted
PostgreSQL and restore verification are green.

[ADR-069](adr/069_grouped_current_source_search.md) defines a compact grouped read
across active FileOS, current Email-family evidence and reviewed KnowledgeCore with
independent limits/ranks and explicit partial coverage. Hosted PostgreSQL and restore
verification are green.

[ADR-068](adr/068_current_email_family_search.md) defines a separate, layered current-
only read for bridged Email messages, attachment text and approved PDF derivatives.
Existing message-only and retained-history reads remain unchanged; hosted PostgreSQL
and restore verification are green.

[ADR-067](adr/067_email_part_bridge_operator.md) defines explicit private commands
for one Email attachment occurrence or one approved PDF derivative, reusing the exact
shared worker scopes and non-consuming preflight. Hosted PostgreSQL and restore
verification are green.

[ADR-066](adr/066_email_document_extraction_bridge.md) defines a separate additive
bridge for an immutable approved Email PDF extraction onto its existing shared
attachment evidence. It reuses bounded legacy text and never reads attachment bytes;
hosted PostgreSQL and restore verification are green.

[ADR-065](adr/065_email_attachment_bridge.md) defines an additive bridge preserving
each Email attachment occurrence as a shared child evidence/part. Existing bounded
text may be indexed; unsafe bytes and approved document revisions are not reprocessed
or rewritten. Hosted PostgreSQL and restore verification are green.

[ADR-064](adr/064_current_bridged_email_search.md) defines an additive Brain read for
explicitly bridged Email evidence that is still current and visible in both shared and
legacy state. Existing Email and retained searches remain unchanged. Hosted
PostgreSQL and restore verification are green.

[ADR-063](adr/063_email_bridge_operator.md) defines a private one-version Email bridge
command with exact shared worker scopes, non-consuming preflight and content-free
output. It adds no scan, scheduler, provider access or search cutover. Hosted
PostgreSQL and restore verification are green.

[ADR-062](adr/062_email_evidence_bridge.md) defines an additive, replayable bridge
from one current immutable Email version into shared DataCore identities, chunks and
provenance. Existing Email ingestion/search remain authoritative; no mailbox access,
automatic backfill or cutover is granted. Hosted PostgreSQL and restore are green.

[ADR-046](adr/046_structured_memory.md) adds reviewed trip/flight/hotel/bill memory,
immutable revisions, independent change cursors and explicit partial freshness.
Migration 0014 and bounded REST/developer UI do not imply automatic interpretation.

[ADR-045](adr/045_owner_message_reader.md) adds a human-only full small-message
reader, explicit original/leaf-part exports and source/authority verification.
Large messages retain explicit projection limits and intact original downloads;
MCP/assistant evidence remains bounded. No mailbox privileges or migration.

[ADR-044](adr/044_review_fixes.md) fixes signing-key cache contention and lost
sender ambiguity. Single-flight refresh preserves valid cached access; source-bound
sender-rule eligibility fails closed for historical evidence without validation.

[ADR-043](adr/043_browser_operator_tls.md) adds explicit private browser-mode TLS
startup, mutually exclusive authentication flags and non-consuming preflight.
It preserves loopback-only binding; UI and actual browser acceptance remain gates.

[ADR-042](adr/042_browser_authorization_sessions.md) defines the explicit browser
code/PKCE and server-side session flow. The optional backend/REST boundary exists;
ADR-043 supplies the operator command; owner UI and actual browser/TLS acceptance remain required.

[ADR-041](adr/041_stream_deadline_checks.md) closes application chunk-buffering
gaps in the four HTTP readers, with bounded accumulation and delayed-EOF checks.
Existing scopes, response limits and connector availability remain unchanged.

[ADR-040](adr/040_access_token_identity.md) adds the configured access-token
resource-server boundary, explicit RFC/Entra profiles and administrator-owned
identity bindings with current SQL authorization and administrator audit. Exact
verification is in the build receipt; browser login, real issuer enrollment and hosted release remain gates.

[ADR-039](adr/039_read_worker_controller.md) adds explicit bounded Fastmail read
operation, non-consuming private preflight, exact ingest-worker identity and fresh
file/account guards. No enrollment, schema/grant change or live acceptance.

[ADR-038](adr/038_document_owner_review.md) adds separate owner PDF approval/history/
cancellation and bounded cited page evidence, plus opt-in document search. It uses
existing APIs and source/authorization fences; no schema or permission expansion.

[ADR-037](adr/037_documentation_verification.md) strengthens offline documentation
inventory/path/section-link checks, including GitHub templates, with regression tests.
It adds a methods reading guide but no runtime or permission change. The next
runtime assignment at that increment was the document owner interface, now ADR-038.

[ADR-036](adr/036_document_operator_controller.md) adds the separate explicit PDF
operator command, fixed-purpose/policy private configuration, exact document-worker
identity and loopback server channel option. Shared controller primitives preserve
MIME permissions. Demo owner credentials now use an explicit human-scope allowlist.
No new schema, dependency, live policy or owner-screen controls.

[ADR-035](adr/035_approved_document_processing.md) adds synthetic-only document
approval/jobs, immutable extraction revisions, opt-in FTS and cited results.
Migration 0012 and a separate worker scope preserve source/body state. ADR-036 adds
operator execution and ADR-038 adds owner UI; live/scanner and hosted acceptance remain.

[ADR-034](adr/034_source_bound_pdf_worker.md) adds an explicit source-bound restricted
PDF worker, separate image/contract and synthetic tests. No attachment queue,
publication, scanner, API or broader MIME recovery authority is granted. The next
durable approval-to-search design remains open.

[ADR-033](adr/033_known_answer_synthetic_mailbox.md) adds coherent fictional MIME,
independent format checks, known-answer manifests and bounded/paced synthetic
ingestion through existing transactions. No live delivery or binary extraction.

[ADR-032](adr/032_operator_processing_controller.md) adds an explicit private,
bounded operator command for approved jobs, configuration preflight and graceful
shutdown. It adds no enrollment, SQL grants, schema or hosted service.

[ADR-031](adr/031_processing_review_screen.md) adds bounded durable processing
history and explicit owner-screen approval/cancellation, with session/view fencing
and uncertain-request idempotency. No worker or mailbox capability is enabled.

[ADR-030](adr/030_durable_recovery_jobs.md) connects explicit human approval to
durable isolated-processing jobs, bounded claims/retries and atomic fenced
completion. API and worker remain separate; no hosted identity or daemon is enabled.

[ADR-029](adr/029_isolated_large_mime_recovery.md) adds a restricted, image-bound
large-MIME processor for the human-authorized Recovery library. Default API parsing
and binary-extraction deferral remain unchanged. Docker control is a separate
trusted worker privilege, never granted to the API or untrusted parser.

[ADR-028](adr/028_encrypted_large_evidence.md) adds opt-in encrypted filesystem raw
evidence and SQL manifests (0009), large-message holding and coordinated synthetic
object/database restore. It supersedes historical small-message-only preservation
statements, not parser limits. No hosted storage or binary extraction is implied.

[ADR-027](adr/027_quarantine_recovery.md) adds audited, human-requested retry of
current held MIME and parser-versioned evidence (migration 0008). It supersedes
the no-retry UI boundary in ADR-021; no raw-download or mailbox permission is added.

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

## Accepted prototype evolution

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

## Historical attachment boundary (superseded in part by later ADRs)

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

## Accepted provider and worker evolution

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

## Worker history and pending deployment choices

### ADR-016 — Resumable read worker with fenced leases (2026-09-20)

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

### ADR-017 — Certified inventory reconciliation and durable MIME quarantine

Supersedes the earlier bounded-MIME failure pause and cursor-expiry pause decisions
for newly running v2 workers; historical ADRs above record earlier shipped behavior.

**Decision (2026-09-20):** checkpoint schema v2 adds a reconciliation phase. Every
listing generation records the IDs actually received in a tenant/account inventory.
Only a complete, query-state-consistent listing whose unique ID count equals its
declared total can start reconciliation. Reconciliation hides absent local projections
in bounded batches, never deletes provider mail or retained evidence, then replays
changes from the pre-listing Email baseline. Query churn starts a fresh inventory
generation while preserving that baseline. Expired history starts a fresh full import;
legacy v1 checkpoints are safely reimported rather than trusted as certified inventories.

Within the existing 1 MiB raw bound, rejected MIME is retained byte-for-byte with a
hash, immutable failure receipt and current-message status in the same transaction
as the event and checkpoint. A quarantined update hides its old searchable projection;
later valid input or explicit deletion resolves current status without erasing the
receipt. Oversized downloads still fail closed, because their full bytes cannot yet
be retained. No binary execution, automatic reprocessing, send or mailbox writes.
An owner-scoped read-only sync-status endpoint exposes aggregate processing counts,
worker outcome and whether review is required; it never returns raw mail or credentials.
Synthetic corpus generation is offline-only and deterministic, with reserved invalid
addresses and no external model or provider calls.

**Tests:** synthetic multi-page imports, history expiry, list churn, incomplete or
contradictory inventories, crash/replay, poison mail mixed with good mail, foreign
tenant access, immutable receipts, batch bounds and end-to-end API evidence.

**Rollback:** additive migrations and v2 checkpoints require forward-compatible
workers; stop old workers before migration. Restore only through an explicit restore
workflow; do not down-migrate or discard inventory/evidence. Production cloud,
credential enrollment, retention cleanup and isolated binary extraction remain gates.

### ADR-018 — Consolidated hosting planning target (not provisioned)

Owner preference is fewer hosting accounts, not Microsoft-only application or
mailbox software. Prefer the same Azure hosting account/subscription as RealEstateOS
if that is the hosting home selected there, with isolated Email Brain resources,
identities, databases, secrets and budgets. Retain portable Python/PostgreSQL and
provider adapters. AWS remains an alternative if that is the actual existing
hosting home. No cloud resources, paid services, Entra app registrations, model
subscriptions or migration have been created or authorized by this planning choice.
Region, costs, identity design and deployment approval remain gates. See the
updated [hosting recommendation and sources](HOSTING_DECISION.md).

### ADR-021 — Read-only quarantine review surface

Related provider decisions are maintained in focused records:
[ADR-019: Gmail](adr/019_gmail_read_contract.md),
[ADR-020: Graph](adr/020_graph_read_contract.md), and
[ADR-022: injected IMAP](adr/022_imap_read_contract.md).

Expose current quarantine receipt metadata to an authenticated owner with
`email.evidence.read`, scoped to one account. Return at most 50 entries per page,
using receipt UUID keyset pagination; this is a live list, not a complete export
snapshot. Include fixed reason/parser version/hash and source ID, never raw MIME,
exception text, provider credentials or active attachments. Quarantine review is
informational: no dismiss, delete, reprocess or mailbox action capability is added.
Show this and aggregate sync state in the local owner UI. Clear visible evidence
on credential changes and reject stale asynchronous results after session changes.

Adversarial review additionally requires all persisted MIME projection strings to
be NUL-free and strict UTF-8 encodable before SQL. Decoder-produced invalid strings
must quarantine their unchanged source bytes. Both synthetic seed commands verify
unenrolled synthetic account status again inside each ingestion transaction; future
administrative enrollment must use the same account lock and stop worker callers.

Tests cover absent/foreign account identifiers, scope denial, bounded paging,
current-status filtering and the no-raw-data API contract. Production login,
audited reprocessing and browser accessibility acceptance remain gates.

## Additional accepted prototype decisions

[ADR-061 current-aware grouped retrieval](adr/061_current_aware_unified_search.md)
adds an explicit current-FileOS evidence mode to grouped KnowledgeCore search while
preserving retained-history compatibility and separate ranks.

[ADR-060 current FileOS search](adr/060_current_fileos_search.md) adds a cross-source
read over latest activated generations without silently redirecting compatibility or
unified search.

[ADR-059 private FileOS index operator](adr/059_fileos_index_operator.md) adds an
explicit authenticated build/activate and activation-only rollback command with exact
worker scopes. It does not schedule work or switch global search.

[ADR-058 immutable FileOS index generations](adr/058_fileos_index_generations.md)
adds completion-bound, deterministic lexical generations, append-only activation and
reactivation rollback. Mutation remains a trusted library operation until a narrow
operator command is separately accepted.

[ADR-057 read-only rebuild preview](adr/057_fileos_rebuild_preview.md) verifies current
normalized documents and chunks before any index-rebuild executor is authorized.

[ADR-056 completed-inventory reconciliation](adr/056_fileos_inventory_reconciliation.md)
adds exact per-run membership and immutable absence evidence without deletion or
search-visibility effects.

[ADR-055 FileOS completion and freshness](adr/055_fileos_completion_freshness.md)
separates imported/partial work from an immutable fully accounted run and exposes only
latest-complete source status.

[ADR-054 authenticated FileOS publication](adr/054_fileos_operator_publication.md)
adds a closed private operator configuration, exact worker scopes, idempotent snapshot
publication and repeated authorization checks without source effects.

[ADR-053 isolated FileOS documents](adr/053_isolated_fileos_documents.md) adds
source-revalidated PDF/DOCX/XLSX extraction through a dedicated networkless,
read-only container; it grants no source effects or OCR authority.

[ADR-052 grouped unified search](adr/052_grouped_unified_search.md) composes DataCore
evidence and KnowledgeCore assertions in separately ranked, independently bounded
layers requiring both scopes; it does not imply Email migration or synthesis.

[ADR-051 reviewed KnowledgeCore assertions](adr/051_knowledgecore_reviewed_assertions.md)
adds evidence-required entities, relationships, claims, events, projects, commitments,
corrections, bitemporal fields and lexical retrieval without automatic model writes.

[ADR-050 Brain API read slice](adr/050_brain_api_read_slice.md) adds source-neutral,
progressive search/evidence/content/change endpoints with separate scopes and bounded
untrusted content while preserving legacy Email API compatibility.

[ADR-049 FileOS text extraction](adr/049_fileos_text_extraction.md) adds bounded,
hash-reverified, read-only text/Markdown/HTML/CSV extraction with explicit outcomes
and live parity against the pinned FOS-Master donor.

[ADR-048 DataCore persistence](adr/048_datacore_persistence.md) adds bounded,
idempotent FileOS snapshot import, immutable source/evidence/provenance records,
deterministic chunks and tenant-isolated lexical retrieval without changing Email
tables or authorizing source writes.

[ADR-047 MasterBrain foundation](adr/047_masterbrain_foundation.md) establishes the
final product identity, shared core boundaries, non-destructive FOS-Master migration
protocol and first read-only DataCore hash/dedupe extraction.

[ADR-026 calendar attachments and format fixtures](adr/026_calendar_attachments_and_format_fixtures.md)
adds bounded searchable calendar source evidence and synthetic attachment/provider
format tests. It grants no calendar action or public-corpus import authority.

New accepted prototype decisions: [ADR-023 synthetic logical restore drill](adr/023_synthetic_restore_drill.md),
[ADR-024 opt-in local classification candidates](adr/024_local_model_classification.md),
and [ADR-025 reviewed virtual sender rules](adr/025_reviewed_rule_activation.md).
No production deployment, real model quality, mailbox effects or live-service
authorization is implied by these additive local/CI capabilities.

## Explicitly rejected for initial build

SQLite as multi-user source of truth; public database/model/MCP endpoints; vector-only retrieval; automatic send/delete; direct assistant SQL; direct model provider credentials; rules as executable code; graph database by default; whole-mailbox prompts; Git storage of email/live secrets.
