# Build and validation receipt

Updated 2026-09-22 Pacific. Product: `jbone3311/CW-EmailBrain`, verified **private**.

## Verified authenticated FileOS publication command

Runtime revision **e7f319cae5a68e4a2072a326fba9ab853cb15643** and the
tenant-isolated test correction **aaaf156a0c8ad6f7243fd11300da2b4309f59ded** passed
[CI 35713893737](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35713893737)
and [restore 35713893769](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35713893769),
observed 2026-09-22 Pacific.

- The hosted suite passed **2,394 Python tests** with PostgreSQL and no skips; the
  deployment gate repeated the suite. Ruff, strict mypy over **65 source files**,
  **134 Node contracts**, and documentation verification over **120 Markdown files /
  774 local paths and fragments** passed.
- Real PostgreSQL cases proved non-mutating preflight, least-privileged publication,
  exact idempotent replay, deterministic no-duplicate documents, source byte/mtime
  preservation, privileged DSN refusal and revoked local worker refusal.
- All restricted runtime boundaries stayed green: five real MIME-container cases, 15
  Email PDF-container cases and five FileOS PDF/DOCX/XLSX container/SQL cases. The
  populated PostgreSQL 17 restore passed in 26 seconds.
- Local gates passed **2,042 tests / 352 explicit PostgreSQL skips**, 134 Node
  contracts, lint, strict types, documentation and deployment checks. Local SQL skips
  are not passes; the hosted suite exercised the new two-case SQL module.
- The first hosted run exposed a test-only cross-tenant counting error: the denial
  assertion observed the successful fixture from another tenant. The query was scoped
  to its own tenant; runtime code and permissions were unchanged, and the complete
  rerun passed.
- FOS-Master remains clean at
  **218d5caec2f20b9047fd3eb8e027dc671acf0c15**. This command adds no scheduler,
  public upload, durable whole-run completion receipt, file effect, cutover, rename or
  retirement.

## Verified isolated FileOS PDF and Office extraction

Runtime/test revision **a6488c66ff5027789be093374b9b269f2c945fa2** adds the
source-bound, isolated DataCore PDF/DOCX/XLSX path. It passed
[CI 35711403192](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35711403192)
and [restore 35711403138](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35711403138),
observed 2026-09-22 Pacific.

- The hosted suite passed **2,379 Python tests** with PostgreSQL and no skips; the
  deployment gate repeated the same suite successfully. Ruff, strict mypy over
  **64 source files**, **134 Node contracts**, and documentation verification over
  **119 Markdown files / 771 local paths and fragments** passed.
- The dedicated locked worker image built from the dependency lock. Five real-container
  cases passed: bounded PDF, DOCX and XLSX reads; source substitution/external-link
  refusal; and PostgreSQL publication/search of all three formats without source writes.
- The ordinary runtime image still excludes `pypdf`, `openpyxl`, `python-docx` and
  `lxml`. The existing five MIME-container and 15 PDF-container cases also remained
  green. The populated PostgreSQL 17 logical restore passed in 29 seconds.
- The live donor harness matched unchanged FOS-Master commit
  **218d5caec2f20b9047fd3eb8e027dc671acf0c15** for DOCX/XLSX extracted tokens and
  sheet counts plus the prior text/HTML/CSV/hash/dedupe and **3,000-file** stress corpus.
- Local gates passed **2,029 tests / 350 explicit PostgreSQL skips**, 134 Node
  contracts, lint, strict types, docs and deployment checks. Local SQL skips are not
  passes; the hosted suite and container publication case exercised PostgreSQL.
- This is a read-only additive tranche, not antivirus or production acceptance.
  Legacy Office, archives, images/OCR, root enrollment, incremental operation,
  live-source shadowing, effects, cutover, FOS rename and retirement remain open.

## Verified grouped MasterBrain retrieval

Runtime/test revision **b60acd2** adds a dual-scope, grouped search over DataCore
evidence and KnowledgeCore assertions. It passed
[CI 35707895947](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35707895947)
and [restore 35707895954](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35707895954),
observed 2026-09-22 Pacific.

- The hosted suite passed **2,369 Python tests** with no skips and two dependency
  warnings; Ruff and strict mypy over **61 source files** passed.
- **134 Node contracts**, five actual MIME-container cases and 15 actual PDF-container
  cases passed. Documentation verification passed **117 Markdown files / 762 local
  paths and fragments**.
- The real PostgreSQL test publishes source text and a reviewed project, then verifies
  one `/v1/brain/unified-search` request returns both evidence and knowledge layers.
  Unit contracts prove dual-scope enforcement, independent 25-result caps, strict
  kind filters and explicit `within_layer_only` ranking.
- The populated PostgreSQL 17 restore remained green. This additive endpoint does not
  change stored data, migrate legacy Email evidence, calibrate cross-layer ranks,
  synthesize answers or authorize source effects.
- Local gates passed **2,019 tests / 350 explicit PostgreSQL skips**. Local SQL skips
  are not passes; the hosted suite exercised the PostgreSQL endpoint.

## Verified reviewed KnowledgeCore foundation

Runtime/test revision **7d2afbf** adds the reviewed, evidence-linked KnowledgeCore
foundation and its `/v1/knowledge` API. It passed
[CI 35706332421](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35706332421)
and [restore 35706332264](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35706332264),
observed 2026-09-22 Pacific.

- The hosted suite passed **2,368 Python tests** with no skips and two dependency
  warnings. The deployment gate repeated the suite successfully; repeated runs are
  not additional unique tests.
- Ruff, strict mypy over **61 source files**, **134 Node contracts**, both restricted
  processor image builds, five actual MIME-container cases and 15 actual PDF-container
  cases passed. Documentation verification passed **116 Markdown files / 761 local
  paths and fragments**.
- PostgreSQL integration covers all seven knowledge assertion kinds, concurrent
  idempotent publication, conflicting and superseded claims, corrections, temporal
  fields, evidence links, API access, immutable rows and tenant isolation.
- PostgreSQL 17 restore verified **53 tables / 212 rows / two tenants / four encrypted
  objects / two identity bindings** with equal table hashes, including restored
  KnowledgeCore entity/claim retrieval and cross-tenant denial. The real drill took
  22.65 seconds; the 29 restore safety tests also passed. This is not a production RTO.
- Local gates passed **2,018 tests / 350 explicit PostgreSQL skips**, 134 Node
  contracts, strict types, lint and documentation checks. Local SQL skips are not
  passes; the hosted count above exercised PostgreSQL.
- FOS-Master remains unchanged at
  **218d5caec2f20b9047fd3eb8e027dc671acf0c15**. This tranche adds no source writes,
  automatic model publishing, FileOS cutover, rename or retirement. Known-answer
  extraction evaluation, Email memory migration, FOS fact parity, graph traversal,
  unified synthesis and broader document/OCR ingestion remain open.

## Verified MasterBrain working read slice

Runtime/test revision **a06bcad12facb084cf7d5ef4c031e1919cfd0e71** implements
the additive DataCore persistence/index, verified FileOS text extraction and the
progressive Brain API read slice. It passed
[CI 35703242987](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35703242987)
and [restore 35703242983](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35703242983),
observed 2026-09-22 Pacific. Later receipt-only changes do not alter this runtime.

- The complete hosted suite passed **2,364 Python tests** including real PostgreSQL
  cases, with no skips and two existing dependency warnings. The deployment gate
  repeated the same suite successfully; repeated runs are not additional unique tests.
- Ruff, strict mypy over **59 source files**, **134 Node contracts**, both container
  builds, CLI/runtime-image checks, five actual MIME-container cases and 15 actual
  PDF-container cases passed.
- Documentation verification passed **114 Markdown files / 755 local paths and
  fragments**. Local full suite passed **2,015 tests / 349 explicit PostgreSQL skips**;
  skipped local SQL cases are not passes.
- The live donor harness matched unchanged FOS-Master commit
  **218d5caec2f20b9047fd3eb8e027dc671acf0c15** for hash/name/both dedupe, pair
  comparison, SHA-256/MD5, UTF/HTML/CSV extraction and a **3,000-file stress corpus**.
- PostgreSQL 17 restore verified **41 tables / 185 rows / two tenants / four encrypted
  objects / two identity bindings** with equal content hashes, forced RLS, identity
  revocation and database-only-restore refusal. The 29 restore safety tests passed;
  14.43 seconds includes disposable startup and is not a production RTO claim.
- The working vertical path is: read-only FileOS snapshot → idempotent tenant-isolated
  import → source re-hash → bounded text/Markdown/HTML/CSV extraction → immutable
  provenance/chunks → lexical index → scoped Brain search/evidence/content/changes.
- The first hosted run found and preserved two security boundaries: Brain scopes must
  not leak into legacy Email credentials, and immutable version rows must not receive
  update privilege merely to lock publication. The corrected advisory lock and local
  test contexts passed the full rerun; no permission was widened.
- FOS-Master is unchanged and remains the rollback/reference implementation. PDF,
  Office, archives, images/OCR, KnowledgeCore claims/entities, unified Email+FileOS
  search, live root enrollment, hosted identity enrollment and production shadow
  acceptance remain open. No file/mail effects, real source, model call, paid service,
  rename, retirement or cutover was enabled.

## Verified MasterBrain foundation

Runtime/test revision **fa514df9aef97c1e339996478ca97b92eaa434c7** establishes
the MasterBrain identity and ADR-047 boundaries, plus the first read-only DataCore
donor extraction. It passed
[CI 35696953888](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35696953888)
and [restore 35696953874](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35696953874),
observed 2026-09-21 Pacific. Later receipt-only changes do not alter this runtime.

- Full local Python suite: **1,969 passed / 344 explicit PostgreSQL skips** with two
  pre-existing dependency deprecation warnings. The skipped SQL cases are not passes.
- **134 Node contracts** passed. Full Ruff and strict mypy over **53 source files**
  passed. The deployment/repository quality gate and diff checks passed.
- Documentation gate passed: **105 Markdown files / 740 local paths/fragments**.
- The live-donor harness passed hash, name and combined duplicate scans against an
  unchanged FOS-Master checkout at
  **218d5caec2f20b9047fd3eb8e027dc671acf0c15**. The focused DataCore suite passed
  three cases. The synthetic corpus includes exact duplicates, name versions, empty
  duplicates and donor exclusion patterns.
- Local Python 3.14 did not load the pre-existing editable-install `.pth` inside two
  isolated subprocess tests. A normal wheel reinstall made both tests pass; the same
  issue affected the untouched `email_brain` import and was not a product regression.
- The first CI run correctly rejected a synthetic file named with the forbidden `.db`
  extension. The fixture was replaced with a safe AppleDouble-style exclusion case;
  no gate was weakened. The full CI and restore rerun above passed.
- No live source, database migration, file move/delete, remote model, cloud resource,
  FileOS cutover, FOS-Master modification/rename/retirement, or Brain API runtime was
  added. Golden/shadow/production acceptance remains open.

## Verified structured memory

Runtime/test revision **9769a22170279beb705d3674576fcd098ba8c966** passed
[CI 35659369430](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35659369430)
and [restore 35659434985](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35659434985),
observed 2026-09-21. Later receipt-only changes do not alter this runtime.

- **2,310 Python passes, including 344 real PostgreSQL cases**, no CI skips;
  **134 Node contracts**, **five actual MIME-container cases** and **15 actual
  PDF-container cases** pass. Repeated repository-gate suites and restore subsets
  are not additional unique tests. New memory coverage: **46 offline/API cases,
  18 SQL cases and 12 Node contracts**.
- The SQL cases exercise reviewed publication, source/tenant/account binding,
  assistant write denial, idempotency/no-op/stale conflicts, retained historical
  reads, trip links, exact decimal amounts, concurrent update winners, a held-open
  uncommitted publication followed by a second writer, and partial freshness.
- Lint, type checks over **50 source files**, locked dependencies, both container
  builds, CLI smoke, runtime-reader exclusion and repository gate pass. Docs:
  **98 Markdown files / 840 local paths/fragments** before this receipt addition.
  Local full suite: **1,966 passes / 344 explicit SQL skips**, 134 Node passes;
  separate restore-script typing, diff checks and JavaScript syntax checks pass.
- Exact-revision restore: **30 tables, 162 rows, two tenants, four encrypted
  objects and two identity bindings**, including populated memory revisions and
  receipts. Whole-table/object hashes match; RLS, identity revocation and refusal
  of database-only recovery pass. **29 restore safety tests** pass. **26.53 seconds**
  includes disposable startup; not production RTO, managed PITR or key-loss recovery.
- Initial CI found one outdated existing upgrade-test expectation: its explicit
  migration list omitted the newly applied 0014. New memory SQL tests passed.
  The assertion now includes 0014 while retaining immutable-evidence checks;
  no migration or permission was weakened. The later full run above is green.
- Incremental secret scan from b663d13 through 9769a22 found no leaks. Two existing
  test warnings and action/runner migration notices remain non-failing backlog.
- This is **owner-reviewed memory**, not automated mailbox understanding. The
  labelled parser abstains on general email; the separate `/memory` JSON editor
  is a developer preview. Node contracts are not actual browser/accessibility
  acceptance. The fictional reader-only server does not provide memory storage.
  No real mailbox, paid service, LLM call, airline/bank verification, MCP enrollment
  or mailbox write was enabled. Migration 0014 and runtime regrant are required.

## Historical verified owner reader

Runtime **c3cb5c4105bee7d018c1e5c7c6f8b00823c32b78** passed
[CI 35630644823](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35630644823)
and [restore 35630644811](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35630644811),
observed 2026-09-21. Subsequent receipt-only edits do not change this tested runtime.

- **2,246 Python passes, including 326 real PostgreSQL cases**, no CI skips;
  **122 Node contracts** (38 reader), **five actual MIME-container cases** and
  **15 actual PDF-container cases** pass. Repeated quality-gate runs and restore
  subsets are not additional unique tests. The reader adds 90 Python cases:
  64 unit/API, six preview and 20 SQL cases.
- Lint, type checks over **47 source files**, locked dependencies, both container
  builds, CLI smoke, runtime-reader exclusion and repository gate pass. Docs:
  **96 Markdown files / 816 local paths/fragments** before this receipt update.
  Local: **1,920 Python passes / 326 explicit SQL skips**, 122 Node passes and
  separate restore-script typing with `MYPYPATH=src`.
- Restore verified **27 tables, 147 rows, two tenants, four encrypted objects,
  two identity bindings**, matching hashes, RLS, revoked-context denial and
  database-only restore refusal. **29 safety tests** passed. **14.08 seconds**
  includes disposable startup, not production RTO, managed PITR or key-loss recovery.
- The first reader CI run at c494ae3 failed one SQL test: its audit assertion used
  the runtime role, which correctly cannot read the audit table. The corrected test
  reads audit through a separate disposable administrator and explicitly verifies
  runtime-role denial. No production permission was widened. The later run above
  verifies the correction and explicit two-step browser saving.
- Actual fictional browser smoke verified long-body tail, inert HTML text, four
  document receipts, the large-message projection warning, session clearing and
  browser-side hash verification before presenting a **Save verified file** link.
  Clicking the link reached the save-request status; completed filesystem saving
  was **not confirmed** in the in-app browser. User/browser save acceptance remains
  required. This is not full accessibility or cross-browser certification.
- Staged/incremental secret scans from 498dd4c found no leaks. Two existing test
  warnings and action/runner migration notices remain non-failing backlog.
- No real mailbox, hosted service, paid account, SQL migration or dependency was
  added. Full selected-body display applies to source MIME up to 1 MiB; larger
  originals remain stored projections on screen with verified original export.
  The fictional preview substitutes storage and is not database authorization proof.

## Historical owner reader — local implementation checkpoint

ADR-045 is implemented from base **498dd4ceed6a906e2440ec3aa90c3a97aec04b20**.
New exact-commit CI/restore must pass before claiming SQL/container completion.

- Local: **1,920 Python passes, 326 explicit SQL skips**, two existing warnings;
  47-source-file type check, lint, locked offline dependency sync, repository gate,
  diff and docs checks pass. Docs: **96 Markdown files / 816 local paths/fragments**
  before this receipt-only addition. Existing Node suites: 84 passes; new reader
  Node suite: 32 passes. Repeated runs are not additional unique tests.
- New Python cases: 64 reader unit/API, six fictional-preview, 20 actual SQL cases
  (the latter are local skips, not passes). A real SQL/API-to-DOM bridge is included.
- Actual local browser smoke confirms fictional search, complete long-body tail,
  no executable message elements and explicit attachment controls. Original download
  reached the browser handoff status, but the in-app browser's download event did
  not arrive; saved-file acceptance is not certified by this checkpoint.
- No real mailbox, production SQL, cloud storage, worker enrollment, paid service,
  formatted HTML, large-MIME API parsing, or hosted availability. The fictional
  preview substitutes storage and is not database authorization proof.

## Historical verified review corrections

Runtime **98a334c47253d7e1af74a948837d2c40e9ff9c95** passed
[CI 35624876529](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35624876529)
and [restore 35624876390](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35624876390),
observed 2026-09-21. Subsequent receipt-only edits do not change this tested runtime.

- **2,156 Python passes, including 306 real PostgreSQL cases**, no CI skips;
  **84 Node contracts**, **five actual MIME-container cases** and **15 actual
  PDF-container cases** pass. Repeated gate suites/restore subsets are not extra tests.
- All **53 new regressions** pass: **41 offline and 12 real SQL**. Two cache tests
  failed the former blocking path before correction. Direct old/new comparisons
  confirm both multiple-author and duplicate-From sources stop matching, without
  changing body text. The six concurrency cases also passed five local repeat runs.
- Current search and previews require exact source sender eligibility, including
  body/attachment/PDF hits and legacy snapshots. Raw/evidence retention, unchanged
  public response shapes and strict/legacy worker contracts passed.
- Lint, 46-module typing, locked dependencies, images/smoke/reader exclusion and
  quality gate pass. Docs: **93 Markdown files, 785 local paths/fragments**.
  Local **1,850 passes / 306 SQL skips**, 84 Node passes and separate restore typing.
- Restore: **27 tables, 147 rows, two tenants, four encrypted objects, two identity
  bindings**, matching hashes, RLS/revocation and database-only refusal; **29 safety
  tests** pass. **14.35 seconds** includes disposable startup, not production RTO/PITR.
- Staged/incremental secret scans from 3ac6771 found no leaks. Two existing test
  warnings and action/runner migration notices remain non-failing backlog.
- No SQL migration, dependency, real account, paid service or mailbox privilege
  added. Ordinary parser is v5. Legacy messages remain readable but cannot match
  sender rules until authorized revalidation. Browser UI/hosted acceptance remain open.

## Historical review corrections — local checkpoint

ADR-044 is implemented from base **3ac67711f11d50a56468b17b1ed77ed8cd7515d9**.
Publication CI/restore must verify the new exact commit; prior receipts do not
certify the new runtime. No real account or service is used.

- **1,850 local Python passes, 306 explicit SQL skips**, two existing warnings;
  **84 Node contracts**, lint, 46-module typing, restore-script typing, locked sync,
  repository quality gate and diff checks pass. Docs: **93 Markdown files / 785
  local paths and fragments** before receipt-only additions.
- **53 new regression cases: 41 offline and 12 SQL**. Two cache tests failed the
  old lock-held network path before correction. The review also reproduced first-
  sender selection from ambiguous raw headers; new tests cover ordinary/isolated
  normalization, legacy worker fallback and strict boolean status.
- SQL acceptance covers body/attachment/PDF search, rule previews, legacy snapshot
  eligibility, unchanged public envelopes and retained body/raw bytes. These are
  not local passes. Existing tenant/identity and recovery suites remain required.
- No dependency or SQL migration. Ordinary parser advances to v5; parent-first
  isolated-worker rollout and historical-label behavior are documented in ADR-044.

## Verified private browser TLS/operator

Runtime **69e52e037c7d842f010e417d3f3e57466b55a2a7** passed
[CI 35616709666](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35616709666)
and [restore 35616709609](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35616709609),
observed 2026-09-21. Later receipt-only edits are not a new runtime verification.

- **2,103 Python passes including 294 real PostgreSQL cases**, no CI skips;
  **84 Node contracts**, **five actual MIME-container cases** and **15 actual
  PDF-container cases** passed. Repeated gate runs are not additional tests.
- All **43 new operator/TLS cases** passed in CI and locally. These include real
  TLS 1.2/1.3 handshakes over in-memory OpenSSL buffers with trusted success and
  wrong-host/untrusted-certificate refusal, not browser or hosted TLS acceptance.
- Both images, CLI smoke, runtime-reader exclusion, locked dependencies, lint,
  typing over **46 modules**, repository gate and **92 Markdown / 780 local path
  and fragment checks** passed. Separate restore-script typing passed locally.
- Restore verified **27 tables, 147 rows, two tenants, four encrypted objects,
  two identity bindings**, hash equality, tenant/identity RLS, revoked-context
  denial and database-only refusal. **29 safety tests** passed. **14.79 seconds**
  includes disposable startup; not production RTO, managed PITR or key-loss recovery.
- Local: **1,809 passes, 294 explicit SQL skips**, 84 Node passes; staged and
  incremental secret scans from 5c0114a found no leaks. Two pre-existing test
  warnings and action/runner migration notices remain non-failing backlog.
- The private repository now includes explicit browser-mode TLS startup and
  non-consuming preflight. Owner sign-in UI, actual browser acceptance, real
  issuer/MFA and hosted operation remain gates. No real mailbox or paid service enabled.

## Historical private browser TLS/operator — local checkpoint

ADR-043 adds explicit browser-mode startup and non-consuming preflight from base
**5c0114a4be6351931791834942cf3d6ba7306f7d**. Publication CI/restore must verify
the new exact commit; the earlier backend receipt below is not that verification.

- **1,809 local Python passes, 294 explicit SQL skips**, two existing warnings;
  **84 Node contracts** pass. Locked sync, lint, typing over **46 source modules**,
  separate restore typing, repository gate, docs and diff checks pass.
- **43 new operator cases** cover generated private certificates, dates/SAN/key
  mismatch, weak keys, encrypted-key refusal, links/permissions, scrubbed parser
  errors, mode conflicts and no-network/no-database/no-listener preflight.
- Real OpenSSL TLS 1.2 and 1.3 handshakes use the Uvicorn context and generated
  certificates over in-memory buffers, with trusted success and wrong-host/untrusted
  certificate refusal. This is not a socket, browser-trust installation or hosted test.
- No dependency, migration, grant, real identity or mailbox changed. Owner UI and
  actual-browser acceptance remain the next bounded slice, not completed features.

## Verified browser session backend

Runtime **5c0114a4be6351931791834942cf3d6ba7306f7d** passed
[CI 35599565083](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35599565083)
and [restore 35599565086](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35599565086),
observed 2026-09-21. This verifies ADR-042, not later ADR-043/operator work.

- **2,060 Python passes including 294 real SQL cases**, no CI skips; **84 Node
  contracts**, **five actual MIME-container** and **15 actual PDF-container** cases.
  Repeated release-gate suites and restore subsets are not additional tests.
- Both container images, CLI smoke, independent-reader exclusion, lint, locked
  dependencies, typing over **45 source modules** and restore-script typing pass.
  Documentation checks cover **91 Markdown files and 774 local paths/fragments**.
- Restore: **27 tables, 147 rows, two tenants, four encrypted objects, two identity
  bindings**, matching content hashes, RLS, current revocation and database-only
  restore refusal. **29 restore-safety cases** pass. **31.17 seconds** includes
  disposable startup; not production RTO/PITR, key-loss recovery or real issuer proof.
- Local **1,766 passes and 294 explicit SQL skips**; 102 new offline browser cases,
  ten new real-SQL cases in CI and one EOF-key-reader regression. Generated keys and
  fictional HTTP only. Staged/incremental secret scans from 611ee2d found no leaks.
- Two existing deprecation warnings and runner/action migration notices remain
  non-failing backlog. No browser UI, live issuer, cloud account or mailbox enabled.

## Historical browser session backend — local checkpoint

ADR-042's optional backend/REST slice was checked from base **611ee2dd87a30b0e334e69fbb834234b96d504d9**.
That base's [documentation CI 35597127919](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35597127919)
passed; it does not verify the new backend. Publication CI/restore must supply
exact-commit SQL/container evidence before this increment is accepted.

- **1,766 local Python passes, 294 explicit SQL skips**, two existing deprecation
  warnings; **84 Node contracts** pass. Lint, typing over **45 source modules**,
  separate restore-script typing, locked sync, repository gate and diff checks pass.
- **102 new offline browser cases**, **ten new SQL/API cases**, and one added
  key-reader EOF deadline regression are present. The SQL cases are not local
  passes. Fake authorization/token/key HTTP and generated RSA keys only.
- Coverage includes state/PKCE/issuer/client, unexpected ID/refresh token denial,
  expiry/capacity/restart, concurrent callbacks/reads, logout and late cancellation,
  current mapping, cookie/Host/Origin/CSRF/fetch metadata and private configuration
  redaction. SQL cases exercise both profiles, search/evidence isolation and binding
  revision/membership/expiry. Key retrieval now checks EOF time and caps before append.
- Documentation checks cover **91 Markdown files and 774 local paths/fragments**
  before receipt-only additions. No schema, dependency, grant or restore fixture changes.
- Default CLI/UI remain unchanged. Next wire private operator/TLS configuration
  and owner UI, then prove actual browser behavior. No real issuer, MFA policy,
  refresh/ID-token login, distributed sessions, public hosting or mailbox enabled.

## Verified identity foundation and response hardening

Runtime **88af6332012af820eedcede9ae78adff34a930df** passed
[CI 35596527992](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35596527992)
and [restore 35596528021](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35596528021),
observed 2026-09-21 Pacific. Later receipt-only documentation does not change this
runtime and must not be described as the commit tested by these runs.

- **1,947 standard Python tests passed, including 284 real PostgreSQL cases**,
  with no CI skips. **84 Node contracts**, **five actual MIME-container** and
  **15 actual PDF-container** cases passed. Repeated release-gate suites and
  restore subsets are not additional tests. Both images, CLI smoke, reader
  exclusion, locked dependencies, lint and typing over **43 source modules** passed.
- ADR-040/migration 0013 provides configured RFC/Entra access-token verification,
  server-owned identity mappings, current transaction authority and administrator
  audit. **124 offline identity cases and 35 SQL/API cases** cover the increment;
  fake issuers/generated keys do not establish real-issuer acceptance. Duplicate
  Authorization headers are rejected and missing credentials get a plain challenge.
- ADR-041 adds **16 transport cases** across Fastmail/Gmail/Graph/Ollama. Five
  tests failed the old buffered code before the correction; all pass afterward.
  The identity reader has its own equivalent regression proof. Incoming fragments
  now trigger cooperative checks without an extra fixed-size application buffer;
  byte caps and stream closure hold. This is not a hard DNS/TLS/process deadline.
- Restore verified **27 tables, 147 rows, two tenants, four encrypted objects and
  two identity bindings**. Hash equality, tenant/identity isolation, revoked-context
  denial and database-only refusal passed. **14.39 seconds** includes disposable
  startup; it is not production RTO/PITR. The **29 restore-safety cases** passed.
- Local: **1,663 Python passes, 284 explicit SQL skips**, 84 Node passes, locked
  sync, lint, source/restore-script typing, repository/docs/diff checks. CI supplies
  the real SQL/container evidence unavailable locally. Two existing deprecation
  warnings and GitHub action/runner migration notices remain non-failing work.
- Runtime documentation checks covered **89 Markdown files and 749 local paths/
  fragments**. Incremental secret scanning from 84997c4 through 88af633 found no
  leaks. This is not an exhaustive dependency, security or accessibility audit.

The documentation pack explains the game plan, current-versus-target features,
processing methods, identity/authorization, hosting boundaries, test feeds,
operations and Factory's next assignment. Historical receipts and source-health
observations retain their original dates rather than becoming fresh claims.

**Next:** browser sign-in/session lifecycle on the implemented token/mapping
foundation, then independent-service acceptance. No real issuer/app registration,
mailbox, paid hosting, public listener, MFA policy, team grant or mailbox-write
authority was enabled. The full product goal remains active.

## Historical configured API identity — local implementation checkpoint

ADR-040/migration 0013 adds RFC/Entra access-token verification, administrator-owned
identity mappings and current SQL authority. This checkpoint was checked locally
from base **84997c4f32dea58652343b5498e73d6a50ba85c4**; publication CI/restore must
provide the new exact-commit database/container evidence before acceptance.

- **1,643 local Python passes, 284 explicit PostgreSQL skips**; two existing
  deprecation warnings. **120 new offline identity cases** and **35 new SQL/API
  cases** are present; the latter are not local passes. **84 Node contracts** pass.
- Lint, strict typing over **43 source modules**, separate restore-script typing,
  CLI help, locked dependencies and diff checks pass. Documentation checks cover
  **88 Markdown files and 745 local paths/fragments** before receipt-only changes.
- Keys/tokens are generated in memory; all issuer HTTP in tests is fictional.
  SQL tests include both token profiles through the real API, mapping/RLS,
  revocation/revision, foreign evidence, runtime grant denials and administrator
  audit. Populated upgrade includes 0013. The restore fixture now seeds two identity
  bindings and tests mapped search/isolation and revocation after restore.
- Reviewed selected PyJWT advisory and installed MIT license; pinned 2.14.0.
  Focused upstream health observations are in [OSS evaluation](OSS_EVALUATION.md).
  This is not an exhaustive security or supply-chain certification.
- No real issuer, app registration, mailbox, public listener, paid resource,
  browser login, MFA policy or team grant was enabled. Independent review and
  complete identity/session lifecycle remain open. Existing durable processing
  approvals are not cancelled merely by token/binding revocation.

The earlier documentation-only revision 84997c4 passed
[CI 35592669766](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35592669766).
That result does not verify the new identity runtime. The next build assignment
after this slice is browser/session lifecycle over the existing mapping boundary,
not another verifier scaffold. The full product goal remains active.

## Documentation-only next-delivery review

Reviewed 2026-09-21 from clean base **c721f52a7811e236cc3de704e397f48eda602f01**.
That base's [CI 35591511467](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35591511467)
was observed successful. The following local results cover the editorial working
tree, not an already-published revision or a new runtime feature:

- Root product map, feature/method explanations, roadmap, backlog and Factory
  handoff now agree: identity is next; existing synthetic PDF/read commands and
  owner controls must not be rebuilt. Hosting, browser, scanner/live acceptance
  and broader grants remain separate gates. No source/schema/dependency change.
- All **86 Markdown documents** passed required-inventory and local-link/heading
  checks; **28 documentation-checker tests** passed. Legacy EB-006 navigation is
  retained. Link checks do not prove factual freshness or rendered accessibility.
- Locked offline dependency sync, lint, typing over **42 source modules**, repository
  quality gate and diff checks passed. Full local Python: **1,523 passed, 249 SQL
  cases explicitly skipped**, with two existing deprecation warnings. **84 Node
  contracts passed**. Repeated gate suites are not extra tests.
- No local database/container/live tests were newly run. The runtime's real SQL,
  restricted-container and restore evidence remains attached to 0b4f0d3 below.
  Public-source activity/pricing was not rescanned and its measurement dates are
  unchanged. No identity provider, mailbox or hosted resource was contacted.

Publication CI must be checked against the resulting documentation commit; the
prior runtime receipt is not a substitute for that check. This is a documentation
refresh, not completion of the active product build or production identity work.

## Bounded read-worker operator

Runtime **0b4f0d33bbdfedaad42dbbc7b2f09991cc2af923** passed
[CI 35590968421](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35590968421)
and [restore 35590968376](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35590968376),
observed 2026-09-21 Pacific. Later receipt-only documentation is not the SHA tested
by these runs and changes no runtime behavior.

- **1,772 standard Python tests passed**, including **249 real PostgreSQL cases**;
  no CI skips. **84 Node contracts**, **five actual MIME-container** and **15 actual
  PDF-container** cases passed. Repeated release-gate suites and restore subsets
  are not counted twice. Both images, default-image reader exclusion, CLI smoke,
  locked dependencies, lint, typing and documentation checks passed.
- **104 new standard cases**: 81 offline operator/configuration/identity tests and
  23 actual SQL cases. Real Fastmail HTTP logic uses a fictional injected transport;
  no provider is contacted. Tests cover non-consuming preflight, explicit execution,
  exact ingest scope, private files/keys, current binding, restart/search/evidence,
  token/owner/account/lease changes during downloads, persisted pauses/retries,
  stop and encrypted large-message preservation plus exact source readback.
- Authorization failures use a distinct guard exception rather than the worker's
  malformed-MIME path. SQL checks verify revoked/stale work cannot publish the
  page or advance its checkpoint, does not fabricate a parser pause, and closes
  its HTTP client. Existing lease recovery is retained; no automatic reset.
- Restore reverified **26 tables, 142 rows, two tenants and four encrypted objects**,
  equal hashes, tenant RLS and database-only refusal. **13.99 seconds** includes
  disposable startup, not production RTO/PITR. The unchanged fixture and 29 safety
  tests passed; no hosted key-recovery or live-provider claim.
- Local: **1,523 Python passes, 249 explicit PostgreSQL skips**, 84 Node passes,
  locked sync, lint, strict typing over **42 source modules**, separate restore
  typing, repository/docs/diff checks and CLI help. Staged and incremental secret
  scans through 0b4f0d3 found no leaks. Two existing Python deprecations and GitHub
  action/runner migration notices remain non-failing supply-chain work.
- The gate checked **86 Markdown files and 696 local paths/fragments** at the
  runtime revision. GitHub's Markdown API rendered the read-guide headings; this
  is not browser accessibility or external-source freshness verification.

[ADR-039](adr/039_read_worker_controller.md) and the [operator guide](READ_CONTROLLER.md)
define `sync-read`: private configuration, zero-request/zero-claim preflight,
explicit provider-read invocation, fixed account/secret binding, fresh authority
checks, bounded runs and content-free outcomes. Shared identity code preserves
MIME/PDF scope separation. No schema, dependency, SQL grant, HTTP API, enrollment,
mailbox effect or installed service was added. The command is implemented but has
not been used on real mail. Production identity, enrollment/resume administration,
hosted storage/supervision/alerts, live acceptance and soak remain gates. The next
implementation assignment is the configured OIDC/identity boundary, not another
read-controller scaffold. The full product goal remains unfinished.

## Owner PDF screen and current documentation pack

Implementation **8d8af93**, contract correction **f73c2352b14ddcceccf7ea2aaf42b9c614b02fe0**.
[CI 35589125895](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35589125895)
and [restore 35589125878](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35589125878)
passed at f73c235, observed 2026-09-21 Pacific. Subsequent receipt-only documentation
does not change the tested runtime and is not the revision tested by these runs.

- **1,668 standard Python tests passed**, including **226 real PostgreSQL cases**,
  with no CI skips. **84 Node contracts** (25 session/rules, 27 MIME, 32 PDF),
  **five actual MIME-container** and **15 actual PDF-container** cases passed.
  Repeated repository-gate suites and restore subsets are not counted twice.
- New coverage includes four real SQL/API-response-to-DOM cases for extracted,
  partial, encrypted/deferred and failed documents; four fixed static-asset cases;
  and the PDF owner suite's consent, idempotency, stale-context, identity, paging,
  cancellation, opt-in search and cited-page checks. The bridge uses a known-answer
  reader; actual extraction remains the separate container suite's responsibility.
- The first [CI run 35588376901](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35588376901)
  failed all four bridge cases: the UI wrongly expected PDF-result `unscanned`
  on original attachment receipts, whose persisted contract is `not_scanned`.
  The fix corrects that validator and its offline fixtures, adds negative scan-state
  coverage and preserves source/identity checks. No receipt/schema migration or
  malware-safety assertion was introduced. The four real-response cases now pass.
- Restore: **26 tables, 142 rows, two tenants, four encrypted objects**, equal
  hashes, tenant RLS and database-only refusal; **14.37 seconds** including disposable
  startup. The unchanged fixture and 29 restore safety tests passed. This is not
  production RTO, managed PITR or hosted key-loss recovery.
- Local: **1,442 Python passes, 226 explicit PostgreSQL skips**, 84 Node passes,
  locked development sync, lint, strict typing over 41 source modules, separate
  restore-script typing, repository/docs/diff checks. Incremental secret scan of
  6984edf..f73c235 found no leaks. Two existing Python deprecations and GitHub's
  action Node-runtime/Ubuntu migration notices remain non-failing tracked work.
- A limited browser smoke at 8d8af93 checked initial layout, fictional connection,
  default-off PDF search, invalid-account handling and session/checkbox clearing.
  It did **not** exercise PDF approval/results against SQL, keyboard/screen-reader
  acceptance or mobile layout. The synthetic preview server and tab were closed.

The pack now explains ADR-038's owner workflow and aligns product features,
methods, roadmap, security, APIs, deployment and Factory's next assignment. CI
checked **84 Markdown files and 668 local paths/fragments** at f73c235; subsequent
receipt links increase that number. GitHub's Markdown API rendered the owner-guide
headings. Neither navigation checks nor rendered HTML certify factual freshness or
accessibility. Historical research/OSS counts retain their actual observation dates.

No real mail, provider writes, remote model, cloud resource, production identity,
scanner acceptance or Factory mutation. The next implementation package is the
bounded read-worker operator entry point; browser/live/hosted acceptance remain
separate gates. See [owner guide](DOCUMENT_REVIEW_SCREEN.md) and [handoff](FACTORY_HANDOFF.md).

## Methods guide and documentation verification

Documentation/tooling revision **874c288** adds the plain-language
[methods guide](METHODS_GUIDE.md), explicit next owner-workflow outcome, corrected
MIME/PDF command wording and the regression-tested offline documentation gate
from [ADR-037](adr/037_documentation_verification.md). No application runtime,
schema, dependency, permission or hosted resource changes. Historical research
dates and prior verification remain intact; no new OSS activity scan is claimed.

[CI 35585839904](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35585839904)
passed at **874c288b368550b80c085b09cb61c4081e51d5f9**, observed 2026-09-21 Pacific:
**1,660 Python tests, including 222 real PostgreSQL cases**, no CI skips;
**52 Node contracts, five actual MIME-container and 15 actual PDF-container cases**.
The repeated repository-gate suite is not counted twice. Both images, default-image
reader exclusion, CLI smoke, locked dependencies, lint, typing and docs checks passed.
Existing action Node-runtime and future Ubuntu-runner migration notices remain
non-failing supply-chain work. This increment did not rerun the separate restore
workflow; the unchanged application/schema restore proof remains the 73a8459 run
below. Later receipt-only edits are not the revision tested by this run.

Local verification at that revision: **1,438 Python passes, 222 explicit PostgreSQL
skips**, **52 Node UI-contract passes**, locked dependency sync, lint, strict typing
over 41 source modules plus the documentation checker, repository/docs/diff checks.
The 28 new documentation regressions are included in the Python count, not added
again. Two existing upstream Python deprecations remain. Staged and incremental
secret scans found no leaks in the change.

The gate checked **82 Markdown files and 635 local paths/fragments** at 874c288,
including hidden GitHub templates. GitHub's Markdown API rendered the guide's
headings; the published file's Git blob matched the checkout. These are navigation/
rendered-HTML checks, not browser layout or accessibility acceptance. Later receipt
edits can increase the link count without changing the tested checker.

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
