# Data Model

Updated 2026-09-21. The migration notes and final implemented-schema section
describe executable storage. Entity/project/obligation/grant/vector sketches are
target design, not existing tables. [Migrations](../migrations/) are authoritative
for deployed schema; see [code map](CODE_MAP.md) and [status](IMPLEMENTATION_STATUS.md).

Read the sketches below as a target information model, not ready-to-run SQL.

Migration 0014 now implements `memory_records`, `memory_revisions` and
`memory_receipts` for typed trip/flight/hotel/bill claims. These are distinct from
the general entity/obligation sketches below. Full append-only revisions carry
account-bound evidence/quote/trip links; actor-bound idempotency receipts cover
changes and no-ops. RLS and composite foreign keys protect tenant/account ownership.
See [structured memory](STRUCTURED_MEMORY.md). No general entity graph is added.

ADR-045's [owner reader](MESSAGE_READER.md) adds no columns or tables. It resolves
existing immutable message versions/raw objects/attachment receipts, verifies
source hashes and appends identifier-only read/export events. Complete small-body
reading does not enlarge or rewrite the 100,000-character search projection.

ADR-044 adds internal boolean `sender_rule_eligible` to immutable JSON snapshots,
not a new column/table or SQL migration. Current search/simulation require exact
JSON true; missing/false/non-boolean legacy values deny sender-rule matching.
Ordinary parser provenance is now `stdlib-mime-v5`. Old snapshots and citations
remain unchanged. Public evidence/search envelopes omit this internal field.
`mail_accounts` and `tenant_memberships` already exist; their target field sketches
are not a migration adding all proposed fields. The [worked project scenario](PRODUCT_WALKTHROUGH.md)
explains why original evidence, current derived state and proposed actions need
separate records. The standalone reader adds no table; ADR-035 now adds its separate
durable approval/result model.

Migration 0013 adds administrator-owned `external_identities`: unique verified
issuer/subject/client -> existing tenant/actor, API scopes, human/assistant kind,
active flag and protected monotonic revision. Runtime gets SELECT only; forced
RLS requires verified identity settings even before tenant resolution. Binding
identity is immutable; administrator mutations emit existing audit events with
database-role attribution, not tokens/subjects. Saved request contexts recheck
binding revision, scope/kind, expiry and owner membership. See [identity](IDENTITY_AUTH.md).

ADR-042's optional [browser sessions](BROWSER_AUTH.md) add no migration: bounded
ephemeral process-memory records hold hashed random handles, current-principal
snapshots and expiries, never API tokens. Restart discards sessions/flows. SQL
identity bindings remain authoritative; this is not distributed session storage.

Migration 0012 adds `document_jobs` and append-only `document_extractions`, receipt
immutability, tenant/account/source composite keys, forced RLS, protected approval
identity/transitions, and generated PDF text/FTS. Jobs bind a current source event,
receipt, processor, policy and expiring human approval; results have per-receipt
monotonic revisions and independent citations. The original `recovery_jobs` still
references quarantine receipts. See [contract](DOCUMENT_PROCESSING.md).

Migration 0011 adds `recovery_jobs_history` over tenant, account and descending
immutable creation time/UUID. This supports all-state bounded history without
reusing the unfinished-work-only claim index. No approval fields or grants change.

Migration 0010 adds [durable recovery jobs](RECOVERY_JOBS.md): immutable
tenant/account/receipt/parser approval, actor-bound idempotency, expiry, bounded
lease/claim/retry state and composite references to immutable recovery outcomes.
FORCE RLS and a protection trigger prohibit approval edits and terminal rewrites.
Runtime receives SELECT/INSERT/UPDATE but not DELETE; it receives EXECUTE only on
the narrowly scoped owner/account lock helper, not UPDATE on authority tables.

Isolated recovery reuses migration 0008 parser-versioned snapshots/attempts and 0009
encrypted raw manifests. Parser provenance `sandbox-mime-v1-<full image SHA-256>`
distinguishes isolated output from ordinary `stdlib-mime-v5` without rewriting old
citations. No schema migration, provider event or cursor mutation is introduced.
See [isolated recovery](ISOLATED_MIME_RECOVERY.md).

## Implemented external evidence (0009)

`raw_objects` permits exactly one of inline `raw_mime` or a typed `blob_ref` JSON
manifest: object key, plaintext SHA-256, byte count, ciphertext SHA-256 and key ID.
Generated `raw_size` is non-null and at most 16 MiB; inline bytes retain their
original 1 MiB bound. Contextual object paths and lowercase hashes are constrained
in SQL. Legacy rows, FORCE RLS and immutable triggers remain unchanged.
Quarantine adds `mime_too_large`. See [storage contract](LARGE_EVIDENCE_STORAGE.md).

## Implemented held-message recovery (0008)

`message_versions.parser_version` is generated from the immutable snapshot;
uniqueness is now `(tenant_id,message_id,raw_sha256,parser_version)`. Current
search matches both hash and parser. `quarantine_receipts.source_metadata` records
new source metadata; legacy null means unknown. `recovery_attempts` has immutable
receipt/parser-keyed outcomes, actor/time and optional evidence, FORCE RLS and
composite tenant/account foreign keys. Runtime gets SELECT/INSERT only. See
[recovery](QUARANTINE_RECOVERY.md) for migration compatibility and rollback.

## Implemented rule revision addition (0007)

`rule_simulations` stores immutable tenant/actor-bound sample receipts, proposal
version/hash, base ruleset revision and finite expiry. `rule_revisions` stores
immutable complete snapshots (at most 100 rules) with a unique tenant revision and
optional activation receipt or rollback source. Both use FORCE RLS, composite
tenant receipt/proposal references, append-only triggers and SELECT/INSERT-only
runtime grants. Highest revision is active; zero is empty. No provider/evidence
rows are rewritten. See [reviewed rules](REVIEWED_RULES.md).

## Implemented recovery additions (migration 0006)

`sync_inventory` records observed IDs per tenant/account/generation;
`sync_inventory_seals` certifies the stable listing's unique count before absence
reconciliation. Both are append-only. `message_sync_state` stores each provider
ID's current ready/quarantined/deleted status and latest event key, including IDs
that never produced a normalized message. `quarantine_receipts` preserves parser
version, fixed reason and raw-object hash for rejected MIME. Exact bytes remain
within the 1 MiB bound. Receipts are append-only and all four tables force tenant
RLS with composite ownership keys. Search excludes quarantined projections without
erasing historical evidence. Inventory retention/cleanup remains an explicit gate.

## Conventions

- UUID primary keys; UTC `timestamptz`; canonical JSON only for provider/versioned payloads that do not merit columns.
- Every tenant-owned table includes `tenant_id NOT NULL`; most include `created_at`, `updated_at`, `version`, and soft-delete/tombstone fields.
- Raw evidence is immutable while retained, subject to an authorized purge policy. Derived projections are replaceable. Audit is append-only while retained.
- External IDs are unique only within `(tenant_id, account_id, provider)`.
- Facts use both event/valid time and system/recorded time when truth can change.

## Identity and authorization

```text
tenants
users
tenant_memberships (tenant_id, user_id, role)
service_principals
resource_grants (subject, resource_type/id, permission, conditions)
sessions / api_clients / oauth_connections
```

RLS keys off a transaction-local, server-set tenant/user context. Never depend on client-provided SQL session variables without API validation.

## Provider and synchronization

```text
mail_accounts (provider, address, secret_ref, capability_flags, status)
mailboxes (provider_id, canonical_role, name, delimiter)
sync_cursors (account_id, scope, cursor_kind, opaque_cursor, generation)
provider_events (event_key, kind, provider_version, received_at, payload_ref)
sync_runs (range/cursor, counts, outcome, error)
```

For IMAP, cursor state includes folder, `UIDVALIDITY`, last UID, and reconciliation watermark. Gmail history IDs, Graph delta links, and JMAP states remain opaque strings.

## Evidence and normalized mail

```text
raw_objects (sha256, object_key, media_type, byte_count, encryption/key refs)
messages (account_id, provider_message_id, internet_message_id, thread_id,
          sent_at, received_at, subject, clean_text, headers_subset,
          body_hash, provider_version, lifecycle_state)
message_versions (message_id, provider_version, raw_object_id, observed_at)
participants (message_id, role, identity_id, display/address snapshot)
attachments (message_id, raw_object_id, filename, media_type, size, scan_state)
threads (canonical subject, first_at, last_at, state, summary_version)
thread_members (provider thread identifiers and heuristic links)
```

Do not store raw recipient lists as comma-separated values. Canonical identities and per-message snapshots are both required because addresses and affiliations change.

## People, organizations, projects, and temporal facts

```text
entities (type: person|organization|project|property|trip|event|other)
entity_names (canonical/alias, normalized, validity)
identities (email/domain/provider identity -> entity, confidence, evidence)
relations (subject_id, predicate, object_id, valid_from/to,
           recorded_from/to, confidence, status)
facts (subject_id, predicate, typed_value, valid_from/to,
       recorded_from/to, modality, confidence, supersedes_id)
fact_evidence (fact_id, message_id, excerpt offsets/hash, extractor version)
entity_merges (from_id, to_id, reversible status, evidence)
```

Use a controlled predicate registry and typed value fields. “Closing Friday” remains tentative until corroborated and may later be superseded. Graphiti is a useful reference for temporal facts and provenance ([project](https://github.com/getzep/graphiti)), but v1 stores this model relationally.

## Operational state

```text
obligations (owner_entity_id, counterparty_id, kind, description,
             status, due_at, confidence, source)
obligation_events (opened, updated, completed, cancelled, reopened)
thread_state (status, waiting_on_entity_id, needs_reply, next_action)
projects + project_members + project_threads + project_state
decisions (decision, status, decided_at, evidence)
drafts (provider_draft_id, content_hash, based_on_evidence, status)
```

Operational state is current, queryable projection; its history lives in events and evidence. Derived summaries never replace messages.

## Rules, proposals, and actions

```text
rules (stable_id, active_version_id, status, scope)
rule_versions (priority, predicate AST, effects, risk, provenance, hash)
rule_evaluations (message_id, version_id, matched, decision, trace)
proposals (kind, payload, evidence, risk, proposer, status, expires_at)
reviews (proposal_id/action_id, reviewer, decision, reason, payload_hash)
action_commands (type, target, parameters, preview, idempotency_key, state)
action_attempts (command_id, provider request/result refs, error, timestamps)
change_requests (feature/bug/security, description, examples, status)
```

Rule predicates are a safe declarative AST—not executable Python/SQL/regex without limits. Effects are allowlisted.

## Search

- A same-row generated PostgreSQL `tsvector` weights message subject, sender and clean body. Joined people/project names and attachment chunks require separate authorized search rows or a maintained search projection; a generated column cannot aggregate other tables.
- `message_embeddings` and `entity_embeddings` include model/version/dimension/hash; never mix incompatible embeddings in one index.
- Search documents/chunks reference message evidence and character offsets.
- Retrieval logs store query fingerprint, filters, candidates/scores, selected evidence, feedback, and version—not plaintext query where policy forbids it.

If adopted after retrieval evaluation, [pgvector](https://github.com/pgvector/pgvector)
would keep vectors alongside PostgreSQL transactional data. No vector table or
extension is currently installed by this product. A future SQLite edge cache may
use FTS5 and `sqlite-vec`, but would be disposable and tenant-scoped.

## Audit/event log

`audit_events` fields: event ID, tenant, actor kind/id, request/correlation IDs, event type, resource type/id, before/after hashes, policy/version, purpose, outcome, timestamp, and minimal metadata. Use chained hashes or immutable external storage for tamper evidence where required.

## Implemented schema versus target

The migrations currently implement tenants/memberships/accounts/cursors/events,
raw MIME, current messages, immutable normalized message versions, typed proposals,
proposal evidence links, audit, attachment receipts and intake events.
They also implement immutable rule simulations/revisions, reconciliation inventory
and seals, current sync state, quarantine receipts, recovery attempts/jobs and
separate document jobs/extractions. These are actual tables, unlike the target
entity, obligation and action sketches above. `external_identities` now provides
the bounded external-subject mapping described above. Migrations 0001–0014 describe the
schema; the restore receipt's table count also includes migration bookkeeping.
Worker leases/outcomes are in `sync_workers` and append-only `sync_runs`; enrolled
accounts have administrator-set `provider_account_id`. Current mailbox/keyword
metadata is separate from immutable raw-body evidence snapshots. People,
projects, obligations, temporal facts, actions, grants and vectors above are target
tables, not yet implemented. Source bytes are inline PostgreSQL by default or
explicitly injected encrypted local objects; hosted object storage is pending.
See [status](IMPLEMENTATION_STATUS.md).

Composite tenant/account keys prevent mismatched ownership links. The bootstrap API
only serves owner memberships; generic members/reviewers/operators have no access
until role/grant-aware paths are implemented. All actual tenant-owned tables have
forced RLS. Runtime roles have no delete privileges or raw/audit event updates.

## Retention and deletion policy

Separate policies for raw bodies, attachments, normalized text, derived facts, embeddings, audit, and backups. Disconnecting an account stops sync but does not silently erase data. Tenant deletion creates a tracked purge job, removes search/vector rows and object blobs, invalidates replicas, and records a non-content deletion certificate; backups age out under the published window.
