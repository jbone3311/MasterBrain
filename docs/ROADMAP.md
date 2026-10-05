# MasterBrain Roadmap

Updated 2026-10-05 through ADR-160's merged event timeline, ADR-161's
merged reviewed-commitment due view, ADR-162's merged project dossier, and
ADR-163's in-review first-party project drill-down.
ADR-159's grouped Brain/Ask reviewed-leaf
projection (PR #148 at `f9402d7`), ADR-158's optional direct KnowledgeCore
unsuperseded search (PR #146 at `3bf21b8`), ADR-155's separate-cluster restore
(PR #139 at `9b1ae23`) and ADR-156's merged, nonpublishing FileOS
shadow symlink-target boundary (PR #141 at `082b0e8`). The latest merged
Fastmail resilience is ADR-110/PR #133. ADR-157/PR #144 at `96cb22b`
adds a bounded Ask output-text slice; full response/token and grounded-chat
acceptance remain open.
This is a dependency-ordered plan, not a release claim.
The documentation-only `main` checkpoint encountered
[Actions billing/limit issue #150](https://github.com/jbone3311/MasterBrain/issues/150).
After recovery, ADR-160 [PR #151](https://github.com/jbone3311/MasterBrain/pull/151)
merged at `90ee9e4`. Implementation-head and merged-main CI, container,
strict-runtime and restore gates passed. The isolated local PostgreSQL 17.11
suite also passed 488 tests with a Docker-only skip. ADR-161 separately merged
through PR #152 at `e3826ff` after exact-head gates and passed merged-main
CI, strict-runtime and restore; both full CI runs executed all 490
PostgreSQL-marked tests.
[Current functions](CURRENT_FUNCTIONS.md) and
[implementation status](IMPLEMENTATION_STATUS.md) describe executable behavior;
[build receipts](BUILD_RECEIPT.md) tie verification to exact commits. The
original functions-review baseline was `c8c428b`; later exact-commit evidence is
recorded in the build receipt and GitHub PR checks. No live-source, production or
FileOS cutover acceptance is implied.

## Where we are

| Milestone | Current position | What is still missing |
|---|---|---|
| Product identity and donor baseline | MasterBrain identity, source-layer boundaries, pinned FOS-Master provenance, first hash/dedupe parity and synthetic shadow corpus are in the repo | Full semantic and operational parity, owner cutover decision |
| DataCore read path | Shared persistence, FileOS snapshot/publication, confined extraction, archive derivatives, generation activation/rollback and additive Email bridges work on synthetic/disposable data | Donor inventory-policy decision, live shadow, automatic/supervised work, hosted evidence storage and retention |
| KnowledgeCore | Reviewed evidence-linked base assertions, corrections, lexical search and change feed work; optional direct and grouped current-search/Ask unsuperseded review-chain leaves passed exact-head PostgreSQL, strict-runtime and restore gates; ADR-160 reviewed-event timeline, ADR-161 due-window commitment read and ADR-162 exact-project dossier passed merged-main gates | Cross-kind/valid-time timeline, project/commitment reducers, automatic candidate pipeline, evaluated resolution, rebuild and freshness proof |
| Brain API | Scoped progressive reads, grouped current Email/FileOS/knowledge search with explicit All/Email/FileOS focus, evidence drill-down and partial coverage work; extractive Ask has separate 8-KiB selector-input and returned-untrusted-text caps with visible truncation; a read-only reference client has fictional API parity; enrolled assistants have source-scoped Brain and direct Knowledge/unified reads; ADR-149 denies unfenced legacy Email routes to assistants | Hosted issuer enrollment and derived-cache revocation, cited answer synthesis, named-assistant adapter and full prompt/token/whole-response budgets |
| Owner chat and external assistants | A first-party read-only question workspace and external read client use the same Brain API; Ask returns exact quotes and a separate reviewed KnowledgeCore match list. ADR-163's explicit project-dossier drill-down is locally implemented with exact-head gates pending | Run the owner's interactive trial, evaluate held-out natural questions, corrections and contradictions, review any privacy-approved model adapter separately, then prove named-assistant identity/citation/revocation and hosted acceptance |
| Hosted read-only product | Local/CI synthetic paths and restore drills only | Owner-approved identity, source enrollment, operations, retention, alerts, incident/restore drills and live acceptance |
| FileOS replacement and effects | Private v2 generation plus human-only historical v1/v2 comparison API are merged; no cutover or source effects | Decide donor-policy edge behavior, prove sustained live shadow and v2 current/absence/rollback semantics, then a bounded rollback-ready cohort and owner sign-off; effects require a separate later approval |

## Next verified sequence

The active lanes are deliberately separate. A read-only owner trial and grounded
chat evaluation can proceed without a FileOS policy switch; the private hosting
pilot needs the owner's choices; reviewed source actions remain later work.
Each lane must pass its own acceptance gate before the next dependent step:

| Lane | Next concrete step | Gate that remains open |
|---|---|---|
| Product chat ([#92](https://github.com/jbone3311/MasterBrain/issues/92)) | Record the owner's fictional cross-source question trial, then test held-out questions, contradiction handling, answer/citation budgets and first-party versus API behavior | No model-written answer or named-assistant parity is accepted yet |
| Hosted read-only pilot ([#94](https://github.com/jbone3311/MasterBrain/issues/94), [#3](https://github.com/jbone3311/MasterBrain/issues/3)) | Obtain region, budget, retention, identity and authorized-source decisions; then exercise a private, reversible pilot | No live source, hosted identity, recovery or operations acceptance exists |
| FileOS migration ([migration plan](FOS_MIGRATION.md)) | Review the six recorded donor-policy differences and fault/platform cases, then run an owner-authorized read-only shadow on a bounded root | No v2 current publication, FileOS effect, donor cutover or retirement is approved |
| Reviewed actions ([#93](https://github.com/jbone3311/MasterBrain/issues/93)) | Specify typed propose/preview/approve/execute contracts and reversible first actions | The existing Brain API stays read-only until separate grants, safety tests and approval exist |

The donor remains pinned at `218d5caec2f20b9047fd3eb8e027dc671acf0c15`
and unchanged. The latest ADR-156 shadow hardening reduces what the synthetic
comparison may observe; it does not resolve the six policy differences or
authorize a live root. The exact checkpoint is in the
[build receipt](BUILD_RECEIPT.md).

The synthetic Email reliability tranche uses [ADR-110](adr/110_fastmail_sync_resilience.md)
and preserves the original [Claude draft #45](https://github.com/jbone3311/MasterBrain/pull/45)
as provenance. [PR #133](https://github.com/jbone3311/MasterBrain/pull/133)
renumbered its held-source migration to 0052 and splits only control-byte-
overflowing metadata requests. The valid 50-message overflow page,
unsplittable-row refusal, partial-budget/replay/recovery and populated
migration tests passed, as did exact-head CI, strict runtime and restore.
Merged-main results are in the [build receipt](BUILD_RECEIPT.md). This is not
a live-account, scheduler, hosted-operations or production acceptance; those
remain separately gated. FOS-Master is unaffected.

The latest merged FileOS functional slice is [PR #116](https://github.com/jbone3311/MasterBrain/pull/116):
its final head and merged `main` passed full CI, strict runtime and populated
restore. It exposes **historical review only**. It is not a reason to activate a
v2 generation, reinterpret absence, stop FOS-Master or claim a live product.

Repository governance is tracked separately from functional acceptance:
[ADR-153](adr/153_required_main_checks.md) protects `main` with three
always-on required checks. It was tested with a blocked pending PR and an
automatic merge only after CI succeeded. Passing those synthetic checks does
not prove a live mailbox, hosted privacy boundary or FileOS cutover.

1. Complete the owner's fictional cross-source walkthrough and record expected
   versus observed answers, citations and gaps. The existing local launcher
   self-test is not owner acceptance.
2. Resolve the security and operational gates in
   [#7](https://github.com/jbone3311/MasterBrain/issues/7),
   [#9](https://github.com/jbone3311/MasterBrain/issues/9) and
   [#34](https://github.com/jbone3311/MasterBrain/issues/34) before a hosted
   pilot. An unresolved critical/high defect is not an acceptable release
   exception. Finish assistant enrollment/revocation in
   [#88](https://github.com/jbone3311/MasterBrain/issues/88). A new
   disposable-PostgreSQL Ask regression checks revocation during quote
   selection and the next turn; it does not replace hosted issuer/cache tests.
3. In the FileOS lane, keep FOS-Master pinned and unchanged. Settle cloud-
   placeholder, fault/race and inventory-policy differences; run read-only
   donor shadow on an owner-authorized bounded root. Only then design a
   separately approved v2 current-visibility, later-run, absence and rollback
   transaction with golden, stress and fault gates. The historical API is a
   review aid, not a shortcut to this decision. ADR-152 closes a synthetic
   descendant-directory symlink enumeration leak in the nonpublishing shadow;
   it does not substitute for live-root or cross-platform fault acceptance.
4. In the product lane, use [#92](https://github.com/jbone3311/MasterBrain/issues/92)
   for grounded chat evaluation and [#94](https://github.com/jbone3311/MasterBrain/issues/94)
   for an owner-approved private central API/database pilot. Keep
   [#93](https://github.com/jbone3311/MasterBrain/issues/93) reviewed source
   effects behind separate grants, previews, idempotency and rollback; do not
   treat the present read-only API as a write API.

The later [PR #118](https://github.com/jbone3311/MasterBrain/pull/118) adds a
default refusal for populated legacy 0008/0009 rewrites; it is not an online
upgrade or closure of the hosted migration-lock gate. These lanes can be
researched independently, but each code tranche still needs
its own exact-head and merged-main verification before the next dependent
tranche. Neither PR #116 nor PR #118 creates a new version tag or production
claim.

## Next build packages

These are small PRs with their own tests, documentation and exact-head CI/restore.
Security and data-integrity blockers take priority over adding more surface area.

1. **Finish the fictional user trial.** Run the
   [cross-source walkthrough](CROSS_SOURCE_TRIAL.md) interactively on the owner's
   Mac, record commit, expected/actual known answers, citations, coverage and
   browser behavior. Fix any failure on a branch; do not interpret hosted API
   tests as browser acceptance. An agent-run local in-app browser pass on
   fictional PostgreSQL data found and corrected visible highlight markers
   and an over-technical evidence panel (ADR-136); the owner's independent
   walkthrough remains outstanding. ADR-137 adds a disposable local PostgreSQL
   launcher option for Macs without Docker. ADR-140 makes that one-click path
   use a locked non-editable install after a local `.pth` import failure. Its
   self-test passes on the affected Mac; the owner's interactive acceptance is
   still required. The fictional corpus also contains a deliberately unresolved
   Email/FileOS closing-date conflict: Ask must cite both dates without deciding
   between them. That test does not prove conflict detection or resolution.
   Exact verification belongs in the build receipt.
2. **Resolve security and upgrade findings.** Identity enrollment
   [#6](https://github.com/jbone3311/MasterBrain/issues/6) is fixed on `main` by
   ADR-105; the exact resolver of ADR-106 narrows but does not close the confirmed
   [tenant-context authority bug #7](https://github.com/jbone3311/MasterBrain/issues/7).
   ADR-108 adds an opt-in one-tenant database-login fence. ADR-109 adds a
   synthetic API route through separate lookup and tenant logins. ADR-135/138/139
   add opt-in tenant-bound access to all database-backed private `masterbrain`
   commands. ADR-141 extends this to all three legacy Email worker commands.
   Private library caller routing, credential lifecycle and hosted adversarial
   acceptance remain next. ADR-154 extends the disposable restore drill to
   check two DBA-bound logins and forged tenant settings after logical restore;
   ADR-155 extends that to a second disposable PostgreSQL cluster, requiring
   absent source roles and audited retirement of their restored bindings.
   Neither drill restores role secrets or proves managed-host recovery.
   Independently close #7 and the
   [populated migration lock/rewrite risk #9](https://github.com/jbone3311/MasterBrain/issues/9).
   ADR-148 now refuses implicit populated 0008/0009 heap rewrites and requires
   an explicit maintenance override; it does not make those migrations online
   or cover later populated-index/DDL lock budgets. Measure and rehearse a
   safe upgrade path before closing #9.
   Require exploit/lock evidence, regression tests, restore and an operational
   rollout/rollback receipt. Green synthetic CI alone does not close them;
   release exceptions apply only where [acceptance criteria](RELEASE_ACCEPTANCE.md)
   permit them.
3. **Complete the engineering-quality gate.** Follow
   [#34](https://github.com/jbone3311/MasterBrain/issues/34): package/API version
   identity, content-safe application **and PostgreSQL server** logging, bounded
   failure paths, supply chain, operations and exact release evidence. PR #33 is
   only the API-error first tranche. ADR-120 instruments the trusted
   isolated-controller failure stage without changing its scrubbed public
   outcome; use the next synthetic recurrence to diagnose and resolve
   [issue #64](https://github.com/jbone3311/MasterBrain/issues/64) before
   claiming stable hosted container acceptance.
4. **Extend bounded FileOS derivatives only after review.** Current-only archive-image
   OCR search is implemented under ADR-107 with exact parent/receipt fencing and
   independent Brain API coverage. Automatic selection, fan-out and live-source
   acceptance remain separate gates. [Issue #10](https://github.com/jbone3311/MasterBrain/issues/10)
   is the historical Claude handoff; its old branch/base notes are not current work.
5. **Measure donor policy parity before any switch.** The extracted inventory
   classifier and an isolated, nonpublishing donor-policy shadow profile match the
   pinned donor on the synthetic corpus; neither is wired into publishable
   MasterBrain snapshots. Resolve fault/race/cloud-placeholder behavior, define
   versioned v2 publication and transition from v1 through
   [FOS migration](FOS_MIGRATION.md), then run read-only shadow and rollback
   rehearsals. Do not change FOS-Master or silently adopt donor exclusions.
   DC-002H now confines shadow metadata-only observations against root/ancestor
   swaps. DC-002I adds a source-bound, nonpublishing candidate ledger that keeps
   hashless rows deferred; neither settles cloud-placeholder behavior nor
   authorizes v2 publication. DC-002J's read-only transition preview classifies
   the v1/donor policy gap; it does not create a persisted v2 baseline or absence
   authority. DC-002K also requires the latest exact completed v1 database run
   before and after scanning; it creates no v2 publication or cutover authority.
   DC-002L can retain that candidate and comparison as a private immutable
   review packet after a locked latest-run check. It still does not implement
   v2 persistence, an approved transition or donor-policy publication.
   DC-002M adds bounded private review of that packet; no review result is
   treated as transition approval or a live-root attestation.
   DC-002N adds a relational, nonpublishing v2 staging ledger for hashed,
   hashless deferred, excluded and error observations. It does not change
   current FileOS state; owner-reviewed transition, v2 freshness/absence,
   rollback and live shadow remain separate gates.
   DC-002O adds an exact, locator-free transition plan and synthetic-only
   human-owner approval receipt. DC-002P adds a worker-only fresh scan that
   must match the approved stage exactly and records a historical verification
   receipt. DC-002Q adds a private third exact scan and policy-scoped hashed
   DataCore evidence preparation; it deliberately leaves the v1 current
   pointer and all search/freshness state unchanged. DC-005N addresses the
   separate v1 large-completion ledger cost before broader transition stress.
   DC-002R adds separately scoped, synthetic-only owner authorization bound
   to the exact preparation and plan. DC-002S now seals a fresh,
   source-locked private completion ledger with a compact inspection.
   DC-002T publishes and accounts for normalized documents on the prepared
   v2 evidence without activating them as current. DC-002U (ADR-126) adds an
   exact private v2 generation in shared DataCore index tables with
   database-enforced activation refusal. PR #81 merged with exact-head and
   merged-main gates green. DC-002V (ADR-128) adds a private human-review
   comparison of one named v2 generation with active v1 using the same lexical
   query. ADR-147 gives that comparison a bounded, human-only Brain API route;
   it is still a historical preview, not current-search visibility. Current visibility,
   later v2-run behavior, absence
   suppression, rollback and live acceptance remain separate decisions before
   any switch.
   Repeated 3,000-row runs against one accumulated disposable database exposed
   a readiness-query timeout in the existing v2 builder; track the populated-
   database scaling work in [#84](https://github.com/jbone3311/MasterBrain/issues/84).
   ADR-131/PR #90's forward-only indexed correction passed fresh and populated
   3,000-row tests, then exact-head and merged-main CI, strict runtime and
   populated restore. The issue is closed without relaxing exact closure or
   the five-second statement gate; live-source acceptance remains separate.
   A separate [controlled v1 completion benchmark](FILEOS_COMPLETION_BENCHMARK.md)
   now isolates the old per-item deferred ledger trigger's 3,000-row cost on
   local and container PostgreSQL 17.11; broader load and operational
   acceptance remain issue #71.
   PRs #52, #55, #57, #59 and #61 are merged with final-head and merged-main CI, strict
   runtime and restore green. PR #63 adds the nonpublishing approval receipt;
   its exact-head and merged-main gates passed after an intermittent container
   rerun tracked in issue #64. V2 publication remains a separate step.

The first three tranches can be reviewed independently of 5D implementation.
None authorizes a real account, live root, paid hosting, production release or
FileOS cutover. The separate `v0.2.0a1` tag is synthetic-only.

## Later product milestones

- **Knowledge quality:** migrate narrow Email memory and donor fact lessons only
  through evidence-backed, versioned projections. Evaluate aliases, temporal
  correction, contradictions, project state and commitments on held-out cases.
- **Client-neutral access:** the read-only reference client and fictional REST
  parity are implemented. Synthetic bootstrap and administrator-bound OIDC
  Brain assistants must enroll explicit source IDs for the original three
  search/evidence reads, ADR-133's two status reads and ADR-142's retained,
  aggregate and exact-FileOS Brain reads. ADR-143 adds unified Brain and direct
  Knowledge reads, with all directly linked evidence sources required.
  OIDC grant removal
  invalidates future transactions. ADR-149 keeps legacy Email compatibility
  routes human/operator-only instead of creating a second assistant read path.
  Hosted issuer enrollment, hosted semantics and derived-cache invalidation
  remain [issue #88](https://github.com/jbone3311/MasterBrain/issues/88).
  A named MCP/other assistant adapter still requires prompt-injection isolation,
  compactness, citations and cross-assistant conformance. The REST Brain API
  remains the source of truth; no assistant integration is certified today.
- **Owner conversational workspace:** the read-only question screen uses the
  scoped API for current Email and FileOS quotes plus separately labelled,
  source-scoped reviewed KnowledgeCore matches. It removes fixed question
  boilerplate, verifies exact citations and exposes partial coverage, but is
  not AI-written synthesis or a stateful chat.
  Next evaluate held-out questions, contradictions and follow-up context, then
  add separately approved cited synthesis and prove native/external parity.
- **Hosted read-only acceptance:** choose region/budget, retention, enrollment,
  sharing and first source with the owner; deploy private storage/keys, supervised
  workers, protected telemetry and real backup/restore. Pilot one disposable
  Email account and one bounded FileOS root only after authorization.
- **FileOS cutover:** shadow the unchanged FOS-Master, compare inventories,
  hashes, derivatives, query answers, failures and performance, then switch one
  reversible cohort with owner sign-off. Rename or retirement is a separate
  later decision.
- **Reviewed effects:** design typed preview, policy, approval, idempotent
  execution, quarantine and rollback for selected Email and FileOS actions. Both
  chat and external clients may propose actions, but only separately scoped
  executors can change a source. No autonomous send, permanent deletion or mass
  file movement is in the initial release. See [the interface contract](USER_INTERFACES.md).

## Checkpoint discipline

For each tranche: pin the starting commit and donor revision if applicable;
write/update its ADR and testable acceptance; build on a branch; run unit, fault,
PostgreSQL, browser, restricted-worker and parity checks as applicable; update
the [status](IMPLEMENTATION_STATUS.md), [functions](CURRENT_FUNCTIONS.md),
[code map](CODE_MAP.md), [changelog](../CHANGELOG.md) and
[receipt](BUILD_RECEIPT.md); obtain review; merge without rewriting history;
verify the resulting `main` commit. A tag is a separate decision after all
[synthetic-alpha gates](RELEASE_ACCEPTANCE.md#synthetic-alpha-checkpoint-not-production-acceptance)
and exact-commit evidence pass. Production and cutover use their stricter gates.
