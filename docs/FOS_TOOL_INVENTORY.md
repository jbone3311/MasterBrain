# FOS-Master Common Tool and Test Inventory

Baseline: `jbone3311/FOS-Master` commit
`218d5caec2f20b9047fd3eb8e027dc671acf0c15` (inspected 2026-09-21). The donor has
159 top-level Python tools and 24 top-level Python test modules under `_SYSTEM`.
This inventory covers common intake/data/knowledge candidates; domain-specific
report generators, governance utilities and UI helpers remain donor-local unless a
later tranche identifies shared behavior.

## DataCore candidates

| Concern | Exact donor files | Existing donor tests | Migration order |
|---|---|---|---|
| Hash and duplicate discovery | `dedup_tool.py`, `dedup_engine.py` | `test_dedup_tool.py`, `test_dedup_engine.py` | DC-001 read-only core now; policy engine later |
| Safe filesystem effects | `safe_fileops.py`, `safe_delete.py`, `folder_history.py` | `test_safe_fileops.py`; dedup/broker invariants embedded elsewhere | Effects phase only |
| Source discovery | `scan_domains.py`, `index_tools.py`, `fos_tools.py`, `domain_paths.py`, `spoke_config.py` | `test_scan_domains.py`, `test_fos_tools.py`, `test_spoke_tools.py` | DC-003 read-only adapter |
| FileOS inventory exclusions | `junk_filter.py` (shared by scanner and reconciler) | donor 18-case self-test; MasterBrain 3,000-path live classifier parity | Pure classifier extracted; snapshot integration awaits policy ADR |
| Intake | `intake_preflight.py`, `intake_pipeline.py`, `intake_classifier.py`, `intake_router.py`, `intake_consolidate.py`, `intake_manager.py`, `ingest_folder.py` | five matching `test_intake_*.py` modules | DC-003/DC-004 |
| Extraction | `doc_extract.py`, `extract_metadata.py`, `archive_unpack.py`, `image_triage.py`, `zip_index.py`, `statement_extract.py` | `test_doc_extract.py`, `test_extract_metadata.py`, `test_archive_unpack.py`, `test_image_triage.py` | DC-004 by format/risk |
| Index/retrieval | `content_search.py`, `embed_documents.py`, `cross_db_search.py`, `corpus_reconcile.py` | `test_embed_documents.py`; parity corpus required for others | DC-005 |
| Persistence | `db_connect.py`, `db_migrate.py`, `db_audit.py`, `schema_manager.py`; `spoke_state_schema.sql` | `test_db_audit.py` | Reimplement contract on shared PostgreSQL primitives |
| Provenance/audit | `lineage_tracker.py`, `audit_history.py`, `change_scan.py`, `drift_report.py`, `content_integrity_check.py` | partial operational/self-tests; new golden faults required | DC-002 onward |
| Validation/error visibility | `data_validator.py`, `_lib/verify.py`, `_lib/errlog.py`, `content_regression_check.py` | `test_data_validator.py`, `test_errlog.py` | Shared worker primitives after contract audit |

## KnowledgeCore candidates

| Concern | Exact donor files | Existing donor tests | Migration note |
|---|---|---|---|
| Entities/facts | `extract_facts.py`, `fact_db.py`, `fact_verify.py`, `extract_all_domains.py` | No complete known-answer suite found | Import as claims with evidence/confidence, not truth |
| Cross-domain reports | `reporting.py`, `report_data_collector.py` | No complete semantic suite found | Use as query/evaluation reference |
| Routing knowledge | `routing_engine.py`, `naming_classifier.py`, `spoke_config.py` | intake suites cover portions | Separate learned pattern from effect authority |
| Freshness/lineage | `ssot_freshness.py`, `ssot_drift_check.py`, `source_registry`/`output_lineage` schema | Operational checks | Map to KnowledgeCore freshness and provenance |

## Overlap requiring consolidation, not blind copy

`email_core.py`, `email_ingest_adapter.py`, and `email_sanitizer.py` with
`test_email_core.py`, `test_email_ingest_adapter.py`, and
`test_email_sanitizer.py` overlap the retained Email capability. They are reference
inputs for a behavior comparison, not a second Email stack.

The donor's `unified_index`, FTS5 triggers, `file_history`, intake queue, routing
patterns, entities/mentions, document facts and fact type registry inform the shared
model. They are not copied wholesale because MasterBrain requires hosted tenancy/RLS,
immutable evidence versions and source-neutral provenance.

## Baseline content hashes

The exact first-tranche source hash is:

```text
093f1800e8faff59b70502865f73e4aeaa56112edd43326fc8c7c548cdc5bff8  _SYSTEM/tools/dedup_tool.py
746932e5ce033a9b8f8bd7155a88dfbb6d1c57a9916aea2230e6afbe1a3ab269  _SYSTEM/tools/doc_extract.py
823ce03a8d7e2b8c42845ae1685db0ed92391461428b989034b9d83140421a41  _SYSTEM/tests/test_doc_extract.py
```

The migration ledger pins the Git commit as the primary provenance. The extraction
hashes cover the DC-004 text/Markdown/HTML/CSV candidate and its donor test suite;
optional PDF/Office/image dependencies remain outside that tranche. Each later tranche
must add source hashes for all transitive candidate files before adaptation.

DC-004C archive audit adds:

```text
a1d20a266313d7b2c36af3ffc78311ee1999824cfe933883a3ed4f87223d21ba  _SYSTEM/tools/archive_unpack.py
a5b177791a3045661b42c1aa4692b54546c8ce18711f00d7ca74fd08c055dfbc  _SYSTEM/tests/test_archive_unpack.py
```

The pinned donor archive suite passes 47 hermetic/adversarial tests. Runtime imports
are standard-library-only plus best-effort logging. `intake_pipeline.py`,
`doc_extract.py`, `email_core.py` and `intake_preflight.py` are integration references;
`zip_index.py` and `archive_manager.py` contain database/file effects and are excluded.
See [archive extraction plan](FILEOS_ARCHIVE_EXTRACTION.md).

DC-004D image/OCR audit adds:

```text
b3fbc5ab7bf8ce06072865b5f1c0c3cd57ab968c0490e6996f95ed37c657cfb0  _SYSTEM/tools/image_triage.py
553503e599e91636e8e004b45e348559a3e43fc848b0dd1310454641db22be63  _SYSTEM/tools/extract_metadata.py
83cff8f74b5736d7efb1fd130f968b6295f12a906d2281f1037781c7a4119335  _SYSTEM/tests/test_image_triage.py
```

Together with the already pinned `doc_extract.py` and its test hash, the focused donor
image suites pass 149 tests using the donor's optional dependencies. Useful behavior
is split: `doc_extract.py` supplies a 25-megapixel/5,000-character limit but no OCR
timeout; `image_triage.py` supplies full-decode checks and a 90-second Tesseract
timeout but also naming, SQLite, command and Anthropic effects; `extract_metadata.py`
temporarily disables Pillow's global bomb guard. The tranche therefore extracts a
closed isolated subset rather than copying any module. See the
[image/OCR inventory and contract](ARCHIVE_IMAGE_OCR.md).

FileOS inventory classifier extraction adds:

```text
12110b1b5404c31172d65878a9327bf8f415f8d343b668aa5982948c840da437  _SYSTEM/tools/junk_filter.py
```

The target copy has the same digest. See [classifier contract](FILEOS_JUNK_POLICY.md).
## Gaps found during inspection

- Common-tool test coverage is uneven: intake/dedupe/extraction are comparatively
  strong; knowledge/reporting and several audit/index tools rely on self-tests or
  operations rather than isolated known-answer suites.
- Some tools resolve live hub paths/configuration and cannot be imported safely into a
  hosted multi-tenant service without an adapter boundary.
- File effect safety is distributed across dedupe, safe-delete, domain resolution,
  database audit/history and policy documents. Migrating one file alone would weaken
  the safety case.
- The SQLite schema includes domain-specific tables beside reusable primitives;
  schema extraction must be selective and additive.
