# MasterBrain Roadmap

Updated 2026-10-01. This is a dependency-ordered plan, not a release claim.
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
| KnowledgeCore | Reviewed evidence-linked base assertions, corrections, lexical search and change feed work | Automatic candidate pipeline, evaluated resolution, complete project/commitment reducers, rebuild and freshness proof |
| Brain API | Scoped progressive reads, grouped current Email/FileOS/knowledge search, evidence drill-down and partial coverage work; fictional browser trial is merged | Cited answer synthesis, common client adapter/conformance, full byte/token budgets and revocation proof across caches |
| Owner chat and external assistants | A first-party read-only question workspace uses the same Brain API and shows grouped current hits/evidence; no answer synthesis or certified external assistant exists | Prove native/external parity on one shared corpus, add grounded cited answers, freshness/revocation tests and hosted acceptance |
| Hosted read-only product | Local/CI synthetic paths and restore drills only | Owner-approved identity, source enrollment, operations, retention, alerts, incident/restore drills and live acceptance |
| FileOS replacement and effects | No cutover or source effects | Sustained donor shadow, bounded rollback-ready cohort, owner sign-off; effects require a separate later approval |

## Next build packages

These are small PRs with their own tests, documentation and exact-head CI/restore.
Security and data-integrity blockers take priority over adding more surface area.

1. **Finish the fictional user trial.** Run the
   [cross-source walkthrough](CROSS_SOURCE_TRIAL.md) interactively on the owner's
   Mac, record commit, expected/actual known answers, citations, coverage and
   browser behavior. Fix any failure on a branch; do not interpret hosted API
   tests as browser acceptance.
2. **Resolve security and upgrade findings.** Identity enrollment
   [#6](https://github.com/jbone3311/MasterBrain/issues/6) is fixed on `main` by
   ADR-105; the exact resolver of ADR-106 narrows but does not close the confirmed
   [tenant-context authority bug #7](https://github.com/jbone3311/MasterBrain/issues/7).
   ADR-108 adds an opt-in one-tenant database-login fence. ADR-109 adds a
   synthetic API route through separate lookup and tenant logins; private-worker
   routing, credential lifecycle and hosted adversarial acceptance remain next.
   Independently close or explicitly accept that risk and the
   [populated migration lock/rewrite risk #9](https://github.com/jbone3311/MasterBrain/issues/9).
   Require exploit/lock evidence, regression tests, restore and an operational
   rollout/rollback receipt. Green synthetic CI alone does not close them.
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
   merged-main gates green. Current visibility, later v2-run behavior, absence
   suppression, rollback and live acceptance remain separate decisions before
   any switch.
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
- **Client-neutral access:** implement an MCP/other adapter only after identity
  scopes, prompt-injection isolation, compactness, citation, revocation and one
  common Claude/Grok/ChatGPT conformance suite are specified and tested. The
  REST Brain API is the current source of truth; no assistant integration is
  certified today.
- **Owner conversational workspace:** the first read-only, conversation-shaped
  search screen uses the existing scoped API for current Email, FileOS and
  KnowledgeCore evidence. It is not an AI answer. Next add grounded cited
  synthesis with visible freshness/coverage and a path to the original, then
  prove native and external surfaces agree on a shared corpus.
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
