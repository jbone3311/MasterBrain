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
| Statement intelligence | `statement_extract.py`, `statement_line_items`/`statement_extraction_runs` schema, `CMD_INTELLIGENCE.md` | no dedicated checked-in recipe suite; synthetic golden cases needed | KnowledgeCore typed financial line-item projection | Preserve row grouping and reconciliation outcomes; do not infer a holding from a money mention or sum successive statements |
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
| DC-002AE historical row decisions | Pinned FOS-Master `218d5cae`; donor unchanged | `fileos_v2_later_row_decisions.py`, migration 0093, Brain API, ADR-261 | Fictional exact-row atomic replay/correction/history, forged SQL, worker/source denial and stale-v1 refusal; 100-row/3,000-file service stress and two-cluster populated local restore pass; hosted gates separate | Human review metadata only; no run signoff, absence approval, current search, file effect, live shadow or donor cutover |
| DC-002AD human later classification inspection | Pinned FOS-Master `218d5cae`; donor unchanged | `fileos_v2_later_index_generation.py`, Brain API, ADR-260 | Fictional exact prior-row paging, possible-absence candidate, worker/source-grant and closed-input checks; 3,000-row final-page and empty-filter stress pass | Historical and nonactivating; ADR-261 adds row decisions, while run signoff, rollback, live shadow, hosted gates and cutover remain open |
| DC-002AC human later search comparison | Pinned FOS-Master `218d5cae`; donor unchanged | `fileos_v2_later_index_generation.py`, Brain API, ADR-259 | Fictional human/worker, source-grant, second-run review-flag and unchanged-current-search checks | Historical and nonactivating; ADR-260/261 add classification inspection and row decisions, while run signoff, rollback, live shadow, hosted gates and cutover remain open |
| DC-002AB later shared generation | Pinned FOS-Master `218d5cae`; donor unchanged | `fileos_v2_later_index_generation.py`, migration 0092, ADR-258 | Fictional exact ready-run/hashed-item/chunk assembly, forged SQL and activation refusal; 3,000-file later stress and full local suite pass | Historical and nonactivating; human comparison now ADR-259, while live shadow, rollback, hosted gates and cutover remain open |
| DC-002AA historical later-run completion | Pinned FOS-Master `218d5cae` donor scanner/policy; donor unchanged | `fileos_v2_later_run_completion.py`, migration 0091, ADR-257 | Fictional clean/possible-absence run, ready-attempt and fresh-scan binding, SQL forgery/immutability checks; local full suite 3,856 passed/19 skipped; 3,004-row donor shadow unchanged | Historical only; generation assembly, rollback, owner-approved live shadow, hosted gates, current reads and cutover remain open |
| EB-006I first-party XLSX result review | ADR-242–244 synthetic exact result/review bridge; FOS-Master unchanged | `web/xlsx_review.js`, Email owner screen, ADR-246 | Bounded pages, browser-computed full-text SHA-256, exact human review, stale-session/refusal tests and fictional API-to-UI shape pass | Existing approval ID required; no browser worker power, approval queue, actual-browser/image/hosted gate, live mail or cutover |
| EB-006H server-owned XLSX bridge provenance | ADR-242/243 synthetic review and worker command; FOS-Master unchanged | `email_xlsx_document_bridge.py`, migration 0086, ADR-244 | API rejects caller code revisions; SQL rejects forged new reviews/receipts; exact-result publication and retrieval remain; populated fictional XLSX restore and local full PostgreSQL suite passed at `0c64f8b` | Semantic transform revision, not Git commit; actual-image/hosted and live-source gates open |
| EB-006G restricted reviewed Email XLSX command | ADR-239–242 exact synthetic source/result/review; FOS-Master unchanged | `email_xlsx_publication_controller.py`, CLI, ADR-243 | Distinct worker actor, account pin, tenant-bound login, check/refusal/publication/replay/Search pass on fictional PostgreSQL | No live mail, review screen, actual-image execution, FileOS cutover or financial claim |
| EB-006F split human review and worker publication | ADR-239/240 result and ADR-241 document bridge; FOS-Master unchanged | `email_xlsx_document_bridge.py`, migration 0085, ADR-242 | Human-only bounded inspect/review, worker-only publication, immutable SQL review and source-grant/currentness tests | Exact text-level bridge only; hosted/image/restore and live-source gates open |
| EB-006E reviewed Email XLSX document bridge | ADR-239/240 exact synthetic approval and immutable result; FileOS donor unchanged | `email_xlsx_document_bridge.py`, migration 0084, ADR-241 | Fictional approval → worker result → reviewed normalized document/chunks/provenance → currentness-gated search, plus forgery and revocation tests | Text-level occurrence bridge only; actual-image/hosted/restore, review UI, cell-level tables, live mail and financial parity remain open |
| DC-004G restricted XLSX replay operator | ADR-233 pinned FOS table baseline, ADR-236 reviewed receipt; donor unchanged | `source_tier_fileos_xlsx_table_controller.py`, CLI, ADR-237 | Fictional private config/check, exact source, tenant-bound login and command-to-database receipt pass | No actual-image run, table API, live root, financial claim or cutover |
| EB-006B retained Email XLSX row-layout proof | ADR-232 exact-MIME/part derivation and ADR-234 isolated table worker; donor unchanged | `datacore/email_xlsx_table_derivation.py`, ADR-238 | Fictional occurrence-bound parent/part/text/image checks, blank-row layout distinction and fail-closed faults | Pure digest-only proof; no review receipt, Email XLSX bridge, indexed cells, actual-image run or live mail |
| EB-006C separate Email XLSX extraction approval | ADR-232/238 exact occurrence proof; PDF jobs/bridge remain PDF-only; donor unchanged | `email_xlsx_approvals.py`, migration 0082, ADR-239 | Human-only, synthetic exact-parent/part/image approval, tenant fence, direct SQL forgery/immutability and populated upgrade tests | This tranche is approval only; ADR-240 adds a private result and ADR-241 separately adds a reviewed document bridge. No live account or financial claim |
| EB-006D isolated Email XLSX result | ADR-239 separate exact approval, shared pinned DataCore document image; donor unchanged | `email_xlsx_results.py`, migration 0083, ADR-240 | Fictional exact retained-MIME re-extraction, final source/worker checks, immutable text/digest and formula/forgery refusal | Worker result itself is private and nonpublishing; ADR-241 separately bridges it. Actual-image, live mail and financial claims remain open |
| DC-004F reviewed FileOS XLSX table receipt | ADR-233 pinned FOS table baseline and ADR-235 confined replay; donor unchanged | `source_tier_fileos_xlsx_table_replay.py`, migration 0081, ADR-236 | Fictional current human review, source/version race, grant and immutable SQL receipt tested on disposable PostgreSQL | Digest-only worker observation; no command, actual-image execution, cell publication, live root or cutover |
| DC-004E confined current XLSX table replay | ADR-233 pinned FOS table baseline; existing DataCore no-follow root and document normalizer | `datacore/current_fileos_xlsx_table_replay.py`, ADR-235 | Fictional exact source/text digest, source-root/image binding, row-layout digest and changed/symlink/formula refusal | Pure nonpublishing worker proof, with reviewed receipt in DC-004F; actual-image case collected but locally unrun, no API, live root or cutover |
| DC-004D bounded XLSX row/cell projection | FOS-Master `218d5cae` donor XLSX AST replay and ADR-233 gap baseline | `datacore/xlsx_tables.py`, `xlsx_tables_worker.py`, `xlsx_tables_processor.py`, ADR-234 | Fictional ordinary and 1,000-row row-value parity with donor; physical row positions and sheet visibility retained; formulas fail closed | Separate nonpublishing isolated worker; actual-image gate collected but locally unrun, no persistence, Brain API, financial attestation or FileOS cutover |
| DC-004C XLSX table/gap baseline | FOS-Master `218d5cae`, `doc_extract.py` SHA-256 `746932e5ce033a9b8f8bd7155a88dfbb6d1c57a9916aea2230e6afbe1a3ab269` | `tests/test_xlsx_donor_parity.py`, ADR-233 | Fictional ordinary, 1,000-row and 24 sparse/multi-sheet case value overlap; exact 2,000/2,001-row boundary; explicit table-shape, formula, row-cap, encrypted and `.xlsm` divergences | Nonpublishing exact-donor replay when donor checkout exists; portable DataCore golden in CI; not full workbook/financial parity or a cutover |
| EB-006A retained Email XLSX derivation | Existing shared DataCore `bounded_xlsx_v1` worker extracted for FileOS; FOS-Master donor unchanged | `datacore/email_xlsx_derivation.py`, ADR-232 | Fictional exact parent/part byte proof invokes the same isolated document processor; uncached formulas defer, repeated attachment bytes keep distinct parent identities | Pure nonpublishing proof only; no review receipt, Email bridge/index, actual-image run, live provider or financial claim |
| KC-001N authorized project-fact report and typed field | Donor reporting semantics remain a reference, not a runtime schema | `project_facts.py`, migrations 0066/0071, ADR-211/212 | Fictional grant/currentness/API/client and exact-decimal SQL tests; deliberately no donor money-sum parity claim | First read-only product projection only; no ownership, verified investment balance, live source or donor cutover |
| KC-001O controlled names for new reviewed project facts | FOS report names are reference semantics, never copied as certified facts | `fact_predicates.py`, migration 0073, ADR-214 | Fictional code/SQL catalog parity, unknown/type/unit refusal and retained historical rows | First project-fact catalog only; no generic claim/event/role registry, aliases, ownership, total or donor cutover |
| KC-001P latest predicate retirement and read discovery | Donor reporting names still carry no MasterBrain truth authority | migration 0074, `project_facts.py`, `brain_client.py`, ADR-215 | Fictional later-deprecated SQL rejection and scoped API/client catalog checks | Source-content-free orientation only; no vocabulary edit, owner allocation, total or donor cutover |
| KC-001M entity/money report baseline | Same pinned `reporting.py` and SHA-256 as KC-001L | `report_recipe_parity.py`, ADR-210 | Fictional goldens plus local DuckDB/SQLite exact-donor replay for top entities, cross-domain spread and raw money facts, including 1,000-row repeat and rounding divergence fix | Isolated nonpublishing comparison only; no authorized runtime, verified holdings or cutover |
| KC-001L report coverage/timeline baseline | FOS-Master `218d5cae`, `_SYSTEM/tools/reporting.py` SHA-256 `e52ee7672121a609171a827eab086080dcea159ef987e21f0793e32528521cc9` | `report_recipe_parity.py`, ADR-209 | Explicit fictional goldens, exact-hash donor AST replay for both reports and 1,000-row repeat; wall-clock field excluded | Isolated nonpublishing comparison; ADR-210 follows with entity/money rows; no source-grant-aware runtime report, verified holding or cutover |
| KC-001G private FileOS text replay receipt | Current DataCore no-follow `fileos-text-v1` path; FOS-Master donor untouched | `statement_fileos_replay.py`, migration 0064, ADR-189 | Fictional exact/current FileOS bytes, wrong root, changed text, symlink, source-version race, tenant/grant/SQL refusal and replay | Private worker-observed receipt only; not exposed as a verified holding, no PDF/OCR/Email proof or live cutover |
| KC-001F narrow source-text replay | Existing `fileos-text-v1` DataCore transform; donor unchanged | `statement_derivation.py`, ADR-188 | Fictional exact-byte/hash/text replay and fail-closed mismatches for bounded text/Markdown/HTML/CSV | Pure proof primitive only; no authorized source reacquisition, proposal binding, PDF/OCR/Email proof, live source or cutover |
| KC-001D owner proposal preview | ADR-170/171 first Streetbeat recipe and ADR-172 ledger, donor untouched | `statement_persistence.py` reader, human-only Knowledge route, ADR-173 | Fictional Email/FileOS source/hash/span recheck, paging, assistant refusal, stale/grant denial | Owner API inspection of unreviewed proposals only; no approval, investment dossier, live source or cutover |
| KC-001C durable private statement proposal | ADR-170 pinned Streetbeat recipe, donor untouched | `statement_persistence.py`, migration 0057, ADR-172 | Synthetic current Email/FileOS document binding, exact rows, replay/concurrency, tenant/SQL refusal | Worker-only append-only ledger; no API, reviewed holdings, live source, donor cutover or replacement claim |
| KC-001B typed private statement candidate | ADR-170 pinned Streetbeat syntax and rows, no donor edit | `statement_candidates.py`, ADR-171 | exact decimal, text-span/hash, incomplete/mismatch, Email/FileOS reference, 1,000-row stress | Pure in-memory projector now called by KC-001C; deliberate fail-closed divergences, no direct DB/API/reviewed holding |
| KC-001A statement recipe seed | FOS-Master `218d5cae`, `_SYSTEM/tools/statement_extract.py` SHA-256 `f5b0c8bc5c0c9f01fa8decdecba36a27b81ccfd212894409472bac8526b577fe` | `statement_recipe_parity.py`, ADR-170 | Four fictional golden cases, optional exact-hash donor AST replay, 1,000-row repeatability | Isolated candidate; not runtime, typed financial model, live-source parity or cutover |
| KC-001B Fidelity recipe baseline | Same pinned donor file and hash; donor checkout unchanged | `statement_recipe_parity.py`, ADR-174 | Six fictional goldens including two-column missed-row and zero fallback, optional exact-hash AST replay, 1,000 distinct rows | Low-confidence isolated comparison only; no typed Fidelity proposal, live-source parity or cutover |
| KC-001E Jefferies recipe baseline | Same pinned donor commit/file/hash; donor checkout unchanged | `statement_recipe_parity.py`, ADR-187 | Five fictional goldens: negative cash, multi-lot subtotal, single-lot/unpriced detail, transaction continuation, zero fallback and invalid period; optional exact-hash AST replay and 1,000-security stress | Isolated category/detail/transaction comparison only; no typed Jefferies proposal, verified investment or cutover |
| KC-001H Wells Fargo savings recipe baseline | Same pinned donor commit/file/hash; donor checkout unchanged | `statement_recipe_parity.py`, ADR-191 | Fictional daily-balance direction goldens, mixed/residual and 12/13-unknown boundaries, optional exact-hash AST replay and 1,000-row stress | Isolated deposit-account comparison only; no typed savings proposal, verified balance, live statement or cutover |
| KC-001I Wells Fargo brokerage recipe baseline | Same pinned donor commit/file/hash; donor checkout unchanged | `statement_recipe_parity.py`, ADR-198 | Seven fictional goldens for cash, acquired lots, page-break deduplication, over-six-lot summaries, zero fallback and incomplete tails; optional exact-hash AST replay and 1,000-row stress | Isolated, nonpublishing comparison only; no typed brokerage proposal, verified holding, live statement or cutover |
| KC-001J Wells Fargo credit-line recipe baseline | Same pinned donor commit/file/hash; donor checkout unchanged | `statement_recipe_parity.py`, ADR-199 | Nine fictional goldens for both text layouts, opposite debt signs, linked-bank exclusion, unexpected labels, page/header noise, optional fields and incomplete text; exact-hash AST replay and 1,000-row stress | Isolated supplied-text comparison only; no source-PDF derivation proof, typed loan proposal, verified balance or cutover |
| KC-001K Charles Schwab brokerage recipe baseline | Same pinned donor commit/file/hash; donor checkout unchanged | `statement_recipe_parity.py`, ADR-203 | Nine fictional old-template/failure-era goldens, exact-hash AST replay and 1,000-row stress; Cash-and-Bank-Sweep, symbols, accounting signs and empty redesigned/scanned input | Isolated supplied-text comparison only; no PDF/OCR derivation proof, typed proposal, verified holding or cutover |
| DC-001 read-only hashing/dedupe | FOS-Master `218d5cae`, `_SYSTEM/tools/dedup_tool.py` and `doc_extract.py` with exact source hashes | `src/masterbrain/datacore/dedup.py` | `scripts/datacore_parity.py`; clean-checkout/hash attestation, hash/name/both synthetic corpus | Runtime extraction is complete; 3,000-file parity reran locally on 2026-10-15 with exact donor bytes. Current-branch hosted gate remains unavailable; live cutover is not proved |
| DC-002 contracts/snapshot foundation | FOS inventory/index behavior reviewed; new source-neutral contract | `contracts.py`, `fileos.py`, `masterbrain` CLI | contract/fault/symlink/no-mutation tests; donor exclusion/hash behavior | Complete; hosted gate green |
| DC-002B FileOS inventory classifier | FOS-Master `218d5cae`, `junk_filter.py` SHA-256 `12110b1b...` | `fileos_junk_filter.py` | comment-stripped donor hash; donor self-test and 3,000 synthetic path classifications/pruning | Extracted; local parity and hosted CI/restore green; snapshot integration pending |
| DC-002C scanner-vs-snapshot shadow | FOS-Master `218d5cae`, `scan_domains.py` SHA-256 `bf4a9bb...` | `scripts/fileos_inventory_shadow.py` | 3,000 fictional files, exact common SHA/size, six explicit policy gaps, replay/change/removal, no-hash/rehash, mass-prune guard and symlink boundary | Synthetic shadow and hosted CI green; inventory-policy integration pending |
| DC-002D scanner fault/size boundaries | Same pinned scanner, isolated in-memory SQLite | `tests/test_fileos_inventory_shadow.py` | sparse 100 MiB + 1 and 2 GiB + 1, retained row after read failure, changed-during-hash, broken and directory symlinks | Local donor tests and hosted CI green; policy integration pending |
| DC-002E scanner edge safety | Same pinned scanner, isolated in-memory SQLite | `tests/test_fileos_inventory_shadow.py` | simulated dataless branch, unreadable-directory omission, donor hash-time mutation, unusual valid names | Local donor tests and hosted CI green; policy integration pending |
| DC-002F root-confined FileOS source reads | Same pinned scanner; its outside-root symlink read is intentionally not adopted | `confined_files.py`, snapshot and text/document extraction | synthetic file/ancestor swap below and above root, read/locator stability, ordinary pinned-donor SHA/size shadow | Isolated ADR-100 implementation; 3,000-file local donor shadow passed (3,002 ordinary matches, six policy and two symlink differences); hosted gate and restore green on `6e2eb8e`; no policy switch or cutover |
| DC-002G donor-policy shadow profile | Same pinned scanner/classifier, no donor edit | `fileos_donor_shadow.py`, `scripts/fileos_donor_policy_shadow.py` | isolated synthetic pinned-donor path/size/SHA comparison, metadata-only and sparse-boundary tests | Merged via PR #46 with exact-head and main CI/restore green; 3,004 ordinary rows match on 3,000-file corpus; no publishable manifest, policy switch or live-source claim |
| DC-002H confined shadow metadata | Same pinned scanner; no donor edit | `confined_files.py`, `fileos_donor_shadow.py` | no-follow descriptor metadata stat, root/ancestor/leaf swap tests, 3,000-file pinned-donor replay | Merged via PR #48; exact-head and main CI/restore green; shadow-only, no publishable policy switch |
| DC-002I source-bound donor candidate | Same pinned scanner; no donor edit | `fileos_donor_candidate.py`, ADR-112 | hashed/deferred separation, v1 rejection, malformed/root-drift tests, 3,000-file pinned-donor comparison | Merged via PR #50; exact-head and main CI/restore green; nonpublishing candidate only, not a v2 manifest or policy switch |
| DC-002J v1-to-donor transition preview | Same pinned scanner; no donor edit | `fileos_donor_transition.py`, ADR-113 | complete-shape v1 comparison, six explicit policy gaps on 3,000-file pinned-donor corpus, 10,000-item v1 bound and fault/root/time tests | Merged via PR #52; final head and merged-main CI/strict/restore green; no v2 publication or switch |
| DC-002K completed v1 baseline preview | Same pinned scanner; no donor edit | `persistence.py`, `fileos_donor_transition.py`, ADR-114 | exact latest completed v1 receipt/intake/items, pre/post-scan check, concurrent newer-run refusal, scope and PostgreSQL tests | Merged via PR #55; final-head and merged-main CI/strict/restore green; nonpublishing, no v2 baseline transaction or switch |
| DC-002L immutable transition review packet | Same pinned scanner; no donor edit | migration 0038, `fileos_donor_transition.py`, `persistence.py`, ADR-115 | one scan, completed-v1 binding, locked insert, immutable/RLS packet, replay and nonpublication tests | Merged via PR #57; exact-head and merged-main CI/strict/restore green; not a v2 baseline, owner approval or FileOS switch |
| DC-002M bounded transition review read | Same pinned scanner; no donor edit | `persistence.py`, ADR-116 | content-free summary, evidence-scoped locator pages, stale-run and digest-tamper tests | Merged via PR #59; exact-head and merged-main CI/strict/restore green; private only, no approval, v2 publication or FileOS switch |
| DC-002N nonpublishing v2 inventory staging | Same pinned scanner; no donor edit | migration 0039, `persistence.py`, ADR-117 | hashed/deferred/excluded/error SQL shape, locked packet binding, 3,000 hashless row stress, count balance, replay, RLS and nonpublication | Merged via PR #61; exact-head and merged-main CI/strict/restore green; no v2 completion or switch |
| DC-002O human transition review receipt | Same pinned scanner; no donor edit | migration 0040, `fileos_transition_approval.py`, ADR-118 | exact plan/row/digest/count recheck, human owner scope, blocker and stale-run refusal, immutable/RLS receipt, no publication | Merged via PR #63; exact-head and merged-main CI/strict/restore green after one intermittent container rerun (issue #64); no v2 baseline transaction or switch |
| DC-002P approved-stage fresh verification | Same pinned scanner; no donor edit | migration 0041, `fileos_v2_baseline.py`, ADR-119 | worker scope, fresh exact row/root/policy match, stale-run and changed-source refusal, immutable/RLS receipt, no publication | Merged via PR #66; local full suite, 3,000-file pinned-donor shadow and PR CI/strict/restore green; merged-main full CI passed on attempt 2 after issue #64 MIME recurrence on attempt 1; no v2 importer, completion or switch |
| DC-002Q v2 evidence preparation | Same pinned scanner; no donor edit | migration 0042, `fileos_v2_preparation.py`, ADR-121 | third fresh scan, policy-scoped candidate-to-DataCore version map, hashed evidence, hashless preservation, v1-import compatibility, replay/lock/RLS/nonpublication | Merged via PR #70; exact-head CI/strict/restore and local 3,000-row preparation stress green; legacy v1 large-completion performance issue #71 remains; no v2 completion, current-read switch or FileOS cutover |
| DC-002R owner baseline authorization | No donor edit | migration 0044, `fileos_v2_authorization.py`, ADR-123 | exact reviewed-plan/preparation/count binding, human-only scope, replay, stale-v1 refusal, RLS/nonpublication | Merged via PR #75; exact-head CI/strict/restore green; no v2 completion or cutover |
| DC-002S private v2 baseline completion | Same pinned scanner; no donor edit | migration 0045, `fileos_v2_completion.py`, ADR-124 | fresh exact scan, authorization/preparation/stage binding, hashless preservation, 3,000-row stress, RLS/replay/nonactivation | Merged via PR #77; exact-head CI/strict/restore and local full suite green; no current-read switch or cutover |
| DC-002T v2 document publication readiness | Same pinned scanner/extraction references; no donor edit | migration 0046, `fileos_v2_document_publication.py`, ADR-125 | source-bound text/document processing, exact ready/blocked hashed-row ledger, no current activation | Merged via PR #79; exact-head and merged-main CI/strict/restore green; no v2 current index, absence or cutover |
| DC-002U private shared v2 generation | Existing DataCore generation/chunk contracts; no donor edit | migration 0047, `fileos_v2_index_generation.py`, ADR-126 | exact ready-attempt item/chunk closure, replay/stale/direct-SQL refusal, 3,000-row stress and v1 regression | Merged in PR #81 with exact-head and merged-main CI/strict/restore green; SQL bars v2 activation, so no current-read switch, absence or cutover |
| DC-002V private v2 search comparison | Existing DataCore lexical query; no donor edit | `fileos_v2_index_generation.py`, `persistence.py`, ADR-128 | human-only exact-generation preview, stale/tenant/scope refusal, active-v1 separation and 3,000-row bounded query | Merged via PR #85; exact-head and merged-main CI/strict/restore green; readiness scaling was corrected later by PR #90. At this checkpoint there was no API route; DC-002W later added one. No activation, absence or donor cutover |
| DC-002W human v2 review API | Existing ADR-128 reviewer and pinned donor; no donor edit | `api.py`, `schemas.py`, ADR-147 | closed bounded request, human/three-scope gate, direct library/API parity, stale/unknown refusal and nonactivation | Merged via PR #116; final-head and merged-main CI/strict/restore green; historical preview only, with no current v2 visibility, source effects or cutover |
| DC-002X confined shadow directory walk | Pinned FOS-Master `218d5cae` scanner; no donor edit | `fileos_donor_shadow.py`, ADR-152 | descendant/ancestor symlink swaps cannot enumerate outside filenames; ordinary 3,004-row and maximum 9,998-row donor comparisons unchanged | Merged via PR #130 with exact-head CI/strict/restore green; nonpublishing security correction, not policy acceptance or cutover |
| DC-002Y shadow symlink-target boundary | Same pinned scanner; no donor edit | `fileos_donor_shadow.py`, `fileos_donor_candidate.py`, ADR-156 | all symlink target kinds become coverage errors without target-type inspection; v2 profile/candidate refuse stale v1 staging; ordinary donor golden parity unchanged | Merged via PR #141; corrected exact-head CI/strict/restore and 9,994-file local donor stress passed; merged-main results in build receipt; no v1 switch or cutover |
| DC-002Z unencodable locator boundary | Same pinned scanner; no donor edit | `fileos.py`, `fileos_donor_shadow.py`, `fileos_donor_candidate.py`, ADR-167 | synthetic surrogate and Linux-required invalid-byte fixture; valid siblings remain visible, affected parent gets one opaque error, v1 completion and v2 candidacy refuse | Fail-closed safety divergence from donor SQLite text behavior; does not establish live platform acceptance or cutover |
| DC-002U readiness scaling correction | Same immutable shared generation and pinned donor; no donor edit | migration 0048, ADR-131 | indexed exact chunk/base closure, existing five-second statement limit, direct-SQL wrong-text and activation refusal, fresh full suite plus two populated 3,000-row repeats | Merged via PR #90 with exact-head and merged-main CI/strict/restore green; issue #84 closed, no current v2 visibility or cutover |
| DC-005N linear v1 completed ledger | Existing v1 FileOS run semantics; no donor edit | migration 0043, `persistence.py`, ADR-122 | items-before-receipt, one deferred whole-run check, source-locked item and receipt triggers, replay/direct SQL/3,000-item stress | Merged via PR #73; exact-head CI/strict/restore green; [controlled trigger-cost comparison](FILEOS_COMPLETION_BENCHMARK.md) passed on local and container PostgreSQL 17.11, broader load remains issue #71; no v2 publication or FileOS cutover |
| DC-003 persistence/index | FOS SQLite schema studied; source-neutral PostgreSQL implementation | `persistence.py`, migration 0015 | replay/drift/concurrency/RLS/immutability/search and populated restore | Complete; hosted gate and restore green |
| DC-004A bounded text extraction | FOS-Master `218d5cae`, `doc_extract.py` + donor tests | `extraction.py`, `FileOSAdapter` | live UTF/HTML/CSV donor parity; fault and end-to-end publication corpus | Complete; hosted gate and restore green |
| DC-004B isolated PDF/Office | FOS-Master `218d5cae`, `doc_extract.py` + donor tests | document contract/worker/processor + dedicated image | DOCX/XLSX live-donor tokens; real PDF/DOCX/XLSX faults/container/SQL | Complete; hosted container and restore gates green |
| DC-004C selected archive/image OCR | FOS-Master `218d5cae`, `archive_unpack.py`/`image_triage.py` as references; no donor edit | isolated archive/image workers, exact selected OCR receipts/operator and ADR-107 current read | bounded worker corpora, exact member/parent/receipt fencing, tenant/limit tests, image parity harness | Explicit synthetic path implemented; automatic selection, broad donor shadow and cutover unaccepted |
| DC-005A explicit operation | Existing DataCore contracts; donor remains reference | `fileos_controller.py`, `masterbrain fileos publish` | closed config/auth/replay/source-integrity/SQL corpus | Complete; hosted PostgreSQL and restore gates green |
| DC-005B completion/freshness | Shared intake/publication contracts | migration 0017 + DataCore/Brain freshness | exact binding/counts/replay/immutability/RLS/restore | Complete; hosted PostgreSQL and restore gates green |
| DC-005C inventory reconciliation evidence | FOS-Master `218d5cae`, `corpus_reconcile.py` lessons | migration 0018 + completed-run item/absence ledgers | exact ledger balance/stale-run refusal/absence/RLS/restore | Complete; hosted PostgreSQL and restore gates green |
| DC-005I completion coverage safety | DC-002E donor omission/race findings; ADR-094 | `persistence.py`, `fileos_controller.py` | blocked error ledger, private preflight, consecutive-run absence regression | Hosted PostgreSQL/restore green; later policy, mass-loss, exclusion and root guards are separate PRs |
| DC-005J mass-loss completion guard | Pinned donor `scan_domains.py` tripwire; ADR-095 | `persistence.py` | 20→10 refusal, unchanged complete run/absence, 20→12 acceptance, replay and threshold boundaries | Hosted CI/restore green on PR #19; no override or cutover |
| DC-005K versioned inventory-policy identity | Current snapshot v1 and ADR-096; donor policy still reference-only | `fileos.py`, `persistence.py`, migration 0031 | exact policy digest, unchanged-policy replay/absence, drift refusal, SQL new-insert constraint, populated legacy upgrade | Hosted CI/restore green on PR #20 runtime head; review/integration and legacy baseline remain |
| DC-005L excluded-locator accounting | Current snapshot v1, ADR-097 and pinned donor shadow divergence | `fileos.py`, `persistence.py` | exact bounded exclusion ledger, one-item size/symlink/directory transition refusal, genuine deletion | Hosted CI/restore green on PR #21 runtime head; review/integration pending; no donor policy switch |
| DC-005M physical-root binding | Current snapshot v1, ADR-098, no donor edit | scanner/controller/adapter, DataCore intake/completion, migration 0032 | same-root replay, wrong-root pre-intake refusal, scan-time drift, legacy unknown preservation, SQL trigger/receipt constraints, restore | Hosted CI/restore green on PR #22 runtime head; review/integration pending; no cutover |
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
DC-002G consumes the extracted classifier only in an isolated, nonpublishing
inventory profile. It narrows the known membership gap in synthetic comparison,
but does not replace snapshot v1 or authorize metadata-only publication.
DC-002H makes even that shadow profile's metadata-only observation root-bound
without opening placeholder bytes. It does not prove real cloud-placeholder
behavior or change the donor's pathname-based scanner.
DC-002I gives that observation a [source-bound candidate ledger](FILEOS_DONOR_CANDIDATE.md).
Null-digest donor rows remain deferred without version or evidence identities;
the current v1 importer intentionally refuses the ledger.
DC-002J provides a [read-only transition preview](FILEOS_DONOR_TRANSITION.md)
that classifies each prior v1 item without inferring deletion across the policy
boundary. It is not a completion receipt or cutover authorization.
DC-002K binds an opt-in private preview to the latest exact completed v1 run,
checking again after the donor scan. It does not reserve that run after return,
persist v2 state or change the FileOS completion/absence path.
DC-002L can seal one candidate and preview as an immutable, private review
packet only after an advisory-locked latest-run recheck. It does not change
the completion/absence path, authorize publication or attest future root state.
DC-002M makes that packet inspectable through a compact private summary and
separately authorized locator pages. Its current-run flag is a read-time status,
not approval or a baseline reservation.
DC-002N projects one current sealed packet into a separate relational v2
staging ledger. Hashless rows stay hashless; SQL balances the four row kinds.
Staging is not a completed run, freshness or absence authority and does not
switch the source policy.
DC-002O can bind a human owner's decision to one exact staged plan after a
fresh latest-v1 check. The receipt is historical review evidence, not a
completed v2 baseline, deletion evidence, live-root attestation or cutover.
DC-002P rechecks that approval and performs a fresh source scan while holding
the source lock. Exact staged-row parity produces a historical verification
receipt, still not a completed v2 run, continuing root attestation or cutover.
DC-002Q rechecks the historical artifacts and performs another exact, bounded
source scan under that lock. Hashed rows become policy-scoped shared evidence
with an immutable candidate-to-prepared mapping. This avoids colliding with
v1's mtime-bearing immutable version while keeping hashless rows hashless.
It changes no current pointer, v1 run, absence or search result.
DC-002R binds a separate human owner's authorization to that exact prepared
stage, plan digest and count maps. It still does not complete a v2 baseline or
attest live root bytes; completion must recheck the source separately.
DC-002S performs that fresh source-locked recheck and seals one private,
historically complete v2 baseline over the immutable stage/prepared ledger.
It is inspectable without locators, but neither v1 current state nor search
and absence inference consumes it.
DC-002T processes the prepared hashed versions through existing bounded
extraction and records a complete document outcome attempt. It is a direct
dependency of v2 indexing, not a current-read or policy switch.
DC-002W exposes only the already-bounded ADR-128 comparison to a human with
explicit transition-review, search and evidence grants. A historical v2 hit
is not current FileOS data or cutover evidence; SQL still refuses activation.
ADR-135 adds an opt-in tenant-bound database login to the private v1 FileOS
publisher. It changes neither donor policy nor v2 activation and is not a
cutover gate by itself. ADR-138 extends that opt-in fence to FileOS indexing
and rollback; ADR-139 extends it to the private archive derivative commands.
ADR-141 routes the three legacy Email worker commands through an opt-in bound
login. Private v2 library callers, hosted credential operations and operational
acceptance still need separate work. None of these changes proves FileOS cutover.

## Proposed next tranches

The local pinned-donor comparison on 2026-10-03 passed at both 3,000 stress
files and the 9,994-stress-file maximum (10,000 prior v1 rows), with zero
unexplained membership differences; 44 focused donor tests passed. A
2026-10-15 direct recheck at the 9,994-file maximum against the unchanged
pinned donor again found zero unexplained membership differences across 9,998
ordinary, replay, changed, metadata-only and candidate rows. It retained the
six known transition policy gaps; see the [current receipt](BUILD_RECEIPT.md).
The merged PR #164 filename probe adds a pinned-donor cross-directory case/Unicode
corpus and conditional same-directory sibling probes. The former passed on
this Mac; the latter could not run on its collision-folding filesystem. A
shared-path sibling probe passed on hosted Linux, but the pinned donor is not
checked out there; donor-on-Linux collision parity still needs evidence. It
does not close platform parity.
The follow-up 260-file case-collision corpus passed locally against the pinned
donor on a temporary case-sensitive APFS volume. That closes a local
same-directory case-variant comparison only; APFS still folded Unicode
normalization siblings, and hosted CI has no pinned donor checkout. No
donor-on-Linux Unicode claim or policy switch follows from it.
The test-only parity tranche pins exact donor scanner/classifier source copies
with SHA-256 checks so hosted Linux can run the golden corpus without access
to the private FOS-Master repository. The original checkout remains the local
authority and is not edited; the copied files are not runtime code. A
dedicated CI step refuses silent skips of distinct case/Unicode siblings. The
PR #167 code-head Linux gate passed all three such tests using the exact
snapshot; both full suites executed all 491 PostgreSQL-marked tests. This
closes synthetic donor-vs-DataCore parity for those filename cases on hosted
Linux, not real placeholder/permission behavior, the six policy gaps, live
shadow or cutover.
ADR-167 treats a name that cannot become UTF-8 text as incomplete scan
coverage before reading its bytes. A Linux-required test compares the pinned
donor's SQLite-text failure with MasterBrain's opaque parent error; the
transition candidate refuses that error rather than staging a partial source.
This is a deliberate safety difference, not a new claim of donor parity or
permission to modify the source name automatically.
This is capacity evidence for the synthetic, nonpublishing path only. The six
known policy gaps, real cloud placeholders, permission faults, live platform/name
behavior, owner-authorized live shadow, later v2 current/absence semantics and
rollback still require review. No v2 activation or FOS-Master change is
authorized by this result; see the [exact receipt](BUILD_RECEIPT.md).
ADR-251 adds a pure, synthetic-only consecutive donor-observation preview for
the later-run policy question. It separates possible absence from hashless,
deferred, excluded and error-covered paths, but is not connected to an actual
completed v2 baseline and cannot create absence or current-read authority.
ADR-252 now binds that policy preview to the real completed v2 baseline under
the private source lock and a fresh synthetic root scan. Only an ephemeral
count/digest summary returns; the immutable later-run ledger, absence/current
semantics, live shadow and rollback are still open.
ADR-253 retains the next synthetic observation as an immutable private review
packet linked to that same completed baseline. It can be replayed and inspected
without rescanning, but is explicitly not a per-row completed later-run ledger.
Absence, v2 current reads, live shadow, rollback and donor cutover remain gated.
ADR-254 projects that historical packet into a separately sealed, exact-row
coverage closure for future processing. It accounts for current donor rows and
prior classifications but does not process hashed evidence or complete a later
run. All current/absence/cutover gates remain unchanged.
ADR-255 now prepares policy-scoped, source-bound DataCore evidence for those
sealed hashed rows only after an exact fresh donor-policy rescan. A new later-
only file is represented without becoming current. Document publication,
terminal processing of all rows, completed later-run semantics, rollback,
live shadow and cutover remain separate gates.
ADR-256 now processes accepted later hashed rows into historical normalized
documents and seals one explicit outcome per current row. Deferred/excluded
rows are accounted without fabricated content; scan errors still block at
preparation. The attempt is not a completed later run, current index or
absence authority. FOS-Master remains unchanged.
ADR-257 now completes one historical later run only after a ready attempt
and a fresh matching source scan. The immutable receipt retains possible-
absence, mass-loss and prior-coverage review flags but grants no current
index, absence-event, source-effect or cutover authority. Next assemble an
exact generation, prove rollback, and run owner-approved live shadow.
ADR-258 now assembles an exact later-run shared DataCore generation and
checks its hashed item and chunk membership in SQL. It cannot be activated;
ADR-259 now adds the human historical comparison with separate result layers
and run review flags; it changes no current read or donor source. The next
step, ADR-260, exposes exact historical prior-row classifications for bounded
human inspection. The remaining gates are explicit owner adjudication,
rollback-ready policy, live shadow and hosted validation.

1. **DC-002 donor inventory policy:** review the isolated shadow profile,
   source-bound candidate, completed-baseline preview and staged v2 rows, then
   extend fault/platform acceptance. ADR-119 adds fresh approval-bound source
   verification, and ADR-121 prepares hashed evidence without publishing it.
   ADR-123 adds owner authorization for an exact prepared baseline attempt.
   ADR-124 adds a private completed baseline. ADR-125 adds document readiness.
   ADR-126's private shared-table v2 generation readiness is merged;
   ADR-128 compares its historical search with active v1 under human-only
   review; ADR-147 makes that comparison available through a human-only,
   bounded Brain API route. Activation remains barred. Separate ADRs are still
   required for current visibility, later v2 runs, absence suppression,
   rollback and cutover.
2. **DC-004C archives/images/OCR:** explicit isolated workers and current read are
   implemented. Extend format-specific corpora, containment, donor shadow and
   reviewed selection before any automatic fan-out or cutover.
3. **DC-005G retrieval policy:** private generation operation and initial query parity
   are complete; expand the corpus and define deliberate global current/historical
   visibility before redirecting existing DataCore or unified search.
4. **KC-001 claim/entity projection:** import donor lessons without treating model
   output as truth.
   Preserve the donor's separate statement recipe/line-item/reconciliation path and
   source-tier/hash confirmation behavior; build a synthetic golden corpus before
   extraction. The [live-alpha preservation assessment](LIVE_ALPHA_AND_FOS_PRESERVATION.md)
   defines the cross-source company-dossier known answer. This KnowledgeCore track
   can be developed while the FileOS inventory policy remains in shadow; it does
   not authorize a donor cutover.
   KC-001A (ADR-170) seeds one isolated Streetbeat recipe and four fictional donor
   goldens. KC-001B (ADR-171) adds a private typed/text-span candidate with
   deliberate fail-closed coverage checks. Next: extend vendor and fault corpus,
   verify source-tier/hash derivation under tenant grants, and design an atomic,
   reviewable evidence-linked projection. Neither slice authorizes live intake.
5. **FileOS effect broker:** last, after read-side parity and explicit safety ADRs.

## Cutover and rollback

Cutover requires zero unexplained golden differences, agreed production-shadow
tolerances, equivalent or better failure visibility, backup/restore proof, a versioned
rollback procedure, and owner sign-off. Rollback returns reads/writes to FOS-Master
without discarding new evidence; queued MasterBrain work is fenced and reconciled.
FOS-Master retirement is a separate decision after sustained accepted operation.
