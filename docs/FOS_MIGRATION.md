# FOS-Master Migration and Parity Plan

## Safety contract

FOS-Master is the battle-tested donor and remains the operational FileOS reference.
Do not destructively rewrite, retire, rename, or point production FileOS at
MasterBrain until the relevant tranche passes unit, golden-corpus, integration,
shadow-production, rollback, and owner-acceptance gates. Its Git history and runtime
data stay intact.

Every extracted component records donor repository, path, commit, tests, adaptations,
and later fixes. Prefer history-preserving subtree/filter extraction when moving a
whole coherent module; for small extractions, record provenance in source and the
migration ledger below.

## Donor inventory

The detailed file/test catalog is [FOS_TOOL_INVENTORY.md](FOS_TOOL_INVENTORY.md).

| Candidate group | Representative donor files | Tests | Destination | Risk / decision |
|---|---|---|---|---|
| Hash/read-only dedupe | `dedup_tool.py`, `dedup_engine.py` | `test_dedup_tool.py`, `test_dedup_engine.py` | DataCore digest/dedupe | First tranche copies only read-only generic core; delete engine deferred |
| Safe file effects | `safe_fileops.py`, `safe_delete.py`, `folder_history.py` | `test_safe_fileops.py`, broker tests/invariants | Effect broker, not base DataCore | High risk; requires quarantine, re-hash, litigation hold, audit, rollback |
| Domain scan/index | `scan_domains.py`, `index_tools.py`, `fos_tools.py` | `test_scan_domains.py`, `test_fos_tools.py` | FileOS adapter + DataCore index | Remove hard-coded roots only after baseline capture |
| Intake | `intake_preflight.py`, `intake_pipeline.py`, `intake_classifier.py`, `intake_router.py`, `intake_consolidate.py` | matching intake tests | FileOS adapter + DataCore intake | Preserve dry-run, isolation, naming and routing behavior |
| Extraction | `doc_extract.py`, `extract_metadata.py`, `archive_unpack.py`, `image_triage.py` | matching extractor tests | DataCore extraction workers | Sandbox, dependency, format, size and error-contract review |
| Embedding/search | `embed_documents.py`, `content_search.py`, `cross_db_search.py` | `test_embed_documents.py` plus golden queries | DataCore indexing/retrieval | Separate deterministic FTS from optional embeddings |
| Database primitives | `db_connect.py`, `db_migrate.py`, schema tables, `db_audit.py` | `test_db_audit.py` | DataCore persistence | Reconcile SQLite donor behavior with PostgreSQL tenancy/RLS |
| Provenance/audit | `lineage_tracker.py`, `audit_history.py`, `file_history` schema | audit/invariant tests | DataCore provenance | Preserve append-only receipts and source hashes |
| Knowledge extraction | `extract_facts.py`, `fact_db.py`, `fact_verify.py`, `reporting.py` | operational corpus tests needed | KnowledgeCore | Convert extracted values into claims, never unquestioned facts |
| Email utilities in FOS | `email_core.py`, `email_ingest_adapter.py`, `email_sanitizer.py` | three email suites | Compare with Email capability | Inventory for lessons; do not create competing Email stack |

This inventory is code-level but not yet a complete semantic audit of every helper.
Each tranche must enumerate transitive imports, configuration, schema dependencies,
side effects, platform assumptions, and uncovered behavior before extraction.

## Parity method

1. Pin a donor commit and record file hashes.
2. Build a synthetic golden corpus covering happy paths, boundaries, failures, junk,
   held-out tests, cross-domain duplicates, collisions, partial files, and restarts.
3. Capture normalized donor results and audit/error behavior.
4. Run the same corpus through MasterBrain and fail on unexplained differences.
5. Add property/fault tests and performance budgets; never normalize away semantics.
6. Run both implementations in read-only shadow mode on authorized production-like
   inventory; compare counts, identities, hashes, metadata, errors, and timing.
7. Document intentional differences through an ADR and owner approval.
8. Switch one bounded cohort with rollback; observe; expand gradually.

Golden fixtures are synthetic and contain no private FileOS data.

## Migration ledger

| Tranche | Donor baseline | MasterBrain location | Parity | Status |
|---|---|---|---|---|
| DC-001 read-only hashing/dedupe | FOS-Master `218d5cae`, `_SYSTEM/tools/dedup_tool.py` | `src/masterbrain/datacore/dedup.py` | `scripts/datacore_parity.py`; hash/name/both synthetic corpus | Complete; 3,000-file parity and hosted gate green |
| DC-002 contracts/snapshot foundation | FOS inventory/index behavior reviewed; new source-neutral contract | `contracts.py`, `fileos.py`, `masterbrain` CLI | contract/fault/symlink/no-mutation tests; donor exclusion/hash behavior | Complete; hosted gate green |
| DC-002B FileOS inventory classifier | FOS-Master `218d5cae`, `junk_filter.py` SHA-256 `12110b1b...` | `fileos_junk_filter.py` | comment-stripped donor hash; donor self-test and 3,000 synthetic path classifications/pruning | Extracted; local parity and hosted CI/restore green; snapshot integration pending |
| DC-002C scanner-vs-snapshot shadow | FOS-Master `218d5cae`, `scan_domains.py` SHA-256 `bf4a9bb...` | `scripts/fileos_inventory_shadow.py` | 3,000 fictional files, exact common SHA/size, six explicit policy gaps, replay/change/removal, no-hash/rehash, mass-prune guard and symlink boundary | Synthetic shadow and hosted CI green; inventory-policy integration pending |
| DC-002D scanner fault/size boundaries | Same pinned scanner, isolated in-memory SQLite | `tests/test_fileos_inventory_shadow.py` | sparse 100 MiB + 1 and 2 GiB + 1, retained row after read failure, changed-during-hash, broken and directory symlinks | Local donor tests and hosted CI green; policy integration pending |
| DC-002E scanner edge safety | Same pinned scanner, isolated in-memory SQLite | `tests/test_fileos_inventory_shadow.py` | simulated dataless branch, unreadable-directory omission, donor hash-time mutation, unusual valid names | Local donor tests and hosted CI green; policy integration pending |
| DC-003 persistence/index | FOS SQLite schema studied; source-neutral PostgreSQL implementation | `persistence.py`, migration 0015 | replay/drift/concurrency/RLS/immutability/search and populated restore | Complete; hosted gate and restore green |
| DC-004A bounded text extraction | FOS-Master `218d5cae`, `doc_extract.py` + donor tests | `extraction.py`, `FileOSAdapter` | live UTF/HTML/CSV donor parity; fault and end-to-end publication corpus | Complete; hosted gate and restore green |
| DC-004B isolated PDF/Office | FOS-Master `218d5cae`, `doc_extract.py` + donor tests | document contract/worker/processor + dedicated image | DOCX/XLSX live-donor tokens; real PDF/DOCX/XLSX faults/container/SQL | Complete; hosted container and restore gates green |
| DC-005A explicit operation | Existing DataCore contracts; donor remains reference | `fileos_controller.py`, `masterbrain fileos publish` | closed config/auth/replay/source-integrity/SQL corpus | Complete; hosted PostgreSQL and restore gates green |
| DC-005B completion/freshness | Shared intake/publication contracts | migration 0017 + DataCore/Brain freshness | exact binding/counts/replay/immutability/RLS/restore | Complete; hosted PostgreSQL and restore gates green |
| DC-005C inventory reconciliation evidence | FOS-Master `218d5cae`, `corpus_reconcile.py` lessons | migration 0018 + completed-run item/absence ledgers | exact ledger balance/stale-run refusal/absence/RLS/restore | Complete; hosted PostgreSQL and restore gates green |
| DC-005I completion coverage safety | DC-002E donor omission/race findings; ADR-094 | `persistence.py`, `fileos_controller.py` | blocked error ledger, private preflight, consecutive-run absence regression | Local unit green; hosted PostgreSQL/restore pending |
| DC-005D deterministic rebuild preview | Shared normalized document/chunk contracts | `fileos_rebuild_preview` + Brain API | run-bound pagination/hash/identity/chunk verification/no effects | Complete; hosted PostgreSQL and restore gates green |
| DC-005E immutable index generations | Shared normalized document/chunk contracts | migration 0019 + DataCore active-generation reads | exact generation/replay/activation/rollback/RLS/restore | Complete; hosted PostgreSQL and restore gates green |
| DC-005F private generation operator | DC-005E generation contract | `masterbrain fileos index` | exact scopes/check/replay/revocation/rollback/query parity | Complete; hosted PostgreSQL and restore gates green |
| DC-005G current FileOS retrieval | DC-005E active generations | Brain API `/v1/brain/fileos-search` | two-source/multi-query parity/rollback/RLS/restore | Complete; hosted PostgreSQL and restore gates green |
| DC-005H current-aware grouped retrieval | DC-005G + reviewed KnowledgeCore | explicit unified-search visibility | compatibility/current selection/scopes/RLS | Complete; hosted PostgreSQL and restore gates green |

DC-001 deliberately excludes local config discovery, donor logging, CLI presentation,
and all delete/move operations. Those omissions do not change the returned scan and
comparison contracts being adopted; the live-donor harness compares those outputs.
DC-002B preserves the donor scanner/reconciler filter separately from DC-001 dedupe
defaults; see [inventory classifier contract](FILEOS_JUNK_POLICY.md). It is not yet
used for snapshots or a FileOS cutover.
DC-002C measures [whole-inventory shadow differences](FILEOS_INVENTORY_SHADOW.md)
without publishing a manifest or touching the donor database. The scanner policy
switch requires a separate decision and consecutive-run acceptance tests.

## Proposed next tranches

1. **DC-004C archives/images/OCR:** separate opt-in workers with format-specific
   corpora, expansion/page budgets and containment.
2. **DC-005G retrieval policy:** private generation operation and initial query parity
   are complete; expand the corpus and define deliberate global current/historical
   visibility before redirecting existing DataCore or unified search.
3. **KC-001 claim/entity projection:** import donor lessons without treating model
   output as truth.
4. **FileOS effect broker:** last, after read-side parity and explicit safety ADRs.

## Cutover and rollback

Cutover requires zero unexplained golden differences, agreed production-shadow
tolerances, equivalent or better failure visibility, backup/restore proof, a versioned
rollback procedure, and owner sign-off. Rollback returns reads/writes to FOS-Master
without discarding new evidence; queued MasterBrain work is fenced and reconciled.
FOS-Master retirement is a separate decision after sustained accepted operation.
