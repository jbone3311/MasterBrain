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
| `brain_fileos_run_receipts` | Fully accounted run, outcomes and provenance | Append-only |
| `brain_fileos_run_items` | Exact item/outcome membership of a completed run | Append-only |
| `brain_fileos_absence_events` | Item absent between consecutive completed inventories | Append-only |

Every table carries `tenant_id`, has forced PostgreSQL row-level security and is
available only through explicit runtime-role grants. FileOS evidence is
`source_bound`: this tranche stores a relative locator and verified hash, not file
bytes. The source remains authoritative and read-only.

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
