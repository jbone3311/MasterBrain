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
| DC-002V private v2 search comparison | Existing DataCore lexical query; no donor edit | `fileos_v2_index_generation.py`, `persistence.py`, ADR-128 | human-only exact-generation preview, stale/tenant/scope refusal, active-v1 separation and 3,000-row bounded query | Merged via PR #85; exact-head and merged-main CI/strict/restore green; readiness scaling was corrected later by PR #90; no public route, activation, absence or donor cutover |
| DC-002W human v2 review API | Existing ADR-128 reviewer and pinned donor; no donor edit | `api.py`, `schemas.py`, ADR-147 | closed bounded request, human/three-scope gate, direct library/API parity, stale/unknown refusal and nonactivation | Implemented on branch for synthetic/disposable review; full gates pending; no current v2 visibility, source effects or cutover |
| DC-002U readiness scaling correction | Same immutable shared generation and pinned donor; no donor edit | migration 0048, ADR-131 | indexed exact chunk/base closure, existing five-second statement limit, direct-SQL wrong-text and activation refusal, fresh full suite plus two populated 3,000-row repeats | Merged via PR #90 with exact-head and merged-main CI/strict/restore green; issue #84 closed, no current v2 visibility or cutover |
| DC-005N linear v1 completed ledger | Existing v1 FileOS run semantics; no donor edit | migration 0043, `persistence.py`, ADR-122 | items-before-receipt, one deferred whole-run check, source-locked item and receipt triggers, replay/direct SQL/3,000-item stress | Merged via PR #73; exact-head CI/strict/restore green; controlled performance comparison remains issue #71; no v2 publication or FileOS cutover |
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
5. **FileOS effect broker:** last, after read-side parity and explicit safety ADRs.

## Cutover and rollback

Cutover requires zero unexplained golden differences, agreed production-shadow
tolerances, equivalent or better failure visibility, backup/restore proof, a versioned
rollback procedure, and owner sign-off. Rollback returns reads/writes to FOS-Master
without discarding new evidence; queued MasterBrain work is fenced and reconciled.
FOS-Master retirement is a separate decision after sustained accepted operation.
