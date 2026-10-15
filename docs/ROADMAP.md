# MasterBrain Roadmap

ADR-245 adds a real native PostgreSQL dump/restore proof for the existing
fictional seed while hosted Docker jobs are stopped before execution. Next
populate synthetic XLSX review/receipt rows in the restore seed and verify
them in both native and hosted drills; schema-only restore is insufficient
for that feature's merge gate.

ADR-244 closes the reviewer-supplied XLSX code-provenance gap before any
operator or live-source expansion. The server owns a semantic transform
revision and migration 0086 enforces it; actual-image, hosted and restore
gates still precede merge.

ADR-243 adds an exact-review, account-pinned Email XLSX publication command
with a tenant-bound worker login. Fictional command-to-PostgreSQL execution
passes; the first-party review screen and actual-image/hosted/restore gates
are still needed before this becomes an accepted operator workflow.

Current correction: ADR-242 separates human XLSX inspection/review from
worker-only document publication. Migration 0085 enforces an unexpired,
exact-result human review for each new receipt; the human credential does not
gain ingest/publication scopes. The first-party review screen, actual-image
run, hosted exact-head CI, independent restore and live-source acceptance
remain open. Librarian import continues to use the existing
`masterbrain_project_dossier_markdown_v1` export; no new format is planned.

ADR-241 now publishes one exact-approved, complete synthetic Email XLSX
result as a reviewed DataCore document with deterministic chunks, provenance
and an immutable occurrence receipt. Generic and Email-family retrieval are
currentness-gated; the first-party review UI, cell-level citations and table
index remain next steps. The actual-image case is collected but unexecuted
locally. Hosted CI, populated restore and live-source acceptance remain open;
FOS-Master stays untouched.

ADR-240 now seals complete isolated text for one exact ADR-239 approved
synthetic Email XLSX occurrence. ADR-241 adds its human-authorized DataCore
document bridge. No cell-level spreadsheet claim or live-mail access follows;
real-image, hosted CI and independent restore remain open.

ADR-239 now supplies an immutable, human-only synthetic Email XLSX extraction
approval distinct from the PDF jobs. ADR-240 implements the exact-approval
worker and immutable private result; the occurrence-specific reviewed DataCore
bridge follows in ADR-241.
The approval alone publishes no text, and live Fastmail
remains out of scope. Hosted CI is currently stopped before steps by the
GitHub account payment/spending-limit gate.

The pinned FOS XLSX baseline now has a 24-case sparse/multi-sheet value
matrix and exact 2,000/2,001-row boundary contrast. It supports the bounded
DataCore table path but does not close formula, `.xlsm`, financial citation or
full FileOS parity gaps. Keep FOS-Master as the runtime authority until those
and the hosted/restore gates are independently resolved.

ADR-238 adds a synthetic-only retained Email XLSX row-layout proof: exact
parent/part identity, the pinned table image, and the existing normalized
text digest must agree. Next is a separate reviewed XLSX extraction and
occurrence-specific Email bridge, followed by a tenant-fenced receipt and
private command. This proof publishes no cells and grants no live-mail access.

ADR-237 exposes ADR-236's reviewed XLSX layout receipt through an exact
tenant-bound private command. Next run the actual immutable-image case,
exact-head hosted CI and independent restore; then design reviewed cell-level
citations and bounded table retrieval. No live root, financial assertion or
FileOS cutover is authorized.

ADR-236 now seals one synthetic, reviewed current FileOS XLSX table replay in
an immutable tenant-fenced receipt after a final source and worker check.
ADR-237 supplies the exact private command. The actual immutable-image and
independent restore gates remain before reviewed cell-level citations or a
bounded table read. No live root, financial assertion or FileOS cutover is enabled.

ADR-235 adds a private, nonpublishing FileOS XLSX table replay over exact
confined source bytes. A row-layout digest distinguishes physical coordinates
that the indexed text digest cannot. ADR-236 now adds the current human-review
receipt; ADR-237 supplies the private command. Actual-image and independent
restore gates remain. No table publication, live root, financial claim or
FileOS switch follows from this proof.

ADR-234 adds a separate, source-bound XLSX worker that returns bounded physical
rows and positional cell values, with sheet visibility and no fabricated
headers. Its ordinary and 1,000-row values match the pinned FOS donor on the
fictional corpus. Next run the new explicit actual-image gate, define reviewed
cell-level provenance and feature coverage, then build the approved Email XLSX
extraction/bridge. It is not yet a searchable table or financial evidence.

ADR-233 pins the FOS-Master XLSX table output and verifies the ordinary
overlap plus formula, row-cap, encrypted and `.xlsm` differences against
DataCore on fictional bytes. Preserve the donor's useful table/row structure
without importing its unsafe cached-formula or partial-truncation claims as
complete evidence. A reviewed Email XLSX receipt cannot precede a separately
approved extraction and occurrence-specific bridge; the PDF-only approval
path is not a substitute. See [ADR-233](adr/233_pinned_fos_xlsx_table_baseline.md).

ADR-232 proves one exact retained fictional Email XLSX attachment can be
re-extracted through the existing shared, isolated DataCore document worker
without publishing text. The proof retains parent Email occurrence identity
and rejects incomplete/formula-dependent results. Next: approved XLSX extraction
and an Email document bridge, then a tenant-fenced, review-bound digest receipt
and private command; actual-image, hosted and independent restore checks follow.
There is still no live Email spreadsheet bridge,
cell locator, automatic index publication or certified financial statement.

ADR-231 now serializes a reviewed Email PDF receipt with both the controlled
Fastmail account transition and a direct privileged account-status update,
without granting the worker account UPDATE. Completed document jobs are
terminal/immutable. Next: actual-image execution, exact-head hosted CI,
independent populated restore and separate live-provider acceptance. This
fence does not authorize live mail, OCR or financial publication.

ADR-230 adds the restricted, exact-account Email attachment PDF replay
command with tenant-bound database login, pinned image, worker reauthentication
and no-selected-MIME-read check mode. Fictional command-to-database receipt
proof now passes. Next: actual immutable-image execution and hosted/restore
gates; ADR-231 supplies the account transition fence. OCR, issuer
proof and financial publication remain unavailable.

ADR-229 now seals one current reviewed Email attachment PDF text-layer replay
in a protected digest-only receipt. The next Email step is a tenant-bound,
exact-account private command (ADR-230), then actual-image, hosted and
independent restore gates. ADR-231 later supplies the account transition
fence; OCR, sender/issuer proof and
financial publication remain out of scope.

ADR-228 adds the first nonpublishing Email attachment PDF replay proof from
retained MIME through the pinned isolated Email PDF worker. The next Email
tranche, ADR-229, binds it to one current, granted, nonexcluded reviewed
attachment and stores an immutable tenant-fenced digest receipt. A narrow
operator command and actual-image gate remain. The pure proof alone is
not an issuer, OCR, financial or live-mail acceptance.

ADR-227 exposes ADR-226's current reviewed FileOS PDF text-layer receipt as
one exact, tenant-bound operator command. Its check mode reads no selected PDF
or review row and does not construct the processor; fictional execution is
tested. Next: actual immutable-image container, independent restore, the
review-bound Email attachment PDF receipt, OCR/visual coverage and issuer/
conflict policy.
No live root, financial claim or FileOS cutover is authorized.

ADR-226 now binds the confined FileOS PDF text-layer replay to one current
human source-tier review and stores an immutable digest-only receipt after a
second locked source and worker-authorization check. ADR-227 supplies the
tenant-bound command; actual immutable-image container validation, independent
restore, OCR/visual coverage and issuer-conflict policy before any financial
claim or FileOS cutover. Synthetic-only owner authorization still applies.

ADR-225 adds the first confined FileOS PDF text-layer replay primitive: exact
source bytes are re-read and re-extracted through the pinned restricted
document processor, with digest-only output and no database write. The next
gate is a tenant-bound source-tier receipt with final database/currentness
checks, real immutable-image container validation and independent restore;
image-only/OCR, issuer and financial truth remain unresolved.

ADR-224 now exposes the reviewed Email MIME replay as an exact authenticated
operator command with a mandatory tenant-bound login and check mode that
reads no selected MIME or review row. Fictional inline and encrypted paths
are tested. ADR-228 adds a separate pure attachment/PDF byte proof; its
review-bound receipt, issuer/conflict policy, independent restore and hosted
gates remain. No live mailbox or financial claim.

ADR-223 adds a point-in-time worker-observed Email MIME-to-text replay for a
current reviewed direct-parser message, covering inline and encrypted retained
bytes. ADR-224 now exposes it through a tenant-bound operator command; prove other
parser/attachment/PDF derivations and resolve authority conflicts before any
financial publication. No live mailbox or source-tier cutover is authorized.

ADR-222 removes an encrypted-Email bridge blocker: source-version byte size
now follows the storage-independent retained MIME size. ADR-223/224 provide
the later direct-parser text replay and command; neither authorizes live mail.

ADR-221 closes two XLSX false-success cases: uncached formulas and overlong
cells now defer with no published text. Full sheet/cell/feature coverage,
formula/display policy and source-tier attestation are still required before
using spreadsheet-derived financial facts.

ADR-220 closes one unsafe PDF outcome: a mixed text/no-text document is now
deferred with no published text rather than labeled fully extracted. This is
not a complete PDF/OCR proof; per-page coverage, OCR, spreadsheet fidelity
and source-tier replay remain on the critical path to a financial claim.

ADR-219 now exposes the ADR-218 FileOS text replay as one exact, authenticated
operator command with a mandatory tenant-bound database login and no-source-
read check mode. Fictional local execution and revocation rollback are tested;
no live root has been used. Next: PDF/OCR and spreadsheet completeness,
other Email attachment/PDF byte replay, issuer/conflict policy, independent restore and
hosted gates before using a tier in any financial publication.

ADR-218 now records a point-in-time, worker-observed FileOS **text** replay
for an ADR-217 human tier review. The confined read and exact byte-to-text
proof are shared DataCore machinery with the older statement-proposal replay.
Next: PDF/OCR and spreadsheet coverage proofs, equivalent authorized Email
bytes, issuer/conflict policy and a restricted operator command. Neither a
stored replay nor a tier review is a verified investment claim or cutover.

ADR-217 adds a human-reviewed, current-source tier classification route and
append-only record; it is deliberately not an independent byte attestation.
Next replay authorized source bytes and extraction coverage (PDF/OCR included),
resolve conflicting authority reviews, and only then design financial-claim
publication. The synthetic-only and no-FileOS-cutover gates remain in force.

ADR-216 now pins the FOS fact-verifier's pure tier/variant/status behavior in
fictional donor parity without treating donor `CONFIRMED` as a MasterBrain
financial attestation. The next source-tier gate is an immutable, reviewed,
version/hash-bound attestation with current grant and exclusion checks.
ADR-215 makes latest-revision retirement effective and lets clients discover
the actual SQL vocabulary. Next complete issue #183 with a human-reviewed
vocabulary proposal/version process and explicit alias compatibility; the
read-only catalog is not an edit workflow.

ADR-214 now controls new project-fact predicate names and their value/unit
shapes. Next complete issue #183 with owner-reviewed name proposals,
unambiguous deprecated aliases and generic claim/event/role coverage, while
preserving old facts and safe replay. Then add ownership/source-tier semantics
and the known-answer cross-source company dossier before any financial total.

ADR-213 closes a misleading substring-citation path in ADR-212's typed
measurement field. The next product tranche remains a controlled fact-name
registry, ownership/source-tier semantics and a known-answer cross-source
company dossier. Exact-head hosted gates still must run before merge.

ADR-211 now supplies the first authorized current-evidence project fact report
through KnowledgeCore and the external client. The next financial/report step
is a controlled predicate and ownership model on top of ADR-212's opt-in
exact-decimal unit/currency fact field, followed by a known-answer fictional
company dossier; no donor money sum is promoted
to an investment balance. Hosted gates are still pending.

ADR-209/210 compare all five FOS intelligence-report row shapes in isolated,
synthetic, nonpublishing code. ADR-211 takes the first product projection from
authorized current reviewed facts; it deliberately leaves amount units,
currency, ownership and completeness unresolved. Next, design those typed
contracts and run a known-answer fictional company dossier with denial and
currentness tests. The donor's money-fact sum must never be reported as an
investment balance. Hosted gates and FileOS cutover remain open.

ADR-208 now supplies a separate disposable combined-source demo for the owner
to run locally: fictional Email and FileOS evidence flows through DataCore,
Brain search and a cited reviewed project dossier. The old Email-only demo
remains intact. Next product gates are hosted exact-head acceptance, an owner
walkthrough and held-out questions, then separately authorized live-source
and named-assistant trials; this fixture is not a pilot or FOS-Master cutover.

ADR-207 implements a separate synthetic-only, private selected artifact-link
Markdown proposal queue and transaction-bound reviewed publication on an open
PR. Stage, private preview and explicit atomic human review check the current
project, exact artifact and separately cited basis occurrence, full quote and
source grants. A local same-cluster populated logical restore passed; exact-head
hosted CI, strict-runtime, independent-container restore and merged-main gates
remain. Same-hash distinct occurrences and a 25-row mixed batch with
late-fault rollback now pass locally; the current exporter permits at most
25 artifact lines in one Markdown exchange. Next: hosted gates, then a
separately designed paged exchange for overfull dossiers.
Artifact IDs are evidence occurrences, not content hashes or automatic FileOS
effects. FOS-Master remains untouched.

ADR-206 now implements a **synthetic-only** selected source-stated
project-fact Markdown proposal path on an open PR branch. Facts use separate
private, atomic batch/decision tables because their reviewed publication
receipt differs from ADR-186's generic Knowledge receipt. The exact exported
fact line, typed sidecar, cited quote, current project and all direct evidence
are checked at stage, private preview and explicit human review. Approval
creates a new fact ID inside the batch transaction; rejection creates no fact.
The local synthetic suite now covers a valid-but-wrong truncated quote
citation, source-scope denial at all three gates and revocation between
inspection and staging. A local same-cluster source-to-target logical
dump/restore now preserves pending and approved batches and their private
visibility; the independent-container hosted restore remains unverified.
Next: obtain exact-head hosted CI/strict-runtime/restore and merged-main gates
for ADR-206/207, then design typed inferred basis separately. This
is not an automatic or lossless round trip, live-source gate or FOS-Master
cutover.

ADR-205 adds selected project-member roles to the synthetic Markdown-to-
private-proposal path, with exact member/entity citation IDs retained and
rechecked through human review. ADR-206/207 now provide the separate synthetic
fact and artifact-link gates; inferred claims still need a typed basis model.
This is not automatic dossier generation, a lossless round
trip, live-source acceptance or FOS-Master cutover.

ADR-204 proves a small, synthetic Cedar Harbor company dossier through the
existing compact/Markdown API and external client: reviewed project, event,
commitment, source-stated fact and linked FileOS artifact with original evidence.
It is a known-answer integration case, not automatic knowledge generation or
source freshness. Next: owner walkthrough, held-out cross-source questions,
the synthetic fact/artifact approval round-trip trial, then explicit
live-source and financial source-tier gates. The owner chose MasterBrain's
current Markdown export as the Librarian import format; do not invent missing
full quotes or observation metadata from that lossy export.

ADR-203 extends isolated FOS-Master statement parity to Charles Schwab's
old-template supplied text. Next financial gates remain source-byte-to-text
proof for PDF/OCR, typed reviewable proposals beyond Streetbeat, independent
source-tier attestation and a known-answer cross-source investment dossier.
The donor's scanned and redesigned-template eras are not accepted by this
recipe; none of this authorizes a real statement or FileOS cutover.

ADR-202 supplies the first synthetic-only Markdown-to-private-proposal stage:
an owner may select project, event and commitment rows from the current export
format, provide missing typed metadata, and hold them for explicit ADR-186
human review. It binds exact Markdown/selection context to the immutable batch
and rechecks full quotes on specifically cited current evidence. ADR-205 later
adds member staging; ADR-206 now adds a separate selected source-stated
project-fact queue; ADR-207 later adds separate artifact-link staging.
Inference/basis links, full-fidelity
round trip and live-source acceptance remain separate gates.

ADR-201 adds an owner-only current-evidence inspection of the selected
MasterBrain dossier Markdown format. It checks every claimed quote preview
against its cited evidence but remains read-only and synthetic-only; a later
proposal write must recheck full assertion bases and require the missing
metadata and explicit human review.

The owner selected the existing MasterBrain dossier export as the Librarian
exchange format. ADR-200 adds only a bounded, read-only candidate inventory
parser with a fictional exporter-to-parser proof. Claimed IDs and citations
remain unverified and no proposal is staged. The next gate is a separately
specified evidence-reverified, human-reviewed staging path with missing
metadata supplied explicitly; no observation time or full quote may be
invented from the Markdown cutoff or quote preview.

ADR-197 merged via PR #232 as a synthetic-only export tranche: a fail-closed whole-project
Markdown read checks current full source-quote citations for older reviewed
assertions before formatting them. A bounded, authorized dossier is possible;
uncitable or overfull sections produce no Markdown. It does not establish a
Librarian import round trip, inferred statement approval, automatic related-file
matching, source freshness, live Fastmail acceptance or FOS-Master cutover.

ADR-196 is merged via PR #230: a source-grant-safe,
export-time quote-rechecked **project-facts Markdown fragment** with a fixed
partial-coverage warning. It does not render older unverified project,
event, commitment, member or artifact text as cited prose. The following
tranche establishes export-time citation contracts for those sections. The proposal-only Markdown
importer and inferred-basis model remain separate gates.

ADR-195's synthetic implementation is merged via PR #228: direct source-stated, exact-quote-checked
project facts and a source-scoped dossier section. It is not a complete Markdown export,
an inferred-fact path or live-source acceptance. Exact PR-head and independent
merged-main gates passed.

ADR-193 supplies reviewed project-to-artifact evidence links. ADR-194 adds a
separately bounded, current-authorized artifact section to the project dossier
and owner workspace. Export must render only
currently authorized, export-time-verified citations. Neither step is
automatic association, a computed current file roster, a complete Librarian
round trip, or a FileOS effect.

ADR-192 tightens the synthetic Librarian proposal path: project aliases now
need an exact quote in their own evidence. Before a Markdown dossier can claim
citations, verify each displayed quote
against currently authorized evidence. Historical directly
published Knowledge rows are not retroactively quote-certified. This remains
read-only planning, not a live-source or FileOS cutover gate.

ADR-189 now supplies a private, source-reacquired FileOS text replay receipt
bound to one statement proposal. ADR-190 exercises it in the disposable
fictional cross-source trial, while keeping the owner row unreviewed. The next
financial gate is to establish a separately trusted worker attestation/storage
boundary, expose the receipt only
with explicit source/currentness labels in owner review, and require verified
source tier plus human approval before any financial claim publication.
PDF/Office/OCR, Email attachment and archive transforms require their own
exact-version proof paths; source hashes alone do not qualify. The owner has
authorized synthetic-only testing, not live FileOS or Fastmail access.

ADR-188 provides only the first narrow deterministic source-byte replay
primitive for bounded FileOS text/Markdown/HTML/CSV. ADR-189 connects it to
one private worker-observed receipt; no existing proposal is retroactively
upgraded from hash consistency without a fresh byte replay.

Owner decision, 2026-10-14: **synthetic-only Fastmail testing for now**. Do not
enroll a real Fastmail account or read personal mail. Continue fictional/
disposable scope and pre-fetch exclusion tests, pinned-donor FileOS/statement
parity, and the owner-run fictional cross-source trial. A real mailbox pilot is
deferred until a new explicit owner authorization names its exact account/window
and the retention, credential and operating boundaries are decided. FileOS
roots retain their separate approval gate. Existing scoped code is not
authorization for either source.

ADR-186 supplies the first private KnowledgeCore proposal batch and atomic
per-row human review for source-stated assertions over current, granted,
nonexcluded evidence. It does not ingest Markdown or admit inferred claims.
The owner selected ADR-197's current export layout. Next: evidence-safe
proposal staging, typed inference/basis model, and full-fidelity round-trip
tests; keep the
source exclusion and synthetic-only gates intact.

ADR-184 now supplies the first synthetic pre-index Email exclusion tranche:
exact JMAP mailbox memberships, a policy-bound cursor, count-only public
status, and current-visibility suppression with preserved history. ADR-185
adds SQL-level retained Brain and reviewed KnowledgeCore visibility denial for
an older message subsequently excluded, including attachment/document bridges.
Remaining before a private pilot: complete cross-route audit (including
privileged historical Email routes), reviewed policy changes
for already-used accounts, sender/category policy choices, retention/purge
decision, and a separate owner-authorized disposable live-provider gate.
FileOS keeps its independently pinned donor exclusion semantics.

ADR-179 provides a local owner-reviewed, administrator-assisted check/enroll/
disconnect path for a brand-new exact pinned Fastmail account, tested without
provider contact. Next is an explicitly authorized disposable live-provider
acceptance plan and the retention, credential, alerting and hosting decisions
needed before a private alpha uses real mail. It is not a hosted enrollment or
production rollout.

ADR-178 connects the exact pinned mailbox/date window to a version-2 private
`sync-read` command and tests fictional restart, out-of-scope metadata, pause
and revocation. Version 1 remains account-wide. Next is a reviewed account
enrollment/revocation workflow, supplied locally and synthetically by ADR-179,
and a disposable live-provider acceptance plan. Neither this code nor a green
synthetic check approves real Fastmail access.

ADR-177 adds the synthetic/disposable database scope fence: an administrator
pins one exact window on an unused Fastmail account, worker leases and cursors
must match it, and old `sync-read` refuses pinned accounts before provider I/O.
ADR-178 supplies a private scoped operator and fictional restart/revocation
proof; ADR-179 adds local reviewed enrollment/disconnect. Live acceptance
remains open.

ADR-176 makes scoped Fastmail reading executable as a synthetic library worker:
version-4 scope-bound checkpoints, repeated filtered inventories, and
pre-download metadata refusal. ADR-177 supplies the durable account/lease
database fence; ADR-178 supplies operator binding. No live pilot is approved.

ADR-175 adds the typed Fastmail mailbox/date query and metadata-recheck
primitive used by ADR-176. ADR-177 supplies account-bound scope and a database
lease fence, and ADR-178 supplies operator binding. Live acceptance remains
open. Version-1 `sync-read` remains account-wide and refuses pinned accounts.

ADR-174 extends the pinned, synthetic-only statement donor comparison to the
low-confidence Fidelity recipe. Six fictional goldens preserve its exact
duplicate, missed-row, zero-fallback and period behavior. This is not a second
typed proposal path or a completeness claim; source-byte-to-text proof,
explicit incomplete coverage, remaining recipes and owner review remain ahead.
ADR-180 adds the donor's OCR-bank recipe as a third isolated comparison, with
fictional wrapped-amount and year-rollover cases. It does not prove OCR input
quality, bank-fact publication or the remaining donor recipes and reports.
ADR-181 adds isolated Morgan Stanley comparison, explicitly retaining the
cash-detail double-count guard, OCR confidence/date loss and zero fallback.
ADR-187 adds isolated Jefferies category/detail/transaction comparison,
including negative margin cash and multi-lot subtotal behavior. ADR-191 adds
isolated Wells Fargo savings daily-balance sign comparison, including its
ambiguous low-confidence cases. ADR-198 adds an isolated Wells Fargo brokerage
cash/lot/reconciliation comparison, including incomplete-tail behavior. ADR-199
adds an isolated Wells Fargo credit-line text comparison across two donor layouts;
source-PDF completeness remains unproven. None makes a
user investment dossier operational.

ADR-173 adds a human-only, read-only preview of source-rechecked ADR-172
statement proposals. It is an inspectable synthetic API slice, not a reviewer
approval workflow, first-party dossier, assistant read or live investment claim.
ADR-189 now supplies a private, text-only FileOS replay receipt; explicit
owner review/approval, trusted worker attestation and proof for other source
transforms remain required before any KnowledgeCore financial publication.

ADR-172/PR #190 adds a worker-only, evidence-bound and tenant-fenced statement
proposal ledger for one current normalized Email/FileOS document; its exact-head
and merged-main full CI, strict-runtime and restore gates passed. It narrows the
durable-line-item gap, but owner approval, explicit currency verification,
other donor recipes and reports, complete source-byte derivation proof and a
cross-source company dossier remain open. No live source or FileOS cutover is
authorized by this tranche.

Updated 2026-10-06 through ADR-160's merged event timeline, ADR-161's
merged reviewed-commitment due view, ADR-162's merged project dossier, and
ADR-163's merged first-party project drill-down (merged-main restore passed;
full CI and final strict gate were blocked before execution by hosted runners),
and ADR-164's merged reviewed schedule (exact-head and merged-main gates passed).
The ADR-120 image-check diagnostic follow-up merged through PR #160 after
exact-head and merged-main gates passed. It does not resolve intermittent
large-MIME issue #64.
ADR-165's selected answer-citation recheck merged through PR #162 after
exact-head and merged-main gates passed. It narrows a
selection-time evidence race but does not add generated chat or a durable
current-source snapshot.
The test-only pinned donor snapshot in PR #167 let hosted Linux run the
FOS-Master scanner against case and Unicode-normalization sibling corpora:
the dedicated three-test gate and both full code-head suites passed. That
narrows synthetic platform parity; the six donor-policy differences, real
cloud placeholders, permission faults, authorized live shadow and FileOS
cutover remain open.
ADR-167 adds a fail-closed synthetic invalid-byte-name guard and a required
Linux donor probe. It is a safety divergence, not a donor-policy switch or
live-root acceptance.
ADR-159's grouped Brain/Ask reviewed-leaf
projection (PR #148 at `f9402d7`), ADR-158's optional direct KnowledgeCore
unsuperseded search (PR #146 at `3bf21b8`), ADR-155's separate-cluster restore
(PR #139 at `9b1ae23`) and ADR-156's merged, nonpublishing FileOS
shadow symlink-target boundary (PR #141 at `082b0e8`). The latest merged
Fastmail resilience is ADR-110/PR #133. ADR-157/PR #144 at `96cb22b`
adds a bounded Ask output-text slice; full response/token and grounded-chat
acceptance remain open.
This is a dependency-ordered plan, not a release claim.
The [Librarian interoperability review](LIBRARIAN_INTEROP.md) refines
[issue #174](https://github.com/jbone3311/MasterBrain/issues/174) and its twelve
children. ADR-169 records the code-first, proposal-only boundary; it adds no
working Markdown import/export. In particular, bounded FileOS CSV/XLSX extraction
already exists, attachment occurrences must not be collapsed by hash, and source
exclusions must precede any live fetch. ADR-186 adds the private source-stated
proposal queue and atomic human review; the Markdown importer, inference
basis, table locators and export remain implementation gates, not current
functions. ADR-182 adds reviewed project aliases; ADR-183 adds reviewed
project/entity roles, but not a current roster or role registry.
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
| Product identity and donor baseline | MasterBrain identity, source-layer boundaries, pinned FOS-Master provenance, first hash/dedupe parity and synthetic shadow corpus are in the repo; PR #167 adds exact-source Linux case/Unicode-name parity tests | Full semantic and operational parity, owner cutover decision |
| DataCore read path | Shared persistence, FileOS snapshot/publication, confined extraction, archive derivatives, generation activation/rollback and additive Email bridges work on synthetic/disposable data | Donor inventory-policy decision, live shadow, automatic/supervised work, hosted evidence storage and retention |
| KnowledgeCore | Reviewed evidence-linked base assertions, corrections, lexical search and change feed work; optional direct and grouped current-search/Ask unsuperseded review-chain leaves passed exact-head PostgreSQL, strict-runtime and restore gates; ADR-160 reviewed-event timeline, ADR-161 due-window commitment read and ADR-162 exact-project dossier passed merged-main gates; ADR-182 adds reviewed project-alias candidate resolution; ADR-183 adds evidence-backed project members/roles | Cross-kind/valid-time timeline, full dossiers, strict role registry, automatic candidate pipeline, evaluated resolution, rebuild and freshness proof |
| Brain API | Scoped progressive reads, grouped current Email/FileOS/knowledge search with explicit All/Email/FileOS focus, evidence drill-down and partial coverage work; extractive Ask has separate 8-KiB selector-input and returned-untrusted-text caps with visible truncation; a read-only reference client has fictional API parity; enrolled assistants have source-scoped Brain and direct Knowledge/unified reads; ADR-149 denies unfenced legacy Email routes to assistants | Hosted issuer enrollment and derived-cache revocation, cited answer synthesis, named-assistant adapter and full prompt/token/whole-response budgets |
| Owner chat and external assistants | A first-party read-only question workspace and external read client use the same Brain API; Ask returns exact quotes and a separate reviewed KnowledgeCore match list. ADR-163's explicit project-dossier drill-down merged with exact-head gates green; its original merged-main full CI and final strict gate were blocked before execution by hosted runners (#158), with later main commits green. ADR-164's explicit reviewed schedule merged with exact-head and merged-main gates green | Run the owner's interactive trial, evaluate held-out natural questions, corrections and contradictions, review any privacy-approved model adapter separately, then prove named-assistant identity/citation/revocation and hosted acceptance |
| Hosted read-only product | Local/CI synthetic paths and restore drills only | Owner-approved identity, source enrollment, operations, retention, alerts, incident/restore drills and live acceptance |
| FileOS replacement and effects | Private v2 generation plus human-only historical v1/v2 comparison API are merged; no cutover or source effects | Decide donor-policy edge behavior, prove sustained live shadow and v2 current/absence/rollback semantics, then a bounded rollback-ready cohort and owner sign-off; effects require a separate later approval |
| FOS intelligence preservation | Donor generic facts, statement factory, reconciliation states and cross-domain reports are inventoried; nine isolated recipe baselines through ADR-203 include Wells Fargo savings/brokerage/credit-line and old-template Schwab supplied text, while ADR-171/172/173 add Streetbeat-only typed candidates, private storage and owner inspection; ADR-189 adds a private current-FileOS text replay receipt, not runtime investment analysis | Extend known-answer/parity corpus across reports and Schwab's unsupported scanned/redesigned eras; prove complete source-PDF extraction for credit-line, trusted worker/source-tier attestation and PDF/OCR/Email derivation; explicit owner review/publication; then an evidence-linked cross-source company dossier |

## Next verified sequence

The active lanes are deliberately separate. A read-only owner trial and grounded
chat evaluation can proceed without a FileOS policy switch; the private hosting
pilot needs the owner's choices; reviewed source actions remain later work.
Each lane must pass its own acceptance gate before the next dependent step:

| Lane | Next concrete step | Gate that remains open |
|---|---|---|
| Product chat ([#92](https://github.com/jbone3311/MasterBrain/issues/92)) | Record the owner's fictional cross-source question trial, then test held-out questions, contradiction handling, answer/citation budgets and first-party versus API behavior | No model-written answer or named-assistant parity is accepted yet |
| Hosted read-only pilot ([#94](https://github.com/jbone3311/MasterBrain/issues/94), [#3](https://github.com/jbone3311/MasterBrain/issues/3)) | Deferred by the owner's synthetic-only decision. Continue fictional/disposable scope and exclusion proof; seek new explicit authorization and region, budget, retention, identity and exact-source decisions before any private pilot | No live source, hosted identity, recovery or operations acceptance exists |
| FileOS migration ([migration plan](FOS_MIGRATION.md)) | Review the six recorded donor-policy differences and fault/platform cases, then run an owner-authorized read-only shadow on a bounded root | No v2 current publication, FileOS effect, donor cutover or retirement is approved |
| FOS intelligence ([preservation assessment](LIVE_ALPHA_AND_FOS_PRESERVATION.md)) | Extend the nine isolated recipe baselines to report composition and Schwab's unsupported eras; prove credit-line PDF-to-text completeness, harden ADR-189's private FileOS text replay into a separately attested worker/source tier, then design owner review/publication and other-format proofs for the statement ledger | No donor-equivalent investment dossier, owner-approved statement row or verified holdings claim exists yet |
| Librarian interoperability ([review](LIBRARIAN_INTEROP.md), [#174](https://github.com/jbone3311/MasterBrain/issues/174)) | ADR-186 adds private source-stated proposals; ADR-197/200/201 add cited Markdown export, inventory and inspection; ADR-202/205 stage selected project/event/commitment/member rows; ADR-206/207 add separate selected fact/artifact-link staging and explicit atomic human review on an open PR | Hosted/merged-main gates for both new routes, inferred proposals, automatic dossier generation and full round trip remain open; overfull/uncitable exports refuse, and live-source acceptance requires separate approval |
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
