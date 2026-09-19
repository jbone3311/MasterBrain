# Data Model

## Conventions

- UUID primary keys; UTC `timestamptz`; canonical JSON only for provider/versioned payloads that do not merit columns.
- Every tenant-owned table includes `tenant_id NOT NULL`; most include `created_at`, `updated_at`, `version`, and soft-delete/tombstone fields.
- Raw evidence is immutable. Derived projections are replaceable. Audit is append-only.
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

- A generated PostgreSQL `tsvector` combines weighted subject, people, organization/project names, clean body, and attachment text.
- `message_embeddings` and `entity_embeddings` include model/version/dimension/hash; never mix incompatible embeddings in one index.
- Search documents/chunks reference message evidence and character offsets.
- Retrieval logs store query fingerprint, filters, candidates/scores, selected evidence, feedback, and version—not plaintext query where policy forbids it.

PostgreSQL holds transactional data and vectors together via [pgvector](https://github.com/pgvector/pgvector). A SQLite edge cache may use FTS5 and `sqlite-vec`, but it is disposable and tenant-scoped.

## Audit/event log

`audit_events` fields: event ID, tenant, actor kind/id, request/correlation IDs, event type, resource type/id, before/after hashes, policy/version, purpose, outcome, timestamp, and minimal metadata. Use chained hashes or immutable external storage for tamper evidence where required.

## Retention and deletion

Separate policies for raw bodies, attachments, normalized text, derived facts, embeddings, audit, and backups. Disconnecting an account stops sync but does not silently erase data. Tenant deletion creates a tracked purge job, removes search/vector rows and object blobs, invalidates replicas, and records a non-content deletion certificate; backups age out under the published window.
