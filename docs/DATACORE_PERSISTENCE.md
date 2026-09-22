# DataCore Persistence and Lexical Retrieval

Checkpoint 2 adds an additive shared persistence slice. It does not replace any
EmailBrain table and does not alter FOS-Master.

## Durable records

| Record | Purpose | Mutation rule |
| --- | --- | --- |
| `brain_sources` | Enrolled Email or FileOS source identity | Status/display metadata only |
| `brain_source_items` | Stable source-relative locator and current pointer | Observation pointers only |
| `brain_source_versions` | Hash, size, type, metadata and observation time | Append-only |
| `brain_evidence` | Evidence identity and storage/retention state | Append-only |
| `brain_normalized_documents` | Bounded normalized text | Append-only |
| `brain_chunks` | Deterministic offsets, hashes and FTS vector | Append-only |
| `brain_provenance*` | Transform, version, code/config and inputs | Append-only |
| `brain_change_events` | Source-version and publication notifications | Append-only |
| `brain_jobs` | Bounded extraction/OCR/normalization/index work | Controlled state transitions |
| `brain_import_receipts` | Actor-scoped idempotency result | Append-only |
| `brain_email_bridge_receipts` | Legacy Email evidence to shared identity/provenance closure | Append-only |
| `brain_parts` | Parent/child evidence link and immutable attachment occurrence outcome | Append-only |
| `brain_email_attachment_bridge_receipts` | Legacy attachment occurrence to shared part/evidence closure | Append-only |
| `brain_email_document_bridge_receipts` | Approved legacy PDF derivative to shared document/provenance closure | Append-only |
| `brain_fileos_run_receipts` | Fully accounted run, outcomes and provenance | Append-only |
| `brain_fileos_run_items` | Exact item/outcome membership of a completed run | Append-only |
| `brain_fileos_absence_events` | Item absent between consecutive completed inventories | Append-only |
| `brain_index_generations` | Run/code/chunker-bound generation identity and counts | Append-only |
| `brain_index_generation_items` | Exact per-generation item/document disposition | Append-only |
| `brain_index_generation_chunks` | Deterministically rebuilt lexical chunks | Append-only |
| `brain_index_generation_receipts` | Database-validated generation readiness | Append-only |
| `brain_index_activations` | Active generation selection and rollback history | Append-only |

Every table carries `tenant_id`, has forced PostgreSQL row-level security and is
available only through explicit runtime-role grants. FileOS evidence is
`source_bound`: this tranche stores a relative locator and verified hash, not file
bytes. The source remains authoritative and read-only.

Current Email versions may be added through `bridge_current_email_version`. It
requires both shared ingest and document-publication scopes, the exact legacy UUID,
an idempotency UUID and a code revision. It preserves raw MIME in `raw_objects`, uses
opaque shared locators, publishes the legacy lexical fields with the deterministic
`email-message-v1` normalizer and records the complete mapping in migration 0020.
Historical, deleted, quarantined or inconsistent projections fail closed. Existing
Email ingestion and search are not redirected.

`bridge_email_attachment` maps one explicit immutable attachment receipt only after
its parent message is bridged and still current/visible. Each occurrence gets a
distinct opaque item/version/evidence/part even when hashes match. Existing non-empty
bounded extracted text is normalized and chunked; deferred, skipped, failed, pending
and empty outcomes create no document. Bytes remain inside the retained parent MIME
and are never read or copied by the bridge.

`bridge_email_document_extraction` requires an immutable extraction with a completed
approval job plus its already-bridged, current attachment occurrence. It publishes
bounded extracted or partial PDF text as another document on the same evidence,
records processor/policy/revision/result provenance and never loads attachment bytes.

## Snapshot import

`DataCoreStore.import_fileos_snapshot` validates the whole manifest before opening
its publication transaction. It enforces the manifest version, FileOS source kind,
stable item/version identity derivation, one observation time, safe locators,
lowercase SHA-256, scalar metadata, count agreement and a 10,000-item bound.

Imports are idempotent per tenant, actor and UUID key. Reusing a key with a different
request fails. Existing identities with different meaning fail. The transaction
serializes the source, appends only genuinely new versions and changes the current
pointer only when the observation is not older. Any failure rolls back the entire
manifest.

## Text publication and search

`publish_text` requires `brain.document.publish`, accepts at most 1 MiB of valid
NUL-free text, deterministically chunks it at soft whitespace boundaries, records
hashes/provenance and publishes a change. Repeating the same version, normalizer and
body is a no-op. It does not extract or interpret files; Checkpoint 3 supplies
isolated format workers.

`search` requires `brain.search`, uses PostgreSQL `simple` full-text search, returns
at most 50 compact chunk hits, and includes document, evidence, source and locator
identities for drill-down. Direct assistant SQL is not an API.

`search_current_email_family` separately ranks current bridged message documents,
ADR-065 attachment text and ADR-066 approved PDF derivatives. Each layer has its own
1–25 result bound and every branch rejoins the current visible legacy parent plus
shared parent/child current pointers. Generic retained-history and message-only search
remain unchanged.

## Recovery and operations

The existing migration checksum lock and least-privilege grant path include these
tables. The synthetic restore drill hashes every public table before and after
restore, so DataCore records participate automatically once seeded. Destructive
down-migration is not a rollback mechanism: stop this path and restore through the
tested recovery procedure if required.

Migration `0017_fileos_run_receipts.sql` separates whole-run completion from intake.
A receipt is inserted only after every snapshot item is accounted and is bound to the
same actor, UUID and canonical manifest digest as its intake. Closed outcome counts
and published-document totals are checked in Python and PostgreSQL. The latest
complete receipt drives source freshness; partial work never advances it.

Migration `0018_fileos_inventory_reconciliation.sql` adds the exact per-item ledger.
A deferred database constraint independently balances it against the receipt. Only a
newer completed observation can become current; a stale completion conflicts. Missing
items are recorded only by comparing two consecutive completed ledgers, so partial
imports cannot manufacture deletion. Absence retains all evidence and does not yet
change search visibility.

`fileos_rebuild_preview` reads a maximum of 50 opaque item records from the latest
completed ledger while holding the source completion lock. It recomputes normalized
body/document/chunk hashes and identities, returning only verification dispositions
and counts. The cursor is bound to that exact run. The preview writes only the normal
access audit; it does not execute a rebuild or change source/index state.

Migration `0019_datacore_index_generations.sql` executes the separately accepted
derivative rebuild. It reconstructs bounded chunks from verified normalized documents
for the exact latest completed run. The plan digest and generation ID include the run,
observation, item/evidence/document identities, code revision and chunker version.
PostgreSQL validates declared counts before readiness and prevents later append.

Activation requires `brain.index.activate` and an idempotency key. Active-generation
search reads only the newest append-only activation for one FileOS source. Reactivating
an older ready generation is rollback; no evidence or index generation is mutated.
Generation build/activation are library operations in this tranche, not public API
mutations or automatic scheduling.

`search_current_fileos` selects the newest activation independently for every
tenant-visible source and searches only those immutable generation chunks. The Brain
API exposes this as `/v1/brain/fileos-search`. Existing `search` remains a retained-
history compatibility path rather than being silently redefined.
