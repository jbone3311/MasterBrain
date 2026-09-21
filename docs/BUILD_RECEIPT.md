# Build and validation receipt

Updated 2026-09-21 Pacific. Product: `jbone3311/CW-EmailBrain`, verified **private**.

## Explicit PDF operator execution and demo credential repair

Implementation/test revision **73a8459** passed
[CI 35584256073](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35584256073)
and [restore 35584256115](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35584256115),
observed 2026-09-21 Pacific. Later receipt-only edits do not change this tested runtime.

- **1,632 standard Python tests passed**, including **222 real PostgreSQL cases**;
  no CI skips. **52 Node contracts**, **five actual MIME-container cases** and
  **15 actual PDF-container cases** passed. Repeated repository-gate and restore
  subsets are not counted twice.
- **79 new standard cases**: 68 offline controller/credential/server-option checks
  and 11 PostgreSQL cases. They test closed fixed-purpose/policy configuration,
  MIME-versus-document separation, exact worker scope, synthetic account/runtime
  role/owner denial, no-claim preflight, private key material, bounded counters,
  credential rotation/revocation, stop, cancellation and restarted publication.
- The added actual-container case invokes **fresh CLI processes** through private
  configuration, encrypted source, the real restricted PDF image, real SQL and
  cited search. Preflight leaves attempts at zero; execution publishes one result;
  restarting finds no duplicate work. Original raw bytes and sync cursor survive.
- Fixed demo provisioning's accidental inclusion of a worker-only scope. The
  regression exercises emitted credential generation/serialization/registry
  authentication with SQL provisioning mocked; it is not a new live enrollment test.
  A fixed human allowlist and validation now precede credential-file publication.
- Restore reverified **26 tables, 142 rows, two tenants and four encrypted objects**,
  equal hashes, RLS and refusal of incomplete database-only recovery. **18.24 seconds**
  includes disposable startup, not production RTO/PITR. Restore fixtures/results
  are unchanged; the real extraction/CLI check is the separate CI proof above.
- Local: **1,410 passed, 222 explicit PostgreSQL skips**, 52 Node passes, locked
  dependencies, lint, strict typing over **41 modules**, separate restore-script
  typing, CLI help, docs/repository/diff checks. Incremental secret scan through
  73a8459 found no leaks. Two existing Python deprecations and action/runner
  migration notices remain tracked, non-failing supply-chain work.

[ADR-036](adr/036_document_operator_controller.md) and the
[operator guide](DOCUMENT_CONTROLLER.md) describe exact scopes, private files,
unscanned synthetic policy, count/exit semantics and revocation limits. No schema,
new dependency, real mailbox, provider write, cloud resource, remote model or
Factory mutation was added. The document owner UI, hosted supervision, live/scanner
policy and sustained acceptance remain open; the next assignment is the owner UI.

## Documentation and handoff consistency pass

Documentation-only follow-up to **25f69de**, whose
[CI 35580992550](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35580992550)
was observed successful. Runtime/schema remains a2c5957 with test follow-up 9a99dfa,
covered by the exact receipts below. No new runtime, migration, dependency, workflow
permission or cloud deployment is introduced by this documentation pass.

Corrected stale PDF/search/security/runbook claims, explained the separate ingestion,
MIME recovery, document and candidate-model paths, aligned the next build assignment,
expanded contribution guidance and added release acceptance/evidence requirements.
GitHub build/PR templates now request implementation boundaries and exact test scope.
Historical OSS counts and historical test receipts retain their observation dates.

Local recheck: locked development sync, lint, strict typing across 40 modules,
**1,342 Python passes / 211 explicit PostgreSQL skips**, **52 Node passes**, docs and
repository gates. The two existing upstream Python deprecation warnings remain.
Real PostgreSQL/actual-container/restore proof is the linked CI evidence, not the
local skipped cases. This record does not claim CI on a later documentation SHA.

## Approved PDF source-to-search integration

Runtime/schema implementation **a2c5957**, test/document follow-up **9a99dfa**.
[CI 35580405200](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35580405200)
passed at 9a99dfa. The unchanged restore/runtime implementation passed
[restore 35579931717](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35579931717)
at a2c5957. Verified 2026-09-21 Pacific.

- **1,553 standard Python tests passed**, including **211 real PostgreSQL cases**,
  no CI skips. **52 Node contracts**, **five actual MIME-container cases** and
  **14 actual PDF-container cases** passed. Repeated quality-gate suites and the
  restore subset are not counted twice.
- The added actual-container case proves a known PDF-only term absent before
  approval becomes searchable after source-bound approval, restricted extraction,
  SQL publication and document evidence read. The original deferred receipt and
  provider cursor remain unchanged. Default API/MIME reader exclusion still passes.
- **51 new standard cases**: 18 offline configuration/scope/schema checks and
  33 database/API cases. They cover distinct worker authority, actor idempotency,
  queue/paging bounds, concurrent claims/cancel, worker restart/retries, current
  owners/account/enrollment/source events, approval/lease expiry, processor/hash
  substitution, atomic audit rollback, immutable revisions, bounded page excerpts,
  historical/current search, cached-result authorization and foreign resources.
- Restore verified **26 tables, 142 rows, two tenants, four encrypted objects**;
  all hashes and tenant RLS passed. Completed/cancelled/pending document jobs,
  immutable page evidence and document FTS survived. SQL-only/missing-object restore
  was refused. **19.71 seconds** includes disposable startup, not production RTO.
  This drill uses a known-answer document adapter; actual extraction is verified
  separately by the real container suite.
- Local checks: **1,342 passed, 211 explicit PostgreSQL skips**, 52 Node passes,
  locked dependencies, lint, strict typing across **40 source modules**, separate
  restore-script typing, repository/docs/diff checks. Incremental secret scan
  through 9a99dfa found no leaks. Existing two Python deprecations and CI action/
  runner notices remain non-failing, tracked supply-chain work.

The first CI run found the older populated-upgrade test's expected migration list
omitted 0012; the actual upgrade succeeded. The expectation was corrected without
removing immutable-evidence checks. Review also strengthened fault injection: source
replacement/deletion now uses actual ingestion and every mutation must complete,
with the expected terminal/retry state asserted. This avoids treating a failed
fault setup as successful stale-source protection. Final checks above all passed.

[ADR-035](adr/035_approved_document_processing.md) and
[document processing](DOCUMENT_PROCESSING.md) define the synthetic-only API/library,
new worker scope, protected migration, fixed unscanned policy and opt-in search.
No owner document UI, document operator CLI, scanner, real mailbox, cloud resource,
remote model, mailbox write or Factory mutation was added. Those remain separate
work/acceptance gates. This is meaningful integration, not a production release.

## Source-bound restricted PDF worker groundwork

Implementation **a041647** passed [CI 35576368521](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35576368521)
and [restore 35576368531](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35576368531).
Subsequent receipt/status documentation does not change tested runtime.

- **1,502 standard Python tests**, including **178 real PostgreSQL cases**, passed
  without CI skips. **52 Node UI contracts**, **five existing actual MIME-container
  cases** and **13 additional actual PDF-container cases** passed. Repeated gate
  tests and restore subsets are not double-counted.
- New standard coverage: **110 PDF worker/parent contract cases**. Known-answer
  source text, exact MIME/part/hash binding, wrong sources, strict envelopes,
  encrypted/empty-password refusal, damaged/image-only/mixed-page documents,
  feature deferral, stream/text/page limits, unexpected failures, isolation before
  disclosure, exact-owned cleanup and lazy dependency loading are covered.
- Actual PDF containers verified the known-answer mailbox marker, page text,
  partial/no-text, encrypted/damaged/unsupported/over-budget outcomes and a
  substituted attachment hash. They do **not** publish PDF text into SQL/search.
- Local: **1,324 passed, 178 explicit PostgreSQL skips**, two existing upstream
  deprecations; locked sync, lint, strict typing over **39 source modules**, separate
  restore-script typing, 52 Node tests, repository/docs gates and diff checks passed.
- Both images built. CI verified pypdf/openpyxl/docx/lxml stay absent from the
  default API/MIME image; only the separate optional PDF image adds pinned pypdf.
- Restore: **24 tables, 119 rows, two tenants, four encrypted objects**, equal
  hashes and tenant RLS, database-only refusal, **14.91 seconds** including disposable
  startup. No PDF result table exists yet; this is not new PDF-result restoration
  or a production RTO/PITR claim.
- Git-history secret scan through a041647: **43 commits**, no detected leaks.

Review found pypdf's implicit empty-password initialization. The pinned worker
overrides that narrow hook to defer encryption before password work; negative
tests verify it is not invoked. Selected upstream advisories were reviewed, not
exhaustively vulnerability-certified. The private hook needs upgrade regression.

[ADR-034](adr/034_source_bound_pdf_worker.md) and [worker guide](PDF_WORKER.md)
define fixed byte/page/resource bounds, independent partial/unscanned outcomes
and separate profile+image provenance. No API/schema/grants, queue integration,
scanner, OCR, mail action, private input or cloud deployment is added. Existing
ingestion receipts and PDF-only search expectations remain deferred/absent.
Durable tenant-authorized approval, versioned results/citations and FTS integration
are the next EB-006 requirement; standalone parser tests do not close it.

Known warnings remain: Starlette/httpx and anyio aliases; GitHub's Node 20 action
migration and upcoming Ubuntu runner migration. Supply-chain modernization and
production operational/security/live-service gates remain in the backlog.

## September 21 documentation alignment

Documentation-only changes follow `c0e2aec` (whose
[CI 35573423696](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35573423696)
passed). Runtime/test implementation remains `4286504`; no code, schema, lockfile,
permissions or deployment changes are included in this alignment.

The refresh synchronizes product guides, feature/method explanations, changelog,
code map, roadmap and Factory next assignment; corrects stale generator language;
and makes the ready-message attachment-processing gap explicit across architecture,
security, API, storage and operations. Historical third-party counts and receipts
remain dated observations, not newly remeasured results.

Local rechecks: all 16 requested pack documents plus four product guides and local
Markdown file targets passed the documentation checker; locked offline dependency
sync, lint, strict source typing, 52 Node checks, repository gate and whitespace
checks passed. Python: **1,214 passed, 178 PostgreSQL skips, two known upstream
deprecation warnings**. The gate repeats tests; do not double-count it. No local
PostgreSQL/container/live-service acceptance or new model quality is claimed.
The checker validates file targets, not every external URL or Markdown anchor.

## Known-answer synthetic mailbox and paced replay

Implementation **4286504** passed [CI 35572975435](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35572975435)
and [restore 35572975472](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35572975472).
Subsequent receipt/status-only documentation edits do not change tested runtime.

- **1,392 standard Python tests**, including **178 real PostgreSQL cases**, passed
  without CI skips. **52 Node contracts** and **five additional actual-container
  tests** passed. Repeated repository-gate tests/restore subsets are not added again.
- New coverage: **26 generator/format/export tests**, **48 provider-wrapper cases**
  and **14 actual SQL workflow cases**. An independently read PDF/XLSX/DOCX subset,
  PNG/ZIP/MIME/calendar checks, fixed manifest golden, matching hashes, source-date
  disorder, duplicate delivery, simulated metadata/deletion, corruption, interruption,
  ambiguous commit responses, competing feeders and enrollment/scope denial are covered.
- Local: **1,214 passed, 178 explicit PostgreSQL skips**, two existing upstream
  test deprecations. Ruff, strict typing over **36 modules**, separately typed
  restore script, 52 Node checks, documentation/repository gates and diff checks passed.
- CI verified the dev-only pypdf/openpyxl/python-docx/lxml readers are **absent from
  the built runtime image**. Production MIME/binary-extraction permissions are unchanged.
- Restore: **24 tables, 119 rows, two tenants and four encrypted objects**, equal
  content hashes and RLS; database-only restore refused. **20.64 seconds** includes
  disposable cluster startup, not a production RTO or restoration of this new corpus.
- Full Git-history secret scan through 4286504: **40 commits**, no detected leaks.

[ADR-033](adr/033_known_answer_synthetic_mailbox.md) and the updated
[test-mailbox guide](TEST_MAILBOX_PLAN.md) document two commands: exclusive offline
packet export and bounded/optionally paced ingestion into a fresh unenrolled
synthetic account. Cursor identity hashes the exact authored manifest. No model,
provider token, external document input, public corpus or SMTP service is used.

Produced sample: seed 42, three projects, **36 `.eml` sources, 48 attachment
occurrences and 45 scheduled events**. Source packet manifest hash:
`3c8586ccafe4d0b6d259e7d8f372601091691ec45df15a02576f4db3453d2702`.
The packet includes explicitly malformed inputs. ZIP integrity was checked; it
contains fictional data only and is not committed as a mailbox dump.

One local generation measurement with Python 3.14/tracemalloc enabled:
50 projects/750 events: **2.07 s**, **4.48 MiB** peak traced allocations;
500 projects/7,500 events (configured cap): **21.66 s**, **27.73 MiB**.
These measure manifest generation, including source hashing, not total process RSS,
database throughput, provider latency, production load or a sustained soak/SLO.

Still open: broader held-out business layouts, scanned-text/OCR and password-protected
fixtures, multi-day workload measurement, selected live-provider replay/acceptance,
production scanner/binary extraction, OIDC/grants, hosted supervision/Blob/KMS,
retention/purge, model/state/MCP work and Factory audit. Semantic labels in the
manifest remain **unevaluated targets**; deferred documents do not count as extracted.
Dependency releases/licenses were checked from primary sources, not vulnerability-
certified. No new runtime dependencies, SQL grants, schema or mailbox effects.

## Operator-run approved processing

Implementation **0f01724** passed [CI 35570568792](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35570568792)
and [restore 35570568779](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35570568779).
The follow-up **eaeca7a** strengthens the denial test with an actual foreign-tenant
account and updates the roadmap; it changes no runtime or schema. Final
[CI 35570703531](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35570703531)
also passed at eaeca7a. Counts below apply to both runs. Subsequent receipt-only
documentation edits do not change that tested runtime.

- **1,304 standard Python tests**, including **164 PostgreSQL cases**, passed with
  no CI skips; **52 Node UI contracts** and **five additional actual-container
  cases** passed. Repeated gate tests and the restore subset are not added again.
- New coverage: **58 controller unit cases**, **eight SQL workflow cases** and
  **one actual CLI/container case**. Private file modes/type/links/size, closed
  configuration, scoped worker auth, expiry/revocation, bounded polls, stop signals,
  redaction, preflight without claims, restart idempotency and encrypted-source
  processing are tested. Existing SQL lease/crash/cancel tests remain in the suite.
- Local full suite: **1,140 passed, 164 explicit PostgreSQL skips**, two existing
  dependency warnings. Ruff, strict typing over **34 source modules**, separately
  typed restore script, locked sync, 52 Node checks, documentation/repository gates
  and diff checks passed. This does not imply local PostgreSQL or Docker was run.
- Restore on unchanged runtime: **24 tables, 119 rows, two tenants, four encrypted
  objects**, equal content hashes and tenant isolation; database-only recovery
  refused. **15.73 seconds** includes disposable startup, not production RTO.
- Full-history secret scan through eaeca7a: **38 commits**, no detected leaks.

[ADR-032](adr/032_operator_processing_controller.md) and the
[operator guide](PROCESSING_CONTROLLER.md) define `process-jobs`: private explicit
configuration, exact worker scope, no-claim preflight, bounded iterations and
graceful stop. API/parser receive no Docker authority; no SQL grants/schema change.
The actual-container test runs new CLI processes for check, execution and restart,
with tenant-bound encrypted source, bounded text evidence and unchanged raw hashes.
The database tests also show token removal during parsing prevents evidence publication.

Review fixed inherited whitespace normalization so an image ID with trailing
whitespace is rejected, not silently changed. The foreign-account test now checks
an existing other tenant's account, not just an absent UUID. There is no claim of
independent third-party security certification.

Still required: credential enrollment, production OIDC/service principals,
hosted supervision and image/host acceptance, Fastmail operator enrollment/scheduler,
cloud Blob/KMS and independent key recovery, scanner/PDF/Office/OCR extraction,
known-answer continuous fixture feed, live-provider and multi-day soak testing,
MCP/state/model-quality work, retention/purge and Factory audit. Check mode does
not certify processor availability; successful polling can report deferred/failed
work. File revocation is not atomic with SQL publication. No real mail, remote
model, mailbox effect or paid resource is enabled.

## Modernized product pack and owner processing review

Implementation/documentation **814197a**, final test correction **98bb6f2**.
[CI 35568932837](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35568932837)
passed at 98bb6f2. The unchanged runtime/schema/restore implementation passed
[restore 35568746120](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35568746120)
at 814197a. Verified 2026-09-20 Pacific (September 21 UTC).

- **1,238 standard Python tests passed**, including **156 PostgreSQL cases**, no
  CI skips. **52 Node tests passed** (25 existing and 27 processing contracts).
  **Four additional actual-container tests passed**. Repeated repository-gate tests
  and the restore safety subset are not counted again.
- Local: **1,082 passed, 156 explicit database skips**, plus all 52 Node tests.
  Locked dependency sync, Ruff, strict typing over 33 source modules, separately
  typed restore script, repository gate and diff checks passed.
- Documentation gate verified the original **16 pack documents plus four new
  guides** and local Markdown paths. This is not remote-link availability or
  independent factual/accessibility certification.
- Restore: **24 tables, 119 rows, two tenants and four encrypted objects**; equal
  content hashes, tenant authorization/search, processing history and original
  completed/cancelled/queued states. Missing-object/database-only recovery refused.
  **23.77 seconds** includes disposable cluster startup, not production RTO.
- Full Git-history secret scan through 98bb6f2: **35 commits**, no detected leaks.
  Repository visibility rechecked private. Existing concurrent competitive-research
  commits were preserved during integration; no force push.

The initial CI at 814197a caught a new test trying to SELECT audit rows with the
deliberately restricted runtime role. The test-only fix inspects via disposable
test admin, filters the tenant, and explicitly asserts runtime denial. Application
permissions were not broadened. The corrected full CI passed.

ADR-031/migration 0011 add bounded account-scoped history, manual owner refresh,
explicit isolated approval/cancellation, same-key uncertain retries and strict
session/account/view binding. Independent review found and fixed a pending-card
replacement race and a history-pagination row omission; both have regressions.
No new real-browser or accessibility acceptance is claimed: the included visual
preview serves real assets with simulated in-memory jobs, not a database/worker.

Documentation now explains the finished experience, feature-by-feature methods,
actual module layout, delivery dependencies, current versus target capabilities,
hosting independence, operations and the proposed known-answer mailbox feed.
Start at [GAME_PLAN.md](GAME_PLAN.md), [FEATURES_AND_METHODS.md](FEATURES_AND_METHODS.md),
[CODE_MAP.md](CODE_MAP.md) and [TEST_MAILBOX_PLAN.md](TEST_MAILBOX_PLAN.md).
All 16 requested pack documents were updated; historical source snapshots and
receipts retain their observed dates instead of being relabeled freshly measured.

Remaining gates: supervised worker commands/deployment, production OIDC/resource
grants, live enrollment, Azure Blob/KMS/independent key recovery, scanner and binary
PDF/Office/OCR/archive extraction, retention/purge, full browser/accessibility,
MCP/state/vector/model-quality work, disposable-provider acceptance and soak.
The richer continuous fictional feed is planned, not running. No public corpus
download, real mailbox use, provider write, paid resource, model disclosure or
Factory mutation. Two upstream test deprecations and CI action/runner migration
notices remain in the supply-chain backlog.

Subsequent receipt/navigation-only documentation edits do not change tested runtime.
Historical entries below describe their named earlier commits, not current limits.

## Durable human-approved isolated processing jobs

Implementation **bbca37f**, final pressure-test commit **decf1b0**.
[CI 35566333798](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35566333798)
passed at decf1b0. The unchanged runtime/restore code passed
[restore 35566144268](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35566144268)
at bbca37f. Verified 2026-09-20 Pacific (September 21 UTC).

- **1,220 standard Python tests passed**, including **150 real PostgreSQL cases**,
  no CI skips. **Four additional actual-container tests passed**, including API
  approval -> encrypted retained MIME -> restricted image -> atomic job/evidence
  completion -> body/attachment search. **25 Node UI tests passed**. Repeated gate
  suites and the restore safety subset are not counted twice.
- Local: **1,070 passed, 150 PostgreSQL skips**; no local Docker/PG acceptance is
  claimed. Locked dependencies, Ruff, strict typing across 33 source modules,
  separately typed restore script, repository gate, all 16 pack docs/local links,
  container build and CLI smoke passed. Full Git-history secret scan was clean
  through decf1b0.
- Restore: **24 tables, 118 rows, two tenants, four encrypted objects**, equal SQL
  and raw hashes, restored tenant isolation/search/recovery/rules, and unchanged
  completed/cancelled/pending job states. Database-only and missing-object recovery
  were refused. **16.41 seconds** includes disposable cluster startup, not production
  RTO. Owned container and temporary archive/object trees were cleaned up.

The increment adds 67 standard tests (35 PostgreSQL) and one actual-container
pipeline test. Coverage includes human/worker scope separation, immutable approval
identity, actor-bound idempotency, concurrent claim/admission, 100-job account limit,
cancellation, both actors' revocation, account disablement, provider deletion,
expired/replaced leases, fresh wall-clock expiry within a transaction, three-claim
crash/retry exhaustion, parser drift and cached-result fencing. The SQL helper's
search path, lack of PUBLIC execution, explicit tenant boundary and inability to
grant membership/account UPDATE were verified against PostgreSQL.

Migration 0010 and a narrow privileged read/lock helper avoid granting runtime
authority to edit memberships. Publication and job completion share a final
fenced transaction; no database lock survives the untrusted processing interval.
The API can enqueue/check/cancel without Docker privileges or encrypted blob keys.
Approval lasts one hour and remains a durable grant after the submitting login
token expires; cancellation/revocation/expiry controls are documented explicitly.

This is an opt-in **local/CI API and worker library**, not an automatically running
hosted service. Worker supervision, credential enrollment, production OIDC/grants,
Azure Blob/KMS/deployment, UI job controls, scanning and PDF/Office/OCR/archive
extraction, retention/purge, live mailbox acceptance and extended soak remain open.
No live mailbox, paid service, provider write, model disclosure or Factory mutation
was performed. Two upstream test deprecations and action/runner notices remain in
the supply-chain backlog. See [job contract](RECOVERY_JOBS.md),
[ADR-030](adr/030_durable_recovery_jobs.md) and [status](IMPLEMENTATION_STATUS.md).

## Image-bound isolated large-MIME recovery

Code/test commit **bc7ea12**, initial implementation **b860d2e**.
[CI 35564748494](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35564748494)
and [restore 35564748495](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35564748495)
passed on 2026-09-20 Pacific (September 21 UTC).

- **1,153 standard Python tests passed**, including **115 PostgreSQL cases**, no
  CI skips. **Three additional actual-container tests passed**, one exercising
  encrypted objects -> restricted MIME worker -> real PostgreSQL recovery -> body
  and text-attachment search. **25 Node UI tests passed**. Repeated gate runs and
  the restore safety subset are not double-counted.
- Local: **1,038 passed, 115 explicit PostgreSQL skips**. No local Docker acceptance
  is claimed. Ruff, strict typing across 32 source modules, locked dependency sync,
  all 16 pack documents/local links, image build and CLI smoke passed. The restore
  script separately passed strict typing. Full Git-history secret scan was clean
  through bc7ea12.
- Restore regression: **23 tables, 95 rows, two tenants, four encrypted objects**,
  matching hashes and tenant authorization; database-only/missing-object recovery
  refused. Elapsed **15.16 seconds** includes disposable container startup and is
  not a production RTO. Owned test container/archive/object trees were cleaned up.

The increment adds **119 MIME/contract tests**, **54 controller/pipe tests**, **15
recovery-boundary tests** (10 real database), and the three explicit post-build
container cases. Independent review found an injected-adapter contract gap:
inconsistent tuples could have become cached MIME rejections. The final code
validates types, hashes, fields, collection/Unicode/serialization budgets and
outcome consistency before publication or caching; four SQL tests prove malformed
adapter results leave mail held with no attempt. Processor changes and newer provider
events during parsing also prevent publication. No blocking review finding remains.

Actual Docker acceptance verifies fixed local image identity, checked isolation
before raw-byte disclosure, no network/host mounts, read-only filesystem, dropped
capabilities, unprivileged UID, resource limits, disabled logs, bounded pipes and
exact-owned cleanup. The synthetic attachment-heavy message becomes searchable;
its large PDF stays deferred, not falsely extracted. Empty MIME is a deterministic
rejection. This is not a kernel escape audit or real-mail scale/soak certificate.

The feature is an **explicit trusted operator/worker library**, not a public API
Docker endpoint. Default UI/HTTP retry still uses the 1 MiB parser; the isolated
processor can handle retained MIME up to 16 MiB and uses full image hash provenance.
No new SQL migration, provider writes, raw download, model call, real mailbox,
cloud resource or Factory mutation. Hosted authenticated jobs, scanning and
PDF/Office/OCR/archive extraction, OIDC/grants, Azure storage/KMS, retention/purge
and live acceptance remain gates. Two upstream test deprecations and CI action/
runner notices remain tracked supply-chain work. See
[isolated recovery](ISOLATED_MIME_RECOVERY.md), [ADR-029](adr/029_isolated_large_mime_recovery.md)
and [implementation status](IMPLEMENTATION_STATUS.md).

## Encrypted large-email preservation and two-part restore

Implementation commit **cefce1d**, follow-up pressure tests **0e50870**.
[CI 35563585338](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35563585338)
passed at 0e50870; the unchanged runtime/restore implementation passed
[restore 35563364090](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35563364090)
at cefce1d. Verified 2026-09-20 Pacific (September 21 UTC).

- **965 Python tests passed**, including **105 real PostgreSQL cases**, no CI skips;
  **25 Node UI tests passed**. The repeated repository-gate suite is not counted
  twice. Local results: 860 passed, 105 explicit PostgreSQL skips.
- Locked dependencies, Ruff, strict typing across 30 source modules, all 16 pack
  documents/local links, container build and CLI smoke passed. The restore script
  also passed independent strict typing with `MYPYPATH=src`.
- Actual PostgreSQL 17 restore verified **23 tables, 95 rows, two tenants and four
  encrypted external objects**, alongside legacy inline evidence. All table and
  decrypted raw hashes matched; search/evidence/recovery/rules and tenant RLS passed.
  Database-only and empty-object restoration were explicitly refused. Elapsed
  **12.43 seconds** includes container startup, not a production RTO. The drill
  cleaned up its exact owned container, temporary archive and ciphertext trees.
- Full Git-history secret scan was clean through 0e50870. The private worktree
  directory scan also passed before the implementation commit.

Added 72 encrypted-backend tests, 30 Fastmail/worker tests and 24 storage API/unit/
database cases. Coverage includes authenticated tenant/account context, wrong keys,
tampering, symlinks/ownership, concurrent publication, crash/fsync failures, fixed
size budgets, transactional rollback/orphans, SQL manifest forgery, revoked authority
during staging, persisted old-key reads after rotation, missing-key refusal without
cursor movement, and large-message progress through a restarted durable worker.
Independent integration review found no blocking issue; simultaneous mixed
inline/external writer stress remains a useful additional scenario.

Migration **0009** requires coordinated API/worker/backup-reader upgrade. The
encrypted filesystem backend is explicit opt-in; it preserves complete raw messages
up to **16 MiB**, but the parser still caps at **1 MiB**. Larger retained messages
remain visibly held as `mime_too_large`, not parsed/indexed/extracted. Existing
inline evidence is unchanged. No automatic object deletion or raw-download API.

No real mailbox, model, cloud/KMS service, binary extractor or Factory runtime was
activated. Hosted storage/key recovery, production identity/grants, larger isolated
parsing/extraction, retention/purge and live acceptance remain gates. Two upstream
test-client deprecations and action-runtime/runner notices remain tracked supply-chain
work. See [storage contract](LARGE_EVIDENCE_STORAGE.md),
[ADR-028](adr/028_encrypted_large_evidence.md) and [status](IMPLEMENTATION_STATUS.md).

## Audited human recovery of held messages

Code/test commit: `063ac14` (implementation `af76838`, follow-up assertions/UI).
[CI 35561947038](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35561947038)
and [restore 35561947019](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35561947019)
both passed on 2026-09-20 Pacific.

- **839 Python tests passed**, including **86 real PostgreSQL cases**, no CI skips;
  **25 Node UI contracts passed**. The repository-gate repetition is not counted
  twice. Local validation: 753 passes, 86 explicit PostgreSQL skips.
- Locked dependency sync, lint, strict typing across 29 source modules, all pack
  documents/local links, container build and CLI smoke passed. The restore script
  separately passed strict typing with `MYPYPATH=src`.
- Actual PostgreSQL 17 dump/restore verified **23 tables, 82 rows, two synthetic
  tenants**, equal content hashes, tenant authorization, search/evidence and
  recovery-attempt persistence. Elapsed **23.74 seconds** includes disposable
  container startup, not a production recovery-time promise. Owned test resources
  and private temporary archive were cleaned up by the drill.
- Full Git-history secret scan found no leaks through `063ac14`.

Twenty new real-database cases and two API/library cases cover explicit human
authorization, simultaneous retries, competing owner audit, newer provider events,
membership/account revocation, hash corruption, parser crashes, atomic rollback,
old citations, legacy metadata, populated migration and active worker compatibility.
Same-parser output drift now fails closed; it cannot change searchable text while
reusing a historical citation. Ten new UI tests cover explicit clicks, exact parser
binding, cached outcomes, generic errors and session/account/refresh races.

The first CI pass found an old security-test assertion expecting all reprocessing
to be unavailable (838 passed, one failed). That assertion was updated for the
new human-only retry contract without removing its raw-access, paging or isolation
checks. Independent review also caught missing audit on a concurrent cached retry;
it was fixed and both actors/requests are tested. The final UI explicitly displays
the parser version being approved. Two agents implemented/reviewed this increment.

Migration **0008** requires coordinated API/worker upgrade and refuses legacy
parser-provenance mismatches. No raw bytes, provider events, sync cursors or worker
leases are changed by recovery. No real mailbox, model, binary extractor, cloud
resource or Factory runtime was activated. Two upstream test-client deprecations
remain; CI also warns about old action Node runtimes and an upcoming runner-image
change. Dependency/action modernization belongs to the supply-chain backlog.
See [recovery contract](QUARANTINE_RECOVERY.md), [ADR-027](adr/027_quarantine_recovery.md)
and [remaining gates](IMPLEMENTATION_STATUS.md).

## Calendar extraction and realistic attachment formats

Code/test commit: `e3695d8`.
[CI 35560344173](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35560344173)
and [restore 35560344225](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35560344225)
both passed on 2026-09-20 Pacific.

- **817 Python tests passed**, including 66 real PostgreSQL cases, no CI skips.
  **15 Node interface tests** also passed. The repeated repository-gate suite is
  not counted twice. Locally: 751 passes and 66 explicit database skips.
- Lint, strict typing across 28 source modules, docs/link checks, developer image
  build and CLI smoke passed. Restore script also passed separate strict typing.
- Actual synthetic PostgreSQL restore passed for **22 tables, 77 rows, two tenants**
  with equal content hashes, recovered calendar attachment search/evidence, rules
  and tenant authorization. Elapsed 20.52 seconds includes container startup and
  is not a production recovery-time claim. Owned test container/archive cleaned up.
- Full Git-history secret scan found no leaks through the code commit.

Nine deterministic attachment-bearing MIME cases include minimal DOCX/XLSX packages,
PNG files, CSV, folded Unicode calendar invitation/cancellation, nested email and
a mixed bundle. Thirty-one format/payload/hash tests and 36 mocked-provider wrapper
tests independently check expected bytes and receipt outcomes. OOXML structure is
checked, not full Office rendering. Binary extraction is still deferred/skipped,
not counted as successfully read. No public correspondence was imported.

Calendar source extraction has 73 focused parser tests and 11 independent security
cases, plus named/unnamed MIME handling, charset/transfer-encoding failures and two
real database integration tests. Review fixed case-insensitive binary-value refusal;
integration rejects mismatched MIME/body METHOD and malformed transfer encodings.
The existing restore fixture assertion was updated to require the added calendar
attachment and its extracted content, retaining its binary-deferred checks.

This adds searchable calendar evidence, **not** meeting acceptance, RSVP, timezone
conversion, recurrence expansion, URL/alarm execution or obligation changes. Parser
provenance is v4 for new snapshots; old evidence is not silently reprocessed. Four
agents total implemented/reviewed the slice. No real mailbox, calendar, model daemon,
paid cloud resource or Factory runtime was activated. Two upstream test-client
deprecation warnings remain. See [calendar scope](CALENDAR_ATTACHMENTS.md),
[public sample adoption gates](PUBLIC_EMAIL_TEST_DATA.md) and
[remaining product gates](IMPLEMENTATION_STATUS.md).

## Prior reviewed rules, local-model adapter and actual restore proof

Code/test commit: `d5f8f47`.
[CI 35556627769](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35556627769)
and [restore 35556627775](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35556627775)
both completed successfully on 2026-09-20 Pacific.

- **658 Python tests passed**, including 64 real PostgreSQL cases, with no CI skips.
  **15 additional Node interface tests passed**. The repository gate repeats the
  Python suite; this is not counted as another 658 distinct tests.
- Lint, strict typing across 27 source modules, all 16 pack documents/local links,
  developer container build and CLI smoke passed.
- Actual PostgreSQL 17 custom dump/restore verified **22 tables, 73 rows and two
  synthetic tenants**: hashes, evidence, attachment/search results, quarantine,
  approved proposals, active rules and row-level authorization survived recovery.
  Elapsed 23.82 seconds includes disposable container startup and is not production RTO.
- Local checks: 594 Python passes, 64 explicitly skipped database tests; 15 Node
  passes. Full Git-history secret scan found no leaks through `d5f8f47`.
- Four agents total implemented and independently reviewed the changes. Review
  caught/fixed ambient PostgreSQL address redirection in the disposable drill and
  a stale Review Delete selection surviving owner-screen disconnect.

The working feedback loop is propose → approve → bounded sample → explicit human
activation → virtual search labels → append-only revision rollback. Tests cover
the REST lifecycle, concurrent receipts, expiry, foreign tenant/actor, malformed
text, 50-message sample bounds and unchanged provider/evidence state. Review alone
still applies nothing; project/fact/feature/correction application remains deferred.

The opt-in local Ollama library has 90 fake-response tests plus independent runtime
checks. It is not automatically wired into ingestion/API, no daemon was contacted,
and no model accuracy claim is made. No model downloaded, real email accessed,
mailbox changed, paid cloud resource deployed or Factory runtime modified.

The restore drill removed its exact owned disposable container and temporary
synthetic archive. It is logical recovery proof, not managed-cloud PITR, encryption,
offsite backup or regional disaster-recovery validation. Production OIDC, account
enrollment, encrypted large objects, binary extraction, additional durable provider
workers, actual model/MCP integration, controlled actions and Factory bind remain
release gates. Two upstream test-client deprecation warnings remain non-failing.

## Prior parallel implementation and pressure-test pass

Code/test commit: `3b7d972` (integrated implementation `c9e1829`).
[GitHub Actions run 35555204407](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35555204407)
completed successfully:

- **485 Python tests passed**, including 52 real PostgreSQL integration cases;
  no CI database skips. Six additional Node UI-contract tests passed.
- Strict typing passed across 24 source modules; lint, document/link gates,
  developer container build and CLI smoke passed.
- Locally: 433 Python tests passed; 52 database cases explicitly skipped; six
  Node tests passed. Full Git-history secret scan found no leaks through this commit.
- Four agents total worked on implementation and independent adversarial review.
  Changes were integrated and checked together, not counted as isolated successes.

Shipped in this increment: certified inventory reconciliation and expired-history
recovery; exact-byte bounded MIME quarantine; resumable fictional-inbox seeding;
owner import-health and paginated held-message metadata; Gmail/Graph read-only
libraries and an injected-session IMAP contract. Only Fastmail currently has durable
database worker orchestration. New provider libraries are not enrolled live connectors.

The fake-mailbox lifecycle imports 256 varied messages, applies seven changed IDs,
then recovers twenty unseen deletions after expired history. Parser checks include
1,000 seeded bounded random byte inputs. These are not a multi-day soak or measured
production throughput benchmark. [Coverage and gaps](TEST_COVERAGE_MATRIX.md).

Independent review found and verified fixes for decoder-produced NUL/surrogate
strings reaching SQL, inconsistent demo-account guards including a preflight race,
Gmail quota 403 misclassification, Graph non-ASCII Retry-After values and empty-body
deadline bypass. Integration review also corrected real provider/library contract
assumptions: Gmail minimal responses need not contain timestamps/history/thread,
and IMAPClient may consume the inner UID into its response dictionary key.

A temporary loopback UI with a mocked Store was checked in the actual browser:
connect, fictional search, evidence inspection, held-message status, and session
clearing all worked. The temporary server and tab were closed. This was not a live
database/browser integration run or full accessibility acceptance; CI separately
exercises real PostgreSQL and the HTTP API.

Remaining warnings are upstream test-client deprecations and GitHub runner/action
upgrade notices. Production OIDC, cloud infrastructure, restore drills, larger
encrypted objects, binary extraction, durable additional-provider workers, actual
model inference/MCP, action execution and Factory binding remain release gates.
No real mailbox, model, paid cloud service or Factory runtime was activated.

Prior recovery-only pass: `9173e26`,
[CI 35553409905](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35553409905),
180 passing Python tests. The receipt above supersedes its test totals.

## Read-worker refinement pass

Code commit: `01eb47d`.
[GitHub Actions run 35501983332](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35501983332)
completed successfully:

- **119 tests passed**, including 29 real PostgreSQL integration cases; none skipped in CI.
- Strict typing passed across 20 source modules; lint and all document/link gates passed.
- Developer Docker image build and CLI smoke test passed.
- Full Git-history secret scan found no leaks through this code commit.
- Locally: 90 passed, 29 database tests explicitly skipped (no local Postgres).

Added durable listing/change checkpoints, leased single-account orchestration,
stale-worker/account-binding fencing, restart after query churn, retry deadlines,
failure pauses and content-free run receipts. Tests include eight simultaneous
lease contenders, process recreation, crash-after-commit replay, deleted messages
during listing, wrong-account tokens, provider failures, expired cursors and MIME
rollback. Retry bounds cover 15,015 combinations. This is bounded fault/pressure
testing, **not** a long-running soak, production load test or live-provider trial.

The first CI attempt caught PostgreSQL infinity timestamps that Python could not
decode in status rows; a forward migration replaced those sentinels. Review also
prevented an unsafe cursor-expiry reset: that path now explicitly pauses pending
the inventory-diff reconciler. [Worker limits and recovery](READ_WORKER.md).

Remaining warnings: two upstream Python test-client deprecations and CI action/
runner upgrade notices. They do not fail this run; dependency/runtime upgrades
remain in the supply-chain backlog. No additional mailbox/cloud privileges were added.

## Earlier foundation verification

Code commit: `3612ac5`.
[GitHub Actions run 35480784089](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35480784089)
completed successfully:

- **69 tests passed**, including 16 real PostgreSQL integration cases; none skipped in CI.
- Lint passed; strict typing passed across 18 source modules.
- Repository quality gate and all 16 document-pack/local-link checks passed.
- Developer Docker image built and its CLI smoke test passed.
- Local full-history secret scan found no leaks through the tested implementation commit.

The tests exercise actual PostgreSQL 17 using a non-owner runtime role, real HTTP
API-to-database flow, tenant isolation, transaction-local context reset, composite
ownership, concurrent replay, checkpoint rollback, proposal/evidence/review flow,
correlated audit, historical evidence and attachment search/accounting. Provider
network tests use mocked HTTP only. Two upstream test-client deprecation warnings
remain; they are not skipped/failed checks and should be resolved during dependency maintenance.

## What was not done

No real mailbox access, sending, deletion, folder modification, model inference,
paid cloud provisioning, production restore, malware scanning or Factory bind.
No Factory/other Product files were modified. Five portable improvement requests
are staged in this Product's `_FACTORY_CANDIDATES.jsonl`, not adopted upstream.

The working build remains in the Codex project workspace. Factory's actual source
checkout was located at `~/CW-Systems/CW-Factory`; its Dropbox counterpart
is the content surface. Canonical Email Brain local placement is parked in Q08,
so no existing source/content folders have been moved or reorganized. Runtime
databases and credentials must remain outside Dropbox regardless of source placement.

## Reproduce

See [LOCAL_DEVELOPMENT.md](LOCAL_DEVELOPMENT.md). The ZIP is a source-only Git
archive: no `.git`, local venv, caches, credentials, database or real mail. It
contains the docs, implementation, synthetic tests, migrations and dependency lock.
CI evidence above names the exact code commit; subsequent documentation-only
receipt changes do not imply a separate live deployment.
