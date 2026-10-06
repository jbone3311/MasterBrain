# MasterBrain Build Progress

## Pinned-donor FileOS filename parity (2026-10-06, PR #164 merged)

The synthetic read-only shadow now probes case and composed/decomposed Unicode
spelling variants in separate directories against the pinned FOS-Master scanner,
snapshot v1 and the nonpublishing donor-policy profile. A conditional sibling
corpus checks distinct same-directory names only when the filesystem can hold
them. The two focused modules passed 37 tests locally; two sibling tests
skipped on this collision-folding Mac. The broader non-PostgreSQL suite passed
2,669 tests with those two skips, 491 PostgreSQL-marked tests and the separate
local trial launcher deselected. Six browser files passed 164/164; Ruff, mypy,
docs and diff checks passed. PR #164 code head `e4e8c0e` passed hosted full CI
twice with 3,149 tests, 14 skips and all 491 PostgreSQL-marked cases executed
each time, plus restricted workers, strict runtime and restore. The added
shared-path sibling probe passed on the hosted filesystem; the two new
donor-dependent tests skipped because CI has no FOS-Master checkout.
PR #164 merged at `01f3b2b`. Donor-on-Linux collision parity is not claimed. No live root, policy
switch, FileOS effects or FOS-Master mutation is authorized.

## Selected answer-citation recheck (2026-10-06, ADR-165 merged)

An unchanged current-search hit is not enough to prove a selected quote still
matches separately fetched evidence. The read-only answer service now reopens
only cited evidence after the final scoped search, checking its document,
source, kind, body digest and bounded passage prefix before returning a quote.
Changed or missing evidence returns the existing scrubbed stale response;
revoked access fails closed. Service and HTTP regressions cover those races.
The local focused suite passed 35/35, the broader non-PostgreSQL suite passed
2,668 tests with 491 PostgreSQL-marked tests and the separate Mac trial launcher
deselected, all six browser files passed 164/164, and Ruff, mypy, docs and diff
checks passed. PR #162's code head `91b64d8` passed hosted full CI twice with
3,148 tests and all 491 PostgreSQL-marked cases executed each time, plus
restricted worker containers, strict-runtime and restore. Its final
documentation head `c3fff56` passed the same exact-head gates and merged
through PR #162 at `fe7f2b2`. Merged-main full CI, strict-runtime and restore
passed. This is not a durable snapshot or generated chat.

## Isolated image-check failure diagnostics (2026-10-06, ADR-120 follow-up merged)

The recurring synthetic large-MIME CI deadline is now known to occur before
worker creation, but the existing `image` warning combines Docker daemon
security inspection with immutable-image inspection. A focused follow-up
separates those two fixed warning stages without logging content or changing
timeouts, retries, isolation or public failure behavior. The offline controller
suite passed 60/60; the broad local non-PostgreSQL run passed 2,665 tests with
491 database-marked skips and the independent local trial launcher deselected.
The six browser files passed 156/156; Ruff, mypy and documentation checks passed.
The full local run and deployment gate each failed only the separate local
trial launcher before application assertions: Homebrew PostgreSQL 17.11
`initdb` could not allocate a 56-byte System V shared-memory segment because
this Mac's segment table was full (`shmget: No space left on device`, not disk
exhaustion). Two detached segments from failed retries were removed after
verification; older segments with uncertain ownership were left untouched.
The launcher was not subsequently proven green. PR #160's earlier head
`0543633` passed exact-head full CI twice with 3,145 tests and all 491
PostgreSQL-marked cases each time, including restricted large-MIME and FileOS
worker containers. Its strict-runtime and restore reruns passed after runner
recovery. The reconciled head `291d3cb` also passed exact-head full CI twice
with 3,145 tests and all 491 PostgreSQL-marked cases each time; restricted
large-MIME and FileOS worker checks, strict-runtime and restore passed. The
final PR head `2a604a5` passed full CI twice with the same 3,145/491 results,
plus strict-runtime, restore and restricted container checks; PR #160 merged at
`28991f8`. Merged-main full CI, strict-runtime and restore passed. The intermittent
large-MIME deadline did not recur and is not resolved by this diagnostic change.
On the reconciled tree, 2,665 non-PostgreSQL Python tests and all 164 browser
tests passed; 491 PostgreSQL-marked tests and the separate local trial launcher
were not run locally. Ruff, mypy and docs checks passed.

## First-party reviewed schedule (2026-10-05, ADR-164 merged)

[ADR-164](adr/164_owner_reviewed_schedule.md) connects the existing reviewed
event timeline and due-commitment APIs to explicit UTC-window controls in
`/brain`. Each ten-item page is checked before inert rendering; the Next
control carries the server cutoff and cursor, and date/access changes clear
stale reads. The focused browser suite passed 29/29 locally; all six browser
files passed 164/164. Ruff, mypy, docs and diff checks passed. The local
non-PostgreSQL Python run passed 2,663 tests with 491 database-marked skips and
one Docker-only launcher deselected. The separate disposable PostgreSQL 17.11
run passed 490/491 marked cases with one Docker-only skip. PR #159 exact head
`4563bd8` passed full CI twice with 3,143 tests and all 491 PostgreSQL-marked
cases each time, plus strict-runtime and restore; it merged at `cfbdac9`.
Merged-main full CI, strict-runtime and restore passed. No
hosted/live-source status, source effect or FOS-Master cutover is claimed.

## First-party project drill-down (2026-10-05, ADR-163 merged)

[ADR-163](adr/163_owner_project_dossier_drilldown.md) connects the existing
scoped project-dossier read to an explicit control on reviewed project matches
in the first-party `/brain` workspace. The focused local browser suite passed
21/21, including hostile text, independent truncation, invalid responses,
denial and stale-result clearing. The final six-file browser suite passed
156/156.
The local non-PostgreSQL Python run passed 2,663 tests with 491 PostgreSQL
tests correctly skipped and one Docker-backed local launcher deselected. The
separate real-PostgreSQL 17.11 run passed 490/491 marked tests; the remaining
Docker-only case skipped locally. PR #156 exact-head full CI passed 3,143 tests
twice, including all 491 PostgreSQL-marked cases each time; strict-runtime and
restore passed. Merged-main restore passed; full CI and the final strict gate
did not execute because GitHub-hosted runners were unavailable
([#158](https://github.com/jbone3311/MasterBrain/issues/158)).
This is a read-only orientation view, not a live project-state or hosted claim.

## Reviewed project dossier (2026-10-05, ADR-162 merged)

[ADR-162](adr/162_reviewed_project_dossier.md) adds a compact, exact-project
read with independently bounded linked events and commitments, including
undated records. The route and reference client preserve direct evidence
drill-down and source-aware visibility before limiting. Local disposable
PostgreSQL tests cover real API/client behavior, review chains, tenant/source
isolation and no-rewrite migration 0056. PR #154 passed exact-head full CI,
strict runtime and restore and merged at `cf6c656`; the merged-main gates
passed too. This is not a project truth reducer, hosted capability
or FOS-Master cutover. The [build receipt](BUILD_RECEIPT.md) records the
verification boundary and local launcher limitation.

## Reviewed-commitment due window (2026-10-05, ADR-161)

[ADR-161](adr/161_reviewed_commitments_due.md) adds an additive indexed,
read-only due-window view for reviewed commitments, with state/project filters,
source-aware related-object visibility, recorded-cutoff paging, compact previews
and direct evidence IDs. The synthetic PostgreSQL integration exercises due
boundaries, paging, review-chain cutoff, source and tenant isolation and
API/client transport. PR #152 merged at `e3826ff` after exact-head CI,
strict-runtime and restore, and the merged-main gates passed;
it is not an automatic overdue reducer, source freshness or hosted acceptance.

## Reviewed-event timeline (2026-10-05, PR #151)

[ADR-160](adr/160_reviewed_event_timeline.md) adds a read-only event-time
window under KnowledgeCore. Its first page fixes a database recorded-time cutoff;
later pages use an event-ID cursor and the same source/project visibility,
date range and review-chain mode. Direct evidence IDs remain available for
drill-down, while undated events stay in search/history. A provider-neutral
read-only client now requests this page and validates its closed response
contract. Local schema/API/client tests passed, including 2,627 non-PostgreSQL
tests. The isolated local PostgreSQL 17.11 suite passed 488 tests with one
Docker-only skip. After the Actions account gate recovered, implementation
commit `d52b167` passed [full CI](https://github.com/jbone3311/MasterBrain/actions/runs/37150248668)
with all 489 PostgreSQL-marked tests, the deployment repeat and containerized
FileOS worker checks, plus [strict runtime](https://github.com/jbone3311/MasterBrain/actions/runs/37150248761)
and [restore](https://github.com/jbone3311/MasterBrain/actions/runs/37150248722).
The later documentation-only head is separately gated before merge. This is
not a cross-kind timeline, source freshness, hosted read or
FileOS cutover.

## Grouped current reviewed leaves merged (2026-10-03)

[PR #148](https://github.com/jbone3311/MasterBrain/pull/148) merged
[ADR-159](adr/159_current_brain_reviewed_leaves.md) at `f9402d7`. It composes the verified
ADR-158 `unsuperseded` query into the all-source Knowledge layer of grouped
Brain current-search and Ask. Retained direct and unified reads do not change;
focused Email/FileOS reads still skip KnowledgeCore. The response labels its
Knowledge coverage explicitly. Local focused and full non-PostgreSQL tests
passed; exact-head PostgreSQL/full CI, strict runtime and restore passed.
Merged-main checks are tracked in the [build receipt](BUILD_RECEIPT.md). This is neither
valid-time truth nor hosted/live-source acceptance.

## Optional unsuperseded reviewed search merged (2026-10-03)

[PR #146](https://github.com/jbone3311/MasterBrain/pull/146) merged
[ADR-158](adr/158_unsuperseded_reviewed_knowledge_search.md) at `3bf21b8`.
It adds a direct,
explicit KnowledgeCore search option that filters review-chain predecessors
before ranking and limit. It considers a successor/correction only when its
full direct evidence links, and a correction's replacement, are visible under
the caller's source grants. Retained history remains the default; grouped
Brain current-search and Ask did not switch in that initial tranche; ADR-159
later merged the separate composition.
Local non-PostgreSQL tests, Ruff, mypy and documentation checks passed;
exact-head full PostgreSQL CI, strict runtime and populated restore passed
before merge. Merged-main checks passed; links and exact counts are in
the [build receipt](BUILD_RECEIPT.md). This is not current valid-time truth,
conflict resolution or a live product gate.

## Ask output-text budget merged (2026-10-03)

[PR #144](https://github.com/jbone3311/MasterBrain/pull/144) merged
[ADR-157](adr/157_ask_output_text_budget.md) at `96cb22b`. It adds a separate 8,192-byte
aggregate ceiling on returned exact quotes plus reviewed KnowledgeCore text.
It preserves exact citations and full source-grant/currentness rechecks, then
shortens or omits reviewed display text with a distinct visible flag. The
browser now counts Unicode code points for the API's character and citation
offset contract. Local focused API/client and browser tests, the full
non-PostgreSQL suite, Ruff, mypy and documentation checks passed. The final
PR head passed full CI including PostgreSQL and deployment checks, strict
runtime and populated restore before automatic merge. The separate merged-main
full CI, strict-runtime and restore runs also passed. Exact runs are in the
[build receipt](BUILD_RECEIPT.md).
This is not a complete response, model-token, hosted-chat or FileOS gate.

## Donor-shadow symlink-target boundary (2026-10-03)

[PR #141](https://github.com/jbone3311/MasterBrain/pull/141) merged
[ADR-156](adr/156_shadow_symlink_target_boundary.md) at `082b0e8` after the
first CI run exposed and the second commit fixed an error-order regression.
The nonpublishing FileOS donor shadow no longer probes a symlink target's type;
directory links now block coverage. New profile/candidate versions require a
fresh scan before staging, while older packets remain immutable history.
The final-head full CI, strict runtime, logical restore and synthetic ledger
checks passed. Exact runs and local host limits are in the
[build receipt](BUILD_RECEIPT.md). This does not accept live-root shadowing,
current v2 visibility, FileOS effects or donor cutover.

## Fresh-cluster restore rehearsal (2026-10-03)

[PR #139](https://github.com/jbone3311/MasterBrain/pull/139) merged
[ADR-155](adr/155_separate_cluster_tenant_restore.md) at `9b1ae23`.
The disposable drill now dumps from one PostgreSQL 17 container and restores
to a second independently owned container. The target lacks source tenant
login roles, bootstraps only fixed policy markers, retires two orphaned
source-name bindings, then enrolls new tenant logins for forged-SQL isolation
checks. Exact-head full CI, strict runtime and restore passed; merged-main
restore and strict runtime also passed. Exact run links and limits are in the
[build receipt](BUILD_RECEIPT.md). This is not managed-host recovery or
credential lifecycle acceptance; issue #7 remains open.

## Two-tenant restore containment proof (2026-10-03)

[PR #137](https://github.com/jbone3311/MasterBrain/pull/137) merged
[ADR-154](adr/154_two_tenant_bound_restore_proof.md) at `abf5292`.
The disposable PostgreSQL 17 drill now provisions two bound logins before
dump and two new bound logins after restore, then checks own/foreign reads,
forged tenant settings, denied foreign audit writes and denied role switching.
The PR-head restore, full CI and strict runtime passed; exact results are in
the [build receipt](BUILD_RECEIPT.md). This narrows issue #7's restore evidence
but does not prove hosted credential lifecycle or separate-cluster recovery.

## Main-branch merge safety (2026-10-03)

[PR #135](https://github.com/jbone3311/MasterBrain/pull/135) merged
ADR-153's stable strict-runtime matrix gate and applied three required
checks to `main`. GitHub held its automatic merge while full CI was running
and merged only after that check passed. The applied rule also requires fresh
PRs and resolved conversations, applies to administrators, and refuses force
pushes/deletion. Exact runs are in the [build receipt](BUILD_RECEIPT.md).
This is repository governance, not a new product capability or live acceptance.

## Fastmail reliability integration merged (2026-10-03)

ADR-110's [PR #133](https://github.com/jbone3311/MasterBrain/pull/133)
preserves Claude's original draft as a merge parent, forward-numbers its
held-source migration to 0052 and handles a
valid metadata response above the fixed control budget without dropping IDs.
The local full gate and separate nested-launcher test passed on fictional data;
exact counts and environmental constraints are in the
[build receipt](BUILD_RECEIPT.md). Exact-head CI, strict runtime and populated
restore passed before the merge at `ff7a296`; merged-main runs are linked in
the receipt and also passed. Live account acceptance remains separate.
FOS-Master is unchanged.

## Post-ADR-152 documentation checkpoint (2026-10-03)

[PR #131](https://github.com/jbone3311/MasterBrain/pull/131) merged the
post-ADR-152 documentation receipt to `main` at `65dcdf7`. The latest
functional change remains [PR #130](https://github.com/jbone3311/MasterBrain/pull/130):
the nonpublishing FileOS donor shadow now confines directory enumeration.
Its exact-head and merged-main CI, strict runtime and populated restore passed;
this does not approve live-root shadowing, v2 current visibility or donor cutover.
The current `main` checks are linked in the [build receipt](BUILD_RECEIPT.md).
At this checkpoint [Claude's draft #45](https://github.com/jbone3311/MasterBrain/pull/45)
was the only open PR, not integrated or release-ready. Its later integration
must resolve the metadata-page budget and migration number against current
`main` and pass independent tests before acceptance; see the
[roadmap](ROADMAP.md#next-verified-sequence).

## FileOS completion scale audit (verified, not a cutover gate)

The opt-in [3,000-row benchmark](FILEOS_COMPLETION_BENCHMARK.md) isolates the
old deferred per-item ledger trigger on today's synthetic FileOS v1 writer.
Two fresh local PostgreSQL 17.11 runs show a roughly 42–46× trigger cost;
the second observed no checkpoints in either measured completion. An
independent [PostgreSQL 17 container run](https://github.com/jbone3311/MasterBrain/actions/runs/37104973815)
showed 33.33× with no measured checkpoints. Final-head and merged-main
checks for the benchmark tranche are in the [build receipt](BUILD_RECEIPT.md).
This does not change FileOS behavior or close issue #71 by itself.

## Latest merged authorization-hardening tranche (2026-10-02)

[PR #120](https://github.com/jbone3311/MasterBrain/pull/120) merged
[ADR-149](adr/149_assistant_legacy_email_denial.md) at
`0591eacf027cadf8feb1696a70cacfc16847165d`. It makes the source-scoped
Brain API the assistant entrance for Email. New bootstrap credentials with
legacy `email.*` scopes are refused, existing OIDC assistant bindings with
those scopes fail authentication and saved-context use, and legacy Email API
dependencies deny even a forged assistant principal before database work.
Human/worker compatibility paths remain. This tranche is synthetic-only and
does not close hosted assistant issue #88. Exact-head checks passed; the
separate merged-main verification is tracked in the
[build receipt](BUILD_RECEIPT.md).

## Latest recorded functional checkpoint (2026-10-02)

[PR #118](https://github.com/jbone3311/MasterBrain/pull/118) merged ADR-148's
administrator refusal gate for populated legacy 0008/0009 rewrites at
`46aa0009ce0e038acd1830739031f502d109aab2`. Exact-head and merged-main
full CI, strict runtime and populated restore passed; links are in the
[build receipt](BUILD_RECEIPT.md). The explicit maintenance override retains
the old lock-heavy SQL. This does not close issue #9 or authorize a populated
production rollout.

## Previous documentation checkpoint (2026-10-02)

[PR #117](https://github.com/jbone3311/MasterBrain/pull/117) reconciled the
roadmap, status and feature inventory after #116. It is a documentation-only
merge at `394b693759624bf4f764ec6a5f8a732231c8c882`; final-head and
merged-main full CI, strict runtime and populated restore passed. This did
not create a new version or live-product claim. ADR-148 was the next code
tranche and is recorded above; it does not make populated upgrades online.

## Previous functional `main` checkpoint (2026-10-02)

[PR #116](https://github.com/jbone3311/MasterBrain/pull/116) merged the
human-only FileOS v2 historical search-review API at
`b6ebcbf7b5e6b12e10967c5d09d7a04970d5d982`. Final-head and merged-main
full CI, strict runtime and populated restore passed; exact run links and the
earlier GitHub billing-startup incident are in the
[build receipt](BUILD_RECEIPT.md). This remains synthetic/disposable review
capability, not v2 current visibility, a live-source pilot, donor cutover or
production release. The detailed next decisions are in the
[roadmap](ROADMAP.md#next-verified-sequence).

## Current synthetic version checkpoint (2026-10-01)

Annotated tag [`v0.2.0a1`](https://github.com/jbone3311/MasterBrain/tree/v0.2.0a1)
points to `main` commit `c0a531d8a7d0991be0a0f1ea717479c07cc20feb`.
Exact-commit full CI, strict-runtime, populated restore and local 3,000-file
pinned-donor DataCore parity passed. See the [build receipt](BUILD_RECEIPT.md).
This is a fictional-data/disposable-database version only. Interactive Mac
acceptance, live-source and production security/operations, and FileOS cutover
are not accepted; FOS-Master remains unchanged.

## Historical `main` checkpoint (2026-09-25)

The repository is now [`jbone3311/MasterBrain`](https://github.com/jbone3311/MasterBrain).
The functional `main` baseline before this documentation change is `c8c428b`:
[full CI 36161891971](https://github.com/jbone3311/MasterBrain/actions/runs/36161891971),
[strict runtime 36161894202](https://github.com/jbone3311/MasterBrain/actions/runs/36161894202),
and [populated restore 36161891866](https://github.com/jbone3311/MasterBrain/actions/runs/36161891866)
passed. [PR #35](https://github.com/jbone3311/MasterBrain/pull/35) merged the
current-function inventory and revised roadmap. Twenty-two already-contained
branches were removed; two divergent historical branches remain unmerged. See
[the consolidation receipt](REPOSITORY_CONSOLIDATION.md). The synthetic-only,
synthetic-only boundary and pending interactive acceptance remain; the tag was
not yet created at this historical checkpoint.

## Previous `main` checkpoint (2026-09-24)

The cumulative synthetic-alpha stack merged through [PR #28](https://github.com/jbone3311/MasterBrain/pull/28) at `2dd4a85`. The strict sender-runtime guard merged through [PR #31](https://github.com/jbone3311/MasterBrain/pull/31) at `20bfc1f`. Privacy-safe API failure correlation and status corrections merged through [PR #33](https://github.com/jbone3311/MasterBrain/pull/33) at `c605e64`. The fictional-data Email/FileOS browser trial, including verified Docker cleanup, merged through [PR #32](https://github.com/jbone3311/MasterBrain/pull/32) at `77192f5`.

That exact `main` commit passed [full CI](https://github.com/jbone3311/MasterBrain/actions/runs/36099402051), [strict-runtime checks](https://github.com/jbone3311/MasterBrain/actions/runs/36099402009), and [populated restore](https://github.com/jbone3311/MasterBrain/actions/runs/36099402006). These proved a testable, synthetic-only checkpoint; the owner's interactive Mac walkthrough is still pending. The `v0.2.0a1` tag had not been created at that point. No live source, production deployment, FileOS cutover, or FOS-Master retirement is accepted. See [checkpoint issue #29](https://github.com/jbone3311/MasterBrain/issues/29) and [hardening gate #34](https://github.com/jbone3311/MasterBrain/issues/34).

The sections below preserve point-in-time branch receipts. Descriptions such as “review” or “integration pending” belong to those historical checkpoints; they do not override the current `main` status above.

## Synthetic alpha integration

ADR-101 defines `0.2.0a1` as a test-only candidate, not a production release.
[PR #27](https://github.com/jbone3311/MasterBrain/pull/27) adds the alpha trial
guide, version/status correction, and CI/restore coverage controls on top of
the tested PR #25 branch. Its exact code head
`9b1b0e0eb71291290ab30c418c9bd8e12e05a8b8` passed
[CI 35927108260](https://github.com/jbone3311/MasterBrain/actions/runs/35927108260)
and [populated restore 35927108311](https://github.com/jbone3311/MasterBrain/actions/runs/35927108311).
The local 3,000-file pinned-donor parity run passed. Those integration gates are
now complete and recorded above. The tag was still pending then. Live use and FileOS
cutover remain prohibited.

## Historical checkpoint detail

**Confined FileOS source reads (isolated, hosted-verified).** ADR-100 addresses a
pathname check/open race in snapshot hashing and text/PDF/Office extraction.
The proposed DataCore descriptor reader walks beneath the authorized root with
no-follow opens, bounds bytes and reopens the locator to detect replacement.
Synthetic leaf/ancestor swaps and ordinary-file tests are added; the pinned
3,000-file donor shadow passes (3,002 ordinary matches, six policy and two
symlink differences). Hosted CI and populated restore passed on code head
`0769227` in PR #25. This does not alter the
inventory policy, authorize effects, or touch FOS-Master.
An additional race review extended the no-follow walk above the authorized root;
its exact code head `6e2eb8e` passed the hosted gate and populated restore.

**Archive ledger/parent integrity (isolated, hosted-verified).** ADR-099 and
migration 0033 close the post-seal archive-child insert gap, bind provenance output
to its normalized document and bind three archive derivative receipt types to the
exact inventory parent version. Synthetic PostgreSQL regressions include a
pre-existing corrupt-child refusal on disposable data. Runtime head `f0064b8`
passed [CI 35897626535](https://github.com/jbone3311/MasterBrain/actions/runs/35897626535)
with 2,741 Python tests and
[populated restore 35897626540](https://github.com/jbone3311/MasterBrain/actions/runs/35897626540).
Review and integration remain. Nothing in this tranche changes FOS-Master,
FileOS source policy or production routing.

**Integration of tested schema and FileOS branches.** A dedicated branch combines
the separately green migration-integrity/truncation stack (#12–#13) with the
FileOS root-binding stack (#14–#22). Migration order is 0029 migration repair,
0030 truncate guards, 0031 inventory policy and 0032 root binding. The merge
preserves both branches' history. The corrected integration head `9790b80`
passed [CI 35893316583](https://github.com/jbone3311/MasterBrain/actions/runs/35893316583)
with 2,738 Python tests and
[populated restore 35893316454](https://github.com/jbone3311/MasterBrain/actions/runs/35893316454).
Factory review PR #11 independently uses migration number 0029,
so it cannot be merged unchanged. Its non-overlapping ledger/FK findings are now
the separate hosted-verified ADR-099/migration-0033 PR #24; workflow suggestions still need
review. No FOS-Master edit or
production cutover is part of this integration.

**Checkpoint 5D — current-only archive-image OCR search proposal.** Work is tracked in
[GitHub issue #10](https://github.com/jbone3311/MasterBrain/issues/10): the Claude
handoff requests an independent review of 5B persistence and a current search layer
on a separate branch and PR. The issue exists; Claude has not submitted a branch or
PR. Checkpoint 5C is accepted on `codex/masterbrain-foundation` in PR #4. Any 5D
implementation requires its own review and hosted gates before integration.

In a separate read-only FileOS parity lane, the pinned donor's scanner/reconciler
inventory classifier has been copied into DataCore with two type-check-only comments
in its standalone self-test. A 3,000-path
synthetic live-donor comparison found no classification or pruning differences.
Hosted [CI 35848399796](https://github.com/jbone3311/MasterBrain/actions/runs/35848399796)
and [restore 35848399781](https://github.com/jbone3311/MasterBrain/actions/runs/35848399781)
passed on [PR #14](https://github.com/jbone3311/MasterBrain/pull/14). Snapshot
integration awaits an explicit policy decision because the donor scanner and DC-001
dedupe defaults differ; no FileOS source behavior changed in this tranche.
See the [classifier contract](FILEOS_JUNK_POLICY.md).

The next isolated lane follows ADR-093: a synthetic FOS scanner-vs-MasterBrain
whole-inventory [shadow comparison](FILEOS_INVENTORY_SHADOW.md), with no database or
source publication. Locally, 3,002 common files matched on size/SHA-256; six exact
path differences reflect the current policies. Replay, one changed file, one
removal, donor no-hash/rehash, a 1,502-row mass-prune refusal and internal/external
symlink policy differences were exercised.
Hosted [CI 35852211467](https://github.com/jbone3311/MasterBrain/actions/runs/35852211467)
passed on [PR #15](https://github.com/jbone3311/MasterBrain/pull/15), including
the browser, deployment, documentation and restricted-worker gates. PR #15 does not
match the restore workflow's path filters, so it did not start a new restore drill;
the underlying PR #14 [restore 35852112586](https://github.com/jbone3311/MasterBrain/actions/runs/35852112586)
passed. Snapshot policy integration and adversarial boundaries remain pending.

The next isolated fault tranche adds sparse size-boundary, read-failure, race and
broken/directory-symlink cases against the pinned donor in memory. Local focused
tests and [hosted CI 35855259654](https://github.com/jbone3311/MasterBrain/actions/runs/35855259654)
are green on [PR #16](https://github.com/jbone3311/MasterBrain/pull/16).
This is still comparison work, not a
FileOS snapshot-policy switch.

Another isolated edge tranche measures a simulated dataless branch, unreadable
directory, donor hash-time mutation and unusual valid filenames. Fourteen focused
shadow tests pass locally and [hosted CI 35857585834](https://github.com/jbone3311/MasterBrain/actions/runs/35857585834)
is green on [PR #17](https://github.com/jbone3311/MasterBrain/pull/17).
The donor's silent one-row removal
and inconsistent raced size/hash reinforce the need for explicit coverage and
stable-read gates before a policy change.

ADR-094 now defines a separate FileOS completion-coverage guard. The private
publisher refuses incomplete manifests before intake, and DataCore completion
independently refuses to advance freshness or absence from scan errors. Local
unit/controller tests and hosted
[CI 35863559605](https://github.com/jbone3311/MasterBrain/actions/runs/35863559605)
plus [restore 35863559359](https://github.com/jbone3311/MasterBrain/actions/runs/35863559359)
pass on [PR #18](https://github.com/jbone3311/MasterBrain/pull/18). This does
not switch donor inventory policy or solve mass loss.

ADR-095 defines the next isolated safety guard: a new complete FileOS run is refused
when at least 10 prior items and at least half the prior inventory disappear. It
matches the pinned donor's mass-prune threshold without performing deletion or
granting a force override. Six focused local unit tests passed; two PostgreSQL
cases were skipped because no local test database is configured. Hosted
[CI 35869402539](https://github.com/jbone3311/MasterBrain/actions/runs/35869402539)
passed 2,689 Python tests and the full non-Python gate, and
[restore 35869402685](https://github.com/jbone3311/MasterBrain/actions/runs/35869402685)
passed on [PR #19](https://github.com/jbone3311/MasterBrain/pull/19)'s runtime
head. A reviewed legitimate-large-removal path remains.

ADR-096 defines the next separate FileOS guard: new completion receipts carry a
validated, versioned inventory-policy digest, and a new run cannot compare against
an unknown legacy or different prior policy. Migration 0031 preserves legacy
receipts without inventing a digest. The corrected runtime head `26fd5b2` passed
[hosted CI 35879001222](https://github.com/jbone3311/MasterBrain/actions/runs/35879001222)
(2,700 Python passed, nine expected skips; browser, deployment, documentation and
restricted-worker gates also green) and populated
[restore 35879001244](https://github.com/jbone3311/MasterBrain/actions/runs/35879001244)
on [PR #20](https://github.com/jbone3311/MasterBrain/pull/20).
Focused local tests and the pinned 3,000-file donor shadow also passed. Review,
integration, a legitimate legacy baseline, per-locator exclusion accounting and
root-binding acceptance remain; no donor policy switch or cutover occurred.

ADR-097 begins the next isolated FileOS safety tranche: a bounded snapshot ledger
records excluded files and pruned directories without reading excluded bytes.
Completion refuses to interpret a previously indexed locator covered by this ledger
or an intentional no-follow symlink skip as deletion. Genuine removals retain the
existing absence behavior. Focused local tests reported 35 passed and three
PostgreSQL skips without a disposable local database; Ruff and the 179-file/955-link
documentation inventory passed. The runtime head `0bd6319` passed
[hosted CI 35885818478](https://github.com/jbone3311/MasterBrain/actions/runs/35885818478)
(2,712 Python passed, nine expected skips; type, browser, deployment, docs and
restricted-worker gates also green) and populated
[restore 35885818538](https://github.com/jbone3311/MasterBrain/actions/runs/35885818538)
on [PR #21](https://github.com/jbone3311/MasterBrain/pull/21). Review and
integration remain. This changes
neither FOS-Master nor the inventory membership policy.

ADR-098 starts the next isolated root-binding tranche. The scanner records a
private, versioned physical-root digest and checks for root drift; the private
publisher and DataCore check it before intake and completion. Migration 0032
preserves unknown legacy roots without auto-claiming a populated source. This is
now [PR #22](https://github.com/jbone3311/MasterBrain/pull/22), stacked on
#21. The runtime head `10a2597` passed
[hosted CI 35890079983](https://github.com/jbone3311/MasterBrain/actions/runs/35890079983)
with 2,721 Python tests and nine expected skips, plus all other gates, and
[populated restore 35890079939](https://github.com/jbone3311/MasterBrain/actions/runs/35890079939).
Review and integration remain; synthetic root mismatch and malformed-binding
tests are included.
FOS-Master remains pinned and unchanged; root binding alone does not certify
the donor inventory policy or authorize cutover.

In parallel, migration-integrity [PR #12](https://github.com/jbone3311/MasterBrain/pull/12)
addresses verified [issue #5](https://github.com/jbone3311/MasterBrain/issues/5)
without touching the 5D search workstream. ADR-091 precedes its forward-only 0029
repair. On a disposable PostgreSQL 17 server, the focused tests passed 4/4 and the
full PostgreSQL-marked suite passed 397 tests; the historical forced-RLS omission was
reproduced. Hosted restore passed in
[run 35839369275](https://github.com/jbone3311/MasterBrain/actions/runs/35839369275);
hosted [CI 35839648723](https://github.com/jbone3311/MasterBrain/actions/runs/35839648723)
passed 2,656 PostgreSQL-backed Python tests and all browser, deployment and
restricted-worker gates. Independent review and integration remain pending.
FOS-Master remains unchanged.

A separate protected-record maintenance [PR #13](https://github.com/jbone3311/MasterBrain/pull/13) follows ADR-092 and
[issue #8](https://github.com/jbone3311/MasterBrain/issues/8). Its additive 0030
migration rejects whole-table truncation of 56 append-only tables, two protected
approval-job tables and audited identity bindings. Thirteen focused disposable
PostgreSQL 17 tests passed. Hosted
[CI 35844322327](https://github.com/jbone3311/MasterBrain/actions/runs/35844322327)
passed 2,669 Python tests, browser, documentation/deployment and restricted-worker
gates; [restore 35844322318](https://github.com/jbone3311/MasterBrain/actions/runs/35844322318)
passed. Independent review and integration are pending. This is not a production
database change.

## Completed gates

- Foundation identity/architecture documentation and ADR-047.
- DC-001 read-only hash/dedupe extraction from pinned FOS-Master.
- Initial live-donor hash/name/both parity corpus.
- Hosted CI and synthetic PostgreSQL restore green at foundation baseline.
- Checkpoint 1 shared CLI, contracts, FileOS snapshots and 3,000-file donor parity
  completed in commit `73b58cb`; hosted CI and restore are green.
- Checkpoint 2 persistence/index completed in commits `20c5fb8` and `380761b`;
  hosted CI and populated logical restore are green.
- Checkpoint 3A text/Markdown/HTML/CSV extraction completed in `afebced`; hosted CI,
  donor parity and restore are green.
- Progressive Brain API read slice completed in `a06bcad`; hosted CI
  [35703242987](https://github.com/jbone3311/MasterBrain/actions/runs/35703242987)
  and restore
  [35703242983](https://github.com/jbone3311/MasterBrain/actions/runs/35703242983)
  are green.
- Final receipt revision `ee6b662` passed hosted CI and restore; it changes only
  measured documentation after the `a06bcad` runtime.
- Checkpoint 4 foundation revision `7d2afbf` passed hosted
  [CI 35706332421](https://github.com/jbone3311/MasterBrain/actions/runs/35706332421)
  and [restore 35706332264](https://github.com/jbone3311/MasterBrain/actions/runs/35706332264).
- Checkpoint 5 grouped retrieval revision `b60acd2` passed hosted
  [CI 35707895947](https://github.com/jbone3311/MasterBrain/actions/runs/35707895947)
  and [restore 35707895954](https://github.com/jbone3311/MasterBrain/actions/runs/35707895954).
- Checkpoint 3B isolated PDF/DOCX/XLSX revision `a6488c6` passed hosted
  [CI 35711403192](https://github.com/jbone3311/MasterBrain/actions/runs/35711403192)
  and [restore 35711403138](https://github.com/jbone3311/MasterBrain/actions/runs/35711403138).
- Checkpoint 3C authenticated publication runtime `e7f319c` plus tenant-isolated test
  correction `aaaf156` passed hosted
  [CI 35713893737](https://github.com/jbone3311/MasterBrain/actions/runs/35713893737)
  and [restore 35713893769](https://github.com/jbone3311/MasterBrain/actions/runs/35713893769).
- Checkpoint 3D whole-run completion/freshness runtime `1e0f87e` plus valid-conflict
  test correction `c12800f` passed hosted
  [CI 35716362139](https://github.com/jbone3311/MasterBrain/actions/runs/35716362139)
  and [restore 35716362094](https://github.com/jbone3311/MasterBrain/actions/runs/35716362094).
- Checkpoint 3E completed-inventory/absence reconciliation revision `77ccc81` passed
  hosted [CI 35718606046](https://github.com/jbone3311/MasterBrain/actions/runs/35718606046)
  and [restore 35718606093](https://github.com/jbone3311/MasterBrain/actions/runs/35718606093).
- Checkpoint 3F deterministic rebuild preview revision `0653a35` passed hosted
  [CI 35720358559](https://github.com/jbone3311/MasterBrain/actions/runs/35720358559)
  and [restore 35720358811](https://github.com/jbone3311/MasterBrain/actions/runs/35720358811).
- Checkpoint 3G immutable index generations revision `b715bf1` passed hosted
  [CI 35725616036](https://github.com/jbone3311/MasterBrain/actions/runs/35725616036)
  and [restore 35725615886](https://github.com/jbone3311/MasterBrain/actions/runs/35725615886).
- Checkpoint 3H private generation operator runtime `8a50eab` plus test-authorization
  correction `4716c88` passed hosted
  [CI 35727909717](https://github.com/jbone3311/MasterBrain/actions/runs/35727909717)
  and [restore 35727909764](https://github.com/jbone3311/MasterBrain/actions/runs/35727909764).
- Checkpoint 3I current FileOS search runtime `42606da` plus two-source stress revision
  `83f5747` passed hosted
  [CI 35729843020](https://github.com/jbone3311/MasterBrain/actions/runs/35729843020)
  and [restore 35729843019](https://github.com/jbone3311/MasterBrain/actions/runs/35729843019).
- Checkpoint 3J current-aware grouped retrieval revision `8bada56` passed hosted
  [CI 35731669724](https://github.com/jbone3311/MasterBrain/actions/runs/35731669724)
  and [restore 35731669604](https://github.com/jbone3311/MasterBrain/actions/runs/35731669604).
- Checkpoint 4A Email evidence bridge runtime `0eae4c4` plus least-privilege
  correction `bb4b45d` passed hosted
  [CI 35734147533](https://github.com/jbone3311/MasterBrain/actions/runs/35734147533)
  and [restore 35734147551](https://github.com/jbone3311/MasterBrain/actions/runs/35734147551).
- Checkpoint 4B private Email bridge operator revision `f600508` passed hosted
  [CI 35736010764](https://github.com/jbone3311/MasterBrain/actions/runs/35736010764)
  and [restore 35736010659](https://github.com/jbone3311/MasterBrain/actions/runs/35736010659).
- Checkpoint 4C current bridged Email search revision `743fb9e` passed hosted
  [CI 35737349912](https://github.com/jbone3311/MasterBrain/actions/runs/35737349912)
  and [restore 35737349873](https://github.com/jbone3311/MasterBrain/actions/runs/35737349873).
- Checkpoint 4D Email attachment occurrence/text bridge runtime `02eefb5` plus
  historical-parent fixture correction `aaf8df0` passed hosted
  [CI 35740735789](https://github.com/jbone3311/MasterBrain/actions/runs/35740735789)
  and [restore 35740736075](https://github.com/jbone3311/MasterBrain/actions/runs/35740736075).
- Checkpoint 4E approved Email PDF derivative bridge runtime `cd425d0` plus
  tenant-isolation fixture correction `c183a07` passed hosted
  [CI 35743436225](https://github.com/jbone3311/MasterBrain/actions/runs/35743436225)
  and [restore 35743436167](https://github.com/jbone3311/MasterBrain/actions/runs/35743436167).
- Checkpoint 4F private Email attachment/document bridge commands revision `6156b70`
  passed hosted
  [CI 35745615962](https://github.com/jbone3311/MasterBrain/actions/runs/35745615962)
  and [restore 35745615958](https://github.com/jbone3311/MasterBrain/actions/runs/35745615958).
- Checkpoint 4G layered current Email-family search revision `9b427e1` passed hosted
  [CI 35749176559](https://github.com/jbone3311/MasterBrain/actions/runs/35749176559)
  and [restore 35749176556](https://github.com/jbone3311/MasterBrain/actions/runs/35749176556).
- Checkpoint 4H grouped current-source search runtime `8da5b36` plus mixed-source
  assertion correction `7939674` passed hosted
  [CI 35751228402](https://github.com/jbone3311/MasterBrain/actions/runs/35751228402)
  and [restore 35751228447](https://github.com/jbone3311/MasterBrain/actions/runs/35751228447).
- Checkpoint 4I current-source coverage runtime `82012e9` plus state-transition stress
  revision `c2c97da` passed hosted
  [CI 35753479059](https://github.com/jbone3311/MasterBrain/actions/runs/35753479059)
  and [restore 35753479343](https://github.com/jbone3311/MasterBrain/actions/runs/35753479343).
- Checkpoint 4J private Email bridge preview runtime `4c3347c` plus current-version
  transition assertion correction `e9cf62f` passed hosted
  [CI 35756327120](https://github.com/jbone3311/MasterBrain/actions/runs/35756327120)
  and [restore 35756327113](https://github.com/jbone3311/MasterBrain/actions/runs/35756327113).
- Checkpoint 4K sealed Email message batch runtime `0fd8c35` plus legacy one-item
  idempotency-ordering compatibility correction `7ca0568` passed hosted
  [CI 35759175176](https://github.com/jbone3311/MasterBrain/actions/runs/35759175176)
  and [restore 35759175355](https://github.com/jbone3311/MasterBrain/actions/runs/35759175355).
- Checkpoint 4L preview design revision `5b26329` passed hosted
  [CI 35761452118](https://github.com/jbone3311/MasterBrain/actions/runs/35761452118)
  and [restore 35761451949](https://github.com/jbone3311/MasterBrain/actions/runs/35761451949).
- Checkpoint 4L attachment/document preview runtime `e3c0ee5` plus checkpoint-tracking
  revision `0c687e8` passed hosted
  [CI 35763636718](https://github.com/jbone3311/MasterBrain/actions/runs/35763636718)
  and [restore 35763636696](https://github.com/jbone3311/MasterBrain/actions/runs/35763636696).
- Checkpoint 4M sealed Email part-batch design `2825529` and runtime `c143e0c` passed
  hosted [CI 35774641187](https://github.com/jbone3311/MasterBrain/actions/runs/35774641187)
  and [restore 35774641102](https://github.com/jbone3311/MasterBrain/actions/runs/35774641102).
- Checkpoint 4N archive design `2aaeb26` and isolated inventory runtime `26473de`
  passed the pinned donor suite/live golden and hosted
  [CI 35780244211](https://github.com/jbone3311/MasterBrain/actions/runs/35780244211)
  plus [restore 35780244282](https://github.com/jbone3311/MasterBrain/actions/runs/35780244282).
- Checkpoint 4O archive persistence design `2d30728`, runtime `03dbb98` and explicit
  upgrade-list correction `08ccb68` passed hosted
  [CI 35783950712](https://github.com/jbone3311/MasterBrain/actions/runs/35783950712)
  plus [restore 35783950915](https://github.com/jbone3311/MasterBrain/actions/runs/35783950915).
- Checkpoint 4P archive-member design `0195a53` and runtime `c7d2d27` passed the
  pinned donor 47-test suite/live golden, 2,525 hosted Python tests, real restricted
  archive-member invocation and
  [CI 35789652225](https://github.com/jbone3311/MasterBrain/actions/runs/35789652225)
  plus [restore 35789652166](https://github.com/jbone3311/MasterBrain/actions/runs/35789652166).
- Checkpoint 4Q archive-member text design `60903a9` and runtime `97aeab1` passed
  2,530 hosted Python tests, migration/forced-RLS/replay/current-fence tests and
  [CI 35792838710](https://github.com/jbone3311/MasterBrain/actions/runs/35792838710)
  plus [restore 35792838718](https://github.com/jbone3311/MasterBrain/actions/runs/35792838718).
- Checkpoint 4R private archive-member operator design `debd740`, runtime `257ab30`
  and hardened acceptance `d66de6e` passed 2,556 hosted Python tests, flat/nested
  forced-RLS publication, replay/revocation/fault tests, the real restricted member
  image, the pinned donor's 47 archive tests and six-case live parity corpus, plus
  [CI 35795580456](https://github.com/jbone3311/MasterBrain/actions/runs/35795580456)
  and [restore 35795580548](https://github.com/jbone3311/MasterBrain/actions/runs/35795580548).
- Checkpoint 4S current archive-derivative search design `d50db4c` and runtime
  `6c7b043` passed 2,556 hosted Python tests, forced-RLS current/stale transition,
  replay-deduplicated query and API/schema tests, the new migration and populated
  restore, all restricted worker containers, plus
  [CI 35796920249](https://github.com/jbone3311/MasterBrain/actions/runs/35796920249)
  and [restore 35796920235](https://github.com/jbone3311/MasterBrain/actions/runs/35796920235).
- Checkpoint 4T private archive-member preview design `7163334`, runtime `0a8c430`
  and deterministic non-bomb oversize-fixture correction `5befc42` passed 2,560 hosted
  Python tests, forced-RLS page/cursor/eligibility/replay/stale-parent tests, no-worker/
  no-source/no-receipt operator checks, all restricted containers, plus
  [CI 35799779137](https://github.com/jbone3311/MasterBrain/actions/runs/35799779137)
  and [restore 35799779396](https://github.com/jbone3311/MasterBrain/actions/runs/35799779396).
- Checkpoint 4U sealed archive-member batch design `b98b720` and runtime `1a3fd58`
  passed 2,568 local Python cases, 134 browser cases, the repository deployment gate,
  real PostgreSQL exact-plan publication/replay, all restricted containers, the pinned
  donor's 47 archive tests and six-case live parity corpus, plus
  [CI 35803130109](https://github.com/jbone3311/MasterBrain/actions/runs/35803130109)
  and [restore 35803130165](https://github.com/jbone3311/MasterBrain/actions/runs/35803130165).
- Checkpoint 4V archive-member PDF/Office design `ea6fd29`, two-worker orchestration
  `6680218`, receipt/selector `0210ad1`, publication `4d098fa`, private command
  `5bb1aa1` and real two-image gate `49b8383` passed 2,582 hosted Python tests, 134
  browser contracts, four chained restricted-image cases, populated restore and all
  prior container gates. PDF/DOCX/XLSX publication is exact, replayable,
  source-preserving and retained-history-only; hosted
  [CI 35810970182](https://github.com/jbone3311/MasterBrain/actions/runs/35810970182)
  and [restore 35810970151](https://github.com/jbone3311/MasterBrain/actions/runs/35810970151)
  are green.
- Checkpoint 4W current archive-document search design `9ba4b88` and runtime
  `7329ba9` passed 2,583 hosted Python tests with real PostgreSQL, 134 browser
  contracts, deployment, documentation and every restricted-container gate. Exact
  receipt/member/child/parent fencing, replay deduplication, tenant isolation and
  stale-parent removal are proven; hosted
  [CI 35816277436](https://github.com/jbone3311/MasterBrain/actions/runs/35816277436)
  and [restore 35816277514](https://github.com/jbone3311/MasterBrain/actions/runs/35816277514)
  are green. The pinned donor's 47 archive tests, six-case live archive parity and
  3,000-file hash/dedupe/extraction stress parity also passed locally without changing
  FOS-Master.
- Checkpoint 4X private archive-document preview design `ce2bf30` and runtime
  `1651c2b` passed 2,586 hosted Python tests with PostgreSQL, 134 browser contracts,
  deployment, documentation and all restricted-container gates. Exact PDF/DOCX/XLSX
  eligibility, sealed paging, replay-deduplicated publication state, tenant isolation,
  stale-parent refusal and non-consuming check mode are proven; hosted
  [CI 35818667860](https://github.com/jbone3311/MasterBrain/actions/runs/35818667860)
  and [restore 35818668296](https://github.com/jbone3311/MasterBrain/actions/runs/35818668296)
  are green.
- Checkpoint 4Y sealed archive-document batch design `2869aed` and runtime `87ea0d0`
  passed 2,594 hosted Python tests with PostgreSQL, 134 browser contracts, deployment,
  documentation and all restricted-container gates. Canonical format/key/order seals,
  check-mode non-consumption, sequential two-worker execution, item-two refusal and
  unchanged-plan replay are proven; hosted
  [CI 35821165890](https://github.com/jbone3311/MasterBrain/actions/runs/35821165890)
  and [restore 35821165886](https://github.com/jbone3311/MasterBrain/actions/runs/35821165886)
  are green.
- Checkpoint 4Z image/OCR inventory design `55b4854`, isolated runtime `cb6b940`,
  runtime binding `f21e534` and bounded scratch correction `512185b` passed 2,606
  hosted Python tests, 134 browser contracts, real byte-bound Tesseract OCR and every
  restricted-container gate; hosted
  [CI 35826212304](https://github.com/jbone3311/MasterBrain/actions/runs/35826212304)
  and [restore 35826212333](https://github.com/jbone3311/MasterBrain/actions/runs/35826212333)
  are green. The clean pinned donor passed 149 focused tests, 12 six-format golden
  cases and 120 generated parity stress cases; animated GIF is deliberately safer.
- Checkpoint 5A one-member archive-image design `6029240` and runtime `b17541d`
  passed 2,620 hosted Python tests, 134 browser contracts and the new four-case real
  archive-plus-image container chain; hosted
  [CI 35829326066](https://github.com/jbone3311/MasterBrain/actions/runs/35829326066)
  and [restore 35829325907](https://github.com/jbone3311/MasterBrain/actions/runs/35829325907)
  are green. Exact nested selection, 64-sibling exclusion, source preservation,
  blank OCR, animation policy and hash substitution refusal are proven.
- Checkpoint 5B archive-image persistence design `16d452a`, runtime `760a644` and
  grant/freshness/provenance correction `63b478d` passed 2,640 hosted Python tests,
  134 browser contracts, every restricted-container gate and populated restore;
  hosted [CI 35833506295](https://github.com/jbone3311/MasterBrain/actions/runs/35833506295)
  and [restore 35833506298](https://github.com/jbone3311/MasterBrain/actions/runs/35833506298)
  are green. The restore verified 72 tables / 238 rows. Exact, equivalent and
  concurrent replay, processor evolution, tenant/current fences, append-only RLS and
  image-specific provenance are proven.
- Checkpoint 5C private archive-image operator runtime `f658ace` passed 2,652 hosted
  PostgreSQL-backed Python tests, 134 browser contracts, every restricted
  worker/container gate and populated restore; hosted
  [CI 35836198307](https://github.com/jbone3311/MasterBrain/actions/runs/35836198307)
  and [restore 35836198414](https://github.com/jbone3311/MasterBrain/actions/runs/35836198414)
  are green. This accepts one explicit image member/key command, not live-source or
  production operation.

## Historical work at checkpoint 5C

The following two sections preserve the then-current handoff and deferrals;
they do not override the current `main` checkpoint above. Current archive-image
OCR search has since been implemented. See the
[feature inventory](MASTERBRAIN_FEATURE_INVENTORY.md) and
[roadmap](ROADMAP.md).

- Track the separate [Claude 5D workstream](https://github.com/jbone3311/MasterBrain/issues/10)
  for independent review of 5B persistence and a proposed current-only OCR search
  layer. No Claude branch or PR has been submitted yet.

## Deferred by design

- Archive-image/OCR current search and batch scheduling until each separate contract
  is accepted.
- Automatic archive-document fan-out and scheduling.
- Automatic knowledge extraction, graph traversal and synthesis until reviewed
  known-answer evaluation exists.
- All file/mail effects and any FOS-Master cutover/retirement.

## Rule for updates

After each checkpoint, record exact commits, tests, donor baseline, CI/restore runs,
known limits, rollback and the next active checkpoint. Do not mark a later checkpoint
active while an earlier gate has unexplained failures.
