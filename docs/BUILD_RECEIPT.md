# Build and validation receipt

Updated 2026-10-05 UTC. Product: `jbone3311/MasterBrain`, verified **private**.

## First-party reviewed schedule — ADR-164 in review

The unmerged `codex/brain-reviewed-schedule` branch adds explicit first-party
UTC-window reads of the existing ADR-160/161 event and due APIs. The focused
Node browser suite passed 29/29 locally and all six browser files passed
164/164. Ruff, source mypy, docs and diff checks passed. The local
non-PostgreSQL run passed 2,663 tests, with 491 database tests skipped and
one Docker-only launcher deselected. The separate disposable PostgreSQL 17.11
run passed 490/491 marked cases, with one Docker-only skip and 2,664 other
tests deselected (245.66 seconds). Exact-head CI, strict-runtime, restore and
merged-main gates are not claimed. This UI read
does not make the reviewed dates or states live-current facts.

## First-party reviewed-project drill-down — ADR-163 merged

PR [#156](https://github.com/jbone3311/MasterBrain/pull/156) merged at
`c50c3972261f3fbaaea15dcc5354a2dddf1f158b` from exact head
`6ea7888d20befcfa383769914bd9287c16e2f9bf`. It adds an explicit `/brain`
project-dossier control, complete response validation and stale-read refusal.
The focused Node browser suite passed 21/21 locally and the final six-file
browser suite passed 156/156. Exact-head
[CI 37359290556](https://github.com/jbone3311/MasterBrain/actions/runs/37359290556)
passed 3,143 tests, 12 skipped twice (regular and deployment repeat), with
491/491 PostgreSQL-marked cases executed both times; docs, API image and
restricted PDF/FileOS worker container checks passed.
[Strict runtime 37359290672](https://github.com/jbone3311/MasterBrain/actions/runs/37359290672)
and [restore 37359290433](https://github.com/jbone3311/MasterBrain/actions/runs/37359290433)
also passed. Merged `main` CI
[37362023408](https://github.com/jbone3311/MasterBrain/actions/runs/37362023408),
strict runtime [37362023414](https://github.com/jbone3311/MasterBrain/actions/runs/37362023414)
and restore [37362023248](https://github.com/jbone3311/MasterBrain/actions/runs/37362023248)
are queued or in progress; no merged-main result is claimed yet. The existing
ADR-162 API's gates are separate evidence, not proof of this UI merge.
The local non-PostgreSQL Python run passed 2,663 tests, skipped all 491
PostgreSQL-marked tests and deselected one Docker-backed local launcher. A
separate real-PostgreSQL 17.11 run on the disposable
`email_brain_test_dossier_20261005` database passed 490 tests, with one
Docker-only skip and 2,664 non-PostgreSQL tests deselected (204.82 seconds).
Ruff, source mypy, documentation and diff checks pass. Neither local run
substitutes for exact-head container, strict-runtime or restore gates.

## Reviewed project dossier — ADR-162 merged

[PR #154](https://github.com/jbone3311/MasterBrain/pull/154) merged at
`cf6c656b454141e008851c68ab5477487503d789` from exact head
`88e16a9793dffe08c5b92a3f517e723cdc750940`. Exact-head
[CI 37351772063](https://github.com/jbone3311/MasterBrain/actions/runs/37351772063)
passed **3,143 tests, 12 skipped** twice (regular and deployment repeat),
including **491/491 PostgreSQL-marked executed** in each run. Documentation,
API image and dedicated PDF/FileOS document, image and archive worker checks
passed. Exact-head [strict runtime 37351772156](https://github.com/jbone3311/MasterBrain/actions/runs/37351772156)
and [restore 37351772055](https://github.com/jbone3311/MasterBrain/actions/runs/37351772055)
also passed. Merged `main` at the commit above passed
[strict runtime 37353642367](https://github.com/jbone3311/MasterBrain/actions/runs/37353642367)
and [restore 37353642413](https://github.com/jbone3311/MasterBrain/actions/runs/37353642413).
[Full CI 37353642249](https://github.com/jbone3311/MasterBrain/actions/runs/37353642249)
also passed **3,143 tests, 12 skipped** twice, with **491/491
PostgreSQL-marked tests executed** in each run; docs, API image and restricted
PDF/FileOS worker container checks passed. These synthetic checks do not
expand the boundary into hosted or live-source acceptance.

Branch `codex/knowledge-project-dossier` adds one read-only, exact-project
KnowledgeCore dossier, independently bounded linked event and commitment
lists (including undated links), an additive recorded-time index migration
0056, a provider-neutral client method and source-aware regressions. The
starting `main` commit `2acda635a2be6f1a0198859817a23e42225cd879`
passed [full CI 37346476188](https://github.com/jbone3311/MasterBrain/actions/runs/37346476188),
strict runtime and restore before this branch was proposed. That is **base**
evidence, not an ADR-162 head gate.

Local focused schema/API/client tests passed 87 cases. The isolated
PostgreSQL 17.11 end-to-end KnowledgeCore/API/client case and populated,
no-row-rewrite migration case passed after the final source-link validation
change. A second full local run passed **3,153 tests**
with **490/491 PostgreSQL-marked executed**, one Docker-only skip and one
explicitly deselected local trial launcher. The launcher was separately
attempted and failed while `initdb` requested another System V shared-memory
ID on this Mac (`shmget: No space left on device`, not disk exhaustion); it is
not counted as passed. The final future-cutoff assertion was then rechecked
in the focused real-PostgreSQL path (2/2 passed). The six browser test files
passed 151/151 Node tests. Ruff, source mypy, docs and diff checks pass.
No hosted source, FileOS effect, FOS-Master mutation or release tag is claimed.

## Reviewed-commitment due view — ADR-161 merged

[PR #152](https://github.com/jbone3311/MasterBrain/pull/152) merged at
`e3826ff8f6e1a6ad2f5b7a369f4d7e06b7962d08` from exact PR head
`cc6e445638d5ad358e020ff96e3523dd777885d3`. Exact-head
[CI 37340533691](https://github.com/jbone3311/MasterBrain/actions/runs/37340533691)
passed **3,124 tests, 12 skipped**, including **490/490 PostgreSQL-marked**;
the deployment repeat passed the same counts and the API/PDF/FileOS document,
image and archive worker container checks passed. Exact-head
[strict runtime 37340533835](https://github.com/jbone3311/MasterBrain/actions/runs/37340533835)
and [restore 37340533705](https://github.com/jbone3311/MasterBrain/actions/runs/37340533705)
passed. The merged `main` commit separately passed
[CI 37342204761](https://github.com/jbone3311/MasterBrain/actions/runs/37342204761)
with the same **3,124 passed, 12 skipped, 490/490 PostgreSQL-marked** plus
the deployment repeat and container checks;
[strict runtime 37342204648](https://github.com/jbone3311/MasterBrain/actions/runs/37342204648)
and [restore 37342204774](https://github.com/jbone3311/MasterBrain/actions/runs/37342204774)
also passed. These are synthetic CI proofs, not hosted/live-source acceptance.

Branch `codex/knowledge-commitments-due` adds a bounded, read-only due-window
view, additive partial indexes (migration 0055), provider-neutral client method
and PostgreSQL visibility/paging regressions. The focused schema/API/client
suite passed 67 tests; source mypy and targeted Ruff passed. A disposable local
PostgreSQL 17.11 case passed the end-to-end KnowledgeCore/API/client path and
the populated no-row-rewrite migration regression. After repairing the local
virtual environment's subprocess import path, the full non-PostgreSQL run
passed **2,645 tests** with the Docker-backed launcher excluded; the full
PostgreSQL-marked run passed **489 tests, one Docker-only skip** in 143.50
seconds. The isolated base was `email_brain_test_due161_20261005` on port
55443. Ruff, mypy, documentation and diff checks passed. No FOS-Master mutation, hosted
acceptance, overdue computation or source effect is implied.

## Reviewed-event timeline — ADR-160 merged

PR #151 was merged to `main` at
`90ee9e41cff101fcb30ce6ce99f988f8e01d84a4`; the exact PR head
`8cc4feca6ea47a30aaa815c60c206db9f5d51079` passed
[CI 37264285649](https://github.com/jbone3311/MasterBrain/actions/runs/37264285649),
[strict runtime 37264285699](https://github.com/jbone3311/MasterBrain/actions/runs/37264285699)
and [restore 37264285656](https://github.com/jbone3311/MasterBrain/actions/runs/37264285656).
Merged `main` separately passed
[CI 37265330633](https://github.com/jbone3311/MasterBrain/actions/runs/37265330633),
[strict runtime 37265330664](https://github.com/jbone3311/MasterBrain/actions/runs/37265330664)
and [restore 37265330609](https://github.com/jbone3311/MasterBrain/actions/runs/37265330609).
Both CI runs executed 489/489 PostgreSQL-marked tests and the deployment
repeat/container checks. This is synthetic CI evidence, not hosted acceptance.

Branch `codex/knowledge-timeline-read` adds a bounded occurrence-window event
read and forward migration 0054. Nine local schema/API/query-construction
tests passed; the full local non-PostgreSQL suite passed 2,627 tests, with
488 PostgreSQL-marked tests and one host-dependent disposable launcher test
deselected, **not passed in that run**. Ruff, source mypy, documentation and
diff checks passed. An existing isolated local PostgreSQL 17.11 test cluster
then allowed real database verification: the KnowledgeCore timeline integration
test passed after correcting two test expectations for its newly added late
successor. The first full PostgreSQL-marked run passed **487 tests, one skip**
in 221.44 seconds. After adding the populated 0054 migration regression, the
updated full run passed **488 tests, one skip** in 208.34 seconds. The one skip
is the Docker-backed browser launcher, because
Docker is unavailable locally; the separate local launcher cannot initialize
a fresh cluster while macOS's 32 System V shared-memory slots are occupied.
The tests used a newly created, distinct `email_brain_test_timeline151_20261003`
database on port 55443; existing test databases and FOS-Master were untouched.
An additional populated-upgrade regression applied migrations 0001–0053,
inserted both dated/project-linked and undated KnowledgeCore events, then
applied 0054 and verified unchanged rows, row locations and heap filenode,
both partial indexes and idempotent replay. The entire migration-integrity
module passed **5/5** locally. This is not a large-hosted-table lock-budget
or online-index proof.
This proves disposable local PostgreSQL behavior, not hosted acceptance.
After the [Actions billing/limit incident #150](https://github.com/jbone3311/MasterBrain/issues/150),
implementation commit `d52b167740d4607e957183847ba95824ff540323` passed
[full CI 37150248668 attempt 7](https://github.com/jbone3311/MasterBrain/actions/runs/37150248668)
with **3,105 passed, 12 skipped** and **489/489 PostgreSQL-marked executed**.
The deployment gate repeated the 3,105 tests, and the API image, dedicated
PDF/FileOS document/image/archive workers and their restricted extraction
checks all passed. The same commit passed
[strict runtime 37150248761 attempt 4](https://github.com/jbone3311/MasterBrain/actions/runs/37150248761)
and [synthetic populated restore 37150248722 attempt 4](https://github.com/jbone3311/MasterBrain/actions/runs/37150248722).
The documentation-only follow-up commit is separately gated;
none of these runs prove a hosted or live-source deployment.
The local supported-Python 3.11.13 strict-runtime subset
(`test_strict_runtime.py`, `test_rule_control.py`, `test_review_fixes.py`)
passed **92 tests**, including all 13 PostgreSQL-marked cases. Installed
unsupported Python 3.12.4 refused both package entry-point imports with the
required security-patched-parser error. The six CI browser JavaScript files
passed **151 tests** under Node 24. These local checks preceded, and do not
replace, the executed CI interpreter matrix or Docker restore/container gates.
Pre-merge review found and corrected a page-cutoff gap: late successors and
corrections can no longer suppress earlier eligible events on later pages.
The new PostgreSQL regression covers both paths and passed locally;
the nine focused mock/schema/API tests and the 2,627 non-PostgreSQL tests
passed again after this change. The provider-neutral `BrainReadClient.timeline`
adds closed read requests and response validation; its 11 additional transport
cases passed. A subsequent end-to-end regression passed through
`BrainReadClient.timeline`, the authenticated FastAPI route and real
PostgreSQL, paging retained project events across the returned cutoff/cursor.
This does not prove hosted assistant identity. GitHub review is tracked in
[PR #151](https://github.com/jbone3311/MasterBrain/pull/151).
No live source, donor or version change.

## Historical CI execution blocker — issue #150

At documentation-only PR #149's merged-main commit
`168ad65e32174c328d45286e9acbf0331a85b9d4`, [CI](https://github.com/jbone3311/MasterBrain/actions/runs/37147321816),
[strict runtime](https://github.com/jbone3311/MasterBrain/actions/runs/37147321823)
and [restore](https://github.com/jbone3311/MasterBrain/actions/runs/37147321797)
failed **before a runner or any test step started**. Each check annotation
reports failed account payments or an insufficient spending limit. These are
not product test failures or passing runs. The PR head and the preceding
functional merge had executed and passed their required checks; the
documentation-only merge adds no runtime behavior. Actions eligibility later
recovered and PR #151's exact implementation commit passed the three required
workflows above. The failed `168ad65` merged-main runs remain failed historical
evidence, not passing checks; a later merge requires its own exact-head and
merged-main verification.

## Grouped current reviewed leaves — PR #148 merged

[PR #148](https://github.com/jbone3311/MasterBrain/pull/148) merged
[ADR-159](adr/159_current_brain_reviewed_leaves.md) at
`f9402d753db6f37c8f9861c170a2a29e9a21003e`. Its final head
`d12db81566d47275f66e4cb817954b284d14398e` passed
[full CI](https://github.com/jbone3311/MasterBrain/actions/runs/37145217025)
(3,088 tests passed, 12 skipped, including all 488 PostgreSQL-marked tests;
the deployment gate repeated the same 3,088 tests and container/worker
checks passed),
[strict runtime](https://github.com/jbone3311/MasterBrain/actions/runs/37145216964)
and [populated restore](https://github.com/jbone3311/MasterBrain/actions/runs/37145216984).
The merged-main [full CI](https://github.com/jbone3311/MasterBrain/actions/runs/37146314821)
passed, as did merged-main
[strict runtime](https://github.com/jbone3311/MasterBrain/actions/runs/37146314852)
and [populated restore](https://github.com/jbone3311/MasterBrain/actions/runs/37146314751)
passed at that exact merge commit. This selects ADR-158's unsuperseded
KnowledgeCore mode only for grouped current-search and Ask. The retained
direct/unified routes and focused source reads remain unchanged. Focused local
non-PostgreSQL tests passed 74; the full local non-PostgreSQL run passed
2,611 tests, with 488 PostgreSQL-marked and one host-dependent local launcher
test deselected, **not passed** locally. Ruff, mypy, documentation and 16
first-party browser tests passed. No source, donor or version change.

## Unsuperseded reviewed KnowledgeCore search — PR #146 merged

[PR #146](https://github.com/jbone3311/MasterBrain/pull/146) merged
[ADR-158](adr/158_unsuperseded_reviewed_knowledge_search.md) at
`3bf21b8720cc8a28392687bede283f9dbac7e779`. Its final head
`e8957b1c96698f83a6cbef042d6d07575934e7e4` passed
[full CI](https://github.com/jbone3311/MasterBrain/actions/runs/37142497725)
(3,088 tests passed, 12 skipped, including all 488 PostgreSQL-marked tests;
the deployment gate independently reran the same 3,088 tests and the
container/worker checks passed),
[strict runtime](https://github.com/jbone3311/MasterBrain/actions/runs/37142497687)
and [populated restore](https://github.com/jbone3311/MasterBrain/actions/runs/37142497688).
The merged-main checks at this exact commit passed: [full CI](https://github.com/jbone3311/MasterBrain/actions/runs/37143412564),
[strict runtime](https://github.com/jbone3311/MasterBrain/actions/runs/37143412576),
and [populated restore](https://github.com/jbone3311/MasterBrain/actions/runs/37143412567).
The documentation receipt [PR #147](https://github.com/jbone3311/MasterBrain/pull/147)
merged at `53463412486c1cdce223f2077831f1e1ae9c6a87` after its exact-head
required checks passed. Its merged-main strict-runtime and restore checks
passed, including [full CI](https://github.com/jbone3311/MasterBrain/actions/runs/37144260203).
This receipt changed no product behavior.
This adds optional read-only review-chain leaf retrieval, source-grant-aware
suppression, and forward lookup indexes in migration 0053. Retained history
remained the default; grouped Brain current-search and Ask were unchanged at
that checkpoint, before ADR-159.
Local non-PostgreSQL tests passed 2,611; 488 PostgreSQL-marked tests and one
host-dependent disposable launcher test were deselected, **not passed**
locally. Ruff, source mypy and documentation checks passed. FOS-Master and
all source files remain unchanged.

## Ask output-text budget — PR #144 merged

[PR #144](https://github.com/jbone3311/MasterBrain/pull/144) merged
[ADR-157](adr/157_ask_output_text_budget.md) at
`96cb22bd0f9c3247e0ee3bce770a717e43c7d078`. Its final head
`e24cbac` passed
[full CI](https://github.com/jbone3311/MasterBrain/actions/runs/37139485238)
(3,087 tests passed, 12 skipped; all 488 PostgreSQL-marked tests executed,
plus deployment and container checks),
[strict runtime](https://github.com/jbone3311/MasterBrain/actions/runs/37139485229)
and [populated restore](https://github.com/jbone3311/MasterBrain/actions/runs/37139485172)
before automatic merge. Merged-main
[full CI](https://github.com/jbone3311/MasterBrain/actions/runs/37140450382)
also passed (3,087 tests, including all 488 PostgreSQL-marked tests, plus
deployment/container checks), along with
[strict runtime](https://github.com/jbone3311/MasterBrain/actions/runs/37140450350)
and [populated restore](https://github.com/jbone3311/MasterBrain/actions/runs/37140450360).
The change keeps exact source quotes
and bounds the aggregate returned quote/reviewed text at 8,192 UTF-8 bytes.
Focused Ask/client tests passed (70); the first-party browser tests passed
(16), as did the full six-file browser set (151), Ruff, source mypy and the
initial local documentation checker (255 Markdown files, 1,380 local
paths/fragments); the updated head's hosted docs check passed.
The local non-PostgreSQL suite passed 2,610 tests, with 488 PostgreSQL-marked
tests and the one host-dependent disposable launcher test excluded (489
deselected, not passed).
The local disposable launcher remains blocked
by the macOS PostgreSQL shared-memory limit seen on the prior checkpoint; its
failure must not be counted as a passing local database test. No FileOS donor,
source, schema, deployment or product version changes are included.

The [post-merge full CI for PR #142](https://github.com/jbone3311/MasterBrain/actions/runs/37138045748)
subsequently completed successfully at exact `main` commit `d5bb39f`.

## Plan synchronization — PR #143 merged

[PR #143](https://github.com/jbone3311/MasterBrain/pull/143) merged the
README, roadmap and receipt reconciliation at
`2d00b2238257a073066587716b480ffe839a2122`. Its exact-head full CI,
strict-runtime and populated restore passed before merge. Merged-main
[full CI](https://github.com/jbone3311/MasterBrain/actions/runs/37139432806),
[strict runtime](https://github.com/jbone3311/MasterBrain/actions/runs/37139432824)
and [populated restore](https://github.com/jbone3311/MasterBrain/actions/runs/37139432808)
also passed. This was documentation only, not a product version or live gate.

## ADR-156 documentation receipt — PR #142 merged

[PR #142](https://github.com/jbone3311/MasterBrain/pull/142) merged a
documentation-only receipt for ADR-156 at
`d5bb39f968e7750f2cf02dbb513fd311183ebf04`. Its exact-head full CI,
strict-runtime and logical-restore checks passed before merge. It added no
runtime capability, live-source acceptance or product version. The
[post-merge full CI](https://github.com/jbone3311/MasterBrain/actions/runs/37138045748)
later passed at that exact `main` commit, as recorded above.

## Donor-shadow symlink boundary — PR #141 merged

[PR #141](https://github.com/jbone3311/MasterBrain/pull/141) merged
[ADR-156](adr/156_shadow_symlink_target_boundary.md) at
`082b0e849ac69cb0abd9472d3e758f6e59c7d3b5`. The first head `5db15e0`
failed [full CI](https://github.com/jbone3311/MasterBrain/actions/runs/37134626132)
on one PostgreSQL packet test: new profile validation ran before the existing
16-MiB packet-size refusal and changed its error contract. The corrective
`732926e` head restored the size-check order and passed
[full CI](https://github.com/jbone3311/MasterBrain/actions/runs/37135176013)
(3,080 tests, including all 488 PostgreSQL-marked tests, plus deployment checks),
[strict runtime](https://github.com/jbone3311/MasterBrain/actions/runs/37135176287),
[logical restore](https://github.com/jbone3311/MasterBrain/actions/runs/37135176169)
and the [synthetic ledger benchmark](https://github.com/jbone3311/MasterBrain/actions/runs/37135176025).
Local focused tests, Ruff, mypy and documentation checks passed. The local
full suite passed 2,603 tests with one synthetic PostgreSQL launcher test
excluded because macOS `initdb` could not allocate a host shared-memory
segment; this was not counted as a passing local PostgreSQL gate. The pinned,
unchanged FOS-Master comparator matched 3,004 ordinary rows at 3,000 stress
files and 9,998 ordinary rows at the 9,994-file maximum, with zero unexplained
membership differences. Its existing six v1-policy gaps remain explicit.
Merged-main [strict runtime](https://github.com/jbone3311/MasterBrain/actions/runs/37136194994),
[populated restore](https://github.com/jbone3311/MasterBrain/actions/runs/37136194986)
and [synthetic ledger benchmark](https://github.com/jbone3311/MasterBrain/actions/runs/37136194976)
also passed at the exact merge. Merged-main
[full CI](https://github.com/jbone3311/MasterBrain/actions/runs/37136195012)
passed, including its PostgreSQL tests and deployment checks. No live
root, publishable v1 inventory, v2 current read, source effect or donor
runtime was switched.

## Separate-cluster two-tenant restore — PR #139 merged

[PR #139](https://github.com/jbone3311/MasterBrain/pull/139) merged ADR-155
at `9b1ae2365266f57597b8f292c4aea72d281ed207`. Its final head
`7ffd975` passed
[full CI](https://github.com/jbone3311/MasterBrain/actions/runs/37130962823),
[strict runtime](https://github.com/jbone3311/MasterBrain/actions/runs/37130962885)
and the actual [PostgreSQL 17 restore](https://github.com/jbone3311/MasterBrain/actions/runs/37130962801).
The source and target were distinct owned, loopback-only containers with
separate generated passwords. The target bootstrapped only two fixed no-login
policy roles before restore; source tenant login roles were absent. After
hash-equal restoration of 85 tables, 280 rows and four encrypted objects,
two stale source-name bindings were retired before two fresh target logins
passed the ADR-154 forged-context isolation checks. The exact-head restore
reported four bound role/tenant pairs and passed in 22.83 seconds; this is
not a production RTO. Merged-main
[strict runtime](https://github.com/jbone3311/MasterBrain/actions/runs/37132007727)
and [populated restore](https://github.com/jbone3311/MasterBrain/actions/runs/37132007711)
also passed; the merged-main restore reported the same counts and refusal
flags in 19.89 seconds. Merged-main
[full CI](https://github.com/jbone3311/MasterBrain/actions/runs/37132007732)
also passed, including its deployment checks.
No FOS-Master, live source, runtime credential rotation or hosted environment
changed; issue #7 remains open.

## Two-tenant restore receipt — PR #138 merged

[PR #138](https://github.com/jbone3311/MasterBrain/pull/138) recorded the
prior same-cluster proof at `3c27823beee0454180aeb13e3b28d60a28d29033`.
Its exact-head
[full CI](https://github.com/jbone3311/MasterBrain/actions/runs/37129384659),
[strict runtime](https://github.com/jbone3311/MasterBrain/actions/runs/37129384660)
and [populated restore](https://github.com/jbone3311/MasterBrain/actions/runs/37129384813)
passed before automatic merge. Merged-main
[full CI](https://github.com/jbone3311/MasterBrain/actions/runs/37130367289),
[strict runtime](https://github.com/jbone3311/MasterBrain/actions/runs/37130367238)
and [populated restore](https://github.com/jbone3311/MasterBrain/actions/runs/37130367301)
also passed. This was documentation only, not an additional product version.

## Two-tenant bound-login restore proof — PR #137 merged

[PR #137](https://github.com/jbone3311/MasterBrain/pull/137) merged ADR-154
at `abf5292de54458a3b063b40f8270301cb7d216da`. Its final head
`9a375d3` passed
[full CI](https://github.com/jbone3311/MasterBrain/actions/runs/37127823023),
[strict runtime](https://github.com/jbone3311/MasterBrain/actions/runs/37127823028)
and the actual [PostgreSQL 17 logical restore](https://github.com/jbone3311/MasterBrain/actions/runs/37127823127).
The restore job verified 85 tables, 280 rows, two fictional tenants, four
tenant-bound role/tenant pairs across the source and target databases,
content-hash equality and forged-context refusal. Local offline restore
safety tests passed **29**, as did Ruff, source/script mypy and documentation
checks. This is a same-cluster disposable drill, not restored role secrets,
separate-cluster disaster recovery, hosted tenant acceptance or closure of
issue #7.
Merged-main [full CI](https://github.com/jbone3311/MasterBrain/actions/runs/37128717526),
[strict runtime](https://github.com/jbone3311/MasterBrain/actions/runs/37128717529)
and [populated restore](https://github.com/jbone3311/MasterBrain/actions/runs/37128717578)
also passed on `abf5292`.

## Protected-main documentation reconciliation — PR #136 merged

[PR #136](https://github.com/jbone3311/MasterBrain/pull/136) reconciled the
README, roadmap, progress notes and build receipt at
`eab4dba83f439c3938b747e717d6344874185047`. Its exact-head
[full CI](https://github.com/jbone3311/MasterBrain/actions/runs/37126621943),
[strict runtime](https://github.com/jbone3311/MasterBrain/actions/runs/37126621940)
and [populated restore](https://github.com/jbone3311/MasterBrain/actions/runs/37126621949)
passed before automatic merge. Merged-main
[full CI](https://github.com/jbone3311/MasterBrain/actions/runs/37127289376),
[strict runtime](https://github.com/jbone3311/MasterBrain/actions/runs/37127289461)
and [populated restore](https://github.com/jbone3311/MasterBrain/actions/runs/37127289279)
also passed. This was documentation only, not a new product version.

## Main-branch required checks — PR #135 merged

[PR #135](https://github.com/jbone3311/MasterBrain/pull/135) added the
ADR-153 stable `strict-runtime-gate` and versioned main-protection policy.
Its exact head `19907d6` passed
[full CI](https://github.com/jbone3311/MasterBrain/actions/runs/37125012352),
[strict runtime](https://github.com/jbone3311/MasterBrain/actions/runs/37125012361)
and [populated restore](https://github.com/jbone3311/MasterBrain/actions/runs/37125012343).
The applied GitHub rule requires `gate`, `logical-restore` and
`strict-runtime-gate`, strict branch freshness, pull requests and resolved
conversations; it applies to administrators and denies force pushes/deletion.
With the first two checks green and full CI still running, GitHub reported
the PR `BLOCKED`; the requested automatic merge remained queued. Only after
full CI succeeded did GitHub merge it at
`6cdebb6832afd668b60019c0220804d090c83375`. This verifies merge
enforcement for that PR. Merged-main
[full CI](https://github.com/jbone3311/MasterBrain/actions/runs/37125957941),
[strict runtime](https://github.com/jbone3311/MasterBrain/actions/runs/37125957937)
and [populated restore](https://github.com/jbone3311/MasterBrain/actions/runs/37125957963)
also passed. No runtime product behavior, live-source authority or FOS-Master
state changed.

## Latest documentation checkpoint — PR #134 merged

[PR #134](https://github.com/jbone3311/MasterBrain/pull/134) reconciled the
Fastmail integration receipt at `7e99a6648a0843a3fcbb199cb106bf910a52b24c`.
Its final-head [full CI](https://github.com/jbone3311/MasterBrain/actions/runs/37122985816),
[strict runtime](https://github.com/jbone3311/MasterBrain/actions/runs/37122985782)
and [populated restore](https://github.com/jbone3311/MasterBrain/actions/runs/37122985766)
passed. Merged-main [full CI](https://github.com/jbone3311/MasterBrain/actions/runs/37123950883),
[strict runtime](https://github.com/jbone3311/MasterBrain/actions/runs/37123950917)
and [populated restore](https://github.com/jbone3311/MasterBrain/actions/runs/37123950904)
also passed. This was documentation only, not another functional version.

## ADR-110 Fastmail resilience integration — PR #133 merged

The [integration PR #133](https://github.com/jbone3311/MasterBrain/pull/133)
preserves Claude's [draft #45](https://github.com/jbone3311/MasterBrain/pull/45)
commit as a merge parent, ports its held-source schema to forward migration
0052, distinguishes control-byte overflow from malformed JMAP, and bisects a
valid oversized metadata batch before an atomic page commit. A synthetic
50-message response above the unchanged 1 MiB control cap split into two
25-message requests with all 50 items and the inventory seal committed. A
single unsplittable row retained the cursor and failed closed. A reported
source size above 2 GiB was held without allocating or downloading it.
Focused Fastmail/JMAP/worker tests passed **130**, browser tests passed **149**,
Ruff and strict mypy over 98 source files passed, and the documentation inventory
passed. On disposable local PostgreSQL 17.11, the full repository gate passed
**3,085 Python tests, one Docker-only skip and one excluded nested-launcher
test**; the nested local-launcher test passed separately after the task's
other disposable cluster was stopped. macOS had exhausted its 32 SysV shared-
memory IDs with both clusters running; the original socket-DSN run also
violated the trial harness's loopback-DSN requirement. These are test-environment
constraints, not evidence of live-provider correctness. The exact head
`123e89e6aba8194ee5e294320db47cac30ef47fc` passed
[full CI](https://github.com/jbone3311/MasterBrain/actions/runs/37121216438),
[strict runtime](https://github.com/jbone3311/MasterBrain/actions/runs/37121216346)
and [populated restore](https://github.com/jbone3311/MasterBrain/actions/runs/37121216459)
before merging to `main` at `ff7a2960ad90763396bc2b340dd7d69f3bed8bd5`.
Merged-main [full CI](https://github.com/jbone3311/MasterBrain/actions/runs/37122058539),
[strict runtime](https://github.com/jbone3311/MasterBrain/actions/runs/37122058534)
and [populated restore](https://github.com/jbone3311/MasterBrain/actions/runs/37122058546)
also passed. These verify the merged synthetic/disposable state, not a live
Fastmail account or hosted operator rollout; no real mailbox was contacted
or approved.

## Prior `main` documentation checkpoints — PRs #131 and #132

[PR #132](https://github.com/jbone3311/MasterBrain/pull/132) refreshed the
README, roadmap, progress and receipt for the Fastmail integration gate. Its
final documentation head `4b24732` passed
[full CI](https://github.com/jbone3311/MasterBrain/actions/runs/37120001143),
[strict runtime](https://github.com/jbone3311/MasterBrain/actions/runs/37120001165)
and [populated restore](https://github.com/jbone3311/MasterBrain/actions/runs/37120001131).
It merged at `520ba81f3290a201b8f4093b8ac6f46357da1445`; merged-main
[full CI](https://github.com/jbone3311/MasterBrain/actions/runs/37120175490),
[strict runtime](https://github.com/jbone3311/MasterBrain/actions/runs/37120175489)
and [populated restore](https://github.com/jbone3311/MasterBrain/actions/runs/37120175495)
passed. This documentation-only merge did not accept Claude's code or create a
new version.

[PR #131](https://github.com/jbone3311/MasterBrain/pull/131) merged the
post-ADR-152 documentation receipt at
`65dcdf79749bb583ba6597705e3da98865a57d10`. This was a documentation
checkpoint, not a functional change or version release. Its exact-head
full CI, strict runtime and populated restore passed. On the merged commit,
[strict runtime](https://github.com/jbone3311/MasterBrain/actions/runs/37119099301)
and [populated restore](https://github.com/jbone3311/MasterBrain/actions/runs/37119099315)
passed; [full CI](https://github.com/jbone3311/MasterBrain/actions/runs/37119099299)
also passed. At that checkpoint PR #45 was a separate draft; GitHub later
marked it merged when its preserved commit entered `main` through PR #133.

## Confined FileOS donor-shadow directory walk — PR #130 merged

ADR-152 replaces the nonpublishing shadow's pathname directory walk with
root-bound, no-follow descriptor enumeration. A deterministic descendant
symlink swap previously leaked an outside junk filename into the exclusion
ledger without reading bytes; new descendant, nested-ancestor and after-open
move tests now record only a directory coverage error. The focused inventory/
donor/candidate/transition selection passed **62 tests, zero skips**; Ruff, strict
mypy over 98 source files, documentation links and diff checks passed. The
unchanged FOS-Master checkout at `218d5cae` still matched **3,004 ordinary
rows** on the 3,000-file comparison and **9,998 ordinary rows** on the
9,994-file stress comparison (10,000 prior v1 rows), with six explicit policy
gaps and zero unexplained membership differences. Exact-head
[full CI](https://github.com/jbone3311/MasterBrain/actions/runs/37117143203),
[strict runtime](https://github.com/jbone3311/MasterBrain/actions/runs/37117143113)
and [populated restore](https://github.com/jbone3311/MasterBrain/actions/runs/37117143131)
passed on [PR #130](https://github.com/jbone3311/MasterBrain/pull/130)
head `2328e5a`; it merged to `main` at `c834fef`. Merged-main
[strict runtime](https://github.com/jbone3311/MasterBrain/actions/runs/37118024678)
and [populated restore](https://github.com/jbone3311/MasterBrain/actions/runs/37118024743)
passed. Merged-main [full CI](https://github.com/jbone3311/MasterBrain/actions/runs/37118024704)
also passed. No publishable v2 inventory, live-root shadow or donor edit
is claimed.

## Extractive Ask UTF-8 passage budget — PR #128 merged

ADR-151 caps selector-visible text at 2,048 UTF-8 bytes per passage and
8,192 bytes total, and reports upstream character/byte shortening through
`coverage.answer_context_truncated`. Focused unit/browser tests cover Unicode
boundaries, aggregate exhaustion, skipped later evidence reads, exact prefix
citations, malformed text and coverage rendering. A real disposable PostgreSQL
17.11 API/client/assistant focus scenario passed with the new flag. The final
local deployment gate passed **3,037 Python tests, one Docker-only skip**
(484 of 485 PostgreSQL-marked tests executed); all six browser suites passed
**148 tests**. Ruff, strict mypy over 98 source files, the documentation
inventory/link check and diff whitespace check passed. Exact-head
[full CI](https://github.com/jbone3311/MasterBrain/actions/runs/37113897875),
[strict runtime](https://github.com/jbone3311/MasterBrain/actions/runs/37113897648)
and [populated restore](https://github.com/jbone3311/MasterBrain/actions/runs/37113897707)
passed on [PR #128](https://github.com/jbone3311/MasterBrain/pull/128)
head `25ec6f4`; it merged to `main` at `14e91f0`. Merged-main
[strict runtime](https://github.com/jbone3311/MasterBrain/actions/runs/37114695392)
and [populated restore](https://github.com/jbone3311/MasterBrain/actions/runs/37114695418)
passed. Merged-main [full CI](https://github.com/jbone3311/MasterBrain/actions/runs/37114695386)
also passed. This is not a
whole-response/model-token budget or hosted/named-assistant acceptance.

## Pinned FileOS donor capacity comparison — local evidence

On the unchanged FOS-Master checkout at `218d5cae`, the nonpublishing
donor-policy comparator passed with 3,000 stress files (3,004 ordinary matches)
and again with 9,994 stress files, the maximum synthetic v1 corpus bound
(9,998 ordinary, metadata-only, changed and replay matches; 10,000 prior v1
rows). Both runs retained six explicit policy gaps and zero unexplained
membership differences. The focused donor suites passed **44 tests, zero
skips**. These are synthetic local comparisons, not complete semantic parity,
live-root acceptance, v2 current visibility or permission to switch FileOS.

## Explicit Brain source focus — PR #126 and merged `main`

ADR-150 adds optional All/Email/FileOS focus to grouped current search,
extractive Ask, the first-party `/brain` workspace and `BrainReadClient`.
Focused calls skip excluded source and reviewed-knowledge queries and mark
their coverage `not_searched`; grants, scopes, currentness rechecks and
evidence boundaries are unchanged. A real disposable PostgreSQL 17.11
cross-source/API/client/assistant parity test passed, including hidden-source
denial. After the final coverage-label refinement, the focused selection
passed **59 tests** (one PostgreSQL-marked test executed, none skipped). The
local deployment gate passed **3,032 Python tests, one Docker-only skip**
(484 of 485 PostgreSQL-marked tests executed); all six browser suites passed
**147 tests**. Ruff, strict mypy over 98 files, the documentation inventory/link
check and diff whitespace check passed. CI, strict runtime and populated
restore passed on the exact [PR #126](https://github.com/jbone3311/MasterBrain/pull/126)
head `0c64a48` and merged `main` `c984a2e`:
[CI](https://github.com/jbone3311/MasterBrain/actions/runs/37111156596),
[strict runtime](https://github.com/jbone3311/MasterBrain/actions/runs/37111156635),
[populated restore](https://github.com/jbone3311/MasterBrain/actions/runs/37111156665).
This is not a hosted or live-source acceptance claim.

## Ask mid-turn assistant source revocation — local regression

A synthetic OIDC assistant enrolled for one Email and one FileOS source began
an Ask request over both. A test selector removed the FileOS grant after it
received bounded passages but before the final current-search recheck. The
in-flight API response was `403 access_denied`, with no answer or quote; the
next request returned only Email citations. The focused disposable PostgreSQL
17.11 test passed (one PostgreSQL-marked test executed, zero skipped). The
broader Ask/source-grant/cross-source selection passed **57 tests** with one
Docker-only skip (24 of 25 PostgreSQL-marked tests executed). An initial
sandboxed pass failed only when the nested local trial launcher could not
allocate shared memory; the complete selection passed when that disposable
launcher was permitted. The final local deployment gate passed **3,028 Python
tests, one Docker-only skip** (483 of 484 PostgreSQL-marked tests executed)
on disposable PostgreSQL 17.11. All six browser suites passed **145 tests**.
Ruff, strict mypy over 98 source files and the documentation inventory/link
check passed. This is an authorization regression,
not hosted issuer enrollment, cache revocation or issue #88 closure.

## FileOS v1 completion trigger-cost audit — merged verification

The opt-in [benchmark](FILEOS_COMPLETION_BENCHMARK.md) used two equivalent
synthetic 3,000-item FileOS sources on a fresh disposable Homebrew PostgreSQL
17.11 database. With the current schema/writer, completion took **0.529 s**;
adding back migration 0018's old deferred per-item whole-ledger trigger made
the otherwise same completion take **24.404 s** (**46.1×**). PostgreSQL reported
zero timed/requested checkpoints during either measured completion. Both
immutable ledgers had exactly 3,000 rows; the added trigger and ephemeral
login were removed. A first fresh-database run measured 0.577 s versus
24.202 s (41.97×) without checkpoint counters. These are single-machine
wall-clock measurements that isolate trigger overhead, not exact historical
binary replay or a production SLA. On the final local tree, the separate
deployment gate passed **3,027 Python tests, one Docker-only skip** on
disposable PostgreSQL 17.11 (482 of 483 PostgreSQL-marked tests executed);
all six browser suites passed **145 tests**. Ruff, strict mypy over 98 source
files and the benchmark script, documentation links and diff checks passed.
An independent [PostgreSQL 17 Debian container workflow](https://github.com/jbone3311/MasterBrain/actions/runs/37104973815)
passed the same 3,000-row comparison: current **1.520 s**, with old trigger
**50.655 s** (**33.33×**), and zero timed/requested checkpoints during each
completion. The final PR-head [container benchmark](https://github.com/jbone3311/MasterBrain/actions/runs/37105169392)
also passed: **1.548 s** versus **51.810 s** (**33.46×**) with zero
checkpoints. [PR #122](https://github.com/jbone3311/MasterBrain/pull/122)
passed exact-head `26c5cf18e38d979dcc2a5a06ccfdd6611adbc762`
[full CI](https://github.com/jbone3311/MasterBrain/actions/runs/37105169366),
[strict runtime](https://github.com/jbone3311/MasterBrain/actions/runs/37105169368),
[populated restore](https://github.com/jbone3311/MasterBrain/actions/runs/37105169415)
and the dedicated benchmark above. It merged at
`412486037f60184c7d27b4542e52a038ccb9b612`; merged-main checks are
tracked separately. This corroborates the trigger-cost mechanism across two
platforms but is not a production latency guarantee. FOS-Master was not
contacted; [issue #71](https://github.com/jbone3311/MasterBrain/issues/71)
remains open for broader load/platform acceptance, parity and cutover gates.

## ADR-149 assistant legacy Email denial — merged verification

On this branch, synthetic bootstrap tests refused assistant `email.*` scopes;
API tests passed forged assistant principals into legacy search, evidence,
account status, reader, memory, recovery, document and rule routes and observed
denial before protected work. Disposable PostgreSQL integration proved an old
Email-only OIDC assistant binding cannot authenticate or reuse a saved
transaction context; existing enrolled Brain assistant and human/worker paths
continued to pass. The full Python 3.14.7 suite on loopback PostgreSQL 17.11
passed **3,022 tests, one Docker-only skip**; 482 of 483 PostgreSQL-marked
tests executed. All six required browser suites passed **145 tests**. Ruff,
strict mypy over 98 source files, documentation inventory/links and diff
checks passed. A first sandboxed run could not launch its nested disposable
PostgreSQL self-test; the individual test and entire suite passed with the
local launcher permitted. No real account, hosted issuer, source effect or
FOS-Master checkout was touched. [PR #120](https://github.com/jbone3311/MasterBrain/pull/120)
passed exact-head `a3a30627e2d6fd31143200a6e048e45e73f6d966`
[full CI](https://github.com/jbone3311/MasterBrain/actions/runs/37101399730),
[strict runtime](https://github.com/jbone3311/MasterBrain/actions/runs/37101399726)
and [populated restore](https://github.com/jbone3311/MasterBrain/actions/runs/37101399627).
It merged at `0591eacf027cadf8feb1696a70cacfc16847165d`; merged-main
checks are separately recorded at
[full CI](https://github.com/jbone3311/MasterBrain/actions/runs/37102019122),
[strict runtime](https://github.com/jbone3311/MasterBrain/actions/runs/37102019170)
and [populated restore](https://github.com/jbone3311/MasterBrain/actions/runs/37102019176).
The run links are authoritative for their final outcomes. Issue #88 remains
open.

## ADR-148 populated legacy rewrite refusal — merged-main verification

On the final branch source, a disposable loopback PostgreSQL 17.11 database
ran the complete Python 3.14.7 suite: **3,015 passed, one intentional skip**;
481 of 482 PostgreSQL-marked tests executed. The focused populated-upgrade
regression proved default refusal for both legacy rewrites, immediate refusal
under a concurrent writer, bounded refusal under a concurrent reader, no
failed-migration ledger row, explicit override retaining the existing parser
integrity check, and checksum-safe replay. All six browser suites passed
**145 tests**; Ruff, strict mypy over 98 source files, documentation inventory
and diff checks passed. An initial full run used a Unix-socket test DSN that
the cross-source fixture intentionally rejects and could not launch a nested
local cluster inside the sandbox. The final run used the fixture-required
loopback DSN and permitted only a disposable synthetic launcher; it passed.
These local results are separate from the hosted checks. [PR #118](https://github.com/jbone3311/MasterBrain/pull/118)
passed final-head `df7da1b07efd48b8212783eaca1936ac84bf713b`
[full CI](https://github.com/jbone3311/MasterBrain/actions/runs/37097115920),
[strict runtime](https://github.com/jbone3311/MasterBrain/actions/runs/37097115861)
and [populated restore](https://github.com/jbone3311/MasterBrain/actions/runs/37097115901).
It merged at `46aa0009ce0e038acd1830739031f502d109aab2`; merged-main
[full CI](https://github.com/jbone3311/MasterBrain/actions/runs/37097866169),
[strict runtime](https://github.com/jbone3311/MasterBrain/actions/runs/37097866193)
and [populated restore](https://github.com/jbone3311/MasterBrain/actions/runs/37097866201)
also passed. The two generated-column rewrites remain lock-heavy behind an
explicit operator override; issue #9's broader populated-upgrade risk remains
open.

## Post-PR #116 roadmap reconciliation — merged-main verification

[PR #117](https://github.com/jbone3311/MasterBrain/pull/117) changed only
documentation and identity/status metadata. Its final head
`d04c1d5f6652758b7d53546992ab380d45db52eb` passed
[full CI](https://github.com/jbone3311/MasterBrain/actions/runs/37094427920),
[strict runtime](https://github.com/jbone3311/MasterBrain/actions/runs/37094427924)
and [populated restore](https://github.com/jbone3311/MasterBrain/actions/runs/37094427916).
It merged at `394b693759624bf4f764ec6a5f8a732231c8c882`; merged-main
[full CI](https://github.com/jbone3311/MasterBrain/actions/runs/37094998793),
[strict runtime](https://github.com/jbone3311/MasterBrain/actions/runs/37094998794)
and [populated restore](https://github.com/jbone3311/MasterBrain/actions/runs/37094998763)
also passed. No new live/hosted or FileOS cutover claim follows from this
documentation merge.

## ADR-147 human FileOS v2 search review API — merged-main verification

The new human-only Brain route delegates to ADR-128's unchanged historical
reviewer. A fictional PostgreSQL chain built a ready v2 generation, compared
it with no active v1 and then with an active v1, and verified that a later v1
completion makes the API return 409 without exposing hits. The same test
checked exact source/generation binding, invalid inputs, missing targets,
scope and assistant denial, and unchanged activation count. This focused
real-PostgreSQL test passed on a fresh disposable database. On current `main`,
the pinned FOS-Master donor-policy shadow still matched **3,004 ordinary**
rows on the 3,000-file corpus; six v1-to-donor policy gaps remain explicit.
No donor edit, source effect, v2 activation or live-root acceptance occurred.
The complete Python 3.14.7 suite passed **3,014 tests with one intentional
skip** on a fresh PostgreSQL 17.11 cluster; 481 of 482 PostgreSQL-marked tests
executed. All six browser suites passed **145 tests**; Ruff, strict mypy over
98 source files, documentation links/inventory and diff checks passed. The
first full run loaded a stale installed package and returned 404 for the new
route; reinstalling this branch's package corrected the test environment, and
the complete rerun passed. An independent deployment gate on a second fresh
disposable PostgreSQL 17.11 database also passed **3,014 tests with one
intentional skip** and reported `PASS: repository quality gate`. These local
results are separate from GitHub checks. The first hosted attempts on PR #116
failed before any job step because GitHub reported an account payment or Actions
spending-limit gate; they were not test failures. After the account condition
changed, reruns on code head `5771cfc23e424cb840124f2b221bf72aaad2d05e`
passed [full CI](https://github.com/jbone3311/MasterBrain/actions/runs/37053370693),
[strict runtime](https://github.com/jbone3311/MasterBrain/actions/runs/37053370723)
and [populated restore](https://github.com/jbone3311/MasterBrain/actions/runs/37053370719).
The final documentation-only head `4003f540f1e609758318b2314e2f7def56fc89ec`
then passed [full CI](https://github.com/jbone3311/MasterBrain/actions/runs/37092189981),
[strict runtime](https://github.com/jbone3311/MasterBrain/actions/runs/37092190089)
and [populated restore](https://github.com/jbone3311/MasterBrain/actions/runs/37092189948).
[PR #116](https://github.com/jbone3311/MasterBrain/pull/116) merged at
`b6ebcbf7b5e6b12e10967c5d09d7a04970d5d982`; merged-main
[full CI](https://github.com/jbone3311/MasterBrain/actions/runs/37093077307),
[strict runtime](https://github.com/jbone3311/MasterBrain/actions/runs/37093077327)
and [populated restore](https://github.com/jbone3311/MasterBrain/actions/runs/37093077285)
also passed. The finished branch was removed. None of these checks proves
live-root parity, v2 current visibility, absence semantics or donor cutover.

## Fictional contradictory-source Ask corpus — merged-main verification

PR [#115](https://github.com/jbone3311/MasterBrain/pull/115) merged at
`e81a51cda2423c2d18702b51a8d04b90fe74901d`. Its exact-head
[full CI](https://github.com/jbone3311/MasterBrain/actions/runs/37044596370),
[strict runtime](https://github.com/jbone3311/MasterBrain/actions/runs/37044596336)
and [populated restore](https://github.com/jbone3311/MasterBrain/actions/runs/37044596459)
passed. Merged-main
[full CI](https://github.com/jbone3311/MasterBrain/actions/runs/37046381483),
[strict runtime](https://github.com/jbone3311/MasterBrain/actions/runs/37046381401)
and [populated restore](https://github.com/jbone3311/MasterBrain/actions/runs/37046381314)
also passed. The finished branch was removed.

The cross-source trial now has a Maple Arcade file and Email stating different
fictional closing dates. Both are explicitly bridged/indexed. Ask “When is
Maple Arcade closing?” returns exact source quotes for November 12 and
November 19, 2026 with independently resolvable citations and a generic
non-adjudicating answer; the provider-neutral client receives the identical
response. The trial launcher self-test exercises this conflict. On a fresh
disposable PostgreSQL 17.11 cluster, the complete cross-source suite passed
**27 tests with one Docker-only skip**. A FileOS-only assistant returned only
the file's date and could not read the Email's date. The launcher self-test
passed. The complete Python 3.14.7 suite and a separate deployment gate on a
second fresh disposable PostgreSQL 17.11 database each passed **3,014 tests
with one intentional skip**; 481 of 482 PostgreSQL-marked tests executed.
All six browser suites passed **145 tests**; Ruff, strict mypy over 98 source
files, documentation links/inventory and diff checks passed. An initial full
run launched from a `PYTHONPATH` workaround failed three clean-subprocess
imports; the locked non-editable installation made those three pass, and both
subsequent full runs passed. This is evaluation of an unresolved conflict,
not semantic conflict detection, chronology resolution or hosted/live-source
acceptance. The local results are separate from the exact-head and merged-main
checks above.

## ADR-146 reviewed KnowledgeCore in Ask — merged-main verification

PR [#114](https://github.com/jbone3311/MasterBrain/pull/114) merged at
`f93e1c875ecbb189ba33ad2d37a40b9e604ad47f`. Its exact-head
[full CI](https://github.com/jbone3311/MasterBrain/actions/runs/37038265234),
[strict runtime](https://github.com/jbone3311/MasterBrain/actions/runs/37038265817)
and [populated restore](https://github.com/jbone3311/MasterBrain/actions/runs/37038265289)
passed. Merged-main
[full CI](https://github.com/jbone3311/MasterBrain/actions/runs/37040070506),
[strict runtime](https://github.com/jbone3311/MasterBrain/actions/runs/37040070566)
and [populated restore](https://github.com/jbone3311/MasterBrain/actions/runs/37040070588)
also passed. The finished branch was removed.

The answer route now lists at most four reviewed KnowledgeCore matches in a
separate field beside exact source quotes. Each match shows at most five direct
evidence IDs and its full link count. The final current grouped search must
still contain the same assertion, displayed text and **all** direct links;
otherwise the response fails as stale. Source-scoped Knowledge search already
hides mixed-source assertions from a FileOS-only assistant. The external read
client validates the field, and `/brain` renders it as inert text with separate
evidence expansion. A knowledge-only match does not become a source quotation
or a synthesized answer.

Fictional real-PostgreSQL tests published FileOS-only, Email-only, mixed-source,
second-tenant and knowledge-only reviewed assertions. They checked owner and
enrolled-assistant visibility, exact client/API parity, missing or changed
assertions between searches, malformed hits, four-hit/five-link output bounds
and a changed link beyond the displayed five. The disposable browser trial now
seeds one reviewed cross-source commitment; Ask “readiness” returns that match
with two evidence links and no exact source quote. Its local launcher self-test
passes the same path. No live account, donor checkout or source effect was used.

The complete Python 3.14.7 suite passed **3,012 tests, one intentional skip**
on disposable PostgreSQL 17.11; 479 of 480 PostgreSQL-marked tests executed.
A separate deployment gate passed the same count on a second fresh database.
All six browser suites passed **145 tests**; Ruff, strict mypy over 98 source
files, documentation links/inventory and diff checks passed. These local results
are separate from the exact-head and merged-main checks above.

## ADR-145 question-term Ask retrieval — merged-main verification

PR [#113](https://github.com/jbone3311/MasterBrain/pull/113) merged at
`3566928c9774954343cfff5ce0dd9dc49ddb778c`. Its exact-head
[full CI](https://github.com/jbone3311/MasterBrain/actions/runs/37032095337),
[strict runtime](https://github.com/jbone3311/MasterBrain/actions/runs/37032095469)
and [populated restore](https://github.com/jbone3311/MasterBrain/actions/runs/37032095568)
passed. Merged-main
[full CI](https://github.com/jbone3311/MasterBrain/actions/runs/37033792674),
[strict runtime](https://github.com/jbone3311/MasterBrain/actions/runs/37033792690)
and [populated restore](https://github.com/jbone3311/MasterBrain/actions/runs/37033792675)
also passed. The finished branch was removed.

The extractive answer route now removes only a fixed list of question filler
words before its first and final current-source searches. It still sends the
original question to the local selector, enforces all four read scopes,
selects exact authorized quotes and rechecks current visibility. The literal
Search only route is unchanged. On the fictional PostgreSQL corpus, literal
search for “Find the insurance certificate for Cedar Harbor” returned no
Email/FileOS hits, whereas Ask returned both source kinds with verified quotes;
the external read client received the identical answer. Fixed-term, empty and
contraction cases passed unit tests. No synonym or semantic inference is
claimed.

The complete final-tree Python 3.14.7 suite passed **3,005 tests, one
intentional skip** against a fresh disposable PostgreSQL 17.11 database; 478
of 479 PostgreSQL-marked tests executed. A separate deployment gate passed
the same count on a second fresh disposable database. All six browser suites
passed **143 tests** after their credential-clear test caught and removed a
fictional project name from static empty-state copy. Ruff, strict mypy over
98 source files and documentation inventory/link checks passed. These local
results are separate from the exact-head and merged-main checks above. No real
account, hosted model, source effect or FOS-Master checkout was involved.

## ADR-144 default local source quotes — merged-main verification

PR [#112](https://github.com/jbone3311/MasterBrain/pull/112) merged at
`66ed3c99c2f44ca3b91602807b7dec16f7f97089`. Its exact-head
[full CI](https://github.com/jbone3311/MasterBrain/actions/runs/37026010900),
[strict runtime](https://github.com/jbone3311/MasterBrain/actions/runs/37026010284)
and [populated restore](https://github.com/jbone3311/MasterBrain/actions/runs/37026010324)
passed. The merged-main
[full CI](https://github.com/jbone3311/MasterBrain/actions/runs/37027838793),
[strict runtime](https://github.com/jbone3311/MasterBrain/actions/runs/37027838806)
and [populated restore](https://github.com/jbone3311/MasterBrain/actions/runs/37027838702)
also passed. The default read-only Ask path selects bounded, locally ranked
exact Email/FileOS source quotes, with server-verified citations and an
explicit no-selector rollback. It is not freeform synthesis or live/hosted
acceptance; issue #92 remains open.

## ADR-143 source-scoped Knowledge reads — local verification

Forward migration 0051 admits `knowledge.read` and
`knowledge.changes.read` to administrator-bound OIDC assistants while keeping
the old exact-key resolver closed to Brain/Knowledge assistants. The API now
admits enrolled assistants to direct Knowledge search, assertion expansion,
Knowledge changes and unified Brain search. Fictional PostgreSQL tests used
nonempty Email and FileOS evidence in one tenant plus an independent second
tenant with the same FileOS source ID. File-only, Email-only and mixed-source
assertions tested all-direct-evidence filtering before a `LIMIT 1` result;
hidden/unknown assertion and change cursor reads return not found. Knowledge-
only OIDC credentials require enrollment, and grant removal invalidates saved
contexts. No source effect, real account, remote model or FOS-Master change was
involved.

The first complete local run exposed exact migration-list expectations in
upgrade/protected-record tests that omitted the new forward migration. Those
expectations were updated; the exact affected files passed, then the **whole
final-tree Python 3.14.7 suite passed 2,998 tests with one Docker-only skip**
on disposable PostgreSQL 17.11. A separate deployment gate passed the same
count on a fresh second database; 477 of 478 PostgreSQL-marked tests executed.
Six required Node suites passed **143 tests**. Locked non-editable package
rebuild, Ruff, strict mypy over 98 source files, documentation links and diff
checks passed. Exact-head GitHub CI and merged-main checks are separate gates;
this local receipt does not close hosted issue #88 or establish semantic
information-flow safety of reviewer-written assertion text.

## ADR-142 source-scoped Brain read expansion — local verification

Enrolled synthetic-bootstrap and administrator-bound OIDC assistants now use
the existing retained DataCore search, aggregate current Email/FileOS searches
and exact-source FileOS status, preview, index and active search routes.
PostgreSQL integration tests exercised one tenant with nonempty Email and
FileOS sources plus another tenant, hidden/unknown source IDs, source-filtered
`LIMIT 1` results, a cross-tenant canary and OIDC grant revocation. Direct
Knowledge/unified and legacy Email assistant routes remain denied.

On local Python 3.14.7 with disposable PostgreSQL 17.11, the final-tree full
suite passed **2,996 tests, one Docker-only skip**; 475 of 476
PostgreSQL-marked tests executed. A separate deployment gate passed the same
count on a fresh second test database. All six required Node suites passed
**143 tests**. Locked non-editable package rebuild, Ruff, strict mypy over
98 source files, documentation links and diff checks passed. No real account,
hosted issuer, source effect or FOS-Master checkout was contacted. This local
receipt is not exact-head GitHub CI or merged-main evidence, and does not
close issue #88.

## ADR-141 legacy Email worker login — local verification

The opt-in `--tenant-bound-db` mode covers `email-brain sync-read`,
`process-jobs` and `process-documents` in both check and execution. All six
CLI flag/default cases and the three controllers' strict-boolean, encrypted
store and read-worker reopen unit cases passed. Six real PostgreSQL 17.11
tests used two fictional tenants with DBA-bound non-owner logins: every
preflight accepted the authenticated worker's login and refused shared,
wrong-tenant and owner logins before provider, job or Docker work. Bounded
fictional Fastmail, MIME and PDF execution passed through the bound login;
credential revocation, forged-GUC foreign read/write denial, replay and
unchanged original PDF evidence were checked. No real provider or source was
contacted, and FOS-Master was not changed.

An initial complete run exposed one existing encrypted-read integration test
that called the private `_store` helper without the new option. Its false
default was restored and the exact failing test passed on a fresh database.
After rebuilding the installed package with the final code, the **whole**
Python 3.14.7 suite and separate deployment gate each passed **2,996 tests,
one Docker-only skip** against distinct disposable PostgreSQL clusters;
475 of 476 PostgreSQL-marked tests executed. The six required Node browser
suites passed **143 tests**. Locked dependency sync, Ruff, strict mypy over
98 source files, documentation links and diff checks passed. This is local,
synthetic evidence, not hosted credential lifecycle, operational restore or
issue #7 closure. Exact-head and merged-main hosted results belong to their
GitHub checks, not this local receipt.

## ADR-140 fictional Mac trial launcher — local verification

On this Mac, a fresh editable `uv sync` left its generated `.pth` file with the
macOS hidden flag. Python 3.14 skipped the file and the one-click trial failed
to import `email_brain.api`. A separate restricted-sandbox run could not start
PostgreSQL because shared memory was denied. The corrected launcher uses a
locked non-editable install followed by `uv run --no-sync`; its actual
`--backend local --self-test` passed outside the restricted sandbox on
PostgreSQL 17.11, returning two fictional Email hits, two FileOS hits and cited
content. No real source was read or changed. The focused launcher contract
test, Ruff, strict mypy over 98 source files, all 143 required Node browser
tests, documentation and diff checks passed. The full local suite on a fresh
disposable PostgreSQL 17.11 cluster passed **2,978 tests, one Docker-only
skip**, with 469 of 470 PostgreSQL-marked tests executed. The separate
deployment gate passed the same count against another fresh disposable
PostgreSQL cluster. Hosted exact-head and merged-main results must be recorded
separately. FOS-Master is unchanged.

## ADR-139 private derivative worker login — merged verification

PR [#107](https://github.com/jbone3311/MasterBrain/pull/107) merged from
`a99aa2294ff7ba2a65f4287afb112227591a25bf` into `main` at
`eb3dbf0924ce094561b283920089044645940442`. Its exact head passed
[full CI](https://github.com/jbone3311/MasterBrain/actions/runs/36998536832),
[strict runtime](https://github.com/jbone3311/MasterBrain/actions/runs/36998536984)
and [populated restore](https://github.com/jbone3311/MasterBrain/actions/runs/36998536788).
The exact merge commit passed
[full CI](https://github.com/jbone3311/MasterBrain/actions/runs/36999682611),
[strict runtime](https://github.com/jbone3311/MasterBrain/actions/runs/36999682706)
and [populated restore](https://github.com/jbone3311/MasterBrain/actions/runs/36999682591).
The feature branch was deleted after merge. Issue #7 remains open for legacy
workers, credential operations and hosted multi-tenant acceptance.

## ADR-139 private derivative worker login — local verification

The opt-in `--tenant-bound-db` option covers every database-backed private
`masterbrain` Email bridge and FileOS archive derivative command, including
previews and sealed batches. Unit dispatch tests cover all 14 command forms.
Real PostgreSQL 17.11 two-tenant tests prove own-login preflight for every
form, shared/wrong/owner-login refusal, bound Email and archive publication,
batch execution and replay, forged-GUC foreign read/write denial, worker
revocation and unchanged originals. The prior FileOS publish/index paths use
the same shared DataCore worker-store helper and retain their regressions.
The final-tree Python 3.14.7 suite and separate deployment gate each passed
**2,978 tests, one Docker-only skip** against distinct disposable databases;
469 of 470 PostgreSQL-marked tests executed. The six required Node browser
suites passed **143 tests**. Locked dependency sync, Ruff, strict mypy over
98 source files, documentation and diff checks passed. This is local/synthetic
evidence, not hosted acceptance, legacy-worker routing or issue #7 closure.
FOS-Master was not changed.

PR [#106](https://github.com/jbone3311/MasterBrain/pull/106) merged its
documentation receipt at `b1f3b058f34813db3d7a49547228ecc451f03691`.
That merge commit passed [full CI](https://github.com/jbone3311/MasterBrain/actions/runs/36995421597),
[strict runtime](https://github.com/jbone3311/MasterBrain/actions/runs/36995421571)
and [populated restore](https://github.com/jbone3311/MasterBrain/actions/runs/36995421564).

PR [#104](https://github.com/jbone3311/MasterBrain/pull/104) merged at
`62e55c0a12c9a3d3274feb7974878e9d2699a37c`. Its merged-main
[CI](https://github.com/jbone3311/MasterBrain/actions/runs/36989827326),
[strict runtime](https://github.com/jbone3311/MasterBrain/actions/runs/36989827321)
and [populated restore](https://github.com/jbone3311/MasterBrain/actions/runs/36989827316)
all passed. The tagged `v0.2.0a1` checkpoint remains separate from this
later merged-main state.

## ADR-138 tenant-bound FileOS indexing — merged verification

PR [#105](https://github.com/jbone3311/MasterBrain/pull/105) merged from
`b375e1ec583a5831495f7e931bcf81d3f08e6f1c` into `main` at
`7fd659dfbcb38d01dc176db3b3f6b80887fe4a4b`. The exact head passed
[full CI](https://github.com/jbone3311/MasterBrain/actions/runs/36992155627),
[strict runtime](https://github.com/jbone3311/MasterBrain/actions/runs/36992155638)
and [populated restore](https://github.com/jbone3311/MasterBrain/actions/runs/36992155648).

The opt-in private index/rollback operator now binds its runtime PostgreSQL
login to the authenticated worker's exact tenant. A real disposable PostgreSQL
17.11 two-tenant regression passed bound publication, index build/activation,
idempotent replay, second generation and activation-only rollback. It refused
shared, wrong-tenant and owner logins in check mode for both index modes;
forged tenant GUCs on the bound login could not read/write the other tenant.
The source file remained unchanged and revoked worker credentials were refused.
The final-tree full Python 3.14.7 suite passed **2,960 tests, one Docker-only skip**
against a disposable database; 467 of 468 PostgreSQL-marked tests executed.
The separate final-tree local deployment gate passed the same count against another
disposable database. The six required Node browser suites passed **143 tests**;
Ruff, strict mypy over 97 source files, documentation and diff checks passed.
Local verification alone was not used to authorize the merge. FOS-Master was
not changed. This is not hosted acceptance or issue #7 closure.

## ADR-137 Mac trial interpreter correction — local verification

The normal `Start-MasterBrain-Trial.command` initially failed before opening a
browser: its broad `--python 3.12` request selected installed Python 3.12.4,
which the strict sender runtime correctly excludes. The corrected command
selected installed Python 3.14.7 and passed its own `--backend local --self-test`
against a new Homebrew PostgreSQL 17.11 cluster: two fictional Email and two
FileOS search hits, with citation reads. A normal browser-mode launch started
the loopback server and shut it down cleanly. The Mac was locked, so no visual
browser interaction or owner acceptance is claimed. The full Python 3.14.7
suite passed **2,957 tests, one Docker-only skip** against a separate disposable
PostgreSQL 17.11 cluster; 466 of 467 PostgreSQL-marked tests executed. All 147
Node browser tests, Ruff, strict mypy over 97 source files, documentation links
and diff checks passed. An initial suite had three local isolated-subprocess
import failures immediately after `uv` rebuilt `.venv`; reinstalling the local
editable package and rerunning the *whole* suite cleared all three. The
separate local deployment gate passed **2,957 tests, one skipped** against a
fresh disposable cluster. Exact-head hosted results belong to the PR checks;
they are not inferred from this local run. FOS-Master was untouched.

## ADR-137 disposable local PostgreSQL trial — merged verification

PR [#102](https://github.com/jbone3311/MasterBrain/pull/102) merged at
`5a3ff6b1e63dc8fbde9301e97f6f9ca90af55be8` from exact head
`ec047e4228de46ec057a3a53e658576edcee12a0`. The head passed
[CI](https://github.com/jbone3311/MasterBrain/actions/runs/36983583087),
[strict sender runtime](https://github.com/jbone3311/MasterBrain/actions/runs/36983582950)
and [populated restore](https://github.com/jbone3311/MasterBrain/actions/runs/36983582933).
Hosted CI included the Docker-backed actual launcher test; the owner's
independent browser walkthrough remains open.

The actual `--backend local --self-test` launcher passed on this Mac with
Homebrew PostgreSQL 17.11: it created a new temporary cluster, seeded two
fictional Email and two FileOS hits, read citations through the Brain API,
then stopped and removed the cluster. Focused launcher/cleanup tests passed
**5 of 5**. The full local suite passed **2,956 tests, one Docker-only skip**
against a separate disposable PostgreSQL 17.11 cluster; 466 of 467
PostgreSQL-marked tests executed. All 147 Node browser tests, Ruff, strict
mypy over 97 source files and documentation links passed. The first full
attempt had three isolated-subprocess import failures after `uv sync`; repairing
the local editable package install and rerunning the entire suite cleared all
three. The separate local deployment gate passed **2,956 tests, one skipped**
against another disposable cluster. No existing database or source was used;
FOS-Master was unchanged.

## ADR-136 plain-text excerpts and fictional browser trial — merged verification

PR [#101](https://github.com/jbone3311/MasterBrain/pull/101) merged at
`a59a1148b072b1f47101cb37fdb0162a52b3b234`. Its exact head and merged
`main` passed CI, strict sender runtime and populated restore.

An agent-run local browser pass against disposable PostgreSQL 17.11 reproduced
raw `<b>` marker text in Email/FileOS result cards on the trial page and `/brain`.
The branch removes generated markers at the shared DataCore/KnowledgeCore SQL
read boundary. Focused PostgreSQL tests passed **7 of 7 executed**; the browser
then showed two Email and two FileOS Cedar Harbor results, one of each for
insurance, zero for a nonexistent query, and readable bounded FileOS source
text with expandable provenance. The trial now verifies the returned evidence
identity before displaying that text; its browser regression denies a mismatch.
The assistant exercised the in-app browser on fictional data, not the owner's
independent walkthrough or the standard Docker launcher (Docker Desktop is
not installed in this workspace). The full local suite passed **2,954 tests,
one skipped** on PostgreSQL 17.11; 466 of 467 PostgreSQL-marked tests executed.
All 147 browser tests, Ruff, strict mypy over 97 source files, documentation
links and diff checks passed. The local deployment gate repeated the full
PostgreSQL suite and passed **2,954 tests, one skipped**. Hosted exact-head,
strict-runtime and populated-restore checks passed.
No live source, model answer, effect or FOS-Master change is claimed.

## ADR-135 tenant-bound FileOS publisher — merged verification

PR [#100](https://github.com/jbone3311/MasterBrain/pull/100) merged at
`728ac3b0953e696b3563707a05e5f200d587384a` from exact head
`aed3dd2cab082b40b2708f11b2f29a067173a9da`. The head passed
[CI](https://github.com/jbone3311/MasterBrain/actions/runs/36974960962),
[strict runtime](https://github.com/jbone3311/MasterBrain/actions/runs/36974961066)
and [populated restore](https://github.com/jbone3311/MasterBrain/actions/runs/36974960988).
The merge commit passed
[CI](https://github.com/jbone3311/MasterBrain/actions/runs/36975899153),
[strict runtime](https://github.com/jbone3311/MasterBrain/actions/runs/36975899154)
and [populated restore](https://github.com/jbone3311/MasterBrain/actions/runs/36975899184).

One private publisher now has an explicit single-tenant database-login mode.
The authenticated worker tenant, not the manifest or request, selects the
database fence. A real disposable PostgreSQL test proves check, publication,
replay, wrong/shared/owner-login refusal and cross-tenant read/write denial
after a forged tenant GUC.
The local full suite passed **2,954 tests, one skipped** on PostgreSQL 17.11:
466 of 467 PostgreSQL-marked tests executed. All 146 browser tests, Ruff,
strict mypy over 97 source files, documentation links and diff checks passed.
Other workers and hosted credential operations remain issue #7; FOS-Master is
unchanged. The merged feature branch and its disposable local test database
were removed.

## ADR-134 grounded extractive answers — merged verification

PR [#98](https://github.com/jbone3311/MasterBrain/pull/98) merged at
`3f5ee3b16b2494accda6e35d505bde51e4bc3d7c` from exact head
`e93f38e631c713d3b9e384f1450dc08a77d984db`. The head passed
[CI](https://github.com/jbone3311/MasterBrain/actions/runs/36968373504),
[strict runtime](https://github.com/jbone3311/MasterBrain/actions/runs/36968373492)
and [populated restore](https://github.com/jbone3311/MasterBrain/actions/runs/36968373501).
The merge commit's [full CI](https://github.com/jbone3311/MasterBrain/actions/runs/36969615525),
[strict runtime](https://github.com/jbone3311/MasterBrain/actions/runs/36969615531)
and [populated restore](https://github.com/jbone3311/MasterBrain/actions/runs/36969615529)
all passed on the exact merge commit. Both CI gates ran the full PostgreSQL
suite directly and through the deployment gate, then the isolated container
checks. The reference client and browser tests are part of that CI gate.

This increment adds a provider-neutral selector contract, bounded server-verified
exact quotes, read-client parity surface and a first-party quote display with a
search fallback when no selector is configured. It has no enabled real model,
new migration, source effects or FOS-Master changes. A full local run against
disposable PostgreSQL 17.11 passed **2,950 tests, one skipped**; 465 of 466
PostgreSQL-marked tests executed. All 146 browser tests, Ruff, strict mypy over
97 source files, documentation links and diff checks passed. The focused real
PostgreSQL test compared the assistant's exact answer with the external client,
confirmed source-only citations and denied a missing content grant. Local
Python 3.11.13 skipped the hidden editable-install `.pth` file after `uv sync`;
the two CLI subprocess tests passed after installing the same source as a regular
wheel. This was a local environment issue, not a product-code change. No
hosted or live-source acceptance is claimed.

The documentation-only PR [#97](https://github.com/jbone3311/MasterBrain/pull/97)
merged into `main` at `680350593bfee4a8fb78a50b8a0168551f08060f`;
[merged-main CI](https://github.com/jbone3311/MasterBrain/actions/runs/36966064373),
[strict runtime](https://github.com/jbone3311/MasterBrain/actions/runs/36966064505)
and [populated restore](https://github.com/jbone3311/MasterBrain/actions/runs/36966064408)
all passed. This is a documentation receipt, not a product release.

## API-SOURCE-003 source-scoped status — merged verification

PR [#96](https://github.com/jbone3311/MasterBrain/pull/96) merged at
`9c07f00445307ad99fef33a02546564ba9ca0945` from exact head
`fe03439b253d3a2a1806770f4313c327d4b671e5`. The head passed
[CI](https://github.com/jbone3311/MasterBrain/actions/runs/36962808900),
[strict runtime](https://github.com/jbone3311/MasterBrain/actions/runs/36962808873)
and [populated restore](https://github.com/jbone3311/MasterBrain/actions/runs/36962808967).
The merge commit passed
[CI](https://github.com/jbone3311/MasterBrain/actions/runs/36963721901),
[strict runtime](https://github.com/jbone3311/MasterBrain/actions/runs/36963721904)
and [populated restore](https://github.com/jbone3311/MasterBrain/actions/runs/36963721936).
Both CI gates ran the complete PostgreSQL suite directly and again through
the deployment gate, followed by isolated container checks.

ADR-133 and forward migration 0050 extend enrolled assistant access to
`GET /v1/brain/current-coverage` and `GET /v1/brain/changes`. Both apply the
source allowlist before paging and reject hidden-source cursors. The
administrator-owned OIDC binding may now carry `brain.changes.read`; even a
status-only assistant requires a same-tenant source grant, while the legacy
resolver refuses it during rolling upgrades. The provider-neutral reference
client exposes both bounded calls. The remaining Brain/Knowledge routes,
hosted identity, source effects and FOS-Master are unchanged.

On a fresh disposable PostgreSQL 17.11 database, the affected client/OIDC/
cross-source suites passed **46 tests, one skipped**. An initial full run
exposed migration-history fixtures that had not yet listed migration 0050;
these produced 12 setup errors and three recovery failures. After updating
those explicit histories, the focused migration/recovery suite passed
**32 tests**, and the full suite passed **2,929 tests, one skipped** in
156.50 seconds, including 464 of 465 PostgreSQL-marked tests. Ruff, strict
mypy over 96 source files, documentation links and diff checks passed before
the final test-only correction; a targeted status-only assistant regression
passed afterward. The merged-main restore verified 85 tables, 270 rows, two
tenants, four external objects, two identity bindings, matching content hashes,
RLS, identity revocation and refusal of database-only restore. This is
synthetic-only evidence, not hosted or named-assistant acceptance.

## API-SOURCE-002 OIDC Brain grants — merged verification

PR [#91](https://github.com/jbone3311/MasterBrain/pull/91) merged at
`89a4351e35bc83d6bad19fe4a5f0cf9b80d5b11f` from exact head
`9e4b63a69cc3bc7a37a70332defb168e331873be`. The head passed
[CI](https://github.com/jbone3311/MasterBrain/actions/runs/36958088397),
[strict runtime](https://github.com/jbone3311/MasterBrain/actions/runs/36958088367)
and [populated restore](https://github.com/jbone3311/MasterBrain/actions/runs/36958088395).
The merge commit passed the corresponding
[CI](https://github.com/jbone3311/MasterBrain/actions/runs/36958959477),
[strict runtime](https://github.com/jbone3311/MasterBrain/actions/runs/36958959460)
and [populated restore](https://github.com/jbone3311/MasterBrain/actions/runs/36958959449).
Both CI gates ran the full PostgreSQL suite directly and again through the
deployment gate on an accumulated synthetic database. This is not hosted or
named-assistant acceptance; issue #88 remains open.

ADR-132 and forward migration 0049 add administrator-owned, same-tenant source
grants to exact verified OIDC Brain assistant bindings. The source-aware resolver
returns only enrolled IDs; the prior resolver refuses Brain-scoped assistants
during rolling upgrades. Grant changes increment binding revision, emit
content-free audit records and invalidate previously saved contexts on their
next transaction. Existing Email-only OIDC bindings remain compatible. Only
the three ADR-130 source-aware Brain read routes admit these assistants;
hosted issuer enrollment, named-assistant certification, all-route and
derived-cache revocation remain open under issue #88.

After rebasing on merged FileOS readiness migration 0048, a fresh disposable
PostgreSQL 17.11 database passed the focused OIDC/migration/recovery suite:
**73 passed**. The first full suite passed **2,928 tests, one skipped** in
163.83 seconds. After the legacy-resolver fail-closed correction, a second
fresh database passed the same focused **73 tests** and full **2,928 tests,
one skipped** in 126.87 seconds, including 463 of 464 PostgreSQL-marked tests.
Ruff, strict mypy over 96 source files, 140 browser tests, documentation and
diff checks passed before that final SQL-only correction; targeted and full
PostgreSQL gates were repeated afterward. The local deployment gate passed
2,465 non-PostgreSQL tests, skipping 464 database-marked tests by design.
Pinned FOS-Master DataCore parity passed at 3,000 synthetic files; the donor
classifier matched 3,004 paths. FOS-Master was not changed. Docker is not
available on the local host; GitHub's populated restore drill verified 85
tables, 269 rows, two tenants, four external objects and two identity bindings
with matching content hashes, RLS, identity revocation and refusal of a
database-only restore. This remains synthetic-only, not a production RTO or
live-issuer proof.

## DC-002U readiness scaling correction — merged verification

PR [#90](https://github.com/jbone3311/MasterBrain/pull/90) merged at
`056f1b78e706e8e46d48a554f11ab67be788913f` from exact head
`e3b50f547c00bb8e894d618afece8eca04d46884`. The head passed
[CI](https://github.com/jbone3311/MasterBrain/actions/runs/36955928457),
[strict runtime](https://github.com/jbone3311/MasterBrain/actions/runs/36955928432)
and [populated restore](https://github.com/jbone3311/MasterBrain/actions/runs/36955928455).
The merge commit passed the corresponding
[CI](https://github.com/jbone3311/MasterBrain/actions/runs/36956934219),
[strict runtime](https://github.com/jbone3311/MasterBrain/actions/runs/36956934230)
and [populated restore](https://github.com/jbone3311/MasterBrain/actions/runs/36956934207).
Issue [#84](https://github.com/jbone3311/MasterBrain/issues/84) is closed for
the synthetic 3,000-row readiness timeout, not for live-source or cutover acceptance.

ADR-131 replaces only the FileOS v2 readiness chunk comparison and reverse
base count with indexed lookups in forward migration 0048. Exact ID, document,
ordinal, offsets, text and SHA-256 comparison remains mandatory; the five-second
statement limit and SQL refusal of v2 activation are unchanged. No donor or
current-read path was edited. The first `EXCEPT ALL` candidate and a later
half-indexed candidate each timed out in the populated full suite; neither was
committed. This records the failed experiments, not only the successful run.

On a fresh disposable PostgreSQL 17.11 database, the revised full suite passed
**2,924 tests, one skipped** in 119.39 seconds, including 459 of 460 database-
marked tests. The 3,000-hashed-row case then passed again on that populated
database in 70.44 and 83.89 seconds. Runtime-role `EXPLAIN (ANALYZE, BUFFERS)` on a
committed synthetic generation showed indexed chunk lookup and per-document
count at about 25 and 28 ms respectively; committed-plan timing alone is not
the acceptance basis. Ruff, strict mypy over 96 source files, 140 browser
tests, documentation inventory and diff checks passed. The pinned FOS-Master
3,000-file DataCore comparison passed, and donor-policy shadow matched 3,004
synthetic paths with no classifier mismatch. The local deployment gate passed
2,465 non-PostgreSQL tests and skipped 460 PostgreSQL-marked tests by design.
Both exact-head and merged-main CI reran the full PostgreSQL suite in the
deployment gate; every reported check passed. FOS-Master remained unchanged.

## API-SOURCE-001 synthetic assistant source-scoped reads — local verification

ADR-130 limits bootstrap assistant credentials to explicit, bounded source IDs
for the three read-only Brain client routes. Current Email, FileOS and archive
searches filter at SQL before ranking and limits; reviewed Knowledge search
excludes mixed-source assertions. Evidence metadata and bounded text require
the same source grant. Other Brain/Knowledge routes fail closed to assistants;
human routes are unchanged. This is not hosted OIDC enrollment, dynamic grant
revocation, a named assistant or source-effect authority. The broader gap is
tracked in [issue #88](https://github.com/jbone3311/MasterBrain/issues/88).

On a fresh disposable PostgreSQL 17.11 database, the corrected full suite
passed **2,924 tests, one skipped** in 161.81 seconds, including 459 of 460
PostgreSQL-marked tests. The final added same-tenant FileOS limit assertion
and focused source-grant tests passed separately (four tests). The local
deployment gate passed 2,465 non-PostgreSQL tests, skipping 460 database-marked
tests by design. Ruff, strict mypy over 96 source files, 140 browser tests,
documentation and diff checks passed. Pinned FOS-Master 3,000-file DataCore
parity passed; donor-policy shadow matched 3,004 candidate rows with zero
unexplained membership differences and six explicit policy gaps. FOS-Master
was not changed. GitHub exact-head and merged-main checks are not yet claimed.

The first full run had three credential/test-fixture compatibility failures,
now corrected, plus the intermittent existing v2 readiness anti-join timeout
from [issue #84](https://github.com/jbone3311/MasterBrain/issues/84).
The server log identified `enforce_index_generation_ready()`'s unmatched
generation/base-chunk join; an immediate 3,000-row rerun on the retained
synthetic database passed in 64.44 seconds. The second fresh full run passed,
but this is not proof that issue #84 is resolved; its finding is recorded on
the issue. No statement budget was raised and no v2 activation was enabled.

## API-CLIENT-001 provider-neutral read-only client — merged verification

PR [#86](https://github.com/jbone3311/MasterBrain/pull/86) merged at
`3510f8ccda8972bce3221a12fb7ba74fdd546e86` from exact head
`c8ef014d2b8bbae1647b0d18ab24e3d65087d20a`. The head passed the
[CI gate](https://github.com/jbone3311/MasterBrain/actions/runs/36940701978),
[strict runtime matrix](https://github.com/jbone3311/MasterBrain/actions/runs/36940702049)
and [populated restore](https://github.com/jbone3311/MasterBrain/actions/runs/36940701991).
The merge commit also passed the
[CI gate](https://github.com/jbone3311/MasterBrain/actions/runs/36941594096),
[strict runtime matrix](https://github.com/jbone3311/MasterBrain/actions/runs/36941594090)
and [populated restore](https://github.com/jbone3311/MasterBrain/actions/runs/36941594072).

ADR-129 adds a deliberately narrow Python client for the existing Brain API:
grouped current search, selected evidence metadata, and separately authorized
bounded evidence content. The client requires an explicit bearer credential,
rejects insecure non-loopback origins, redirects, cookies, ambient proxies,
malformed responses and oversized responses. A fictional Email/FileOS corpus
proves that direct API calls and client calls return the same grouped evidence;
the separate search and evidence grants remain enforced. This is neither a
deployed Grok, Claude or ChatGPT adapter nor a hosted service, answer generator
or source-action channel.

On fresh disposable PostgreSQL 17.11 databases, the complete suite passed
**2,921 tests, one skipped** in 188.11 seconds, including 457 of 458
PostgreSQL-marked tests. Following a final response-validation change, the
focused client/cross-source suite passed 39 tests, one skipped, including nine
PostgreSQL cases. The deployment gate passed 2,464 non-PostgreSQL tests and
skipped 458 database-marked cases by design. Ruff, strict mypy over 96 source
files, 140 browser tests, documentation and diff checks passed. The pinned
FOS-Master 3,000-file DataCore comparison passed; donor-policy shadow matched
3,004 candidate rows with zero unexplained membership differences and six
explicit transition-policy gaps. No FOS-Master change, live-source acceptance,
hosted deployment or version tag is claimed. The disposable synthetic test
cluster was stopped and removed after validation.

## DC-002V private FileOS v2 search comparison — merged verification

PR [#85](https://github.com/jbone3311/MasterBrain/pull/85) merged at
`b1642def42ebf90a453093bbeb161f5086219847` from exact head
`c0b686cdbe38cb8714dc0aacdf123ed69f1793eb`. The head passed the
[CI gate](https://github.com/jbone3311/MasterBrain/actions/runs/36936295355),
[strict runtime matrix](https://github.com/jbone3311/MasterBrain/actions/runs/36936295199)
and [populated restore](https://github.com/jbone3311/MasterBrain/actions/runs/36936295162).
The merge commit also passed the
[CI gate](https://github.com/jbone3311/MasterBrain/actions/runs/36937616366),
[strict runtime matrix](https://github.com/jbone3311/MasterBrain/actions/runs/36937616260)
and [populated restore](https://github.com/jbone3311/MasterBrain/actions/runs/36937616187).

ADR-128 adds a human-only, scoped comparison of one named ready historical v2
generation with the same source's active v1 generation. Both use one bounded
lexical query; results and ranks remain separate, and v2 is labeled
`historical_preview`. The comparison checks the latest exact v1 baseline and
root under the FileOS source lock. It adds no public API route, v2 activation,
absence authority, source effect or FOS-Master change.

On a fresh disposable PostgreSQL 17.11 database, the complete suite passed
**2,897 tests, one skipped** in 297.21 seconds, including 456 of 457
PostgreSQL-marked tests. A clean 3,000-hashed-row v2 build and bounded search
passed separately in 87.35 seconds. After the full-suite collection, the
additional active-v1-versus-historical-v2 assertion passed separately on a
fresh database. The deployment gate passed 2,441 non-PostgreSQL tests and
skipped 457 database-marked cases by design. Ruff, strict mypy over 95 source
files, 140 browser tests, documentation and diff checks passed. The pinned
FOS-Master 3,000-file DataCore parity passed; the donor-policy shadow matched
3,004 candidate rows with zero unexplained membership differences and six
explicit transition-policy gaps.

Repeated 3,000-row runs retained across several tenants in one disposable
database exposed a five-second timeout in the existing v2 readiness closure
query. A fresh run and the full fresh-suite run passed; the populated-database
scaling investigation is tracked as
[#84](https://github.com/jbone3311/MasterBrain/issues/84). The first preview
query also timed out under that load; it now ranks and limits matching chunks
before joining evidence, without raising the statement budget. A later
repeat-load audit ran four retained 3,000-row tenant cases without failure,
though slower, and measured the reported joins at roughly 20 ms each under a
disposable forced-RLS login. The intermittent trigger-level cause remains
unproven; [issue #84](https://github.com/jbone3311/MasterBrain/issues/84)
stays open. No version tag is assigned; this is not v2 current visibility,
live-root acceptance or donor cutover.

## UI-001 first-party read-only question workspace — merged verification

PR [#83](https://github.com/jbone3311/MasterBrain/pull/83) merged at
`3a1b5277ae7351309384fe609c6faf05a9b680a9` from exact head
`e1dcc3a40fad94e0206d1758c508d2053ab78601`. The head passed the
[CI gate](https://github.com/jbone3311/MasterBrain/actions/runs/36932341977),
[strict runtime matrix](https://github.com/jbone3311/MasterBrain/actions/runs/36932341964)
and [populated restore](https://github.com/jbone3311/MasterBrain/actions/runs/36932341942).
The merge commit also passed the
[CI gate](https://github.com/jbone3311/MasterBrain/actions/runs/36933702507),
[strict runtime matrix](https://github.com/jbone3311/MasterBrain/actions/runs/36933702470)
and [populated restore](https://github.com/jbone3311/MasterBrain/actions/runs/36933702396).

ADR-127 adds `/brain` and packaged static assets. The page calls only existing
scoped current-search and evidence routes; it keeps its bearer credential and
at most eight question/result pairs in browser memory, shows partial coverage,
and does not synthesize answers or offer source actions. Six browser-contract
tests cover no unauthenticated request, grouped hostile-text rendering, scoped
evidence/content denial, stale-response invalidation and malformed results.
The API static-route suite passed 33 tests; the complete suite passed
**2,897 tests, one skipped** in 233.05 seconds on a fresh disposable local
PostgreSQL 17.11 cluster, with 456 of 457 PostgreSQL-marked tests executed.
The local deployment gate separately passed 2,441 non-PostgreSQL tests and
skipped 457 PostgreSQL-marked cases by design. Ruff, strict mypy over 95
source files, 140 browser tests (including the six new workspace cases),
Node syntax, documentation and diff checks passed. An offline wheel build
included all three new workspace assets. The temporary cluster was stopped
and removed after the run. Hosted CI includes the restricted packaged-image,
strict runtime and populated-restore checks cited above. This is
not a hosted chat or a model-generated answer; no version tag is assigned.

## DC-002U FileOS v2 shared generation — merged verification

PR [#81](https://github.com/jbone3311/MasterBrain/pull/81) merged at
`aad195d953eb45a2d844ed9d8d5dc82181fdb985` from base
`a0b21a6fd8f9e74e736c723a0da39820210cf6aa`. Its exact head
`07b0654181c41508ea0ad64629cdac1ab8f928a9` passed the
[CI gate](https://github.com/jbone3311/MasterBrain/actions/runs/36926230869),
[strict runtime matrix](https://github.com/jbone3311/MasterBrain/actions/runs/36926230854)
and [populated restore](https://github.com/jbone3311/MasterBrain/actions/runs/36926230842).
The merge commit also passed the
[CI gate](https://github.com/jbone3311/MasterBrain/actions/runs/36927725340),
[strict runtime matrix](https://github.com/jbone3311/MasterBrain/actions/runs/36927725319)
and [populated restore](https://github.com/jbone3311/MasterBrain/actions/runs/36927725309).

ADR-126, migration 0047 and `FileOSV2IndexBuilder` extend the existing
DataCore generation tables with an exact v2 completion/ready-attempt basis.
One generation item is bound to each hashed attempt item, and readiness
checks exact document and base-chunk closure. A PostgreSQL trigger rejects
all v2 activation, including direct SQL; v1 current search, absence and
FOS-Master remain unchanged. A different code revision produces a distinct
immutable generation rather than replacing prior history.

On a fresh disposable local PostgreSQL 17.11 database, the full suite passed
**2,894 tests, one skipped** in 203.78 seconds, with 456 of 457
PostgreSQL-marked tests executed. The end-to-end 3,000-hashed-row publication
and generation stress case passed separately in 106.03 seconds and again in the
full suite. Early stress attempts exposed five-second statement timeouts in
the v2 readiness anti-join, exact membership join, the earlier publication
ledger read, and a large item/document join in the builder. The final
candidate uses exact set-based ledger comparison, separate indexed
source/preparation reads and bounded document batches; the database statement
budget was not raised. Focused tests cover zero-hash readiness, same-plan replay,
distinct-revision history, concurrent build, forged/missing/chunk rows,
late-child refusal, wrong tenant/scope/client, stale v1 baseline and no
current-read effect. Locked dependency sync, Ruff, strict mypy over 95 source
files, 134 browser tests, the documentation inventory and local deployment
quality gate passed. The pinned FOS-Master 3,000-file hash/extraction parity
and donor-policy shadow passed with zero unexplained membership differences;
six explicit policy gaps remain. The donor repo was not changed. These checks
prove a private, non-current generation tranche, not production acceptance or
v2 activation; no version tag is assigned.

## DC-002T FileOS v2 private document publication — merged verification

PR [#79](https://github.com/jbone3311/MasterBrain/pull/79) merged at
`d8a2f2d627bc231769e6d45f2deace68a9c8a334` from base
`aa1b14752df4aee712c9c0dbb25bb51bdcd98c86`. Its exact head
`d11dd99c8e7d1a8bd8bccd4a716606a92b710a0a` passed the
[CI gate](https://github.com/jbone3311/MasterBrain/actions/runs/36917025127),
[strict runtime matrix](https://github.com/jbone3311/MasterBrain/actions/runs/36917025307)
and [populated restore](https://github.com/jbone3311/MasterBrain/actions/runs/36917025049)
before merge. The merge commit also passed the
[strict runtime matrix](https://github.com/jbone3311/MasterBrain/actions/runs/36918757261)
and [populated restore](https://github.com/jbone3311/MasterBrain/actions/runs/36918757313);
its [post-merge CI gate](https://github.com/jbone3311/MasterBrain/actions/runs/36918757353)
also passed, including the full PostgreSQL suite and isolated FileOS worker checks.

ADR-125, migration 0046 and `FileOSV2DocumentPublisher` add a worker-only
historical publication attempt for the hashed rows of one completed v2
baseline. Each file is extracted through the existing confined/isolated
DataCore path and rechecked against its staged hash; an exact final source
scan and immutable per-row outcome ledger record a ready or blocked attempt.
The prepared v2 version owns any published normalized document. Hashless
rows receive no fabricated content. No v2 current generation, activation,
absence authority, live-root acceptance or FOS-Master cutover is claimed.

On a disposable local PostgreSQL 17.11 database, the full suite passed
**2,894 tests, one skipped** in 178.16 seconds, with 456 of 457
PostgreSQL-marked tests executed. The 3,000-hashed-row end-to-end publication
stress case passed alone and in the full suite. Its first full-suite run hit
the fixed five-second statement budget while reading prepared rows; adding
the explicit tenant key to the indexed join and predicate made the isolated
stress and subsequent complete suite pass without relaxing that budget.
Ruff, strict mypy over 94 source files, 134 browser tests, the offline
documentation inventory and local deployment quality gate passed. The gate
ran 2,438 non-PostgreSQL tests and skipped the 457 PostgreSQL-marked cases by
design; it is not a substitute for the complete database run above. Against
pinned FOS-Master commit
`218d5caec2f20b9047fd3eb8e027dc671acf0c15`, the 3,000-file shared
hash/extraction parity harness passed. The donor-policy shadow matched 3,004
hashed and metadata-only candidate rows with zero unexplained membership
differences; six explicit transition-policy gaps remain. The donor repository
was not changed. No version tag is assigned to the private non-current tranche.

## DC-002S FileOS v2 private baseline completion — merged verification

PR [#77](https://github.com/jbone3311/MasterBrain/pull/77) merged at
`cf0cc219c06f1da15472cca4e3af897363da1215` from base
`5fa419314cb3ccae8f8e5b299b884a09fec93cfc`. Its exact head
`f8ca5ce4ec3792fba800785c0a9428cb278129b7` passed the
[CI gate](https://github.com/jbone3311/MasterBrain/actions/runs/36908899334),
[strict runtime matrix](https://github.com/jbone3311/MasterBrain/actions/runs/36908899015)
and [populated restore](https://github.com/jbone3311/MasterBrain/actions/runs/36908899513)
before merge.

ADR-124, migration 0045 and `FileOSV2BaselineCompleter` add a worker-only,
source-locked fresh scan that seals one owner-authorized v2 historical baseline.
The immutable staged rows and prepared evidence remain its membership ledger;
the compact private inspection explicitly reports no current-read or absence
authority. FOS-Master and v1 reads remain unchanged. This branch is not a
live-root acceptance, v2 current-search switch or FileOS cutover.

On a fresh disposable PostgreSQL 17.11 database, the full local suite passed
**2,894 tests, one skipped** in 234.20 seconds, with 456 of 457
PostgreSQL-marked tests executed. The completion regression covers exact
success/replay, changed source, wrong client/scope/identity/root/tenant,
direct-SQL stale refusal, protected mutation/truncation, no v1/current effect,
metadata-only hashless evidence and 3,000 hashed rows. Locked dependency
sync, Ruff, strict mypy over 93 source files, 134 browser tests, the offline
documentation inventory and local deployment quality gate passed. The pinned
FOS-Master 3,000-file donor-policy shadow returned 3,004 matching candidate
rows, zero unexplained membership differences and six explicit policy gaps.

An initial local full run had nine asset/isolated-command failures after the
macOS editable package install lost its resource/module path; reinstalling the
same local package non-editably resolved them, and the complete rerun above
passed. No version tag was created for a private nonpublishing baseline.

## DC-002R FileOS v2 owner baseline authorization — merged verification

PR [#75](https://github.com/jbone3311/MasterBrain/pull/75) merged at
`ee397e78ab4036c16da7ec13fec4cf9574e89cc3` from base
`14c3ef228a463714bd97a8317349e2bac0c06eec`. Its exact head
`1774f2795e2931df621f9aee8d7459823b26eaae` passed the
[CI gate](https://github.com/jbone3311/MasterBrain/actions/runs/36903503628),
[strict runtime matrix](https://github.com/jbone3311/MasterBrain/actions/runs/36903503754)
and [populated restore](https://github.com/jbone3311/MasterBrain/actions/runs/36903503649)
before merge.

ADR-123, migration 0044 and the private `FileOSV2BaselineAuthorizer` add a
separate human-owner decision bound to the exact reviewed plan, preparation
digest and count maps. A PostgreSQL source-lock trigger refuses a stale v1
baseline even for direct SQL inserts, and composite foreign keys bind the
preparation and acknowledged counts. Forced RLS, tenant-login fencing,
immutability and protected truncation apply. This is an authorization for a
future completion attempt, **not** v2 completion, current search, absence,
live-root acceptance or FOS-Master cutover.

On a fresh disposable local PostgreSQL 17.11 database, the focused
authorization regression passed, including wrong scope/client/digest,
idempotent replay, changed identity, wrong tenant, stale v1 and no-current-
publication checks. The populated upgrade/restore and protected-truncation
suite passed after its catalog-count expectation was updated for the new
table. The complete local suite passed **2,894 tests, one skipped** in
285.62 seconds, with 456 of 457 PostgreSQL-marked tests executed. Locked
dependency synchronization, Ruff, strict mypy over 92 source files, 134
browser tests, documentation inventory and the local deployment quality gate
passed. No version tag was created for this internal nonpublishing authority
receipt; the next tagged milestone requires a tested v2 baseline and explicit
release acceptance, not merely the presence of an authorization row.

## DC-005N linear FileOS v1 completion ledger — merged verification

PR [#73](https://github.com/jbone3311/MasterBrain/pull/73) merged at
`8b4880cc60c3d17a0d2a9cec527a764b1ec1dc12` from base
`4cd680bb3e88646f5e86d9e1caa446be38e7b7a1`. Its final head
`4f1550ef2362050d30cb5e1c6d8a26d1da249264` passed the exact
[CI gate](https://github.com/jbone3311/MasterBrain/actions/runs/36897964263),
[strict runtime matrix](https://github.com/jbone3311/MasterBrain/actions/runs/36897964422)
and [populated restore](https://github.com/jbone3311/MasterBrain/actions/runs/36897964358)
before merge. ADR-122 and forward
migration 0043 make the run-item foreign key deferred, insert new items before
the receipt, retain one deferred full-ledger count/outcome check on that receipt,
and replace 3,000 repeated full-ledger checks with an immediate, source-locked
late-insert guard. Exact replay reads and validates saved rows without trying
to insert into a sealed run. No v1 freshness/absence behavior, v2 visibility,
FileOS source effect or FOS-Master code changes.

On a disposable local PostgreSQL 17.11 cluster upgraded from migration 0042,
the focused replay, missing/wrong-outcome, late-insert and competing-writer
checks passed. Review then caught a direct-SQL receipt race; the migration now
locks receipt inserts too, and the new receipt-versus-item contention test
passed on a fresh disposable database with the final migration checksum.
The earlier migration candidate's **100 PostgreSQL module tests passed** in 43.51 seconds;
the existing end-to-end 3,000-item v1 completion plus v2 staging stress test
passed in 7.65 seconds of test-call time. An earlier all-v1 stress fixture had
shown 14–26-second commit phases under the previous per-item deferred check;
these are not controlled before/after benchmark results. No production timeout
or integrity limit was relaxed. On the final migration checksum, the local
full suite passed **2,894 tests, one skipped** in 82.24 seconds, with 456 of
457 PostgreSQL-marked tests executed. Locked dependencies, Ruff, strict mypy
over 91 source files, 134 browser tests, the deployment quality gate and
offline documentation inventory passed. A controlled before/after performance
comparison and broader platform load remain tracked in
[issue #71](https://github.com/jbone3311/MasterBrain/issues/71). No release tag
was created for this database-integrity fix.

## DC-002Q FileOS v2 hashed-evidence preparation — merged verification

PR [#70](https://github.com/jbone3311/MasterBrain/pull/70) merged at
`f1e665a648c3fb665c577c6d2379aa98a1284a25` from base
`91f3e33f6617f8fe791f84d4a041c4fe1f8f701c`. Its exact-head
[CI gate](https://github.com/jbone3311/MasterBrain/actions/runs/36892751430),
[strict runtime matrix](https://github.com/jbone3311/MasterBrain/actions/runs/36892751272)
and [populated restore](https://github.com/jbone3311/MasterBrain/actions/runs/36892751325)
passed before merge. ADR-121 and migration 0042 add a
worker-only third exact source scan and a policy-scoped mapping from donor
candidate versions to shared DataCore versions/evidence. A local regression
caught that reusing candidate IDs would conflict with v1's immutable mtime
metadata; the final mapping preserves both v1 import compatibility and donor
provenance. Hashless rows gain no fabricated evidence. The operation does not
complete v2 or change current v1 pointers, search, freshness, absence, source
files or FOS-Master.

Disposable local PostgreSQL 17.11 final full suite: **2,893 passed, one skipped**
in 127.62 seconds (456 PostgreSQL-marked cases collected, 455 executed). The
3,000-hashed-row end-to-end preparation stress test passed separately in
24.53 seconds and again in that full suite. An earlier fixture completed all
3,000 rows through the legacy v1 receipt before testing the new v2 path; in
module/full-suite runs that fixture intermittently hit the 5-second statement
budget in the prior-ledger review query. In isolation the query measured about
25 ms. The final fixture keeps one completed v1 item and adds 2,999 donor-only
hashed candidates, still stressing 3,000 prepared evidence rows without
conflating this tranche with legacy v1 completion load. No runtime timeout was
increased. The older v1 large-completion performance is tracked separately
in [issue #71](https://github.com/jbone3311/MasterBrain/issues/71). Ruff and strict mypy over 91 source
files, 134 browser tests, deployment gate and offline documentation inventory
passed. The pinned FOS-Master donor remains clean at
`218d5caec2f20b9047fd3eb8e027dc671acf0c15`; 3,000-file donor-policy
shadow had 3,004 ordinary/hashless matches, 3,006 prior-v1 classifications,
six explicit policy gaps and zero unexplained membership differences. The
3,000-file shared hash/extraction parity harness also passed. The first full
local suite exposed a macOS-specific hidden editable-install `.pth` flag in
three isolated subprocess tests; a non-editable local package install restored
those tests, and the final full suite passed. No version tag was created for
this internal preparation step; `v0.2.0a1` remains the tagged alpha checkpoint.

## ADR-120 isolated-controller failure diagnostics — merged verification

Branch `codex/mime-sandbox-failure-diagnostics` starts from merged `main`
`6f71a7a09ac53a913191214f58b3da656b65f2b2`. The prior `main` full CI,
strict runtime and restore passed. This change keeps the public fail-closed
`MimeUnavailable` behavior but emits only fixed profile/stage/reason warnings
from the trusted controller. Offline tests inject pipe deadline, output limit,
CLI exit, OOM/nonzero worker exit, invalid response and cleanup faults and
assert that source text, private exception messages and container IDs are not
logged. The cause of intermittent issue #64 remains unknown until a new
instrumented recurrence. Local PostgreSQL 17.11 full suite: **2,890 passed,
one skipped** (453 PostgreSQL-marked cases collected, 452 executed); 58
focused controller tests pass. Ruff, formatting, mypy over 90 source files,
the repository quality gate, 134 browser tests and offline documentation
inventory (214 Markdown files, 1,164 local paths/fragments) pass. No local
Docker is installed, so the real-container proof must come from hosted CI.
No version tag is warranted for this diagnostic-only increment; issue #64
remains open and this is not a release.

[PR #68](https://github.com/jbone3311/MasterBrain/pull/68) exact head
`642608d663d12661fc803aa4c73a0a45ff714bab` passed
[full CI and restricted-container checks](https://github.com/jbone3311/MasterBrain/actions/runs/36881603973),
[strict runtime](https://github.com/jbone3311/MasterBrain/actions/runs/36881604054)
and [populated restore](https://github.com/jbone3311/MasterBrain/actions/runs/36881604057).
It merged to `main` at `dc596dbad5ded95834f5c38e96b19bf955d5d39b`.
Post-merge [full CI](https://github.com/jbone3311/MasterBrain/actions/runs/36883070762),
[strict runtime](https://github.com/jbone3311/MasterBrain/actions/runs/36883070772)
and [populated restore](https://github.com/jbone3311/MasterBrain/actions/runs/36883070747)
all passed, including the real restricted large-MIME check. This does not prove the
intermittent failure is fixed; no instrumented recurrence occurred.

## DC-002P approved-stage fresh verification — merged verification

Branch `codex/dc-002p-v2-baseline-verification` starts from merged `main`
`b39ee4667a6d1bddcf574cf914e5f597f701d363`. ADR-119 and migration 0041
add worker-scoped, approval-bound verification by a fresh bounded root scan.
The receipt binds exact staged rows and prior v1 identity but is not a v2
completion or current-read authority. Disposable PostgreSQL 17.11 full suite:
**2,886 passed, one skipped** (453 PostgreSQL-marked cases collected, 452
executed). Ruff, mypy over 90 source files, the deployment gate, 134 browser
tests and offline documentation inventory (213 Markdown files, 1,160 local
paths/fragments) pass. Pinned FOS-Master `218d5caec2f20b9047fd3eb8e027dc671acf0c15`
is unchanged; its 3,000-file fictional shadow matches 3,004 ordinary and
metadata-only rows and 3,006 prior-v1 classifications, with six explicit
policy gaps and no unexplained membership differences. A separate local container
run is not claimed; hosted PR CI/strict/restore passed as linked below. No version tag is warranted
for this nonpublishing internal verification step.

[PR #66](https://github.com/jbone3311/MasterBrain/pull/66) tested exact head
`77625be7d31f71a1b2b55a0aaa8b0dd2b6a1fc1a`: [full CI](https://github.com/jbone3311/MasterBrain/actions/runs/36873836458),
[strict-runtime matrix](https://github.com/jbone3311/MasterBrain/actions/runs/36873836409),
and [populated restore](https://github.com/jbone3311/MasterBrain/actions/runs/36873836443)
all passed. It merged to `main` at
`304d070198369d0b6f8aa9583e2d00dedbff402a`. Post-merge
[strict runtime](https://github.com/jbone3311/MasterBrain/actions/runs/36874909255)
and [populated restore](https://github.com/jbone3311/MasterBrain/actions/runs/36874909220)
passed; the [post-merge full CI](https://github.com/jbone3311/MasterBrain/actions/runs/36874909222)
failed on attempt 1 in the preexisting isolated large-MIME container check:
one `MimeUnavailable` from `DockerMimeProcessor.prepare` was scrubbed by the
worker boundary, so its underlying container failure was not visible. The
same exact-head PR job passed this check. Attempt 2 on the unchanged merged
commit passed that MIME check and the remaining CI gate. This recurrence is
tracked in [issue #64](https://github.com/jbone3311/MasterBrain/issues/64);
the passing rerun does not erase the failed first attempt or diagnose its cause.

## DC-002O exact FileOS v2 transition approval — merged verification

Branch `codex/dc-002o-transition-approval` starts from merged `main`
`747478b2f493c275293fe38b6f137c0e0c850e04`. ADR-118 and migration 0040
add a private, locator-free plan and immutable human-owner review receipt for
one staged donor-policy inventory. The plan rechecks canonical packet and
candidate digests, relational rows, prior item classifications, source root
binding and latest completed v1 receipt under the source lock. Approval is
digest/count-bound and refuses scan errors, unobserved/error-covered prior
items, stale receipts, wrong identities and non-human callers. It changes no
v1 completion, freshness, absence, search, source files or donor repository.
No API route or v2 publication transaction consumes the approval.

Local PostgreSQL 17.11 full suite: **2,883 passed, one skipped**; 451
PostgreSQL-marked cases collected, 450 executed and one skipped. Ruff, mypy
over 89 source files, 134 browser tests and offline documentation inventory
(212 Markdown files, 1,153 local paths/fragments) pass. The pinned-donor
3,000-file fictional comparison matches 3,004 ordinary and metadata-only rows
and 3,006 prior-v1 classifications, with six explicit policy gaps and zero
unexplained membership differences. FOS-Master remains at
`218d5caec2f20b9047fd3eb8e027dc671acf0c15` unchanged. Local container
and populated restore checks are not claimed. No version tag is warranted for
this nonpublishing internal review step.

[PR #63](https://github.com/jbone3311/MasterBrain/pull/63) exact head
`808ed725c5cb79f9f5f854bb23778313dbd543e0` passed the
[strict-runtime matrix](https://github.com/jbone3311/MasterBrain/actions/runs/36864787012),
[populated restore](https://github.com/jbone3311/MasterBrain/actions/runs/36864787032),
and [full CI](https://github.com/jbone3311/MasterBrain/actions/runs/36864787285)
on attempt 2. Full CI attempt 1 failed an existing isolated large-MIME
container test with a scrubbed `MimeUnavailable`; the same exact-head test
passed on attempt 2. This intermittent gate is tracked as
[issue #64](https://github.com/jbone3311/MasterBrain/issues/64), not silently
discarded. PR #63 merged at `d5b7243f8f7cbb1981ff4283743a704e02baa0c2`.
That exact merged-main commit passed
[full CI](https://github.com/jbone3311/MasterBrain/actions/runs/36867169565),
[strict runtime](https://github.com/jbone3311/MasterBrain/actions/runs/36867169467)
and [populated restore](https://github.com/jbone3311/MasterBrain/actions/runs/36867169557).
The previously intermittent MIME container test also passed on merged main;
issue #64 remains open to diagnose its original failure.

## DC-002N nonpublishing FileOS v2 staging — merged verification

Branch `codex/dc-002n-v2-inventory-staging` starts at verified `main`
`f42ed3d49b6c6e79f89c952f4cff5defbea34712`. ADR-117 and migration 0039
add a private, relational staging shape for hashed, hashless deferred, excluded
and error donor observations. A sealed packet is checked against the latest
completed v1 receipt under the source lock. Staging has no v2 completion,
freshness, absence, index, search, API, cutover or source-effect authority.

Local PostgreSQL 17.11 full suite on the final header-last staging design:
**2,881 passed, one skipped**; 449 PostgreSQL-marked cases collected, 448 executed and one
skipped. Ruff, mypy (88 source files), 134 browser tests, 29 restore-drill unit
tests, deployment quality gate and offline documentation inventory (211 Markdown
files, 1,146 paths/fragments) passed. The pinned-donor 3,000-file fictional
comparison matched 3,004 hashed and metadata-only rows, 3,006 prior-v1
classifications and six explicit policy gaps, with zero unexplained membership
differences; FOS-Master remains at `218d5caec2f20b9047fd3eb8e027dc671acf0c15`
and clean. The local container restore attempt stopped before creating a drill
container because this Mac could not inspect Docker; hosted populated restore
is required before merge. No new product tag is warranted for a nonpublishing
stage. The final suite staged **3,000 hashless rows** with the header-last,
single-recount SQL design; count-mismatch and late-insert refusals passed.

[PR #61](https://github.com/jbone3311/MasterBrain/pull/61) exact head
`c06863810d01ea29bbf536785738031766bfc0bb` passed
[full CI 36857667525](https://github.com/jbone3311/MasterBrain/actions/runs/36857667525),
[strict runtime 36857667468](https://github.com/jbone3311/MasterBrain/actions/runs/36857667468),
and [populated restore 36857667543](https://github.com/jbone3311/MasterBrain/actions/runs/36857667543).
It merged at `d72e03bd0d50379800894ae37e7f9cfdc645cde7`, whose exact
`main` commit independently passed
[full CI 36858928315](https://github.com/jbone3311/MasterBrain/actions/runs/36858928315),
[strict runtime 36858928348](https://github.com/jbone3311/MasterBrain/actions/runs/36858928348),
and [populated restore 36858928309](https://github.com/jbone3311/MasterBrain/actions/runs/36858928309).
The short-lived implementation branch was removed after merge; the PR and
commits retain its history. No product version tag was created for this
nonpublishing staging checkpoint.

## DC-002M bounded transition review read — merged verification

Branch `codex/dc-002m-transition-review-read` begins at exact verified `main`
`b1c86e822c39c7d10bf1c714be90062fc3824392`. Pinned FOS-Master
`218d5caec2f20b9047fd3eb8e027dc671acf0c15` is unchanged. ADR-116 adds
a compact, locator-free read of an immutable transition packet, with a separate
`brain.evidence.read` scope and at-most-50-row detail pages. It checks the
canonical digest and reports only whether the latest completed receipt still
matches at read time. No route, approval, publication or source effect is added.

Local disposable PostgreSQL 17.11 full suite: **2,878 passed, one skipped**;
447 PostgreSQL-marked cases collected, 446 executed, one skipped. Focused
review-read PostgreSQL regression and 13 transition unit tests passed. Ruff,
mypy (88 source files), 134 browser tests, offline documentation inventory
(210 Markdown files, 1,138 local paths/fragments), and the local deployment
quality gate passed. The pinned-donor fictional 3,000-file comparison again
matched 3,004 hashed and metadata-only candidates, 3,006 prior-v1
classifications and six explicit policy gaps with zero unexplained membership
differences. Hosted exact-head CI, strict runtime and populated restore are
green at the exact head and merged `main` commit:

[PR #59](https://github.com/jbone3311/MasterBrain/pull/59) exact head
`67e7758b018de0339789abf9861c9f9534550e0e` passed
[full CI 36851543615](https://github.com/jbone3311/MasterBrain/actions/runs/36851543615),
[strict runtime 36851543630](https://github.com/jbone3311/MasterBrain/actions/runs/36851543630),
and [populated restore 36851543737](https://github.com/jbone3311/MasterBrain/actions/runs/36851543737).
It merged at `879425172707899f446c7089e990b7918edd112d`, whose exact
`main` commit independently passed
[full CI 36852405786](https://github.com/jbone3311/MasterBrain/actions/runs/36852405786),
[strict runtime 36852405850](https://github.com/jbone3311/MasterBrain/actions/runs/36852405850),
and [populated restore 36852406974](https://github.com/jbone3311/MasterBrain/actions/runs/36852406974).
No new product version is warranted for this private, nonpublishing read tranche.

## DC-002L immutable FileOS transition review packet — merged verification

Branch `codex/dc-002l-transition-review-packet` begins at `main`
`d90379d1b2f90f2413b82248a5b661961ce972dc`. Pinned FOS-Master
`218d5caec2f20b9047fd3eb8e027dc671acf0c15` remains unchanged.
ADR-115 and migration 0038 add one private, immutable packet pairing a single
donor-policy scan with its exact completed-v1 comparison. The latest-run check
is repeated under the FileOS source advisory lock before insert; it does not
publish v2 state or authorize absence, search, FileOS cutover or source effects.

Local disposable PostgreSQL 17.11 full suite: **2,878 passed, one skipped**;
447 PostgreSQL-marked cases collected, 446 executed, one skipped. Focused
transition unit suite: 13 passed; 134 browser tests passed. Ruff, mypy (88 source files), and offline
documentation inventory (209 Markdown files, 1,133 paths/fragments) passed.
The pinned-donor fictional 3,000-file comparison passed 3,004 hashed and
metadata-only candidate matches, 3,006 prior-v1 classifications and six
explicit policy gaps, with zero unexplained membership differences. The first
full run found historical migration fixtures that omitted 0038; those fixtures
were corrected and the full suite rerun green.

[PR #57](https://github.com/jbone3311/MasterBrain/pull/57) exact head
`741187da6b6a2542eff699900212ce3dbb375500` passed
[full CI 36846667545](https://github.com/jbone3311/MasterBrain/actions/runs/36846667545),
[strict runtime 36846667659](https://github.com/jbone3311/MasterBrain/actions/runs/36846667659),
and [populated restore 36846667503](https://github.com/jbone3311/MasterBrain/actions/runs/36846667503).
It merged at `1003efe7111f7e1edf2c230eb9ebcceea84dd3fc`, whose exact
`main` commit independently passed
[full CI 36847578704](https://github.com/jbone3311/MasterBrain/actions/runs/36847578704),
[strict runtime 36847578889](https://github.com/jbone3311/MasterBrain/actions/runs/36847578889),
and [populated restore 36847578824](https://github.com/jbone3311/MasterBrain/actions/runs/36847578824).
No new version is tagged for this nonpublishing tranche.

## DC-002K completed FileOS baseline preview integration

Branch `codex/dc-002k-completed-baseline-preview` starts from verified `main`
`dd5a165d6deebd94e18019708a6ed8afc178d47f` and leaves pinned FOS-Master
`218d5caec2f20b9047fd3eb8e027dc671acf0c15` unchanged. ADR-114 adds a
private read-scoped check that binds a v1 manifest to the latest exact completed
database run, including its intake receipt, policy/root identity, item versions
and terminal outcome balance. A donor transition preview checks this binding
before and after scanning; a newer completion during scanning refuses the
report. There is no v2 persistence, publication or cutover.

[PR #55](https://github.com/jbone3311/MasterBrain/pull/55) final head
`f173b2c6bfd99a7b0e1790cc880e6ff3d82a8ec1` passed
[full CI 36841087965](https://github.com/jbone3311/MasterBrain/actions/runs/36841087965),
[strict runtime 36841087898](https://github.com/jbone3311/MasterBrain/actions/runs/36841087898),
and [populated restore 36841088014](https://github.com/jbone3311/MasterBrain/actions/runs/36841088014).
It merged at `28c09478ad9e88614644395b1ff35df85d24b793`, whose exact
`main` commit independently passed
[full CI 36842094127](https://github.com/jbone3311/MasterBrain/actions/runs/36842094127),
[strict runtime 36842094298](https://github.com/jbone3311/MasterBrain/actions/runs/36842094298),
and [populated restore 36842094105](https://github.com/jbone3311/MasterBrain/actions/runs/36842094105).

Local full-suite verification on the initial code head with disposable
PostgreSQL 17.11: **2,875 passed,
one skipped**; 445 of 446 PostgreSQL-marked cases executed. The focused
real-database regression covers imported-but-incomplete state, exact completion,
wrong run and changed policy, read-scope denial, a newer completion committed
during scanning, and stale refusal before source scanning. Twelve focused
non-database transition tests passed. Ruff, mypy over 88 source files, 134
browser tests, and documentation inventory (208 Markdown files, 1,125 local
paths/fragments) passed. The pinned-donor fictional 3,000-file harness matched
3,004 hashed and metadata-only candidate rows, 3,006 prior-v1
classifications and six explicit policy gaps, with zero unexplained membership
differences. The donor checkout remained clean.
The final tail added a manifest-mutation fence and a twelfth focused unit
test; Ruff, mypy and documentation checks passed afterward. Its broader
PostgreSQL/container suite is the exact-head hosted CI linked above.

An initial local full-suite run had three subprocess import failures because
this Mac's Python does not expose the editable-install path to isolated or
environment-scrubbed subprocesses. After installing this branch as a normal
wheel, the same full suite passed as reported above; no repository fix was
needed for those three failures. These tests do not establish
metadata-only v2 publication, live-source behavior or owner acceptance.

## v0.2.0a1 synthetic-only version checkpoint

Annotated tag [`v0.2.0a1`](https://github.com/jbone3311/MasterBrain/tree/v0.2.0a1)
dereferences to exact merged `main` commit
`c0a531d8a7d0991be0a0f1ea717479c07cc20feb` (PR #53).
That commit independently passed
[full CI 36835220427](https://github.com/jbone3311/MasterBrain/actions/runs/36835220427),
[strict runtime 36835220388](https://github.com/jbone3311/MasterBrain/actions/runs/36835220388),
and [populated restore 36835220436](https://github.com/jbone3311/MasterBrain/actions/runs/36835220436).
Local pinned FOS-Master `218d5caec2f20b9047fd3eb8e027dc671acf0c15`
DataCore parity passed 3,000 fictional stress files plus fixture scans, edge
cases, hashes, duplicate comparisons and text/HTML/CSV/DOCX/XLSX extraction.
The donor checkout remained clean. The tag is for fictional inputs and
disposable PostgreSQL only; it does not establish interactive Mac, live-source,
hosted-production, security/operations or FileOS cutover acceptance.

## DC-002J v1-to-donor transition integration

Branch `codex/dc-002j-policy-transition-preview` begins from `main`
`7d388b1c44cc2236a87a8ecd79750e565dda1a9f`.
[PR #52](https://github.com/jbone3311/MasterBrain/pull/52) code head
`c47108fb368509f091496fe4003559e0d048aef4` passed
[full CI 36780193102 attempt 2](https://github.com/jbone3311/MasterBrain/actions/runs/36780193102/attempts/2),
[strict runtime 36780193027 attempt 2](https://github.com/jbone3311/MasterBrain/actions/runs/36780193027/attempts/2),
and [populated restore 36780193203 attempt 2](https://github.com/jbone3311/MasterBrain/actions/runs/36780193203/attempts/2).
The final PR head `489948f4dffb3e784a16973bcae487f5d09a5c4a`
independently passed [full CI 36829588640](https://github.com/jbone3311/MasterBrain/actions/runs/36829588640),
[strict runtime 36829588667](https://github.com/jbone3311/MasterBrain/actions/runs/36829588667),
and [populated restore 36829588607](https://github.com/jbone3311/MasterBrain/actions/runs/36829588607).
PR #52 merged into `main` at `899acb7c4fcefb374ebe8a71e711509cdf8e77ae`;
that exact merged commit passed
[full CI 36830955794](https://github.com/jbone3311/MasterBrain/actions/runs/36830955794),
[strict runtime 36830955857](https://github.com/jbone3311/MasterBrain/actions/runs/36830955857),
and [populated restore 36830955947](https://github.com/jbone3311/MasterBrain/actions/runs/36830955947).
Its new library compares a
validated, complete-shape v1 snapshot with a fresh donor candidate at the same
source/root and a newer observation time. It never publishes, persists, or
infers absence. The pinned FOS-Master fictional 3,000-file harness reports
3,006 prior v1 items: 3,002 unchanged, four donor-excluded and two donor-only
hashed items. The six policy gaps are blocked for review. Focused, full local
verification passes: locked dependency sync and, with a normal local wheel
install, 2,427 Python tests with 445
PostgreSQL-marked tests skipped in the no-database run; 134 browser tests;
Ruff; mypy over 88 source
files; 207 Markdown files and 1,119 local links/fragments; and the repository
deployment-quality gate. The pinned donor harness passes on 3,000 fictional
files with 3,004 exact hashed and metadata-only donor-candidate matches, 3,006
prior-v1 classifications and six explicit policy gaps. This is not a release
or cutover receipt; no live-source or owner acceptance is claimed.

A separate disposable local PostgreSQL 17 cluster executed the broader suite:
2,862 passed, one skipped; 444 of 445 PostgreSQL-marked tests executed. An
initial run had three subprocess `ModuleNotFoundError` failures because this
local Python skips the editable-install `.pth` file; after installing the same
commit as a normal wheel into the disposable virtual environment, all three
passed with no repository code change. The cluster was stopped and removed.
This local database result is additional evidence; exact-head hosted
PostgreSQL, restricted-worker containers and populated restore subsequently
passed as linked above.
The pinned donor transition harness also passed with 9,994 synthetic stress
files plus six fixed v1 items: 10,000 prior-v1 classifications, 9,998 exact
donor hashed and metadata-only matches, six explicit policy gaps and zero
unexplained membership differences (41.83 seconds elapsed locally). A 10,000
stress-file attempt correctly hit the 10,000-item v1 manifest bound because
the fixed corpus adds six prior items. The harness now refuses 9,995 or more
stress files before loading the donor; the 10,000-item safety limit remains.
The two new bound tests passed; the current harness reports an argparse error
for an over-limit command instead of a late traceback. The full no-database
suite was rerun after this harness change, while the disposable PostgreSQL run
above predates these two test-only additions.

At the base commit, new `main` GitHub Actions jobs did not start: CI
[36776977739](https://github.com/jbone3311/MasterBrain/actions/runs/36776977739),
strict runtime [36776977859](https://github.com/jbone3311/MasterBrain/actions/runs/36776977859),
and restore [36776977920](https://github.com/jbone3311/MasterBrain/actions/runs/36776977920)
all have zero-step failures annotated with an account payment/spending-limit
message. A CI retry (attempt 2) had the same annotation. This was not a test
failure and did not supersede the green exact-head and merged-main PR #50
receipts or the green PR #51 head. On 2026-10-01, Actions resumed executing
jobs and the exact PR #52 code head passed the three workflows linked above.

## DC-002I donor candidate integration

Branch `codex/dc-002i-donor-candidate-ledger` starts from verified `main`
`b261356e8664527cbd5c4f7ec85fd7877cdad26b`. [PR #50](https://github.com/jbone3311/MasterBrain/pull/50)
merged exact head `1636e71bccd44cbea20742a87ff8f65cddd8cd4b` into `main` at
`3d0febb1dee61abf7c5302d4c3a3a63298f4a066`. Exact head passed
[full CI 36774720287](https://github.com/jbone3311/MasterBrain/actions/runs/36774720287),
[strict runtime 36774720291](https://github.com/jbone3311/MasterBrain/actions/runs/36774720291),
and [populated restore 36774720258](https://github.com/jbone3311/MasterBrain/actions/runs/36774720258).
The exact merged `main` commit independently passed
[full CI 36775458127](https://github.com/jbone3311/MasterBrain/actions/runs/36775458127),
[strict runtime 36775458423](https://github.com/jbone3311/MasterBrain/actions/runs/36775458423),
and [populated restore 36775458037](https://github.com/jbone3311/MasterBrain/actions/runs/36775458037).

Local focused tests pass:
30 candidate/shadow cases, including v1 importer rejection, malformed and
overlapping ledgers, no-follow metadata-only observations and root drift. Full
local Python: 2,418 passed, 445 PostgreSQL-marked skipped (not executed); 134
browser tests passed. Ruff, mypy over 87 source files, documentation inventory
(205 Markdown files, 1,111 links/fragments), and the repository deployment-quality
gate passed. The pinned FOS-Master synthetic 3,000-file
comparison matches 3,004 hashed and 3,004 metadata-only candidate rows exactly,
with zero unexplained membership differences. Hosted PostgreSQL, restricted
worker and restore checks passed on the exact head and merged commit; they do
not replace the local donor comparison. The donor checkout remains unchanged at
`218d5caec2f20b9047fd3eb8e027dc671acf0c15`. No live-source, publishable
v2, or FileOS cutover claim follows from this result.

## DC-002H confined metadata shadow integration

Branch `codex/dc-002h-confined-metadata-shadow` starts from `main`
`e2f323d68b5839708d2f71520d37ed9ff82a2e6f`. [PR #48](https://github.com/jbone3311/MasterBrain/pull/48)
merged exact head `706a9de3c312f4368de23d8920486e5cbcc0263c` at
`553b2e5a3ec936cb181e8a67f2e04eff95c496a4`. The head passed
[full CI 36769463528](https://github.com/jbone3311/MasterBrain/actions/runs/36769463528),
[strict runtime 36769463544](https://github.com/jbone3311/MasterBrain/actions/runs/36769463544)
and [populated restore 36769463527](https://github.com/jbone3311/MasterBrain/actions/runs/36769463527).
The exact merged `main` SHA independently passed
[full CI 36770297142](https://github.com/jbone3311/MasterBrain/actions/runs/36770297142),
[strict runtime 36770297170](https://github.com/jbone3311/MasterBrain/actions/runs/36770297170)
and [populated restore 36770297109](https://github.com/jbone3311/MasterBrain/actions/runs/36770297109).

The tranche adds a no-follow,
root-bound metadata stat to the nonpublishing donor-policy scanner, without
opening leaf bytes or changing publishable snapshot v1. Local focused tests:
34 passed, including unchanged special-file exclusion. Full local Python on the
corrected branch head: 2,404 passed, 445 PostgreSQL-marked skipped
(not executed); 134 browser tests passed. Ruff, mypy over 86 source files,
documentation inventory (203 Markdown files, 1,103 local links), and the
repository deployment-quality gate passed. The pinned FOS-Master synthetic
3,000-file comparison still matches 3,004 ordinary, replay, changed-file and
metadata-only rows, with zero unexplained membership differences. The donor
checkout remains clean at `218d5caec2f20b9047fd3eb8e027dc671acf0c15`.
These synthetic and hosted checks are not live-source or cutover evidence.

## DC-002G donor-policy shadow integration

The branch `codex/dc-002g-donor-policy-shadow` began at verified `main`
`d334c5c85403d30abb6fdbbbbad7e43163fc5eea`. That exact main SHA passed
[full CI 36198583494](https://github.com/jbone3311/MasterBrain/actions/runs/36198583494),
[strict runtime 36198583420](https://github.com/jbone3311/MasterBrain/actions/runs/36198583420),
and [populated restore 36198583568](https://github.com/jbone3311/MasterBrain/actions/runs/36198583568).
Those are **base** checks, not checks of DC-002G. [PR #46](https://github.com/jbone3311/MasterBrain/pull/46)
merged exact head `fa06a2ffca660ba773ec2dfb3757dc29b492ecc2` into `main` at
`dd03e0cf306a52d461558e467214f0dcbbe4977a`. The head passed
[full CI 36764355022](https://github.com/jbone3311/MasterBrain/actions/runs/36764355022),
[strict runtime 36764355037](https://github.com/jbone3311/MasterBrain/actions/runs/36764355037),
and [populated restore 36764354788](https://github.com/jbone3311/MasterBrain/actions/runs/36764354788).
The exact merged `main` SHA then independently passed
[full CI 36765312397](https://github.com/jbone3311/MasterBrain/actions/runs/36765312397),
[strict runtime 36765312617](https://github.com/jbone3311/MasterBrain/actions/runs/36765312617),
and [populated restore 36765312599](https://github.com/jbone3311/MasterBrain/actions/runs/36765312599).

ADR-111 adds a standalone, nonpublishing donor-policy scanner and synthetic pinned-
donor comparator. On the local code head, 40 focused inventory/classifier tests
passed, including coverage-error regressions. Independent full Python validation
passed 2,399 tests
with 445 PostgreSQL-marked tests **skipped**, not executed. Ruff, mypy over 86
source files and documentation inventory (203 Markdown files, 1,102 local links)
passed. The pinned FOS-Master comparison matched 3,004 ordinary/replay/change
rows and 3,004 explicit no-hash metadata rows with zero membership differences.
The unchanged snapshot-v1 comparator still reported its exact six known policy
differences and 3,002 common hashes. FOS-Master stayed clean at
`218d5caec2f20b9047fd3eb8e027dc671acf0c15`.

These are synthetic/local and hosted test gates, not live-source acceptance. No
snapshot-v1 policy switch, production FileOS operation,
live-source acceptance or cutover is claimed.

## Latest verified `main`: opt-in tenant-routed API database access

[PR #43](https://github.com/jbone3311/MasterBrain/pull/43) merged at
`dacc97bd7a6220b92e6672628066441c0dd2d02c`. Its final head
`f0436a00cd56c6d039cdabe809f2144b7b98fd99` passed
[full CI 36196588405](https://github.com/jbone3311/MasterBrain/actions/runs/36196588405),
[strict runtime 36196588456](https://github.com/jbone3311/MasterBrain/actions/runs/36196588456),
and [populated restore 36196588431](https://github.com/jbone3311/MasterBrain/actions/runs/36196588431).
The exact merged `main` SHA independently passed
[full CI 36197334436](https://github.com/jbone3311/MasterBrain/actions/runs/36197334436),
[strict runtime 36197334382](https://github.com/jbone3311/MasterBrain/actions/runs/36197334382),
and [populated restore 36197334408](https://github.com/jbone3311/MasterBrain/actions/runs/36197334408).

Local final-head evidence: 2,829 Python passed, one Docker-only skipped, with
444 PostgreSQL-marked tests executed on a fresh disposable PostgreSQL 17.11
database; 134 browser tests passed. The separate local deployment gate passed
2,384 non-PostgreSQL tests while skipping its 445 database-marked tests; that
gate is **not** counted as database evidence. Ruff, mypy, documentation inventory
(202 Markdown files and 1,096 local paths/fragments) and diff checks passed.
Pinned FOS-Master `218d5caec2f20b9047fd3eb8e027dc671acf0c15` DataCore
parity passed on 3,000 stress files plus edge cases; the donor checkout is clean.

ADR-109 adds an opt-in, private-file API route from exact identity lookup to
distinct tenant-bound data logins. Synthetic two-tenant API search, no-table
lookup authority and missing/wrong/shared-route refusal passed in real
PostgreSQL. The legacy shared-DSN API mode and separate private worker commands
are not tenant-routed by this change. Credential creation/rotation, two-tenant
restore, hosted adversarial review, issue #7 and populated live-upgrade issue #9
remain open. No production multi-tenant, live-source or FOS-Master cutover claim
follows from these gates.

## Previous verified `main`: opt-in tenant-bound runtime login fence

[PR #41](https://github.com/jbone3311/MasterBrain/pull/41) merged at
`ce12933d1b064403e07ce1cdb3efd239cf25f244`. Its head
`5c38c67b83f5ca3580ca61bcc7a7eeb6b3d1d3aa` passed
[full CI 36192548076](https://github.com/jbone3311/MasterBrain/actions/runs/36192548076),
[strict runtime 36192548112](https://github.com/jbone3311/MasterBrain/actions/runs/36192548112),
and [populated restore 36192548136](https://github.com/jbone3311/MasterBrain/actions/runs/36192548136).
The exact merged `main` SHA passed
[full CI 36193250984](https://github.com/jbone3311/MasterBrain/actions/runs/36193250984),
[strict runtime 36193251054](https://github.com/jbone3311/MasterBrain/actions/runs/36193251054),
and [populated restore 36193251021](https://github.com/jbone3311/MasterBrain/actions/runs/36193251021).

Local synthetic evidence: 2,818 Python passed, one Docker-only skipped, with
443 PostgreSQL-marked tests executed on disposable PostgreSQL 17.11; 134 browser
tests passed. The pinned FOS-Master donor at
`218d5caec2f20b9047fd3eb8e027dc671acf0c15` passed DataCore parity on
3,000 stress files and edge cases. Migration 0037 and ADR-108 introduce an
**opt-in** tenant-bound PostgreSQL login fence, test arbitrary SQL with forged
request-context GUCs, and cover security-definer identity and recovery helpers.
The existing shared global runtime login remains unbound; issue #7 remains open
until tenant-aware API/worker routing and credential lifecycle are implemented
and tested. Populated live-upgrade lock risk in issue #9 also remains open.
This is not a production multi-tenant, live-source, or FOS-Master cutover receipt.

## Previous verified `main`: current-only archive-image OCR search

[PR #39](https://github.com/jbone3311/MasterBrain/pull/39) merged at
`d2a418d217333605f9aa4a15d4b7c73819b84c9c`, then that exact `main` SHA
passed [full CI 36187693715](https://github.com/jbone3311/MasterBrain/actions/runs/36187693715),
[strict runtime 36187693520](https://github.com/jbone3311/MasterBrain/actions/runs/36187693520),
and [populated restore 36187693702](https://github.com/jbone3311/MasterBrain/actions/runs/36187693702).
The PR head `5a9543700ca913d72dd9769bcd636db1469720b5` independently passed
[full CI 36186992023](https://github.com/jbone3311/MasterBrain/actions/runs/36186992023),
[strict runtime 36186991911](https://github.com/jbone3311/MasterBrain/actions/runs/36186991911),
and [restore 36186991839](https://github.com/jbone3311/MasterBrain/actions/runs/36186991839).

Local synthetic evidence: 2,815 passed, one Docker-only skipped, with 440
PostgreSQL-marked tests executed; 134 browser tests passed. The eight image-suffix
receipt mappings passed against disposable PostgreSQL 17.11. Pinned FOS-Master
`218d5caec2f20b9047fd3eb8e027dc671acf0c15` archive, image OCR (100 stress
images), and DataCore (3,000 stress files) parity passed. ADR-107 and migration
0036 add only current-image read visibility and a tenant-leading receipt index.
Neither FOS-Master nor active FileOS generations changed. Issues #7 and #9 remain
open; no live-source, populated-index lock-budget, production, or donor-cutover
claim follows from these synthetic gates.

## Previous verified `main` before archive-image search tranche

PR #37 added least-privilege identity administration and merged at `e07bc55`;
PR #38 narrowed runtime identity reads to an exact resolver and merged at
`384d53d38704c38fc9cbef87c0397a51e0c60b6d`. That exact `main` commit passed
[full CI 36184292801](https://github.com/jbone3311/MasterBrain/actions/runs/36184292801),
[strict runtime 36184292780](https://github.com/jbone3311/MasterBrain/actions/runs/36184292780),
and [populated restore 36184292905](https://github.com/jbone3311/MasterBrain/actions/runs/36184292905).
Issue #6 is closed. Confirmed issue #7 (caller-settable tenant authority) and
populated-upgrade issue #9 remain open; no hosted security or production claim is
made. The archive-image search tranche is recorded above on its exact head and
merge commit.

## Repository consolidation (2026-09-25)

The repository was renamed from `jbone3311/CW-EmailBrain` to
[`jbone3311/MasterBrain`](https://github.com/jbone3311/MasterBrain). `main` was
`c8c428bc61c17021394b67b489700123de2e3ea6` before the documentation update.
That exact SHA passed [full CI 36161891971](https://github.com/jbone3311/MasterBrain/actions/runs/36161891971),
[strict runtime 36161894202](https://github.com/jbone3311/MasterBrain/actions/runs/36161894202),
and [populated restore 36161891866](https://github.com/jbone3311/MasterBrain/actions/runs/36161891866).
Twenty-two branch refs already contained by `main` were removed after ancestry
verification; no commits were removed from `main`. Two divergent historical
branches remain for separate disposition. No release, live source, FileOS cutover,
or FOS-Master change was made. See [the exact branch receipt](REPOSITORY_CONSOLIDATION.md).

## Previous `main` synthetic checkpoint (2026-09-24)

The cumulative alpha merge `2dd4a85` (PR #28) and strict sender-runtime merge `20bfc1f` (PR #31) precede two further tested changes: privacy-safe API failure observability in [PR #33](https://github.com/jbone3311/MasterBrain/pull/33), merged at `c605e6446df2c305a757a388f084605f4e8031cd`, and the disposable cross-source browser trial in [PR #32](https://github.com/jbone3311/MasterBrain/pull/32), merged at `77192f52e15139fba1fad72264cc54982095f928`. The trial's Docker startup-timeout cleanup finding was fixed before merge with run-specific marker verification and fault tests.

That exact `main` commit `77192f52e15139fba1fad72264cc54982095f928` passed [full CI 36099402051](https://github.com/jbone3311/MasterBrain/actions/runs/36099402051), [strict sender-runtime 36099402009](https://github.com/jbone3311/MasterBrain/actions/runs/36099402009), and [populated restore 36099402006](https://github.com/jbone3311/MasterBrain/actions/runs/36099402006). The preceding `c605e64` merge also passed its exact `main` [full CI 36098702369](https://github.com/jbone3311/MasterBrain/actions/runs/36098702369), [strict runtime 36098702407](https://github.com/jbone3311/MasterBrain/actions/runs/36098702407), and [restore 36098702434](https://github.com/jbone3311/MasterBrain/actions/runs/36098702434). The historical receipts below preserve earlier point-in-time evidence; older “pending integration” wording is not the current `main` state.

At that older checkpoint, this was a fictional-data, test-only alpha candidate.
Interactive Mac/browser acceptance, the then-open issues #6/#7/#9, production
operations and donor cutover were not satisfied. Issue #6 has since closed as
recorded above. FOS-Master is unchanged; at that older checkpoint,
`v0.2.0a1` had not yet been tagged.

## `main` synthetic alpha integration checkpoint

Cumulative [PR #28](https://github.com/jbone3311/MasterBrain/pull/28) merged
the tested MasterBrain stack into `main` at
`2dd4a8549f29fe56514e1bfa831e9a8b24821b35`. Its exact PR head
`f0de8ba5897488effe9cffeda54d00d10f476339` passed
[CI 35929447361](https://github.com/jbone3311/MasterBrain/actions/runs/35929447361)
and [populated restore 35929447372](https://github.com/jbone3311/MasterBrain/actions/runs/35929447372).
GitHub comparison found zero changed files between that head and the merge commit.
The `main` push itself then passed
[CI 35930140690](https://github.com/jbone3311/MasterBrain/actions/runs/35930140690)
and [populated restore 35930140723](https://github.com/jbone3311/MasterBrain/actions/runs/35930140723)
on the exact merge SHA. This establishes a testable **synthetic alpha baseline**,
not live-source, production or FileOS cutover acceptance. FOS-Master remains
untouched. The tag was not yet created at this historical checkpoint; the
current tagged version and its exact evidence are recorded at the top of this
receipt.

## MasterBrain synthetic alpha readiness candidate

Local commit `947ea6e83fd18d0cb147bbc8325737bb67de194e` was published through
the connected GitHub integration with the exact same tree as remote commit
`9b1b0e0eb71291290ab30c418c9bd8e12e05a8b8` in
[PR #27](https://github.com/jbone3311/MasterBrain/pull/27), targeting the tested
PR #25 branch. That code head passed full hosted
[CI 35927108260](https://github.com/jbone3311/MasterBrain/actions/runs/35927108260)
and the populated PostgreSQL
[restore 35927108311](https://github.com/jbone3311/MasterBrain/actions/runs/35927108311).
The local focused MasterBrain CLI suite passed 20 tests with `PYTHONPATH=src`;
documentation inventory passed (188 Markdown files, 995 paths/fragments). The
separate pinned FOS-Master donor comparison passed fixture scans, pair/hash and
text/HTML/CSV/DOCX/XLSX extraction checks plus 3,000 synthetic files and edge
cases. The initial local pytest collection without `PYTHONPATH=src` failed before
tests ran because that existing virtual environment lacked an installed editable
package; it is not counted as a product failure or pass.

This paragraph describes the earlier readiness PR checkpoint; the cumulative
`main` integration and its own gates are recorded above. No live-source,
hosted-operation, production identity or FileOS cutover acceptance is claimed;
FOS-Master remains unchanged. ADR-101 and the alpha test guide define the boundary.

## Confined FileOS read checkpoint

ADR-100 precedes a DataCore descriptor-relative reader shared by snapshot hashing
and text/PDF/Office extraction. It refuses file and ancestor symlink swaps before
bytes can leave the authorized root, keeps bounded reads and rechecks the locator.
Focused synthetic tests are in `tests/test_fileos_confined_reads.py`; existing
snapshot and donor-shadow race mocks have been adapted to the new read boundary.
Local pinned-donor shadow passed on 3,000 synthetic files: 3,002 ordinary
SHA/size matches, six reason-coded policy differences and two symlink policy
differences; replay, change, removal, no-hash/rehash and mass-prune assertions
passed. Documentation inventory passed (186 Markdown files, 985 paths/fragments).
The existing focused suites passed locally (34 tests), followed by all 14
adversarial confined-read tests. The code head
`076922767e34951f3b8588362f908edd0f1104c2` passed the full hosted
[gate](https://github.com/jbone3311/MasterBrain/actions/runs/35905426481)
and populated [logical restore](https://github.com/jbone3311/MasterBrain/actions/runs/35905426478)
in PR #25. This verifies the isolated branch, not production FileOS cutover or
real cloud-placeholder behavior. No FOS-Master edit or inventory-policy switch
occurs.
The documentation head `9b000cfa139b8eafae9e83a530f3ae7d4f247a6c` also
passed its hosted gate and restore. The extended no-follow walk of ancestors
above the authorized root passed all 15 adversarial tests and the rerun pinned
donor shadow locally. Its exact code head
`6e2eb8e10ca5f740ecfb198ab229eb5e866dd1b7` passed the full hosted
[gate](https://github.com/jbone3311/MasterBrain/actions/runs/35908573023)
and populated [logical restore](https://github.com/jbone3311/MasterBrain/actions/runs/35908572905)
in PR #25. FileOS cutover remains gated.

## Proposed archive-ledger integrity checkpoint

ADR-099 precedes additive migration 0033 on an isolated branch from the green
schema/FileOS integration head. It adds deferred child-insert balance checks,
preflights old inventory ledgers, validates provenance output documents and binds
archive text/document/image receipt parent versions to the exact inventory.
Regression tests cover late member/skip inserts, wrong-parent text receipt,
provenance output, all three FK definitions, and a disposable pre-existing bad
child ledger. Local PostgreSQL is unavailable. No production data repair,
FOS-Master edit or cutover is included.
The first hosted [CI 35897067189](https://github.com/jbone3311/MasterBrain/actions/runs/35897067189)
found only test-harness assumptions: an older migration-list fixture omitted 0033,
an image-receipt catalog assertion expected five rather than six foreign keys,
and the new disposable-upgrade test attempted to use an owner role as a runtime
role. Its populated [restore 35897067297](https://github.com/jbone3311/MasterBrain/actions/runs/35897067297)
passed. The follow-up gives the synthetic upgrade its own non-owner runtime role
and updates both catalog expectations. Corrected runtime head `f0064b8` passed
[CI 35897626535](https://github.com/jbone3311/MasterBrain/actions/runs/35897626535):
**2,741 Python passed, nine expected skips, two upstream warnings**, plus lint,
mypy, browser, deployment, documentation inventory (185 Markdown files and 979
local links), API image and restricted-worker gates. The exact head also passed
[populated restore 35897626540](https://github.com/jbone3311/MasterBrain/actions/runs/35897626540).
These are synthetic database and worker gates, not a production upgrade or donor
cutover. PR review and final documentation-head verification remain.

## Combined schema/FileOS integration checkpoint

The isolated integration branch merges #12–#13 into the exact green #22 FileOS
head without rewriting applied migrations or FOS-Master. Migration order is
0029 migration-integrity repair, 0030 truncate guards, 0031 FileOS policy
identity and 0032 FileOS root binding. Four textual conflicts in progress,
receipt, decision and populated-upgrade test files were reconciled by retaining
both branches' content and sorting the expected migrations. Local focused tests:
**58 passed, 33 PostgreSQL skips** without a disposable database. Ruff check and
format, mypy across 82 source files, documentation inventory (184 Markdown files,
973 paths/fragments) and diff whitespace passed. The first combined
[CI 35892717228](https://github.com/jbone3311/MasterBrain/actions/runs/35892717228)
reached the PostgreSQL suite and found a test-fixture migration-list mismatch:
the PR #13 fixture expected only 0030 after its pre-0030 seed, while the combined
branch correctly also applies 0031 and 0032. The fixture expectation was extended
without changing migration behavior. First combined
[restore 35892717493](https://github.com/jbone3311/MasterBrain/actions/runs/35892717493)
passed. Corrected head `9790b80` passed
[CI 35893316583](https://github.com/jbone3311/MasterBrain/actions/runs/35893316583):
**2,738 Python passed, nine expected skips, two upstream warnings**, plus lint,
mypy, browser, deployment, documentation, API-image and restricted-worker gates.
[Populated restore 35893316454](https://github.com/jbone3311/MasterBrain/actions/runs/35893316454)
passed. This verifies the combined synthetic migration/application stack, not a
production upgrade or FileOS cutover. Factory PR #11's competing 0029 is not included; its independent
schema/workflow findings are tracked as a separate follow-up.

## FileOS physical-root binding checkpoint

ADR-098 preceded the runtime change. A versioned SHA-256 of the resolved root
path bytes, device and inode is carried only in the private snapshot, source row
and completed-run receipt. Scanner and publisher rechecks, intake source locking,
new-insert SQL constraints and legacy-unknown preservation are implemented on
`codex/masterbrain-fileos-root-binding` in PR #22. A different physical root
must fail before intake or absence. Local FileOS and restore
unit suites passed **85 tests**; the focused FileOS/PostgreSQL/recovery selection
passed **55 with nine PostgreSQL skips** because no disposable database is
configured. Ruff check/format and the documentation inventory (180 Markdown files,
963 local paths/fragments) passed. The pinned 3,000-file synthetic donor shadow
reported 3,002 common hash/size matches, the same six known policy differences,
and a 1,502-row donor mass-prune refusal. The unscoped local full-suite collection
was interrupted after a prolonged filesystem stall. Runtime head `10a2597`
passed [hosted CI 35890079983](https://github.com/jbone3311/MasterBrain/actions/runs/35890079983):
**2,721 Python passed, nine expected skips, two upstream warnings**, plus lint,
mypy, browser, deployment, documentation, API-image and restricted-worker gates.
[Populated restore 35890079939](https://github.com/jbone3311/MasterBrain/actions/runs/35890079939)
passed. These are synthetic gates, not live-source parity or cutover proof. No
FOS-Master edit, source effect, donor-policy switch, legacy rebaseline or cutover
is included.

## Local FileOS exclusion-ledger checkpoint

ADR-097 preceded implementation. The snapshot now emits an exact bounded ledger of
excluded file/directory locators, kinds and closed reasons; completion validates it
and refuses a missing prior item covered by an exclusion or intentional no-follow
symlink skip before committing receipt/absence. The manifest hash binds this ledger
to existing immutable receipts. No SQL migration, donor edit, membership-policy
switch, source effect or cutover is included. Synthetic unit and disposable-PostgreSQL
tests cover malformed ledgers and one-item oversize/symlink/directory transitions
versus genuine deletion. Focused local pytest: **35 passed, three PostgreSQL skips**
without a disposable local database, 70 deselected and two upstream warnings.
Ruff check/format and the documentation inventory (179 Markdown files, 955 local
links) passed. Local mypy's normal cache failed with a disk-I/O error; the fresh
no-incremental run was interrupted after prolonged local filesystem delay.
Hosted [CI 35885818478](https://github.com/jbone3311/MasterBrain/actions/runs/35885818478)
on runtime head `0bd6319` passed **2,712 Python tests, nine expected skips,
two upstream warnings**, plus type, browser, deployment, documentation, API-image
and restricted-worker gates. Populated
[restore 35885818538](https://github.com/jbone3311/MasterBrain/actions/runs/35885818538)
passed. Root binding, forged-manifest
resistance, legacy baseline and live-shadow acceptance remain open.
The pinned 3,000-file synthetic donor shadow still reports 3,002 common SHA/size
matches, exactly six known policy differences, and a 1,502-row donor mass-prune
refusal. This is not a live-source or snapshot-policy parity claim.

## Local FileOS inventory-policy checkpoint

ADR-096 preceded migration 0031 and the completion change. New snapshots label
their policy version; a canonical digest of the exact membership policy is saved
with each new immutable completion receipt. Unknown historical policy or changed
policy refuses a new completion before absence inference. Legacy receipts are not
backfilled; no force flag or donor policy switch is added. Unit and PostgreSQL
tests cover digest stability/drift, malformed policy, SQL new-insert enforcement,
replay and consecutive-run absence. Local focused pytest: **24 passed, 3
PostgreSQL tests skipped** (no local disposable database), 77 deselected, two
upstream deprecation warnings. Ruff check/format and diff whitespace checks passed.
The documentation inventory passed (178 Markdown files, 947 local links). The
pinned donor shadow run preserved 3,002 common hash/size matches, exactly six
known policy differences and the 1,502-row donor mass-prune refusal. Hosted
PostgreSQL, full CI and populated restore are pending; no cutover is implied.

The first hosted [restore 35874676362](https://github.com/jbone3311/MasterBrain/actions/runs/35874676362)
stopped in its migrate-and-seed phase (the drill suppresses sensitive exception
details). Inspection found that its synthetic FileOS seed still supplied the old
single-field policy. The seed now uses the same full versioned policy constructor
as the snapshot; the corrected restore run below confirms the repair.
The first [CI 35874676274](https://github.com/jbone3311/MasterBrain/actions/runs/35874676274)
passed the new PostgreSQL policy regression but failed an older populated-upgrade
test whose literal expected migration list ended at 0028. That expectation now
includes 0031. A separate disposable-database regression now seeds a legacy
FileOS receipt before 0031, proves it remains null/immutable after the additive
upgrade, and rejects a new digestless receipt. After the correction, focused local
policy/coverage/recovery pytest reported **26 passed, 1 PostgreSQL skip**, 17
deselected and two upstream warnings. Ruff check/format and the updated
documentation inventory (178 files, 949 links) passed locally. Hosted CI
and restore both completed successfully on corrected runtime head
`26fd5b2`: [CI 35879001222](https://github.com/jbone3311/MasterBrain/actions/runs/35879001222)
passed **2,700 Python tests, nine expected skips, two upstream warnings** and the
browser, deployment, documentation, API-image and restricted-worker gates;
[populated restore 35879001244](https://github.com/jbone3311/MasterBrain/actions/runs/35879001244)
passed. These hosted results verify the corrected runtime, including the synthetic
legacy-upgrade regression; they do not validate a live source, donor policy switch,
root binding or a transition for historical receipts with unknown policy.

## Local FileOS mass-loss checkpoint

ADR-095 records the pinned donor's mass-prune threshold as a fail-closed
MasterBrain completion guard. A newly proposed run missing at least 10 prior
items and at least half the previous complete inventory rolls back its completion
and absence transaction. A lower-level import may remain for diagnosis; there is
no force override, policy switch or donor change. Synthetic threshold and
20→10 refusal / 20→12 acceptance regression tests are included. Local focused
pytest: **6 passed, 2 PostgreSQL tests skipped** (no local test database), 78
deselected, two upstream deprecation warnings. Ruff check/format passed, as did
the documentation inventory (177 Markdown files, 940 links). This alone was not a
PostgreSQL gate pass.

First hosted [CI 35868676705](https://github.com/jbone3311/MasterBrain/actions/runs/35868676705)
ran the PostgreSQL case and exposed a synthetic-fixture defect: rewriting two
unchanged files gave their existing content-derived versions new `mtime_ns`
metadata, which the append-only source-version contract correctly refused. The
test now moves the fictional files outside the scanned root and moves two back,
preserving their metadata. The [restore 35868676442](https://github.com/jbone3311/MasterBrain/actions/runs/35868676442)
passed on the first head. Corrected runtime head `c10a9a0` passed full
[CI 35869402539](https://github.com/jbone3311/MasterBrain/actions/runs/35869402539)
with **2,689 Python passed, 9 expected skips, 2 upstream warnings**, all browser,
deployment, documentation and restricted-worker gates, and populated
[restore 35869402685](https://github.com/jbone3311/MasterBrain/actions/runs/35869402685).
No production behavior was changed to accommodate the fixture. Review, policy
identity and a legitimate-large-removal approval path remain before cutover.

## Local FileOS completion-coverage checkpoint

ADR-094 preceded the code change. A completion-only DataCore validator checks the
manifest error ledger/count and refuses uncertain directory, file, race, boundary
or unknown errors; only an explicit no-follow symlink skip is tolerated. The private
publisher checks before database setup/import, and direct storage completion checks
again. Twenty-four focused unit/controller tests passed locally, and Ruff passed.
A synthetic PostgreSQL regression for clean → incomplete → clean consecutive runs
passed in hosted [CI 35863559605](https://github.com/jbone3311/MasterBrain/actions/runs/35863559605)
on runtime head `d7e698e` (2,682 Python passed, nine expected skips, two upstream
warnings; browser/deployment/restricted-worker gates also passed). The populated
[restore 35863559359](https://github.com/jbone3311/MasterBrain/actions/runs/35863559359)
passed. No schema, donor or source-policy change is part of this tranche.

## Local FileOS scanner-edge safety checkpoint

Fourteen focused shadow tests passed with the pinned donor checkout. New cases
simulate a dataless flag without reading source bytes, an unreadable directory
after a prior donor scan, donor-side content mutation during hashing, and four
unusual valid filenames. The donor silently removed its one old row when the
directory vanished from its walk, and its hash-time race stored the old size with
the new digest. MasterBrain recorded a directory error and the subsequent stable
snapshot showed the size mismatch. The filename locators round-tripped through
both inventories and JSON. These are local synthetic observations, not real cloud
or cross-platform acceptance. Hosted
[CI 35857585834](https://github.com/jbone3311/MasterBrain/actions/runs/35857585834)
passed on PR #17's code head `1845d5f`; the donor-specific comparisons skip on
hosted CI because there is no donor checkout. Integrated inventory policy remains
pending; no donor CLI/default database/registry or MasterBrain publication ran.

## Local FileOS scanner fault/size boundary checkpoint

On a separate branch stacked above PR #15, ten focused shadow tests passed with
the pinned FOS-Master checkout. Sparse 100 MiB + 1 and 2 GiB + 1 byte files
confirmed the shared 100 MiB exclusion versus donor hash and donor metadata-only
row respectively. A forced donor read failure retained the prior row, while the
shared snapshot reported `file_unreadable`; a synthetic hash-time content change
reported `changed_during_scan`. Broken-file and directory symlink outcomes were
checked. The test used a temporary fictional root and in-memory donor SQLite only;
no donor CLI, configured database, registry or MasterBrain publication ran.
Hosted [CI 35855259654](https://github.com/jbone3311/MasterBrain/actions/runs/35855259654)
passed on PR #16's fault-test commit `ad50578` (Python, browser, deployment,
documentation and restricted-worker gates). Hosted CI has no donor checkout, so
its donor-specific tests skip; the 22-test live-donor result is local. PR #16 does
not match the restore workflow's path filter. The remaining adversarial cases and
integrated policy gate are pending.

## Verified FileOS whole-inventory shadow checkpoint

ADR-093 precedes the synthetic-only scanner comparison. The pinned donor scanner
`scan_domains.py` and shared `snapshot_tree` were exercised on 3,000 generated files
plus fixed edge cases. **3,002 common SHA-256/size matches** and exactly six
reason-coded policy differences were observed. Replay stayed unchanged; one content
change updated one donor row; one removal removed one; no-hash deferred 3,002
otherwise-common records and rehash backfilled all 3,004 donor rows. After a mass
loss, the donor refused to prune 1,502 rows, all absent from the fresh snapshot.
The donor followed and hashed two synthetic symlinks, including one outside the
synthetic root; MasterBrain skipped both. No real outside-root file was read.
Seven focused tests and local lint passed. No donor CLI, configured donor database,
registry, MasterBrain publication or live source was used. These are local synthetic
results. Hosted [CI 35852211467](https://github.com/jbone3311/MasterBrain/actions/runs/35852211467)
passed on PR #15's synchronized head `16d9cab`, with 2,669 Python tests passing,
two expected donor-checkout skips, and two upstream warnings. The browser,
deployment, documentation and restricted-worker gates also passed. The donor
comparison itself remains local because CI has no FOS-Master checkout. PR #15 did
not trigger a restore drill under its path filters; the underlying PR #14
[restore 35852112586](https://github.com/jbone3311/MasterBrain/actions/runs/35852112586)
passed. Adversarial boundary coverage and policy integration remain pending.

## Verified FileOS inventory-classifier parity checkpoint

Pinned FOS-Master `218d5caec2f20b9047fd3eb8e027dc671acf0c15` classifier
SHA-256 is `12110b1b5404c31172d65878a9327bf8f415f8d343b668aa5982948c840da437`.
The copied DataCore classifier adds only two type-check comments in its standalone
self-test; removing them reproduces the exact donor hash.
The explicit read-only donor harness compared 3,000 synthetic paths and reported
zero mismatches across file, directory, operational-directory, path-reason and prune
contracts. Twelve focused Python tests, lint and the 173-file/920-link documentation
check passed locally. Runtime/provenance correction `4410a45` and test-import
correction `b86b791` passed hosted
[CI 35848399796](https://github.com/jbone3311/MasterBrain/actions/runs/35848399796)
and [restore 35848399781](https://github.com/jbone3311/MasterBrain/actions/runs/35848399781)
on [PR #14](https://github.com/jbone3311/MasterBrain/pull/14). Hosted CI passed
2,663 Python tests with one expected live-donor skip (no FOS checkout in CI), two
upstream warnings and the deployment/worker gates. This is an extracted classifier,
not scanner/snapshot integration, whole-inventory parity or production cutover.
Independent review and integration are pending.

## Verified protected-record truncation guards proposal

Design **f2756b3**, runtime/tests **99d5783** and test correction **02052da**
passed [CI 35844322327](https://github.com/jbone3311/MasterBrain/actions/runs/35844322327)
and [restore 35844322318](https://github.com/jbone3311/MasterBrain/actions/runs/35844322318)
on separate [PR #13](https://github.com/jbone3311/MasterBrain/pull/13), stacked
on PR #12. Hosted CI passed **2,669 Python tests** with two upstream warnings,
browser contracts, documentation/deployment checks and restricted worker/container
gates. The populated restore passed. Thirteen focused disposable-PostgreSQL 17 tests
passed locally.

- Forward-only migration 0030 refuses direct and foreign-key-cascaded `TRUNCATE` on
  the 56 directly row-guarded append-only tables, two protected approval-job tables
  and audited external identities. Catalog coverage is exact for this baseline.
- Tests reproduced the pre-0030 gap on disposable data, checked all 59 protected
  targets with `CASCADE`, retained synthetic rows/history, runtime privilege denial,
  legitimate row transitions and replay. No real evidence or production database
  was touched.
- This guards accidental privileged bulk erasure, not malicious table owners who
  can disable triggers. PR review and integration remain pending; FOS-Master is
  unchanged.

## Verified migration-integrity repair proposal

Design commit **16b0de3** and runtime commit **fc2a329**, followed by validation
note **bea8c5e**, passed [CI 35839648723](https://github.com/jbone3311/MasterBrain/actions/runs/35839648723)
and [restore 35839648689](https://github.com/jbone3311/MasterBrain/actions/runs/35839648689)
on the separate [PR #12](https://github.com/jbone3311/MasterBrain/pull/12)
branch. Hosted CI passed **2,656 PostgreSQL-backed Python tests**, browser contracts,
deployment/document checks and every restricted worker/container gate. The populated
PostgreSQL 17 restore passed. Locally, four focused disposable-PostgreSQL tests and
the full 397-test PostgreSQL-marked suite passed.

- A non-superuser, non-`BYPASSRLS` owner is rejected before any migration ledger or
  schema write. The focused corpus reproduces the historical 0006 silent omission
  under forced RLS.
- Forward-only migration 0029 repeats the parser-provenance mismatch guard and
  repairs only missing sync-state keys across tenants; existing states and event
  pointers remain untouched. A mismatch rolls the migration back with no receipt.
- Previously applied migration checksums, runtime privileges and the pinned
  FOS-Master donor are unchanged. This is a reviewed-branch proposal, not a
  production database repair or FileOS cutover. Independent review and integration
into the foundation remain pending.

## Verified private archive-image OCR command

Checkpoint 5C design revision **3d9b9b9** and runtime revision **f658ace** passed
[CI 35836198307](https://github.com/jbone3311/MasterBrain/actions/runs/35836198307)
and [restore 35836198414](https://github.com/jbone3311/MasterBrain/actions/runs/35836198414),
observed 2026-09-23 Pacific. Hosted CI passed **2,652 PostgreSQL-backed Python tests**,
**134 browser contracts** and every restricted worker/container gate. The populated
restore passed. These results do not establish live-source or production acceptance.

- The private `masterbrain fileos archive-image` command requires one explicit
  inventory/member/key, a distinct pinned OCR image, exact worker scopes,
  non-consuming check mode, current forced-RLS selection and reauthentication around
  the existing two-worker composition and 5B publication.
- Normal output is limited to opaque identities, chunk count and replay state.
  Blank, deferred, failed and unsupported OCR do not publish. Controller, CLI and
  PostgreSQL regression tests cover the command; hosted restricted worker/container
  gates remain green.
- FOS-Master remains pinned at
  `218d5caec2f20b9047fd3eb8e027dc671acf0c15`. The separate
  [Claude 5D issue](https://github.com/jbone3311/MasterBrain/issues/10) requests an
  independent review of 5B persistence and a proposed current-only OCR search layer.
  The issue is open; Claude has not submitted a branch or PR yet.

## Verified archive-member image OCR persistence

Design revision **16d452a**, runtime revision **760a644** and correction revision
**63b478d** passed
[CI 35833506295](https://github.com/jbone3311/MasterBrain/actions/runs/35833506295)
and [restore 35833506298](https://github.com/jbone3311/MasterBrain/actions/runs/35833506298),
observed 2026-09-23 Pacific.

- Only a complete nonempty, exact-target `bounded_image_ocr_v1` result may publish.
  The forced-RLS transaction reconstructs and locks the current parent/inventory/member,
  writes deterministic child evidence/document/chunks, and records a separate immutable
  image receipt plus provenance binding both sandbox contracts, processor digest,
  format, dimensions, mode, frame policy, truncation, chunking and code revision.
- Exact, fresh equivalent-key and concurrent replay converge without duplicate derived
  data. New equivalent keys cross the current-parent fence; changed keys/requests,
  stale parents, cross-tenant targets and row mutation fail closed. A later processor
  may create a new derivative without changing raw child source identity. Blank,
  deferred and failed OCR create no rows.
- Local verification passed **2,248 tests** with 392 explicit PostgreSQL/container
  skips, 31 focused wrapper/composition cases, strict typing, lint, documentation and
  deployment gates. Hosted CI and deployment each passed **2,640 Python tests** with
  PostgreSQL and no skips, **134 browser contracts**, and every restricted-container
  gate including the four-case real archive-plus-image chain.
- The first hosted runtime run failed at the intended boundary because the new table
  was absent from the explicit runtime grants. Correction `63b478d` added only its
  SELECT/INSERT grants. Parallel review also found and corrected stale fresh-key replay,
  processor-dependent child metadata and missing explicit image-contract/policy
  provenance before acceptance.
- Documentation before this receipt covered **170 Markdown files / 902 local paths
  and fragments**. Populated PostgreSQL 17 restore verified **72 tables / 238 rows /
  two tenants / four encrypted objects / two identity bindings** with equal hashes,
  forced RLS and revocation state.

No raw image/member byte, pixels or EXIF are stored. At the 5B checkpoint, no private
command, current search, preview, batch, scheduler, automatic fan-out, source effect
or FOS-Master cutover was authorized. The accepted 5C command above supersedes only
that historical command limit.

## Verified one-member archive image OCR composition

Design revision **6029240** and runtime revision **b17541d** passed
[CI 35829326066](https://github.com/jbone3311/MasterBrain/actions/runs/35829326066)
and [restore 35829325907](https://github.com/jbone3311/MasterBrain/actions/runs/35829325907),
observed 2026-09-23 Pacific.

- The parent accepts one explicit persisted image member, reopens the current archive
  through the existing no-follow/hash-bound reader, derives the canonical format from
  the validated suffix and sends only the selected bytes to the separate image worker.
  It revalidates the full worker result and immutable processor identity before
  returning bounded in-memory text and metadata.
- Fourteen focused composition tests cover all eight suffix aliases across six static
  formats, nested selection, exact metadata, blank OCR, unsupported/oversize refusal
  before workers, missing source, worker crash, response substitution, format
  masquerade, invalid processor identity and animation policy. The local full suite
  passed **2,231 tests** with 389 explicit PostgreSQL/container skips.
- Hosted CI and deployment each passed **2,620 Python tests** with PostgreSQL and no
  skips, **134 browser contracts**, every prior restricted-container gate and the new
  four-case real two-image chain. The chain proved OCR text, a blank image, animated
  GIF refusal, nested locator, 64 unrelated siblings, source byte/timestamp
  preservation and member-hash substitution refusal.
- Documentation before this receipt covered **168 Markdown files / 897 local paths
  and fragments**. The 29 restore safety tests passed; the unchanged PostgreSQL 17
  shape remains **71 tables / 237 rows / two tenants / four encrypted objects / two
  identity bindings**.

No raw member/image byte or OCR result is persisted or searched. No selector,
operator, batch, scheduler, scanner verdict, automatic fan-out, source effect or
FOS-Master cutover is authorized. The next gate is separately reviewed append-only
publication for one explicit successful result.

## Verified isolated image/OCR worker and donor parity

Design revision **55b4854**, runtime revision **cb6b940**, engine binding **f21e534**
and bounded scratch correction **512185b** passed
[CI 35826212304](https://github.com/jbone3311/MasterBrain/actions/runs/35826212304)
and [restore 35826212333](https://github.com/jbone3311/MasterBrain/actions/runs/35826212333),
observed 2026-09-22 Pacific.

- The separate immutable image accepts only hash/length/suffix/signature-bound,
  single-frame JPEG/PNG/TIFF/BMP/GIF/WebP bytes. It fully decodes before OCR, caps
  input at 8 MiB, pixels at 25 million, Tesseract at 20 seconds, text at 5,000 code
  points/20,000 UTF-8 bytes and response at 64 KiB. It returns no path, EXIF/GPS,
  pixels, command output or exception.
- The container runs non-root with no network, mounts, credentials or capabilities,
  a read-only root and fixed 32 MiB in-memory scratch. Pillow 11.3.0, pytesseract
  0.3.13, Tesseract 5.5.0 and English data 4.1.0-2 are bound; the ordinary API image
  proves those parser dependencies absent.
- Local full-suite verification passed **2,217 tests** with 389 explicit PostgreSQL/
  container skips. Focused resource/protocol tests passed 185 cases. CI and deployment
  each passed **2,606 Python tests** with PostgreSQL and no skips, **134 browser
  contracts**, two real image-container cases and every prior restricted-container
  gate. Documentation covered **166 Markdown files / 888 local paths and fragments**
  before this receipt refresh.
- The first hosted build correctly failed closed on a mismatched Tesseract version;
  the second real OCR run exposed the inherited zero-byte file-write limit. The final
  implementation keeps zero bytes as the default for every older worker and grants
  only image OCR a maximum 32 MiB per file inside the equally bounded scratch area.
- The pinned donor's two focused modules passed **149 tests**. The clean-checkout live
  harness then proved 12 normalized text/blank cases across all six formats, **120
  generated OCR stress comparisons** and one deliberate safer multi-frame refusal.
  The donor remained clean at **218d5caec2f20b9047fd3eb8e027dc671acf0c15**.
- The 29 restore safety tests passed; the unchanged PostgreSQL 17 shape remains **71
  tables / 237 rows / two tenants / four encrypted objects / two identity bindings**.

No raw byte or OCR result is persisted, and no search, operator, batch, scheduler,
scanner verdict, external vision, source effect or FileOS cutover is authorized. The
later 5A receipt above supersedes this section's former composition limitation.

## Verified sealed archive-document batches

Design revision **2869aed** and runtime revision **87ea0d0** passed
[CI 35821165890](https://github.com/jbone3311/MasterBrain/actions/runs/35821165890)
and [restore 35821165886](https://github.com/jbone3311/MasterBrain/actions/runs/35821165886),
observed 2026-09-22 Pacific.

- The closed private plan binds one inventory, exact code revision and 1–100 ordered,
  unique locator/expected-format/idempotency-key triples under a canonical SHA-256
  seal. Suffix and declared PDF/DOCX/XLSX format must agree before database access.
- `masterbrain fileos archive-document-batch` reuses the existing forced-RLS selector,
  hash-bound member reader, isolated document worker and transaction-time publisher.
  It reauthenticates sensitive boundaries, stops at the first refusal and returns only
  indexes/counts and a generic error code.
- Real PostgreSQL committed item one, injected a publication refusal at item two and
  proved item three absent. Retrying the unchanged plan replayed item one and recorded
  items two and three using the original keys; a further retry replayed all three.
  Source archive bytes and timestamp remained unchanged and output exposed no locator,
  format, text or worker metadata.
- CI and deployment each passed **2,594 Python tests** with PostgreSQL and no skips;
  **134 browser contracts** and every restricted-container case passed. Documentation
  covered **164 Markdown files / 881 local paths and fragments**.
- The 29 restore safety tests passed; PostgreSQL 17 restore verified **71 tables / 237
  rows / two tenants / four encrypted objects / two identity bindings** in 16.11
  seconds. FOS-Master remains clean and unchanged at
  **218d5caec2f20b9047fd3eb8e027dc671acf0c15**.

No discovery, generated keys, skip/continue, parallelism, scheduling, public mutation,
images/OCR, source effects or FOS-Master cutover is authorized.

## Verified private archive-document preview

Design revision **ce2bf30** and runtime revision **1651c2b** passed
[CI 35818667860](https://github.com/jbone3311/MasterBrain/actions/runs/35818667860)
and [restore 35818668296](https://github.com/jbone3311/MasterBrain/actions/runs/35818668296),
observed 2026-09-22 Pacific.

- `DataCoreStore.archive_member_document_plan` performs one forced-RLS metadata read
  for an explicitly named current inventory. Exact suffix/media/container and 8 MiB
  fences admit only PDF/DOCX/XLSX candidates; sealed ordinals provide stable bounded
  pages and an ineligible cursor fails closed.
- `masterbrain fileos archive-document-plan` reuses the private configuration and
  exact worker scopes, but constructs neither worker and reads no source/member bytes.
  Check mode does not query a target. Results label replay-deduplicated publication
  state and explicitly declare no source, worker or data effects.
- Real PostgreSQL proved mixed eligible/ineligible selection, paging, receipt replay,
  tenant isolation and parent-replacement refusal. No batch, retry-key generation,
  public route, source effect or automatic continuation was added.
- CI and deployment each passed **2,586 Python tests** with PostgreSQL and no skips;
  **134 browser contracts** and every prior restricted-container case passed.
  Documentation covered **162 Markdown files / 874 local paths and fragments**.
- The 29 restore safety tests passed; PostgreSQL 17 restore verified **71 tables / 237
  rows / two tenants / four encrypted objects / two identity bindings** in 18.56
  seconds. FOS-Master remains clean and unchanged at
  **218d5caec2f20b9047fd3eb8e027dc671acf0c15**.

The next gate is a separately reviewed, sealed document-batch format and executor.
Images/OCR, automatic fan-out, scheduling, source effects and FOS-Master cutover remain
unauthorized.

## Verified current archive-document search

Design revision **9ba4b88** and runtime revision **7329ba9** passed
[CI 35816277436](https://github.com/jbone3311/MasterBrain/actions/runs/35816277436)
and [restore 35816277514](https://github.com/jbone3311/MasterBrain/actions/runs/35816277514),
observed 2026-09-22 Pacific.

- `DataCoreStore.search_current_archive_documents` returns only an exact published
  PDF/DOCX/XLSX derivative whose immutable receipt, sealed inventory/member, current
  parent FileOS version, child version/evidence and normalized document all agree.
  Parent replacement removes the result from current search without deleting retained
  evidence; replay cannot duplicate a result and foreign tenants see nothing.
- `/v1/brain/current-search` exposes a distinct `archive_documents` layer with a
  strict 1–20 limit, independent rank and explicit partial-coverage label. It returns
  only compact search fields and opaque child locators; ordinary FileOS, archive text,
  Email-family, KnowledgeCore and retained-history behavior remains separate.
- Migration `0027_current_archive_document_search.sql` adds only the tenant-leading
  receipt lookup index. The read creates no workers, source reads, generations,
  receipts, evidence, chunks or source effects.
- CI and deployment each passed **2,583 Python tests** with PostgreSQL and no skips;
  **134 browser contracts**, five MIME-container, 15 Email PDF-container, five FileOS
  document-container, two archive-inventory, two archive-member and four chained
  archive-document cases passed. Documentation covered **160 Markdown files / 867
  local paths and fragments**.
- The 29 restore safety tests passed; PostgreSQL 17 restore verified **71 tables / 237
  rows / two tenants / four encrypted objects / two identity bindings** in 20.86
  seconds. The pinned donor's **47 archive tests**, six-case live archive parity and
  3,000-file hash/dedupe/text/Office stress parity passed locally. FOS-Master remains
  clean and unchanged at **218d5caec2f20b9047fd3eb8e027dc671acf0c15**.

This does not authorize archive enumeration, document preview/batches, images/OCR,
automatic fan-out, scheduling, source effects or FOS-Master cutover.

## Verified archive-member PDF and Office derivatives

Design revision **ea6fd29**, orchestration **6680218**, selector/receipt revision
**0210ad1**, publication **4d098fa**, private command **5bb1aa1** and real two-image
gate **49b8383** passed
[CI 35810970182](https://github.com/jbone3311/MasterBrain/actions/runs/35810970182)
and [restore 35810970151](https://github.com/jbone3311/MasterBrain/actions/runs/35810970151),
observed 2026-09-22 Pacific. Revision **a4af448** corrects one refusal assertion and
changes no runtime behavior.

- One exact current PDF, DOCX or XLSX member crosses the existing hash-bound archive
  member reader and then the separate bounded document worker. Neither image sees both
  the source tree and sibling/document parsing authority; raw member bytes remain
  bounded in parent memory and are never persisted.
- Migration `0026_archive_member_documents.sql` adds a separate forced-RLS,
  append-only receipt. The publication transaction locks and reconstructs the current
  parent/inventory/member identity, then records deterministic child evidence,
  normalized document/chunks and provenance binding both immutable processors.
- `masterbrain fileos archive-document` requires both immutable image IDs, exact shared
  scopes and repeated authorization. Check mode constructs neither worker and inspects
  no target. Normal output is content-free and exact-key retry converges on one receipt.
- CI and deployment each passed **2,582 Python tests** with PostgreSQL and no skips;
  **134 browser contracts**, five MIME-container, 15 Email PDF-container, five FileOS
  document-container, two archive-inventory and two archive-member cases passed. The
  new four-case chained-image gate extracted PDF/DOCX/XLSX with 64 unrelated siblings,
  preserved source bytes/timestamps and refused member-hash substitution.
  Documentation covered **158 Markdown files / 865 local paths and fragments**.
- The 29 restore safety tests passed; PostgreSQL 17 restore verified **71 tables / 236
  rows / two tenants / four encrypted objects / two identity bindings** in 15.27
  seconds. FOS-Master remains clean and unchanged at
  **218d5caec2f20b9047fd3eb8e027dc671acf0c15**.

The derivatives remain retained-history-only. Current-search activation, preview,
batching, images/OCR, recursion, automatic fan-out and FileOS cutover are separate
future gates.

## Verified append-only archive manifest persistence

Design revision **2d30728**, runtime revision **03dbb98** and upgrade-expectation
correction **08ccb68** passed
[CI 35783950712](https://github.com/jbone3311/MasterBrain/actions/runs/35783950712)
and [restore 35783950915](https://github.com/jbone3311/MasterBrain/actions/runs/35783950915),
observed 2026-09-22 Pacific.

- Migration `0023_archive_manifests.sql` adds forced-RLS, append-only inventory,
  ordered-member, ordered-skip and actor-scoped replay tables. A deferred database
  trigger seals row counts and aggregate observed bytes to the parent inventory.
- The store accepts only validated complete/partial hash manifests for the exact
  current FileOS source version and immutable archive image. Bomb, duplicate,
  unsupported and invalid results create no rows. Deterministic result drift, stale
  parents and key reuse fail closed.
- Real PostgreSQL proved exact replay, concurrent replay, RLS isolation, runtime
  mutation denial, stale-parent and drift conflicts, and unchanged search/change-feed
  state. No evidence, document, chunk, change-event or index row is created.
- The first hosted run passed 2,507 tests and found one explicit populated-upgrade
  migration list still ending at `0022`; `08ccb68` added `0023` to that expectation.
  The corrected run passed **2,508 Python tests** with PostgreSQL and no skips, **134
  Node contracts**, documentation, deployment and every restricted worker.
- The 29 restore safety tests passed; PostgreSQL 17 restore verified **69 tables / 233
  rows / two tenants / four encrypted objects / two identity bindings** in 17.14
  seconds. FOS-Master remains clean and unchanged at the pinned commit.

No member bytes or archive-derived search visibility exist yet. The next gate is a
separate, one-member, persisted-hash-bound read contract.

## Verified isolated FileOS archive inventory

Design revision **2aaeb26** and runtime revision **26473de** passed
[CI 35780244211](https://github.com/jbone3311/MasterBrain/actions/runs/35780244211)
and [restore 35780244282](https://github.com/jbone3311/MasterBrain/actions/runs/35780244282),
observed 2026-09-22 Pacific.

- A closed source-bound contract and dedicated in-memory ZIP/TAR worker return only
  ordered safe locators, hashes, declared/observed sizes, media hints, nesting
  provenance, skips and bounded accounting. They return no member bytes or text and
  publish nothing to the database or search.
- The worker preserves the donor's 256 MiB cumulative, 64 MiB member, 2,000-file,
  100x ratio and depth-three expansion limits, with a separate 32 MiB compressed-input
  cap. Traversal, links, encryption, corruption, depth and unsupported formats are
  explicit. Bombs and duplicate safe identities publish no child manifest.
- The live harness passed flat ZIP/TAR, nested and filtered cases against unchanged
  FOS-Master commit `218d5caec2f20b9047fd3eb8e027dc671acf0c15`, plus named assertions
  for safer bomb and duplicate publication policies. The donor's 47-test archive suite
  also passed and its checkout remained clean.
- Local checks passed **2,137 Python tests**, with 368 database/container cases
  intentionally skipped, **134 Node contracts**, lint, strict typing across 71 source
  files, the documentation gate and the focused 90-test archive/isolation set.
- CI passed **2,505 Python tests** with PostgreSQL and no skips, all 134 Node contracts,
  prior restricted workers, the new immutable archive image build and two real
  source-bound archive-container cases. Documentation covered 142 Markdown files / 810
  local paths and fragments.
- The 29 restore safety tests passed; PostgreSQL 17 restore verified **65 tables / 232
  rows / two tenants / four encrypted objects / two identity bindings** in 23.97
  seconds. No schema or source checkout changed in this tranche.

Remaining archive work is deliberately separate: append-only tenant-isolated manifest
persistence, then a hash-bound one-member read contract, then explicit extraction and
search publication. No FileOS cutover is authorized.

## Verified sealed Email attachment/document batches

Design revision **2825529** and runtime revision **c143e0c** passed
[CI 35774641187](https://github.com/jbone3311/MasterBrain/actions/runs/35774641187)
and [restore 35774641102](https://github.com/jbone3311/MasterBrain/actions/runs/35774641102),
observed 2026-09-22 Pacific.

- `masterbrain email bridge-parts-batch` accepts one owner-private, canonical-digest
  plan containing one account, one attachment or approved-document kind, the exact
  configured revision and 1–100 ordered unique target/key pairs. Kind is part of the
  digest, so a plan cannot mix dependency levels.
- Batch-only account fencing leaves existing one-item receipt/replay ordering intact.
  Execution reauthenticates before each accepted one-item transaction, stops at the
  first refusal and returns only opaque target identities and counts.
- Real PostgreSQL injected an attachment refusal at item two, proved exactly one
  immutable receipt existed, then retried the unchanged plan to replay one and record
  two. A separately sealed approved-document plan recorded and replayed without
  changing legacy evidence.
- CI and deployment each passed **2,469 Python tests** with PostgreSQL and no skips;
  **134 Node contracts**, five MIME-container, 15 Email PDF-container and five FileOS
  document-container cases passed. Documentation covered **140 Markdown files / 804
  local paths and fragments**.
- The 29 restore safety tests passed; PostgreSQL 17 restore verified **65 tables / 232
  rows / two tenants / four encrypted objects / two identity bindings** in 23.58
  seconds. FOS-Master remains unchanged at
  **218d5caec2f20b9047fd3eb8e027dc671acf0c15**.

## Verified Email attachment/document bridge preview

Runtime revision **e3c0ee5** plus checkpoint-tracking revision **0c687e8** passed
[CI 35763636718](https://github.com/jbone3311/MasterBrain/actions/runs/35763636718)
and [restore 35763636696](https://github.com/jbone3311/MasterBrain/actions/runs/35763636696),
observed 2026-09-22 Pacific.

- `masterbrain email bridge-parts-plan` exposes separate 1–100 item attachment and
  approved-document pages for one explicit account. It returns only opaque legacy
  identities, stable timestamps, state, bridge labels and a kind-specific cursor.
- Real PostgreSQL proves the full dependency chain: no attachment before its current
  message bridge, no document before its attachment bridge, completed approval
  required, duplicate completed approvals collapse to one extraction, one-item bridge
  results update labels, and quarantine removes both queues.
- Check mode authenticates and validates the safe database role without reading a
  target account. The normal read is tenant-scoped and performs no source/provider
  access, byte read, approval, reservation or bridge write.
- CI and deployment each passed **2,458 Python tests** with PostgreSQL and no skips;
  **134 Node contracts**, five MIME-container, 15 Email PDF-container and five FileOS
  document-container cases passed. Documentation covered **139 Markdown files / 803
  local paths and fragments**.
- The 29 restore safety tests passed; PostgreSQL 17 restore verified **65 tables / 232
  rows / two tenants / four encrypted objects / two identity bindings** in 15.74
  seconds. FOS-Master remains unchanged at
  **218d5caec2f20b9047fd3eb8e027dc671acf0c15**.

## Verified sealed Email message bridge batches

Runtime revision **0fd8c35** and legacy one-item idempotency compatibility correction
**7ca0568** passed
[CI 35759175176](https://github.com/jbone3311/MasterBrain/actions/runs/35759175176)
and [restore 35759175355](https://github.com/jbone3311/MasterBrain/actions/runs/35759175355),
observed 2026-09-22 Pacific.

- `masterbrain email bridge-batch` accepts one owner-private, canonical-digest-bound
  plan containing one account, the exact configured revision and 1–100 ordered unique
  message-version/idempotency-key pairs. Check mode validates without target lookup or
  data effects; execution reauthenticates before every existing one-item transaction.
- Unit and CLI tests prove closed schema, digest, private-file, revision, duplicate,
  scope, ordered-dispatch and content-free receipt contracts. Real PostgreSQL injected
  a failure on item two, proved only item one had a receipt, then retried the unchanged
  plan to replay one and record two without duplication.
- The first hosted run found a backward-compatibility regression: account fencing had
  moved target lookup ahead of legacy one-item idempotency lookup. Revision `7ca0568`
  keeps the batch account fence while restoring the established one-item replay and
  conflict ordering; the corrected full gate is green.
- CI and deployment each passed **2,454 Python tests** with PostgreSQL and no skips;
  **134 Node contracts**, five MIME-container, 15 Email PDF-container and five FileOS
  document-container cases passed. Documentation covered **138 Markdown files / 802
  local paths and fragments**.
- The 29 restore safety tests passed; PostgreSQL 17 restore verified **65 tables / 232
  rows / two tenants / four encrypted objects / two identity bindings** in 16.05
  seconds.
- The operator does not discover messages, follow preview cursors, skip refused items,
  bridge attachments/documents, contact a provider or change a mailbox. Existing
  immutable one-item receipts are the retry authority. FOS-Master remains unchanged at
  **218d5caec2f20b9047fd3eb8e027dc671acf0c15**.

## Verified private Email bridge backfill preview

Runtime revision **4c3347c** and current-version transition assertion correction
**e9cf62f** passed
[CI 35756327120](https://github.com/jbone3311/MasterBrain/actions/runs/35756327120)
and [restore 35756327113](https://github.com/jbone3311/MasterBrain/actions/runs/35756327113),
observed 2026-09-22 Pacific.

- `masterbrain email bridge-plan` reads one explicit account through the same private
  closed configuration and exact worker scopes as the one-item bridge. It returns a
  1–100 item page containing only version UUID, recorded time, already-bridged state
  and next cursor; `--check` does not inspect the account.
- PostgreSQL proves stable `(recorded_at, version_id)` pagination, bridged labeling,
  current-version replacement after update, quarantine/delete exclusion, invalid
  account/cursor refusal and tenant isolation. Controller tests prove exact scopes,
  revocation checks and content-free output.
- The first hosted run exposed an invalid test expectation: after an update the new
  current unbridged version correctly replaces the historical version in the plan.
  Revision `e9cf62f` asserts that identity/state transition; runtime code was unchanged.
- CI and deployment each passed **2,446 Python tests** with PostgreSQL and no skips;
  **134 Node contracts**, five MIME-container, 15 Email PDF-container and five FileOS
  document-container cases passed. Documentation covered **137 Markdown files / 801
  local paths and fragments**.
- The 29 restore safety tests passed; PostgreSQL 17 restore verified **65 tables / 232
  rows / two tenants / four encrypted objects / two identity bindings** in 19.41
  seconds.
- The preview creates no bridge, reserves no work, contacts no provider and grants no
  batch execution authority. FOS-Master remains unchanged at
  **218d5caec2f20b9047fd3eb8e027dc671acf0c15**.

## Verified current-source coverage status

Runtime revision **82012e9** and state-transition stress revision **c2c97da** passed
[CI 35753479059](https://github.com/jbone3311/MasterBrain/actions/runs/35753479059)
and [restore 35753479343](https://github.com/jbone3311/MasterBrain/actions/runs/35753479343),
observed 2026-09-22 Pacific.

- `GET /v1/brain/current-coverage` provides a cursor-bounded, single-transaction view
  over registered opaque sources. FileOS rows report active immutable generation and
  latest completed-run facts; Email rows report only current explicitly bridged
  message/attachment/document counts and newest bridge timestamps.
- The route requires `brain.changes.read`, declares incomplete coverage and never
  enumerates filesystem paths, mailboxes, provider IDs or content. It performs no
  scan, bridge, rebuild, activation or source access.
- PostgreSQL proves no-generation and search-ready FileOS states, active/latest-run
  comparison, pagination, tenant isolation and Email counts across update, bridge,
  quarantine, recovery and deletion. Retained evidence remains available while current
  counts disappear as required.
- CI and deployment each passed **2,442 Python tests** with PostgreSQL and no skips;
  **134 Node contracts**, five MIME-container, 15 Email PDF-container and five FileOS
  document-container cases passed. Documentation covered **136 Markdown files / 800
  local paths and fragments**.
- The 29 restore safety tests passed; PostgreSQL 17 restore verified **65 tables / 232
  rows / two tenants / four encrypted objects / two identity bindings** in 17.91
  seconds.
- The endpoint does not claim a complete mailbox/filesystem inventory or calculate a
  policy-dependent stale threshold. FOS-Master remains unchanged at
  **218d5caec2f20b9047fd3eb8e027dc671acf0c15**.

## Verified grouped current-source search

Runtime revision **8da5b36** and mixed-source assertion correction **7939674** passed
[CI 35751228402](https://github.com/jbone3311/MasterBrain/actions/runs/35751228402)
and [restore 35751228447](https://github.com/jbone3311/MasterBrain/actions/runs/35751228447),
observed 2026-09-22 Pacific.

- `POST /v1/brain/current-search` returns separately bounded and ranked active FileOS,
  current Email message/attachment/document and reviewed KnowledgeCore groups. It
  declares within-group-only rank meaning, independent layer reads and incomplete
  coverage instead of implying a globally comparable or complete answer.
- API tests prove both required scopes, closed bounds/kinds, exact group labels,
  independent limits and missing-group behavior. PostgreSQL returns all three source
  families together while retaining the existing routes and drill-down identities.
- The first hosted run exposed an obsolete test assumption, not a runtime defect:
  retained mixed-source search correctly returned Email as well as FileOS, while the
  fixture required FileOS to rank first. Revision `7939674` now asserts the promised
  presence contract; product code and ranking behavior were unchanged.
- CI and deployment each passed **2,441 Python tests** with PostgreSQL and no skips;
  **134 Node contracts**, five MIME-container, 15 Email PDF-container and five FileOS
  document-container cases passed. Documentation covered **135 Markdown files / 799
  local paths and fragments**.
- The 29 restore safety tests passed; PostgreSQL 17 restore verified **65 tables / 232
  rows / two tenants / four encrypted objects / two identity bindings** in 25.6
  seconds.
- Coverage is intentionally partial: FileOS requires an active immutable generation,
  Email requires explicit current bridges and KnowledgeCore remains reviewed retained
  state. There is no cross-layer atomic snapshot, scan, provider access, synthesis or
  cutover. FOS-Master remains unchanged at
  **218d5caec2f20b9047fd3eb8e027dc671acf0c15**.

## Verified current-only layered Email-family search

Revision **9b427e1** passed
[CI 35749176559](https://github.com/jbone3311/MasterBrain/actions/runs/35749176559)
and [restore 35749176556](https://github.com/jbone3311/MasterBrain/actions/runs/35749176556),
observed 2026-09-22 Pacific.

- `DataCoreStore.search_current_email_family` and
  `POST /v1/brain/email-family-search` return three independently bounded/ranked
  layers: current bridged message text, attachment-receipt text and approved PDF
  derivatives. Results remain compact, untrusted and linked by opaque evidence IDs.
- Every SQL branch rejoins the legacy parent raw/parser version, deletion/quarantine
  state and shared parent/child current pointers. Attachment and approved-document
  receipt identities are cross-checked; same-hash attachment occurrences remain
  distinct. Existing message-only and retained-history searches are unchanged.
- PostgreSQL proved all three layers, independent limits, duplicate occurrences,
  update/delete/quarantine disappearance and retained-history availability. API
  contracts proved `brain.search`, closed request bounds and within-layer-only ranking.
- CI and deployment each passed **2,440 Python tests** with PostgreSQL and no skips;
  **134 Node contracts**, five MIME-container, 15 Email PDF-container and five FileOS
  document-container cases passed. Documentation covered **134 Markdown files / 798
  local paths and fragments**.
- The 29 restore safety tests passed; PostgreSQL 17 restore verified **65 tables / 232
  rows / two tenants / four encrypted objects / two identity bindings** in 16.17
  seconds.
- The route is incomplete by definition because only explicitly bridged Email appears.
  It does not batch/backfill, change legacy Email search, compare ranks across layers or
  access a mailbox. FOS-Master remains unchanged at
  **218d5caec2f20b9047fd3eb8e027dc671acf0c15**.

## Verified private Email attachment/document bridge commands

Revision **6156b70** passed
[CI 35745615962](https://github.com/jbone3311/MasterBrain/actions/runs/35745615962)
and [restore 35745615958](https://github.com/jbone3311/MasterBrain/actions/runs/35745615958),
observed 2026-09-22 Pacific.

- `masterbrain email bridge-attachment` and `masterbrain email bridge-document` accept
  one explicit legacy UUID, the existing private closed config and an idempotency UUID.
  Both require the exact shared ingest/document scopes, perform a non-consuming check,
  reauthenticate around execution and return only opaque IDs, counts/status and replay
  state.
- Unit and command tests prove exact dispatch, scope/config denial, revocation,
  content-free scrubbed output and no target inspection during `--check`. PostgreSQL
  executed both operators through the approved PDF path, then proved shared search,
  replay, RLS, immutability and unchanged legacy evidence behavior.
- CI and deployment each passed **2,439 Python tests** with PostgreSQL and no skips;
  **134 Node contracts**, five MIME-container, 15 Email PDF-container and five FileOS
  document-container cases passed. Documentation covered **133 Markdown files / 796
  local paths and fragments**.
- The 29 restore safety tests passed; PostgreSQL 17 restore verified **65 tables / 232
  rows / two tenants / four encrypted objects / two identity bindings** in 23.71
  seconds.
- The commands do not enumerate Email, approve/process documents, read bytes, contact
  providers, schedule work, mutate mailboxes or redirect legacy search. FOS-Master
  remains unchanged at **218d5caec2f20b9047fd3eb8e027dc671acf0c15**.

## Verified approved Email PDF derivative bridge

Runtime revision **cd425d0** and tenant-isolation fixture correction **c183a07**
passed [CI 35743436225](https://github.com/jbone3311/MasterBrain/actions/runs/35743436225)
and [restore 35743436167](https://github.com/jbone3311/MasterBrain/actions/runs/35743436167),
observed 2026-09-22 Pacific.

- `DataCoreStore.bridge_email_document_extraction` publishes one explicitly selected,
  immutable approved-PDF extraction only after its completed approval and ADR-065
  occurrence bridge are proven current. Extracted or partial bounded text becomes a
  deterministic document/chunks on the existing attachment evidence.
- Migration 0022 adds a forced-RLS, append-only receipt binding the legacy extraction,
  completed approval job, attachment and shared identities to processor, policy,
  revision, result digest and exact bridge provenance. The bridge never loads, parses,
  scans, executes or copies attachment bytes.
- PostgreSQL cases prove prerequisite occurrence fencing, approved publication,
  shared search, exact replay, tenant isolation, immutability and rejection of an
  otherwise valid extraction inserted without a completed approval.
- CI and deployment each passed **2,434 Python tests** with PostgreSQL and no skips;
  **134 Node contracts**, five MIME-container, 15 Email PDF-container and five FileOS
  document-container cases passed. Documentation covered **132 Markdown files / 794
  local paths and fragments**.
- The 29 restore safety tests passed; PostgreSQL 17 restore verified **65 tables / 232
  rows / two tenants / four encrypted objects / two identity bindings** in 16.21
  seconds.
- The first hosted application run exposed only a test-fixture error: the new RLS
  assertion used a nonexistent tenant/member, so bootstrap correctly denied it before
  RLS. Correction `c183a07` created a real second tenant/member; the unchanged product
  path then passed the full gate and restore.
- Existing Email approved-PDF search, citations, approvals and attachment state remain
  authoritative. There is no bridge operator, batch/backfill, new format, byte access,
  global search cutover or mailbox effect. FOS-Master remains unchanged at
  **218d5caec2f20b9047fd3eb8e027dc671acf0c15**.

## Verified additive Email attachment occurrence/text bridge

Runtime revision **02eefb5** and historical-parent fixture correction **aaf8df0**
passed [CI 35740735789](https://github.com/jbone3311/MasterBrain/actions/runs/35740735789)
and [restore 35740736075](https://github.com/jbone3311/MasterBrain/actions/runs/35740736075),
observed 2026-09-22 Pacific.

- `DataCoreStore.bridge_email_attachment` maps one explicit legacy attachment
  occurrence beneath its already-bridged, still-current Email evidence. Deterministic
  child item/version/evidence and `brain_parts` identities preserve occurrences even
  when two attachments share bytes; the retained parent MIME remains authoritative.
- Non-empty legacy extracted text publishes through `email-attachment-text-v1` with
  chunks and provenance. Empty extracted or deferred/skipped/failed/pending receipts
  produce explicit zero-document accounting. The bridge never reads, decodes,
  executes, scans, downloads or copies attachment bytes.
- Migration 0021 adds forced-RLS, append-only `brain_parts` and
  `brain_email_attachment_bridge_receipts`. Tests prove duplicate-occurrence
  preservation, extracted and deferred outcomes, exact replay, historical-parent
  rejection, rollback, tenant isolation and immutability.
- CI and deployment each passed **2,432 Python tests** with PostgreSQL and no skips;
  **134 Node contracts**, five MIME-container, 15 Email PDF-container and five FileOS
  document-container cases passed. Documentation covered **131 Markdown files / 793
  local paths and fragments**.
- The 29 restore safety tests passed; PostgreSQL 17 restore verified **64 tables / 231
  rows / two tenants / four encrypted objects / two identity bindings** in 24.14
  seconds.
- The first hosted application run exposed a test-only history-fixture error: it
  created a different provider message rather than a newer version of the bridged
  parent. Correction `aaf8df0` fixed only the fixture, after which the intended
  current-parent rejection passed. The first restore attempt then failed during
  disposable Docker-cluster startup before migration; the unchanged failed job was
  rerun and passed in 38 seconds.
- Existing Email attachment/document search and citations remain authoritative. There
  is no batch bridge, approved-PDF derivative bridge, byte extraction, global search
  cutover or mailbox effect. FOS-Master remains unchanged at
  **218d5caec2f20b9047fd3eb8e027dc671acf0c15**.

## Verified current-only bridged Email retrieval

Revision **743fb9e** passed
[CI 35737349912](https://github.com/jbone3311/MasterBrain/actions/runs/35737349912)
and [restore 35737349873](https://github.com/jbone3311/MasterBrain/actions/runs/35737349873),
observed 2026-09-22 Pacific.

- `DataCoreStore.search_current_email` and `POST /v1/brain/email-search` return only
  explicitly bridged Email documents whose shared current pointer and legacy immutable
  raw/parser version still agree and whose message is not deleted or quarantined.
- Hosted PostgreSQL proved initial visibility, update-before-rebridge disappearance,
  new-version visibility, bounds, and immediate delete hiding while retained DataCore
  history remains queryable. API contracts prove explicit `brain.search` scope,
  current-visibility labeling and bounded untrusted results.
- Hosted CI and deployment each passed **2,430 Python tests** with PostgreSQL and no
  skips; **134 Node contracts**, five MIME-container, 15 Email PDF-container and five
  FileOS document-container cases passed. Documentation covered **130 Markdown files /
  791 local paths and fragments**.
- The 29 restore safety tests passed; PostgreSQL 17 restore verified **62 tables / 230
  rows / two tenants / four encrypted objects / two identity bindings** in 15.54 seconds.
- The route is additive and incomplete by definition: unbridged Email is absent.
  Legacy Email search remains authoritative. No automatic bridge, attachment migration,
  global ranking, unified-mode redirect or mailbox effect is implied. FOS-Master remains
  unchanged at **218d5caec2f20b9047fd3eb8e027dc671acf0c15**.

## Verified private one-version Email bridge operator

Revision **f600508** passed
[CI 35736010764](https://github.com/jbone3311/MasterBrain/actions/runs/35736010764)
and [restore 35736010659](https://github.com/jbone3311/MasterBrain/actions/runs/35736010659),
observed 2026-09-22 Pacific.

- `masterbrain email bridge` accepts one explicit legacy evidence UUID, private closed
  config and idempotency UUID. It requires an exact two-scope worker, verifies the
  least-privileged database role, reauthenticates around execution and returns only
  opaque identities, counts and replay state.
- `--check` is non-consuming and does not inspect the target. Unit and PostgreSQL
  tests prove closed/private configuration, exact scopes, revocation, scrubbed
  errors/output, real command publication, shared search and unchanged legacy evidence.
- Hosted CI and deployment each passed **2,428 Python tests** with PostgreSQL and no
  skips; **134 Node contracts**, five MIME-container, 15 Email PDF-container and five
  FileOS document-container cases passed. Documentation covered **129 Markdown files /
  790 local paths and fragments**.
- The 29 restore safety tests passed; PostgreSQL 17 restore verified **62 tables / 230
  rows / two tenants / four encrypted objects / two identity bindings** in 23.74 seconds.
- There is no automatic scan, batch, attachment migration, provider call, mailbox
  effect or Email search cutover. FOS-Master remains unchanged at
  **218d5caec2f20b9047fd3eb8e027dc671acf0c15**.

## Verified additive Email evidence bridge into DataCore

Runtime revision **0eae4c4** and least-privilege correction **bb4b45d** passed
[CI 35734147533](https://github.com/jbone3311/MasterBrain/actions/runs/35734147533)
and [restore 35734147551](https://github.com/jbone3311/MasterBrain/actions/runs/35734147551),
observed 2026-09-22 Pacific.

- One explicitly selected current, visible, immutable Email version can now publish
  deterministic opaque source/item/version/evidence/document/chunk identities into
  DataCore. Subject, sender and clean text preserve the legacy lexical fields;
  retained raw MIME stays in its original immutable table and is not copied.
- Migration 0020 adds a forced-RLS, append-only bridge receipt tying the legacy UUID
  to every shared identity and exact transform/code provenance. Exact replay is a
  no-op; changed requests, historical versions, deleted/quarantined messages and
  inconsistent snapshots fail closed. The account lock prevents ingestion races.
- The first hosted run correctly exposed that `SELECT ... FOR SHARE` would require
  broader runtime privileges. Revision `bb4b45d` removed the unnecessary row lock,
  retained advisory serialization and added migration-history coverage; no new
  UPDATE/DELETE/table-owner authority was granted.
- Hosted CI passed **2,414 Python tests** with PostgreSQL and no skips; deployment
  repeated the suite. **134 Node contracts**, five MIME-container cases, 15 Email
  PDF-container cases and five FileOS PDF/DOCX/XLSX cases passed. Documentation
  verification covered **128 Markdown files / 786 local paths and fragments**.
- PostgreSQL 17 restore passed 29 safety tests and verified **62 tables / 230 rows /
  two tenants / four encrypted objects / two identity bindings** in 22.5 seconds.
- Existing Email ingestion/search remains authoritative. No automatic scan, bridge
  operator, attachment migration, current-Email read projection, API cutover or
  mailbox effect is implied. FOS-Master remains unchanged at
  **218d5caec2f20b9047fd3eb8e027dc671acf0c15**.

## Verified current-aware grouped FileOS and KnowledgeCore retrieval

Revision **8bada56** passed
[CI 35731669724](https://github.com/jbone3311/MasterBrain/actions/runs/35731669724)
and [restore 35731669604](https://github.com/jbone3311/MasterBrain/actions/runs/35731669604),
observed 2026-09-22 Pacific.

- `/v1/brain/unified-search` now accepts explicit `retained` or `current_fileos`
  evidence visibility. Retained history remains the compatibility default; current
  mode uses newest activated FileOS generations. Knowledge results and their limits
  are unchanged, and ranks remain separate by layer.
- Hosted PostgreSQL completed an exact FileOS run and generation, activated it,
  published reviewed KnowledgeCore objects citing the same evidence, and returned both
  layers under current mode. Contract tests proved default compatibility, mode
  selection, closed values and both-scope enforcement.
- The hosted suite passed **2,411 Python tests** with PostgreSQL and no skips; the
  deployment gate repeated it. **134 Node contracts**, five MIME-container cases,
  15 Email PDF-container cases and five FileOS PDF/DOCX/XLSX cases passed.
  Documentation verification covered **127 Markdown files / 785 local paths and
  fragments**.
- PostgreSQL 17 restore verified **61 tables / 229 rows / two tenants / four encrypted
  objects / two identity bindings** in 14.97 seconds. The 29 restore safety tests passed.
- Local gates passed **2,057 tests / 354 explicit PostgreSQL skips**, lint, strict
  types, browser contracts, documentation, deployment and pinned donor parity.
- FOS-Master remains clean at
  **218d5caec2f20b9047fd3eb8e027dc671acf0c15**. No Email migration, synthesis,
  automatic activation, source effect, cutover, rename or retirement is implied.

## Verified cross-source current FileOS search

Runtime revision **42606da** and two-source stress revision **83f5747** passed
[CI 35729843020](https://github.com/jbone3311/MasterBrain/actions/runs/35729843020)
and [restore 35729843019](https://github.com/jbone3311/MasterBrain/actions/runs/35729843019),
observed 2026-09-22 Pacific.

- `POST /v1/brain/fileos-search` searches only the newest activated immutable
  generation for every tenant-visible FileOS source. Existing retained-history
  DataCore and grouped unified search keep their compatibility behavior.
- Hosted PostgreSQL proved two simultaneously active sources, multi-query identity
  parity, result bounds, changed content, zero hits, rollback disappearance,
  reactivation, API labeling and forced-RLS execution.
- The hosted suite passed **2,411 Python tests** with PostgreSQL and no skips; the
  deployment gate repeated it. **134 Node contracts**, five MIME-container cases,
  15 Email PDF-container cases and five FileOS PDF/DOCX/XLSX cases passed.
  Documentation verification covered **126 Markdown files / 784 local paths and
  fragments**.
- PostgreSQL 17 restore verified **61 tables / 229 rows / two tenants / four encrypted
  objects / two identity bindings**, including current FileOS retrieval, in 14.75
  seconds. The 29 restore safety tests passed.
- Local gates passed **2,057 tests / 354 explicit PostgreSQL skips**, lint, strict
  types, 134 Node contracts, documentation, deployment and the pinned live-donor
  2,000-file-plus-edge stress corpus. Local SQL skips are not passes.
- FOS-Master remains clean at
  **218d5caec2f20b9047fd3eb8e027dc671acf0c15**. No historical route was redirected;
  no scheduler, source effect, cutover, rename or retirement exists.

## Verified private FileOS index operator

Runtime revision **8a50eab** and test-authorization correction **4716c88** passed
[CI 35727909717](https://github.com/jbone3311/MasterBrain/actions/runs/35727909717)
and [restore 35727909764](https://github.com/jbone3311/MasterBrain/actions/runs/35727909764),
observed 2026-09-22 Pacific.

- `masterbrain fileos index` now supports explicit build-and-activate for one exact
  completed run and activation-only rollback to a ready generation. Closed private
  configuration, runtime DSN, exact per-operation worker scopes, non-consuming check
  mode and repeated authentication fence every operation.
- Hosted PostgreSQL proved build/activation, exact replay, distinct code-revision
  generation, activation-only rollback, privileged-role refusal, revoked-worker
  refusal and deterministic active-versus-existing query identities. Source bytes
  remained unchanged.
- The hosted suite passed **2,411 Python tests** with PostgreSQL and no skips; the
  deployment gate repeated it. **134 Node contracts**, five MIME-container cases,
  15 Email PDF-container cases and five FileOS PDF/DOCX/XLSX cases passed.
  Documentation verification covered **125 Markdown files / 783 local paths and
  fragments**.
- PostgreSQL 17 restore verified **61 tables / 229 rows / two tenants / four encrypted
  objects / two identity bindings** in 24.7 seconds. The 29 restore safety tests passed.
- Local gates passed **2,057 tests / 354 explicit PostgreSQL skips**, 134 Node
  contracts, lint, strict types, documentation and deployment checks. The live donor
  harness still matched FOS-Master across the adopted corpus and 2,000-file-plus-edge
  stress set. Local SQL skips are not passes.
- The first hosted run reached successful rollback, then its verification read used a
  fixture context without `brain.changes.read`; authorization correctly denied it.
  Commit `4716c88` uses the established DataCore read context. Runtime permissions and
  behavior were unchanged; the complete rerun passed.
- FOS-Master remains clean at
  **218d5caec2f20b9047fd3eb8e027dc671acf0c15**. The command adds no scanner,
  scheduler, global-search switch, source effect, cutover, rename or retirement.

## Verified immutable FileOS index generations and rollback

Revision **b715bf1** passed
[CI 35725616036](https://github.com/jbone3311/MasterBrain/actions/runs/35725616036)
and [restore 35725615886](https://github.com/jbone3311/MasterBrain/actions/runs/35725615886),
observed 2026-09-22 Pacific.

- Migration 0019 adds forced-RLS, immutable generation/item/chunk/readiness tables and
  append-only activations. PostgreSQL validates exact declared closure before readiness
  and rejects post-ready append. Generation identity binds the latest completed run,
  exact plan, code revision and chunker version.
- Hosted PostgreSQL proved deterministic replay, a distinct generation for a changed
  code revision, changed-run generation, activation replay/conflict, active-only
  queries, prior-generation rollback/reactivation, API reads and immutable closure.
- The hosted suite passed **2,394 Python tests** with PostgreSQL and no skips; the
  deployment gate repeated it. **134 Node contracts**, five MIME-container cases,
  15 Email PDF-container cases and five FileOS PDF/DOCX/XLSX cases passed.
  Documentation verification covered **124 Markdown files / 780 local paths and
  fragments**.
- PostgreSQL 17 restore verified **61 tables / 229 rows / two tenants / four encrypted
  objects / two identity bindings**, including the same active generation and query
  result, in 17.86 seconds. The 29 restore safety tests also passed.
- Local gates passed **2,042 tests / 352 explicit PostgreSQL skips**, 134 Node
  contracts, lint, strict types, documentation and deployment checks. The live donor
  harness matched the pinned FOS-Master baseline across adopted extraction and a
  2,000-file-plus-edge stress corpus. Local SQL skips are not passes.
- FOS-Master remains clean at
  **218d5caec2f20b9047fd3eb8e027dc671acf0c15**. No scheduler, automatic generation,
  global-search switch, source effect, cutover, rename or retirement exists.

## Verified deterministic FileOS rebuild preview

Revision **0653a35d5376efcee5151c35a827f9fa715d242d** passed
[CI 35720358559](https://github.com/jbone3311/MasterBrain/actions/runs/35720358559)
and [restore 35720358811](https://github.com/jbone3311/MasterBrain/actions/runs/35720358811),
observed 2026-09-22 Pacific.

- The run-bound, paginated preview recomputes body digests, deterministic document IDs,
  chunk ranges, chunk digests and chunk IDs for the latest completed inventory. It
  returns `verified`, `rebuild_required` or `source_reprocess_required` without paths,
  text, source effects or DataCore effects.
- The source completion lock prevents a page from mixing inventory runs; page cursors
  must belong to the exact current run. PostgreSQL/API cases proved two-page traversal,
  unknown-cursor refusal, verified and source-reprocess classifications, bounded output
  and no disclosure fields.
- The hosted suite passed **2,394 Python tests** with PostgreSQL and no skips; the
  deployment gate repeated it. **134 Node contracts**, five MIME-container cases,
  15 Email PDF-container cases and five FileOS PDF/DOCX/XLSX cases passed.
  Documentation verification covered **123 Markdown files / 779 local paths and
  fragments**.
- PostgreSQL 17 restore verified **56 tables / 218 rows / two tenants / four encrypted
  objects / two identity bindings** and a `verified` restored rebuild preview in 16.17
  seconds. The 29 restore safety tests also passed.
- Local gates passed **2,042 tests / 352 explicit PostgreSQL skips**, 134 Node
  contracts, lint, strict types, documentation and deployment checks. Local SQL skips
  are not passes; the hosted run is the authoritative database result.
- FOS-Master remains clean at
  **218d5caec2f20b9047fd3eb8e027dc671acf0c15**. No rebuild executor, active-generation
  switch, search-visibility change, file effect, cutover, rename or retirement exists.

## Verified FileOS completed-inventory reconciliation evidence

Revision **77ccc81f0659727e2c26fe0c952421e9ac98f14d** passed
[CI 35718606046](https://github.com/jbone3311/MasterBrain/actions/runs/35718606046)
and [restore 35718606093](https://github.com/jbone3311/MasterBrain/actions/runs/35718606093),
observed 2026-09-22 Pacific.

- Migration 0018 adds immutable, forced-RLS completed-run item ledgers and absence
  events. Deferred PostgreSQL constraints require exact item and grouped-outcome
  agreement with the completion receipt; source/run/time foreign keys prevent a ledger
  from being rebound.
- Completion is serialized per tenant/source and refuses an older or equal observation.
  Absence is derived only between consecutive completed ledgers, never from a partial
  import or crashed publication prefix. Evidence remains retained and searchable.
- The hosted suite passed **2,394 Python tests** with PostgreSQL and no skips; the
  deployment gate repeated it. **134 Node contracts**, five MIME-container cases,
  15 Email PDF-container cases and five FileOS PDF/DOCX/XLSX cases passed.
  Documentation verification covered **122 Markdown files / 778 local paths and
  fragments**.
- PostgreSQL integration proved two completed snapshots, one absence, stale-run
  refusal, exact replay, RLS/immutability and bounded API counts. PostgreSQL 17 restore
  verified **56 tables / 218 rows / two tenants / four encrypted objects / two identity
  bindings**, including the inventory ledger, in 19.06 seconds.
- Local gates passed **2,042 tests / 352 explicit PostgreSQL skips**, 134 Node
  contracts, lint, strict types, documentation and deployment checks. Local SQL skips
  are not passes; the hosted run is the authoritative database result.
- FOS-Master remains clean at
  **218d5caec2f20b9047fd3eb8e027dc671acf0c15**. This tranche adds no automatic
  rebuild, current/historical search policy, scheduler, file effect, cutover, rename or
  retirement.

## Verified FileOS completion receipts and source freshness

Runtime revision **1e0f87ed8ac5fe9fa29d186b2c242c7584d9a24a** and the
valid-conflict test correction **c12800fee682c4f0e922698a8adbc342096f07b7** passed
[CI 35716362139](https://github.com/jbone3311/MasterBrain/actions/runs/35716362139)
and [restore 35716362094](https://github.com/jbone3311/MasterBrain/actions/runs/35716362094),
observed 2026-09-22 Pacific.

- Migration 0017 adds forced-RLS, append-only whole-run receipts. Completion is bound
  to the exact actor, request UUID, source, canonical manifest digest, item/outcome
  counts and extractor/code provenance. Replay preserves the original completion time;
  changed receipts conflict.
- `GET /v1/brain/sources/{source_id}/freshness` reports only the latest completed run.
  A partial/crashed prefix remains explicitly `no_completed_run` and cannot be
  presented as fresh.
- The hosted suite passed **2,394 Python tests** with PostgreSQL and no skips; the
  deployment gate repeated it. **134 Node contracts**, five MIME-container cases,
  15 Email PDF-container cases and five FileOS PDF/DOCX/XLSX cases passed.
  Documentation verification covered **121 Markdown files / 776 local paths and
  fragments**.
- PostgreSQL integration proved exact intake binding, valid replay/conflict,
  immutability, RLS, API access and invalid direct-write rejection. PostgreSQL 17
  restore verified **54 tables / 215 rows / two tenants / four encrypted objects /
  two identity bindings**, including the same latest-complete run, in 18.37 seconds.
- Local gates passed **2,042 tests / 352 explicit PostgreSQL skips**, 134 Node
  contracts, lint, strict types, documentation and deployment checks. Local SQL skips
  are not passes; the hosted run is the authoritative database result.
- The first hosted gate exposed a malformed conflict-test input: its internally
  inconsistent published count was correctly rejected by validation before replay
  conflict detection. The fixture now submits a different but internally valid closed
  outcome set; runtime validation was unchanged, and the complete rerun passed.
- FOS-Master remains clean at
  **218d5caec2f20b9047fd3eb8e027dc671acf0c15**. This tranche adds no scheduler,
  deletion inference, source cursor, file effect, cutover, rename or retirement.

## Verified authenticated FileOS publication command

Runtime revision **e7f319cae5a68e4a2072a326fba9ab853cb15643** and the
tenant-isolated test correction **aaaf156a0c8ad6f7243fd11300da2b4309f59ded** passed
[CI 35713893737](https://github.com/jbone3311/MasterBrain/actions/runs/35713893737)
and [restore 35713893769](https://github.com/jbone3311/MasterBrain/actions/runs/35713893769),
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
[CI 35711403192](https://github.com/jbone3311/MasterBrain/actions/runs/35711403192)
and [restore 35711403138](https://github.com/jbone3311/MasterBrain/actions/runs/35711403138),
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
[CI 35707895947](https://github.com/jbone3311/MasterBrain/actions/runs/35707895947)
and [restore 35707895954](https://github.com/jbone3311/MasterBrain/actions/runs/35707895954),
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
[CI 35706332421](https://github.com/jbone3311/MasterBrain/actions/runs/35706332421)
and [restore 35706332264](https://github.com/jbone3311/MasterBrain/actions/runs/35706332264),
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
[CI 35703242987](https://github.com/jbone3311/MasterBrain/actions/runs/35703242987)
and [restore 35703242983](https://github.com/jbone3311/MasterBrain/actions/runs/35703242983),
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
[CI 35696953888](https://github.com/jbone3311/MasterBrain/actions/runs/35696953888)
and [restore 35696953874](https://github.com/jbone3311/MasterBrain/actions/runs/35696953874),
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
[CI 35659369430](https://github.com/jbone3311/MasterBrain/actions/runs/35659369430)
and [restore 35659434985](https://github.com/jbone3311/MasterBrain/actions/runs/35659434985),
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
[CI 35630644823](https://github.com/jbone3311/MasterBrain/actions/runs/35630644823)
and [restore 35630644811](https://github.com/jbone3311/MasterBrain/actions/runs/35630644811),
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
[CI 35624876529](https://github.com/jbone3311/MasterBrain/actions/runs/35624876529)
and [restore 35624876390](https://github.com/jbone3311/MasterBrain/actions/runs/35624876390),
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
[CI 35616709666](https://github.com/jbone3311/MasterBrain/actions/runs/35616709666)
and [restore 35616709609](https://github.com/jbone3311/MasterBrain/actions/runs/35616709609),
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
[CI 35599565083](https://github.com/jbone3311/MasterBrain/actions/runs/35599565083)
and [restore 35599565086](https://github.com/jbone3311/MasterBrain/actions/runs/35599565086),
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
That base's [documentation CI 35597127919](https://github.com/jbone3311/MasterBrain/actions/runs/35597127919)
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
[CI 35596527992](https://github.com/jbone3311/MasterBrain/actions/runs/35596527992)
and [restore 35596528021](https://github.com/jbone3311/MasterBrain/actions/runs/35596528021),
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
[CI 35592669766](https://github.com/jbone3311/MasterBrain/actions/runs/35592669766).
That result does not verify the new identity runtime. The next build assignment
after this slice is browser/session lifecycle over the existing mapping boundary,
not another verifier scaffold. The full product goal remains active.

## Documentation-only next-delivery review

Reviewed 2026-09-21 from clean base **c721f52a7811e236cc3de704e397f48eda602f01**.
That base's [CI 35591511467](https://github.com/jbone3311/MasterBrain/actions/runs/35591511467)
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
[CI 35590968421](https://github.com/jbone3311/MasterBrain/actions/runs/35590968421)
and [restore 35590968376](https://github.com/jbone3311/MasterBrain/actions/runs/35590968376),
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
[CI 35589125895](https://github.com/jbone3311/MasterBrain/actions/runs/35589125895)
and [restore 35589125878](https://github.com/jbone3311/MasterBrain/actions/runs/35589125878)
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
- The first [CI run 35588376901](https://github.com/jbone3311/MasterBrain/actions/runs/35588376901)
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

[CI 35585839904](https://github.com/jbone3311/MasterBrain/actions/runs/35585839904)
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
[CI 35584256073](https://github.com/jbone3311/MasterBrain/actions/runs/35584256073)
and [restore 35584256115](https://github.com/jbone3311/MasterBrain/actions/runs/35584256115),
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
[CI 35580992550](https://github.com/jbone3311/MasterBrain/actions/runs/35580992550)
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
[CI 35580405200](https://github.com/jbone3311/MasterBrain/actions/runs/35580405200)
passed at 9a99dfa. The unchanged restore/runtime implementation passed
[restore 35579931717](https://github.com/jbone3311/MasterBrain/actions/runs/35579931717)
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

Implementation **a041647** passed [CI 35576368521](https://github.com/jbone3311/MasterBrain/actions/runs/35576368521)
and [restore 35576368531](https://github.com/jbone3311/MasterBrain/actions/runs/35576368531).
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
[CI 35573423696](https://github.com/jbone3311/MasterBrain/actions/runs/35573423696)
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

Implementation **4286504** passed [CI 35572975435](https://github.com/jbone3311/MasterBrain/actions/runs/35572975435)
and [restore 35572975472](https://github.com/jbone3311/MasterBrain/actions/runs/35572975472).
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

Implementation **0f01724** passed [CI 35570568792](https://github.com/jbone3311/MasterBrain/actions/runs/35570568792)
and [restore 35570568779](https://github.com/jbone3311/MasterBrain/actions/runs/35570568779).
The follow-up **eaeca7a** strengthens the denial test with an actual foreign-tenant
account and updates the roadmap; it changes no runtime or schema. Final
[CI 35570703531](https://github.com/jbone3311/MasterBrain/actions/runs/35570703531)
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
[CI 35568932837](https://github.com/jbone3311/MasterBrain/actions/runs/35568932837)
passed at 98bb6f2. The unchanged runtime/schema/restore implementation passed
[restore 35568746120](https://github.com/jbone3311/MasterBrain/actions/runs/35568746120)
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
[CI 35566333798](https://github.com/jbone3311/MasterBrain/actions/runs/35566333798)
passed at decf1b0. The unchanged runtime/restore code passed
[restore 35566144268](https://github.com/jbone3311/MasterBrain/actions/runs/35566144268)
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
[CI 35564748494](https://github.com/jbone3311/MasterBrain/actions/runs/35564748494)
and [restore 35564748495](https://github.com/jbone3311/MasterBrain/actions/runs/35564748495)
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
[CI 35563585338](https://github.com/jbone3311/MasterBrain/actions/runs/35563585338)
passed at 0e50870; the unchanged runtime/restore implementation passed
[restore 35563364090](https://github.com/jbone3311/MasterBrain/actions/runs/35563364090)
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
[CI 35561947038](https://github.com/jbone3311/MasterBrain/actions/runs/35561947038)
and [restore 35561947019](https://github.com/jbone3311/MasterBrain/actions/runs/35561947019)
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
[CI 35560344173](https://github.com/jbone3311/MasterBrain/actions/runs/35560344173)
and [restore 35560344225](https://github.com/jbone3311/MasterBrain/actions/runs/35560344225)
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
[CI 35556627769](https://github.com/jbone3311/MasterBrain/actions/runs/35556627769)
and [restore 35556627775](https://github.com/jbone3311/MasterBrain/actions/runs/35556627775)
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
[GitHub Actions run 35555204407](https://github.com/jbone3311/MasterBrain/actions/runs/35555204407)
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
[CI 35553409905](https://github.com/jbone3311/MasterBrain/actions/runs/35553409905),
180 passing Python tests. The receipt above supersedes its test totals.

## Read-worker refinement pass

Code commit: `01eb47d`.
[GitHub Actions run 35501983332](https://github.com/jbone3311/MasterBrain/actions/runs/35501983332)
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
[GitHub Actions run 35480784089](https://github.com/jbone3311/MasterBrain/actions/runs/35480784089)
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
