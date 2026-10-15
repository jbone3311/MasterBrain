# MasterBrain Implementation Status

The exact `0c64f8b` code head passed the complete fictional local suite on
Python 3.14 and fresh disposable PostgreSQL 17.11: 3,823 passed, 19 skipped,
zero failed; 691/692 PostgreSQL-marked tests executed. The cluster was removed.
Hosted exact-head checks still stopped before job steps for account billing,
and immutable-image XLSX execution and independent review remain open.

ADR-245's local native PostgreSQL 17.11 restore passed with a populated
fictional XLSX review/publication: 120 tables, 424 rows, five external
encrypted objects and two tenants with matching hashes and RLS checks. The
restored reviewed document was searchable. This proves local populated-row
durability, not isolated-worker execution; hosted Docker restore and
actual-image execution remain open.

ADR-244 removes caller-declared XLSX bridge code provenance. Server code
and migration 0086 enforce one semantic revision for new review/receipt
rows; 47 focused tests pass, including 44 PostgreSQL-marked executions.
The full local synthetic suite passes 3,819 tests with 19 skips. Actual-image,
hosted CI and independent populated restore remain open for this change.

ADR-243 makes the reviewed synthetic Email XLSX bridge operable through a
private worker command with exact scopes, account pin and tenant-bound SQL
login. Fictional command-to-PostgreSQL check, wrong-account refusal,
publication, replay and retrieval pass. The full local synthetic suite passes
3,819 tests with 19 skips. This checkpoint still needs actual-image command
execution, hosted CI and independent populated restore.

ADR-242 corrects ADR-241's unreachable combined credential: the API now
supports human-only, bounded XLSX result inspection and digest/count-bound
publication review; a separate worker uses the private bridge. Migration
0085 requires that review for every new receipt. Focused fictional PostgreSQL
tests pass 16/16. The complete local synthetic suite passes 3,806/3,806,
with 19 skips; actual-image execution, hosted CI and independent populated
restore have not been rerun for this correction.

ADR-241 adds an explicit human, digest-and-count-bound synthetic Email XLSX
publication on the existing attachment occurrence. It records normalized
text/chunks, provenance and an immutable tenant-fenced bridge receipt, then
lets generic Brain and Email-family search return the derivative only while
the source is current. Fictional PostgreSQL tests pass; actual-image execution,
hosted CI, independent restore, review UI, cell-level citations and live
Fastmail remain open. This is not a financial/source-tier approval.

ADR-240 adds a private, synthetic-only worker for one current Email XLSX
approval. It rechecks retained parent/part bytes, runs the pinned isolated
document extractor, and seals only complete bounded text in a separate
immutable, tenant-fenced result. Focused approval/result/migration tests pass
50/50 on disposable PostgreSQL at that checkpoint. ADR-241 separately adds
the reviewed DataCore document bridge; the worker alone does not publish.
Actual-image and hosted gates remain open.

ADR-239 adds a separate synthetic-only human approval row for one exact
currently bridged Email XLSX attachment. The service and SQL guard reject
nonhuman, wrong-account, paused-source and forged-parent cases; migration,
truncation and populated-upgrade tests pass on disposable PostgreSQL. It does
not run extraction, publish a document, search cells or enable live mail.
The full local synthetic Python suite passed 3,794 tests, 19 skipped and zero
failed; 677/678 PostgreSQL-marked cases executed. Hosted, actual-image and
independent restore gates remain open.

An exact-head CI check on `afb7cb8` failed before any test step; its
GitHub annotation explicitly names failed account payments or an insufficient
spending limit. This is an external runner gate, not a failing test. Hosted
CI, actual-image and independent restore must run before PR #245 can merge.

ADR-238 adds a nonpublishing synthetic Email XLSX physical-row proof bound to
exact retained MIME/part bytes, the pinned table image and an existing indexed
text digest. Fictional focused tests pass; actual-image, hosted and restore
gates remain. It does not approve Email XLSX extraction, publish cells, access
a live mailbox or make a financial claim.

The current branch's repaired full synthetic local gate passed 3,754 Python
tests with 19 skips on locked Python 3.11.13 and disposable loopback-only
PostgreSQL 17.11; 673/674 PostgreSQL-marked tests executed. Browser tests
passed 167/167, repository-wide Ruff/mypy and docs/structural checks passed.
The initial Unix-socket attempt was rejected by the trial's intended
loopback-only preflight and exposed migration 0081 expectations in older
upgrade tests; those were fixed before the green run. Actual Docker-image,
hosted exact-head and independent restore gates remain open. See
[BUILD_RECEIPT](BUILD_RECEIPT.md).

ADR-237 adds `masterbrain fileos replay-tier-xlsx-tables` with a closed
private config, exact review/source binding, mandatory tenant-bound worker
login and check mode that reads no selected workbook. Fictional command and
command-to-PostgreSQL tests pass. The actual-image reviewed receipt test is
collected but not run locally. Hosted/restore and live-root gates remain open.

ADR-236 now binds the confined XLSX table proof to one current human source-
tier review and stores only an immutable, tenant-fenced layout receipt after
a second locked source check. A fresh disposable PostgreSQL 17.11 run passed
11 focused replay and migration tests; Ruff and strict focused mypy passed.
ADR-237 adds the operator command; there is no table API/index, cell-level
citation, live root, financial approval or FOS-Master cutover. Actual-image,
hosted and independent
restore gates remain open.

ADR-235 now proves a fictional FileOS XLSX can be re-read through a confined
source root and the same pinned document image, with source/text and physical
row-layout digests. The primitive is pure and nonpublishing; ADR-236 adds a
current human-review receipt. No API table read, live root or source effect is
enabled. The actual-image case is collected but not run locally; hosted/restore
gates remain.

At code commit `5165a03`, a fresh local PostgreSQL 17.11 and locked Python
3.11.13 ran the full CI-mode Python suite: 3,726 passed, 18 skipped and one
failure solely because the actual Docker-backed trial requires Docker on this
Mac. All 670 PostgreSQL-marked tests executed. Browser 167/167, repository-
wide Ruff/mypy, structural deployment and docs checks passed. This is strong
local synthetic evidence, not green full CI, actual-image validation, hosted
acceptance or production readiness. The exact receipt is in
[BUILD_RECEIPT](BUILD_RECEIPT.md); hosted jobs still fail before starting due
to account payment/spending limits.

ADR-234 adds a separate fixed-profile XLSX row/cell projector that retains
physical sheet/row and positional cell information without changing indexed
text. Fictional pinned-donor plain/1,000-row values match; formulas yield no
partial table. A pure digest check binds rendered values/order to an existing
normalized document, not physical coordinates. This is nonpublishing and
awaits actual-image, hosted, review
and restore gates before any source-tier or Brain API claim.

ADR-233 now pins and replays the donor's XLSX table extractor on fictional
workbooks against DataCore. Ordinary authored values overlap, but structured
tables, cached-formula behavior, row caps, encrypted classification and `.xlsm`
are explicit differences. This is not complete FileOS replacement parity.

ADR-232 adds a synthetic-only, nonpublishing Email XLSX derivation proof using
the existing isolated shared DataCore document worker. It binds exact parent
MIME and part hashes, validates full extracted text/digest and preserves
occurrence identity; no Email bridge, receipt, live mailbox, index publication
or financial claim is enabled. Actual-image, hosted and restore gates remain.

The current branch corrects the synthetic combined-source demo's evidence:
its reviewed Melron project now links the exact email and file occurrences
containing its quote, rather than whichever email happened to bridge first.
The v2 demo requires fresh disposable state and activates the fictional FileOS
index for current search. The next synthetic slice adds one quoted event,
proposed relative-date reply request, source-stated note and generated-file
link; it does not infer a date or a person/role. On locked Python 3.11.13 and
disposable PostgreSQL 17.11, the expanded demo and adjacent
cross-source/fact/artifact suites passed 65 tests with one skip. Ruff, focused
mypy and docs passed on this slice.
Before that additive slice, browser checks passed 167/167 and the structural
deployment gate passed. A forced-CI full local run passed 3,694 tests with 18
skips and one expected runner-only failure because Docker is unavailable on
this host. It is **not**
an exact-head full CI pass. Hosted checks still fail before job start due to
GitHub account payment/spending limits; actual-image and independent Docker
restore gates remain open. No live-source or FOS-Master cutover is accepted.

ADR-231 adds a tenant-bound account row-lock function in migration 0080 and
acquires the existing account advisory lock before the final reviewed Email
PDF receipt check. Fictional races prove that a controlled disconnect winning
first prevents the receipt, while a direct privileged status update waits for
a replay that wins first. Completed document jobs are terminal/immutable;
shared runtime logins lack the new function grant. This is not live-provider,
actual-image, hosted or independent-restore acceptance.

ADR-230 exposes ADR-229's reviewed Email PDF text-layer receipt through a
private `masterbrain email replay-tier-pdf` command. A closed config pins one
account and immutable PDF image; a two-scope worker and tenant-bound database
login are mandatory. Check mode opens no selected MIME/PDF or processor.
Fictional controller/CLI and command-to-database tests pass, including
shared/owner login refusal. Real-container, hosted and independent restore
gates remain. No live mail, OCR or financial publication is claimed; ADR-231
later supplies the account-status transition fence.

ADR-229 now has a worker-only, current reviewed Email attachment PDF replay
receipt in protected migration 0079. It binds one child occurrence to its
approved extraction and retained parent MIME, re-runs ADR-228's isolated
text-layer proof and seals only digests/identities/page count after final
current/grant/authorization checks. Fictional PostgreSQL and SQL-guard tests
pass. ADR-230 adds the private command; no real-image execution, live mail,
OCR, sender/issuer proof or financial claim is enabled. ADR-231 later locks
the account row after the shared advisory lock; completed document jobs are
already terminal/immutable. Hosted/restore gates remain open.

ADR-228 now has a pure synthetic-only Email PDF attachment derivation proof.
It replays one exact MIME part with the isolated, pinned legacy PDF worker and
compares the whole DataCore text and image/policy normalizer. Changed parent
MIME, wrong part, partial/image-only/encrypted PDFs and invented text refuse.
That pure function itself adds no database receipt or review/currentness fence;
ADR-229 now adds them separately. It adds no operator command,
OCR/visual completeness, live Fastmail authorization or financial claim.

ADR-227 exposes one exact reviewed FileOS PDF text-layer replay through a
tenant-bound private `masterbrain fileos replay-tier-pdf` command. A closed
config pins source/root and immutable processor image; a document-only worker
token and DBA-bound tenant login are mandatory. Check mode reads no selected
PDF/review row and constructs no processor; fictional command-to-database
execution writes only ADR-226's digest receipt. No live root, actual image
container validation, OCR/visual completeness, issuer proof, financial claim
or FileOS cutover is accepted. Hosted and independent restore gates remain.

ADR-226 now records a worker-observed, point-in-time PDF text-layer replay for
one current human-reviewed FileOS document. ADR-225 supplies the confined
byte-to-text proof through the pinned restricted document processor; migration
0078 seals only digests, page count and source identity after final locked
currentness and optional authorization checks. Fictional PostgreSQL and full
local suite pass. ADR-227 adds the exact command; actual immutable-image
container validation, OCR/visual completeness, issuer authenticity, financial
claim, live root or
FileOS cutover is accepted. Hosted and independent restore gates remain open.

ADR-224 exposes ADR-223's current reviewed direct-parser Email MIME replay as
an exact tenant-bound operator command. A two-scope worker token and one
configured account are mandatory. Check mode validates private credentials,
account, database binding and optional encrypted storage without reading the
selected MIME or writing a receipt. Fictional inline/encrypted command-to-
database tests pass locally; no live account, attachment/PDF completeness,
financial approval or FileOS cutover is claimed. Hosted and independent
restore gates remain open.

ADR-219 exposes the FileOS tier-text replay through a restricted operator
command with a mandatory tenant-bound database login, exact review/source
selection and a document-publish-only worker token. Check mode never reads
the selected file or writes a receipt; execution reauthenticates inside the
final transaction. Synthetic command-to-database execution and revocation
rollback pass locally. No live source, PDF/OCR completeness, financial
approval or FileOS cutover is claimed; ADR-223/224 later add direct-parser
Email replay separately.

ADR-218 adds a point-in-time FileOS text-byte replay receipt for an ADR-217
human tier review and moves the shared confined read/text derivation into
DataCore. The older statement replay uses that same path without changing its
contract. This is an internal worker-scoped operation, not an exposed command
or a guarantee of later file freshness. Production worker credential gating,
PDF/OCR and spreadsheet coverage and financial publication remain open;
ADR-223/224 later add direct-parser Email replay. Full fictional local
PostgreSQL/browser gates pass; hosted and
independent restore gates remain open.

ADR-217 adds a current-source, source-granted human tier review record and
Brain API read/write routes. The row pins the stored source/document hashes,
exact quote and controlled T1/T2/T3 authority kind; an independent SQL guard
checks the current basis and reviewer context. The strict read client refuses
forged financial-truth meaning. This is a reviewed document classification,
not a trusted byte replay, OCR-completeness proof, corroborated value,
ownership statement or investment balance. Full fictional local PostgreSQL
and browser suites pass; hosted and independent restore gates remain open.

ADR-215 corrects catalog retirement: a newer deprecated revision now blocks
new project facts instead of exposing an older active revision. The Brain API
and provider-neutral client can list the database's latest bounded project-
fact vocabulary without source content; enrolled assistants and scoped human
clients can read it. Private fact-proposal preview reflects latest SQL status,
but no vocabulary-edit or automatic alias capability exists. Local fictional
focused tests pass; hosted and independent restore gates remain.

ADR-214 adds a versioned, code-and-SQL-controlled predicate catalog for **new
reviewed project facts**. Unknown names, wrong value types and wrong/missing
measurement units are rejected after exact idempotent replay and by the SQL guard.
Historical rows retain their original predicate and NULL registry version;
read formats are unchanged. Unknown names can enter the private fact-proposal
queue with an explicit preview warning but cannot be approved until a
reviewed catalog migration. This does not yet cover generic claims, events
or roles, map deprecated aliases, or provide a dedicated owner-approved
registry proposal queue. Issue #183 remains open. Local fictional
focused gates pass; hosted and independent restore gates remain.

ADR-213 strengthens ADR-212's quote binding: a typed amount and its
unit/currency must appear as complete lexical tokens, not substrings of a
larger figure or word. Migration 0072 validates previously typed rows and
fails closed on a misleading one; it never repairs evidence automatically.
This is still a source-stated lexical check, not verified ownership, a
portfolio balance or a certified currency interpretation. Local fictional
model, PostgreSQL and migration/recovery tests pass; hosted gates remain.

ADR-212 adds optional exact-decimal, unit and currency metadata to **new**
human-reviewed project facts under migration 0071. The amount string and unit
token must occur in the still-current source quote; old facts remain untyped.
Only the source-granted ADR-211 report exposes the typed object and strict
external client validation. No ownership, currency conversion, automatic
number extraction, certified balance or numeric aggregation is present.
Local fictional PostgreSQL and pure validation tests pass; hosted gates remain.

ADR-211 adds a read-only, source-granted project fact report API and validated
external-client method. It groups one bounded page of current-evidence,
reviewed source-stated facts by predicate; differing asserted previews and
disputed/retracted rows are page-local review signals. It does not aggregate
money, certify a contradiction, know currency/ownership, or create a complete
company dossier. Local fictional PostgreSQL tests pass; hosted exact-head
and merged-main gates remain open.

ADR-210 extends the isolated ADR-209 donor comparison to `top_entities`,
`entity_crossdomain` and `dollars_by_domain`. Fictional goldens and direct
read-only pinned-donor DuckDB replay cover duplicate mentions, spread,
filtering, rounding and 1,000-row repeats. All five donor report row shapes
now have a local comparison, but none is an authorized runtime report,
financial truth claim, live-source use or FOS-Master cutover. ADR-211's
separate reviewed-fact page is not a donor money report or investment total.

ADR-209 first added an isolated, nonpublishing comparison of the pinned
FOS-Master `coverage` and `timeline` intelligence-report row semantics.
Fictional goldens, exact-hash local donor replay and a 1,000-row repeat passed.
ADR-210 subsequently added the three remaining row-shape comparisons; neither
tranche reads a live database, certifies source freshness, calculates
investments or supplies a Brain API report.

ADR-208 adds a separate, replay-safe combined-source local demo. A fresh
disposable PostgreSQL instance, internal Email seed, DataCore Email bridge,
fictional FileOS snapshot/text publication and reviewed synthetic project
were exercised through a running loopback API: Brain search returned both
source kinds and the project exported a current cited Markdown dossier. The
old Email-only demo and its narrower token are unchanged. This is neither a
live Fastmail/FileOS root pilot nor hosted/assistant acceptance.

Private Knowledge proposal review now holds source-item and source-status
locks from current-evidence validation through approval. Member review also
locks the separately linked project and entity citation sources; a concurrent
source pause or current-version change waits for the transaction. This is a
synthetic-only transaction fence, not a live provider or Email exclusion
policy snapshot, and the generic direct Knowledge publisher is unchanged.

The fictional Cedar Harbor cross-source trial now tests the owner-selected
Markdown through actual fact and artifact-link proposal API routes and
explicit human review, then reopens both reviewed results and original
evidence. It does not automate sidecar creation, infer new facts, accept live
sources or prove a lossless dossier round trip. Exact validation is in the
build receipt.

ADR-207 adds a separate synthetic-only selected artifact-link Markdown queue
on the open PR: exact selected line, typed full-quote sidecar, current local
project, artifact and separately cited basis are checked at stage, private
preview and atomic human review. Migration 0070 protects private immutable
batches, decisions and reviewed publication receipts. Local full/restore
tests are tracked in the build receipt. Hosted and merged-main acceptance,
inferred basis, live-source use and FileOS cutover remain open.

ADR-206 now adds selected project-fact Markdown staging into a separate,
private synthetic proposal queue. Its typed sidecar supplies the full quote,
evidence set, observation time, confidence and value type omitted by the
export; the visible line must match exactly. Preview and explicit atomic
human review recheck current project and evidence grants. A fact-specific
review receipt publishes approved rows through the same validated
transaction-bound direct fact primitive; rejected rows never publish. This
open-PR implementation has local synthetic tests, but hosted and merged-main
gates remain outstanding. It is not inferred-fact
review, automatic approval, live-source access or a lossless round trip.

ADR-205 extends the synthetic-only, owner-selected Markdown import to one
selected project-member role per typed proposal row. A member needs an already
reviewed local project and person/organization entity; the visible line,
entity citation and member quote must match exact current authorized evidence.
Immutable private proposal rows now retain the selected citation IDs so
preview and explicit human review recheck the same bases. Approval creates a
new local member ID, never a permission. Project facts, artifact links,
inference, full round-trip fidelity and live-source acceptance remain open.

ADR-204 extends the disposable Cedar Harbor trial with a reviewed project,
appraisal event, Email-plus-FileOS commitment, exact FileOS term-sheet link
and source-stated loan fact. The existing compact and Markdown dossier APIs
and provider-neutral client now have one coherent fictional cross-source
acceptance case, including original-evidence drill-down and a file-only
assistant denial. This is not a live-source result, investment analysis,
automatic import/review, inferred fact or FileOS cutover. The owner selected
the current MasterBrain Markdown export as the later Librarian import exemplar;
ADR-200 through 202 still stage only a subset as unreviewed proposals.

ADR-203 adds a ninth isolated, exact-hash FOS-Master statement text-recipe
comparison for Charles Schwab brokerage. Fictional old-template rows and
failure-era inputs test Cash-and-Bank-Sweep headings, positional/inline tickers,
parenthesized cash flows, confidence downgrade, zero fallback and a 1,000-row
repeat. It is not a source-PDF/OCR extraction proof, typed statement proposal,
reviewed investment, live source or FileOS cutover. Exact validation is in
the build receipt.

ADR-202 adds a synthetic-only human route that stages selected project,
event and commitment rows from the owner-selected Markdown format as private
ADR-186 proposals. The typed sidecar must supply omitted full quotes,
observation time, confidence and evidence links; visible fields must match
exactly. Same-transaction current/full-quote checks and an immutable import
context digest prevent altered citations and conflicting idempotent replay.
No proposal is automatically reviewed; ADR-205 later adds member staging,
while fact and artifact-link imports now use separate ADR-206/207 queues;
inferred imports, live sources and full
round-trip fidelity remain open. Source claimed
IDs are selection markers, not publication IDs; selected child rows require
an existing local project. Local/hosted
validation is tracked in the build receipt.

ADR-201 adds a synthetic-only, human-only Brain API inspection of the
owner-selected MasterBrain dossier Markdown. It checks every claimed quote
preview against that citation's current, granted, nonexcluded normalized
evidence in one tenant-fenced transaction and refuses a partial inventory.
It does not stage or approve a Knowledge proposal, verify the full stored
quote or observation time, certify freshness or access a live source. Focused
fictional API/PostgreSQL and full-gate results are in the build receipt.

ADR-200 is merged on `main` via PR #239 as a synthetic-only, read-only intake
checkpoint for the owner-selected
MasterBrain dossier export format. It inventories fixed sections and claimed
IDs/citations under strict bounds; a fictional database test parses an actual
ADR-197 export. It does not verify input citations, stage Knowledge proposals,
infer an observation time from the export cutoff, import full assertion fields,
approve rows or complete a Librarian round trip. Exact-head hosted full CI,
strict runtime and logical restore passed; independent merged-main validation
is tracked in the build receipt.

ADR-199 adds an eighth isolated, exact-hash FOS-Master statement recipe
comparison for Wells Fargo Priority Credit Line supplied text. Nine fictional
goldens and pinned-donor replay cover both donor layouts, debt-negative
balances, optional fields, linked-bank exclusion, unknown transaction labels,
page/header noise and incomplete text; a 1,000-row repeat checks stability.
This pure parser is not a PDF source-to-text proof, runtime intake, a typed loan
proposal, a verified debt claim or a FileOS cutover. Schwab and donor reports
remain outside the parity corpus, and FOS-Master remains unchanged.

ADR-198 adds a seventh isolated, exact-hash FOS-Master statement recipe
comparison for Wells Fargo brokerage. Fictional goldens cover cash, acquired
lots, page-break lot deduplication, more-than-six-lot summaries, zero fallback,
incomplete tails and reconciliation; an optional pinned-donor AST replay and
1,000-row stress check protect the extraction. It is not connected to runtime
intake, statement proposal publication, the Brain API or a live source. The
donor remains unchanged; Wells Fargo credit-line, Schwab and intelligence
reports still needed their own corpus and acceptance at that checkpoint.

ADR-197 is merged on `main` via PR #232 as a synthetic-only tranche: an exact-project
Markdown read combines independently bounded reviewed events, commitments,
members/roles, related artifact occurrences and source-stated facts. It
verifies older assertions' full quotes at export time and refuses an uncitable
or overfull dossier without a partial body. It does not add inferred facts,
automatic artifact matching, a Markdown importer, source-freshness proof or
live-source acceptance. Exact-head hosted full CI, strict runtime and restore
passed, as did independent merged-main full CI, strict runtime and restore;
the build receipt links each run.

ADR-196 is merged on `main` via PR #230 as a bounded, synthetic-only
Markdown **fact fragment**. It reuses ADR-195's pre-limit current-source and
exact-quote visibility, adds a separate content-read scope, escapes all
untrusted text, and reports partial coverage with a cursor. This is not a
complete project dossier or a live-source acceptance result; local and hosted
gates are tracked in the build receipt; exact-head and independent merged-main
full CI, strict runtime and populated restore all passed.

ADR-195 is merged on `main` via PR #228 as a synthetic-only, source-stated
project-fact capability. A distinct
immutable, tenant-fenced table freezes the direct evidence set and quote basis;
the SQL guard and human route require current nonexcluded evidence and an exact
normalized-text quote. A separately paged Brain API read and independently
bounded dossier section filter every source before limits, with reference
client and inert owner-workspace validation. The fact is **not** in generic
Knowledge lexical search/change feed yet; no inferred basis, controlled
predicate registry, typed currency, complete Markdown dossier or
live-source acceptance is claimed. Exact PR-head and independent merged-main
full CI, strict-runtime and populated restore all passed.

ADR-194 extends the exact-project dossier with an independently bounded
reviewed artifact-link history section. The owner workspace and reference
client validate and show exact evidence IDs under current source grants; the
same visibility predicate as ADR-193 runs before the dossier limit. This
remains synthetic-only and does not present a computed current file roster,
filenames/bytes, source freshness or export-ready citations. Source-scoped
export-time citation checks for older assertions and a complete Markdown
renderer remain open; ADR-196 adds only the narrow source-stated fact fragment.

ADR-193 adds a synthetic-only, human-reviewed association between one exact
project and one exact Email/FileOS evidence occurrence, with a separately
quoted current basis. A bounded Brain API page returns link status, source
kind and evidence IDs only after project, artifact and basis grants pass; it
does not expose paths, text or an inferred match. Immutable tenant-fenced
migration 0065 and fictional PostgreSQL/API/client tests cover replay,
cross-tenant/source denial, exclusion and pagination. A full related-files
dossier, Markdown export and live-source acceptance remain open. ADR-194
adds the bounded historical artifact display; branch/hosted verification is
in the build receipt.

ADR-192 closes a project-alias citation hole in ADR-186's synthetic private
proposal batches: every alias quote must appear in its own current, granted,
nonexcluded normalized evidence at stage, preview and review. This does not
retroactively validate directly published reviewed assertions, prove semantic
truth, or implement a Markdown dossier. The direct-publication and export-time
citation gates remain open.

ADR-191 adds a sixth isolated, exact-hash donor recipe comparison for Wells
Fargo savings. Fictional daily-balance groups preserve single-row signs,
whole-day direction, mixed keyword/residual and bounded subset resolution,
ambiguous/no-solution low-confidence defaults, missing balances and a
1,000-row repeat. This pure float parser is not called by runtime intake or
financial publication and is not a verified bank balance, live statement,
FileOS cutover or donor-equivalent investment analysis.

ADR-190 connects the existing private FileOS text replay to the disposable
fictional browser trial. Startup reopens its own synthetic statement file and
fails closed if the private receipt cannot be recorded. The trial self-test
checks the saved source digest; the owner still sees only an unreviewed
proposal. No live root or public verified-investment claim is enabled.

ADR-189 adds a synthetic-only private worker library that reacquires exact
current FileOS bytes through the no-follow DataCore reader, reruns ADR-188's
bounded text transform and records an immutable, tenant-fenced replay receipt
for one existing statement proposal. It double-checks the source/version/root
basis around the read; direct SQL can only insert a row matching stored basis,
not prove the worker ran. The public owner preview and reviewed KnowledgeCore
remain unchanged: there is no user-facing verified holding or live-source
acceptance. PDF/Office/OCR/Email proof, a separate worker-login attestation
boundary and explicit financial review/publication are still open.

ADR-188 adds a synthetic-only pure byte-to-text replay check for the exact
`fileos-text-v1` transform. It rejects a source digest paired with unrelated
normalized text and leaves a digest-only proof value; ADR-189 now uses it in
the private FileOS receipt path, but not the owner preview. PDF/Office/OCR,
Email attachments, robust worker attestation and reviewed financial publication
remain open. The existing statement preview is **not** verified investment truth.

ADR-187 adds a fifth isolated, exact-hash donor statement recipe baseline for
Jefferies. Fictional category holdings, lower-confidence security details and
transactions preserve negative cash, multi-lot grand totals, subtotal skips,
zero fallback and wrapped-continuation loss. The pure parser is not called by
runtime intake, KnowledgeCore publication or Brain API. It does not establish
portfolio completeness, investment truth, a live source or FileOS cutover.
Verification and merge status are recorded in the [build receipt](BUILD_RECEIPT.md).

ADR-186 adds a synthetic-only private batch queue for 1–50 source-stated
Knowledge assertions. It checks exact quotes against current, granted,
nonexcluded DataCore evidence at stage, preview and review; 40-row fictional
approval/rejection, rollback and RLS cases exercise atomic explicit decisions.
Only approved rows pass through the existing reviewed publication path. No
Markdown importer, inferred claim, automatic model approval, live source or
FileOS cutover is implied. Final exact-head and merged-main gates are tracked
in the [build receipt](BUILD_RECEIPT.md).

ADR-185 adds a synthetic/disposable SQL visibility fence for retained Brain
search, direct evidence/content and changes, plus reviewed KnowledgeCore
assertions, when previously ingested Email later becomes mailbox-excluded.
Parent, attachment and approved-document bridge receipts resolve to the same
current exclusion state. The filter is applied before ranking/pagination and
conjoined with source grants. No immutable history is purged; privileged
historical Email access, policy changes on used accounts, and real-provider
acceptance still require separate owner decisions and tests.

ADR-184 adds a synthetic scoped Email mailbox exclusion: an exact, sorted
private-mailbox set is bound to the account/cursor fingerprint, checked against
`Email/get` membership before provider or retained-byte access, and recorded
as `excluded` rather than a false deletion. Existing current Email/Brain search
is hidden in the same transaction; immutable evidence is not purged. Internal
reconciliation retains an opaque provider ID; user-facing sync status exposes
only an excluded count. Sender/category policies, retroactive purge, policy
changes on a used account and live Fastmail acceptance remain open. ADR-185
subsequently adds the retained Brain/reviewed KnowledgeCore read fence.

ADR-183 adds evidence-backed, reviewed person/organization roles on a project,
with immutable history, source-grant-safe exact/project-dossier/search/change
reads and separately bounded members in the reference client and first-party
workspace. This is a synthetic implementation tranche, not a current roster,
access-control role, automatic Librarian import, or live-source acceptance.
Its branch verification and merge status are recorded in the build receipt.

ADR-182 adds reviewed, evidence-linked project aliases, a candidate-only
source-scoped lookup API and provider-neutral client method. A shared address
returns multiple candidates rather than merging deals. The append-only SQL
manifest prevents later direct alias additions to a reviewed project; old
projects retain exact-title fallback without a heap rewrite. PR #203 passed
exact-head and merged-main full PostgreSQL CI, strict-runtime and populated
restore gates; see the [build receipt](BUILD_RECEIPT.md). This is not
automatic entity matching, current-project truth or a complete dossier.

ADR-181 adds a fourth isolated FOS-Master statement recipe baseline for Morgan
Stanley OCR text. Fictional exact-donor comparison preserves a cash-bucket
sub-component exclusion, parenthesized debits, OCR confidence/date loss and
the zero-total fallback. It is not runtime OCR, a verified investment report,
complete activity capture or FileOS cutover.

ADR-180 adds a third isolated, donor-matched statement recipe baseline for
OCR-derived bank text. Fictional cases exercise a wrapped amount, December to
January date assignment, mismatch, invalid dates and 1,000-row repeatability.
It is not runtime OCR, bank-account intake, a reviewed financial fact or a
FileOS cutover. Other donor recipes and intelligence reports still need parity.

ADR-179 adds a local owner-managed `fastmail-source` command to check, atomically
create a previously absent exact pinned Fastmail account, or disconnect it
without changing its pin or evidence. It requires a human-only management
credential, current owner membership, an exact worker tenant and explicit
account/scope confirmations. Fictional CLI/disposable PostgreSQL tests include
mid-download disconnect refusal. It does not contact Fastmail, revoke its
token, reactivate a source, hide retained history, approve a live mailbox pilot
or provide hosted enrollment.

ADR-178 adds version-2 private `sync-read` configuration for one exact
mailbox/date window and binds preflight, every guarded request and worker
construction to ADR-177's account pin. Fictional HTTPS/disposable PostgreSQL
tests cover restart, wrong pin, out-of-scope metadata, tenant denial, pause and
mid-step revocation. Version 1 stays account-wide. ADR-179 adds a separate
synthetic local enrollment/disconnect command; real Fastmail acceptance and
hosted service remain absent.

ADR-177 adds a synthetic/disposable PostgreSQL account pin and worker
lease/cursor fence for the ADR-176 scoped Fastmail mode. The old account-wide
`sync-read` preflight refuses a pinned account before constructing a provider
client, and its database lease path is independently fenced. ADR-178 adds the
private scoped operator and ADR-179 adds local reviewed enrollment/disconnect;
real-provider acceptance remains absent.

ADR-176 adds a synthetic-only scoped Fastmail inventory worker with version-4
scope-bound checkpoints, repeated filtered scans and pre-download metadata
checks. ADR-177 binds its lease and cursor to an administrator-pinned account
fingerprint but does not connect it to `sync-read`; a real folder/date pilot
remains unapproved. ADR-178 separately connects the scoped worker to version-2
private configuration.

ADR-175 adds a typed Fastmail mailbox/date query filter and a separate metadata
scope check, now used by ADR-176's opt-in library worker. Version-1 CLI
configuration instantiates the unscoped account-wide worker; version 2 uses
the exact scoped worker under ADR-177's SQL fence. Reviewed enrollment and
provider-read acceptance remain required before a private Fastmail pilot.

ADR-174 adds an isolated, behavior-matched Fidelity recipe baseline with six
fictional goldens, optional exact-hash donor replay and 1,000-row stress. The
donor's two-column missed-row and zero-total fallback limitations remain
visible. This is not runtime intake, a typed Fidelity proposal, verified
investment data or FileOS cutover.

ADR-173 adds a human-only, source-rechecked and paged read-only API preview of
ADR-172's private statement proposals. Each returned row has a bounded quote
from its immutable normalized document and an explicit proposed-extraction
label. The fictional browser trial opens one such row on explicit click through
the same API. It is not a live first-party investment dossier, assistant route,
approval, reviewed holding or live source. Synthetic PostgreSQL/API verification
is tracked in PRs #192 and #193; owner interactive acceptance remains separate.

ADR-172 adds an additive private PostgreSQL ledger for one explicitly selected,
current normalized Email/FileOS statement. A scoped worker verifies the
document/evidence/source-version binding and records exact-decimal candidate
rows, coverage status and idempotency receipts; tenant isolation and direct-SQL
guards passed disposable PostgreSQL, exact-head and merged-main full CI,
strict-runtime and populated restore via PR #190. This does not expose an API/CLI,
owner review, verified holdings, a live source or FileOS cutover. Hosted gates
for this tranche are tracked in the [build receipt](BUILD_RECEIPT.md).

ADR-171 adds private, in-memory exact-decimal Streetbeat row candidates for
fictional Email/FileOS evidence references, with extracted-text SHA-256 and
row spans. The standalone projector does not ingest, store, source-grant check,
review or serve them; ADR-172 is the separate worker-persistence boundary.
The donor's other recipes and investment reports are not preserved yet.

ADR-170 adds an isolated Streetbeat statement-recipe parity candidate
with fictional donor goldens. It is not connected to ingestion, KnowledgeCore,
Brain API or real statements, and does not make investment analysis operational.
The float-based donor semantics are preserved only for comparison; a typed decimal,
evidence-linked projection needs a separate reviewed tranche.

Updated 2026-10-05. The preceding merged grouped Brain/Ask read checkpoint is
ADR-159/PR #148 at `f9402d7`: unsuperseded reviewed leaves in the all-source
Knowledge layer, with exact-head full CI, strict runtime and populated restore
green. The subsequent documentation-only merged-main checkpoint could not
start Actions jobs because of [billing/limit issue #150](https://github.com/jbone3311/MasterBrain/issues/150).
Actions recovered for ADR-160 [PR #151](https://github.com/jbone3311/MasterBrain/pull/151):
implementation commit `d52b167` passed executed full PostgreSQL/worker CI,
strict-runtime and restore gates. PR #151 merged at `90ee9e4` and its
merged-main CI, strict-runtime and restore gates passed too. ADR-161's
commitment due view merged in PR #152 at `e3826ff`, with exact-head and
merged-main gates green. The prior direct KnowledgeCore read
checkpoint is ADR-158/PR #146 at `3bf21b8`, with exact-head and merged-main
checks green. The prior Ask output-budget checkpoint is
ADR-157/PR #144 at `96cb22b`: aggregate Ask output-text budgeting, with
exact-head and merged-main CI, strict runtime and restore green. The latest Email functional
checkpoint is ADR-110/PR #133 at `ff7a296`: synthetic Fastmail read-worker resilience,
with exact-head and merged-main CI, strict runtime and populated restore passed.
ADR-154/PR #137 later strengthens the disposable two-tenant restore drill;
it changes no product runtime path and does not close hosted issue #7.
ADR-155/PR #139 extends that proof to a fresh target PostgreSQL cluster,
including orphaned role-binding retirement and new target login enrollment.
It remains a synthetic drill, not managed-host credential recovery.
The runs are linked in the [build receipt](BUILD_RECEIPT.md); no live
mailbox is accepted. The latest FileOS shadow hardening checkpoint on `main` is
ADR-156/PR #141 at `082b0e8`; its corrected exact head passed full CI, strict
runtime and populated restore. The prior ADR-152/PR #130 at `c834fef` also
passed exact-head and merged-main checks. Later documentation checkpoints and Fastmail
integration evidence are tracked in the [build receipt](BUILD_RECEIPT.md).
ADR-151/PR #128 at `14e91f0` passed exact-head and merged-main full CI,
strict runtime and populated restore. ADR-150/PR #126 at `c984a2e` passed
exact-head and merged-main full CI, strict runtime and populated restore.
PR #125 at `8e62664` and
ADR-149/PR #120 at `0591eac` also passed these
gates. The previous ADR-148/PR #118 at
`46aa000` also passed those gates. The last functional FileOS slice is
PR #116 at `b6ebcbf`; its final-head and merged-main gates passed. Tagged
synthetic checkpoint `v0.2.0a1` is
`c0a531d8a7d0991be0a0f1ea717479c07cc20feb`; its exact full CI,
strict-runtime, populated restore and local pinned-donor DataCore parity passed.
**Implemented** means executable in this repository; it does not
mean hosted, live-source accepted, or production ready. The cumulative stack first
landed on `main` through PR #28 (`2dd4a85`), followed by strict-runtime PR #31
(`20bfc1f`), privacy-safe API logging PR #33 (`c605e64`), fictional cross-source
trial PR #32 (`77192f5`) and reconciled documentation PR #30 (`1e081ea`).
Exact baseline `main` CI,
strict-runtime and populated restore passed. See [current functions](CURRENT_FUNCTIONS.md)
for callable paths. The individual PR receipts below are historical verification,
not still-open integration work. Interactive Mac acceptance, issues #7/#9,
production and FileOS cutover remain open.

## Implemented

- ADR-164 adds an explicit read-only reviewed schedule panel in `/brain` over
  the existing event timeline and due-commitment APIs. It requires a bounded
  UTC window and All focus, validates each compact page, and provides separate
  evidence drill-down. PR #159 exact-head and merged-main full CI,
  strict-runtime and restore gates passed. It is not live source status or an action.

- ADR-163 adds an explicit, read-only reviewed-project dossier control in the
  first-party `/brain` Ask and Search only results. PR #156 exact-head full CI,
  strict-runtime and restore passed. Merged-main restore passed; full CI and
  the final strict gate were blocked before execution by hosted runners
  ([#158](https://github.com/jbone3311/MasterBrain/issues/158)). It uses
  the existing scoped API and cannot claim live project truth or source effects.

- ADR-162 adds a merged, bounded, read-only exact-project dossier with
  source-aware linked events and commitments, including undated links. Local
  disposable PostgreSQL behavior and migration checks passed; PR #154 exact-head
  CI, strict-runtime and restore gates passed, as did the merged-main checks.
  It does not reconcile
  project truth, certify freshness or authorize FileOS effects.

- ADR-161 introduces an additive due-time index migration and a read-only,
  source-aware reviewed-commitment due-window API/client. Exact-head and
  merged-main gates passed; it does not compute overdue status,
  change FileOS or assert hosted/live-source acceptance.

- ADR-160 adds a bounded, recorded-cutoff-paged reviewed-event occurrence timeline
  under `knowledge.search`, with source-aware project filtering and retained
  or unsuperseded visibility. It excludes undated events and claims no source
  freshness, cross-kind timeline or hosted acceptance. An isolated local
  PostgreSQL 17.11 database passed the 488 executable PostgreSQL-marked tests;
  the Docker browser launcher skipped locally. Exact implementation-commit CI
  subsequently executed all 489 PostgreSQL-marked tests and the worker,
  strict-runtime and restore gates. This does not establish hosted acceptance.

- ADR-159 composes ADR-158's source-grant-aware unsuperseded projection into
  grouped Brain current-search and Ask, with explicit coverage labeling.
  Direct KnowledgeCore and unified retained-history searches remain unchanged;
  multiple leaves are not valid-time truth. Exact-head PostgreSQL, strict
  runtime and restore gates passed; merged-main checks are in the receipt.

- ADR-158 adds an optional `unsuperseded` direct KnowledgeCore lexical mode.
  It omits correction records and predecessors only when source-authorized
  successors or corrections with visible replacements exist, before rank and
  limit. Retained history is still the default. This is a review-chain leaf
  view, not valid-time truth, contradiction resolution, grouped Brain current
  KnowledgeCore behavior, or hosted acceptance. Exact-head PostgreSQL and PR
  gates passed; merged-main checks are tracked in the build receipt.

- ADR-157 caps aggregate exact quote plus reviewed KnowledgeCore display text
  returned by Ask at 8,192 UTF-8 bytes. Exact quotes and links remain intact;
  reviewed excerpts may be shortened or later matches omitted with a separate
  output-truncation flag. The client and browser reject over-budget responses;
  browser character/offset checks now match the API's Unicode code-point
  semantics. This is not a total response or model-token budget.

- ADR-156 removes symlink-target type probing from the nonpublishing FileOS
  donor-policy shadow. Directory links become coverage errors, and new
  candidate/profile versions refuse reuse of old-policy packets for staging.
  This is synthetic hardening, not live-root or FileOS cutover acceptance.

- ADR-152 makes the nonpublishing FileOS donor-policy shadow enumerate each
  directory through a no-follow descriptor instead of `os.walk`. Synthetic
  descendant/ancestor swaps and an after-open move now produce directory
  coverage errors without listing outside filenames. The pinned 3,000-file
  donor comparison still matched 3,004 ordinary rows with six known policy
  gaps. PR #130 passed exact-head CI, strict runtime and restore; this is not
  a publishable scanner or live-root acceptance.

- ADR-151 bounds the extractive Ask selector's source passage text by UTF-8
  bytes (2,048 each, 8,192 total), retains exact prefix citations and reports
  truncated context to the API, read client and first-party UI. This is not a
  tokenizer-aware prompt limit, whole-response budget, remote model approval
  or hosted acceptance.

- ADR-150 adds an optional, explicit All/Email/FileOS focus to grouped current
  search and extractive Ask. The API skips excluded source and KnowledgeCore
  reads, keeps the response shape, reports unsearched layers, and rechecks
  answer citations within the selected focus. `/brain` and `BrainReadClient`
  use the same contract. This is local/fictional read behavior, not an access
  grant, hosted assistant integration or model-based source selection.

- ADR-168 makes Email and FileOS independently optional in the grouped current
  search and extractive Ask coverage response. The source-kind map distinguishes
  a registered visible source from no registered source, a hidden/ungranted
  source, and a focus-excluded source. It does not claim a live connector,
  current index or complete query coverage; detailed readiness remains in
  `/v1/brain/current-coverage`.

- ADR-149 excludes assistants from legacy `email.*` API dependencies before
  route work, refuses bootstrap assistant Email scopes and rejects old OIDC
  Email-only assistant bindings at each Store transaction. Enrolled assistants
  continue through source-filtered Brain/Knowledge reads. This chooses a
  single assistant read surface; it does not certify a hosted issuer, named
  assistant or derived-cache revocation under issue #88.

- ADR-148 adds a default refusal before unapplied legacy migrations 0008 and
  0009 rewrite populated `message_versions` or `raw_objects`. A nonwaiting
  writer-fencing lock makes the emptiness check stable until DDL, and a
  five-second lock budget bounds readers that block the stronger DDL lock. The explicit
  administrator maintenance override preserves the old SQL and its provenance
  checks; it is not an online upgrade or issue #9 closure. PostgreSQL tests
  exercise both refusals, a concurrent writer, the override and replay.

- ADR-147 gives the existing ADR-128 historical FileOS v2 search reviewer a
  bounded, human-only Brain API route for one named ready generation versus
  active v1. The route requires transition-review, search and evidence scopes,
  labels v2 as a historical preview and refuses stale baselines; assistants
  cannot call it. PR #116 merged with final-head and merged-main full CI,
  strict runtime and populated restore green. This is synthetic/disposable
  review access, not an owner UI,
  v2 current visibility, live-source acceptance or FOS-Master cutover.

- ADR-146 adds a bounded, separate reviewed KnowledgeCore match list to Ask,
  with at most five displayed direct evidence IDs per assertion and a full
  source-grant/evidence-link recheck before disclosure. The first-party page
  renders these as inert text beside exact DataCore source quotes; the external
  client validates the same response. The fictional trial now includes one
  reviewed cross-source commitment. This is not automatic claim synthesis,
  KnowledgeCore current-state resolution or hosted acceptance.

- ADR-145 derives a bounded lexical query for extractive Ask by removing only
  fixed question boilerplate. Initial and final current-source searches use
  the same terms; the selector sees the original question. Fictional
  PostgreSQL Email/FileOS evidence supports a natural-question known answer
  that literal full-question search misses. No synonym/semantic understanding,
  hosted acceptance or source-effect authority is implied.

- ADR-144 makes the first-party Ask route return locally selected, bounded
  exact source quotes by default. This is deterministic retrieval over already
  authorized evidence, not a model-generated answer or remote inference;
  `answer_selector=None` restores the fixed 503/fallback behavior. The owner's
  interactive Mac walkthrough and live/hosted acceptance remain open.

- ADR-143 applies the all-direct-evidence source-grant predicate to Knowledge
  assertion expansion and change-feed anchor/page selection, admits enrolled
  assistants to direct Knowledge and unified Brain reads, and extends OIDC
  scope/source fences through migration 0051. This is synthetic read-path
  containment, not hosted identity, semantic information-flow certification,
  legacy Email assistant access or issue #88 closure.

- ADR-142 extends enrolled-assistant reads to retained DataCore search,
  aggregate current FileOS/Email searches, and exact-source FileOS status,
  preview, index and active search. Filtering precedes limits; hidden sources
  return not found. At that checkpoint direct Knowledge, unified and legacy
  Email routes remained denied; ADR-143 later admits the first two. Hosted
  issue #88 acceptance remains open.

- ADR-141 adds opt-in `--tenant-bound-db` to legacy `email-brain sync-read`,
  `process-jobs` and `process-documents`. The authenticated worker tenant binds
  preflight and execution, including encrypted stores and read-worker reopen,
  to one PostgreSQL login. Fictional two-tenant tests cover all three modes;
  this is not credential lifecycle or hosted issue #7 acceptance.

- ADR-140 makes the fictional Mac trial launcher install non-editably and run
  without a second implicit sync. Its actual local PostgreSQL 17.11 self-test
  passed on the affected Mac after the editable `.pth` import failure; this is
  not the owner's browser acceptance or a hosted/live-source product claim.

- ADR-139 extends opt-in `--tenant-bound-db` to every private `masterbrain`
  Email bridge and FileOS archive derivative command, including previews and
  sealed batches. A shared DataCore helper binds the authenticated worker
  tenant to one login; synthetic two-tenant PostgreSQL tests cover all check
  modes plus selected Email/archive publication and replay. At that checkpoint,
  legacy worker routing, credential lifecycle, hosted adversarial acceptance
  and issue #7 remained open; ADR-141 later routes the three worker commands.

- ADR-138 adds an explicit `--tenant-bound-db` mode to private FileOS index
  build/activation and activation-only rollback. Both modes require the
  authenticated worker tenant's DBA-bound login even in check mode; shared,
  owner and wrong-tenant logins fail. The default local mode and other private
  workers remain unchanged. This is synthetic/disposable containment, not
  closure of issue #7, hosted acceptance or FileOS cutover.

- ADR-137 adds a disposable local PostgreSQL 17 option to the fictional browser
  trial so an owner Mac without Docker can exercise the same API and seed. It
  creates no live-source or existing-database access. The Mac command now
  chooses a supported Python 3.13–3.14 patch; its actual self-test passed on
  Python 3.14.7 and Homebrew PostgreSQL 17.11. The server also started and
  stopped cleanly, but the Mac was locked during browser inspection. The
  owner's interactive walkthrough remains open.

- ADR-136 returns plain search excerpts from shared DataCore and KnowledgeCore
  reads, so the trial and `/brain` do not show PostgreSQL highlight markup.
  The fictional trial displays verified bounded source text, with provenance
  separately expandable. An agent-run local browser check on synthetic data
  covered Cedar Harbor, insurance, no match and evidence drill-down; the
  owner's independent walkthrough and all live/hosted acceptance remain open.

- ADR-135 adds an explicit `--tenant-bound-db` mode to the private FileOS
  publisher. Check, publication and replay use one authenticated worker tenant
  and a DBA-bound single-tenant login; a shared, unbound or wrong-tenant login
  fails before intake. The default legacy local mode and other private workers
  remain unchanged. This is synthetic/disposable containment, not closure of
  issue #7 or hosted multi-tenant acceptance.

- ADR-134 adds an optional, provider-neutral extractive answer boundary to
  `POST /v1/brain/answers`, the first-party `/brain` workspace and the external
  read client. The server bounds passages, rejects invented or stale quotes and
  returns exact evidence citations after a current-source recheck. ADR-144
  later provides a local default selector; explicit disablement returns 503
  and retains grouped-search fallback. This is not a configured model, freeform synthesis,
  hosted chat, named-assistant acceptance or source-effect capability.

- API-SOURCE-003 extends source-aware assistant reads to bounded current
  coverage and change-feed status under ADR-133 and forward migration 0050.
  OIDC status-only assistants still require explicit enrollment; hidden-source
  cursors fail closed, and grant removal invalidates saved contexts. The
  provider-neutral reference client uses the same routes. This is synthetic
  integration work: PR #96's exact-head and merged-main CI, strict runtime
  and populated restore passed. This is not hosted or named-assistant
  acceptance. Issue #88 remains open.

- API-SOURCE-002 adds an administrator-owned OIDC source-grant table, exact-key
  source-aware resolver and transaction-time revision/source checks under ADR-132
  and migration 0049. An assistant binding with Brain read scopes cannot mix
  legacy Email scopes or authenticate without an enrolled same-tenant source.
  Grant add/remove is audited and invalidates saved contexts at the next
  transaction. ADR-133 subsequently adds two source-aware status routes. This is a
  synthetic/disposable implementation, not hosted issuer enrollment, a
  named-assistant connection, cache revocation or full assistant route coverage.
  PR #91's exact-head and merged-main CI, strict runtime and populated restore
  passed; issue #88 remains open for the hosted and broader-route gates.

- ADR-131 adds a forward-only correction to the private FileOS v2 generation
  readiness gate. It uses indexed exact chunk comparison and base counting
  under the existing timeout, without changing SQL activation refusal, current
  search or FOS-Master. Fresh full-suite and two populated 3,000-row repeats pass
  locally; PR #90's exact-head and merged-main CI, strict runtime and populated
  restore passed. Issue #84 is closed; live-source and cutover gates remain.

- API-SOURCE-001 applies explicit, bounded source enrollment to synthetic
  bootstrap assistants using the initial three read-only client routes (ADR-130).
  Current Email/FileOS/archive searches and reviewed Knowledge results filter
  before limits; evidence metadata/content enforce the same allowlist, and
  initially unreviewed Brain/Knowledge routes are denied. Human reads are unchanged.
  Hosted issuer enrollment, derived-cache invalidation and full route coverage
  remain [issue #88](https://github.com/jbone3311/MasterBrain/issues/88).

- API-CLIENT-001 adds a provider-neutral, read-only reference client under
  ADR-129. It calls the same grouped current-search and separately scoped
  evidence/content routes as `/brain`, later extended to source-scoped coverage
  and change status by ADR-133, with fixed-origin, bounded-response,
  redirect and error-scrubbing guards. Fictional PostgreSQL conformance compares
  its results with direct Brain API calls. It is not a deployed or certified
  Claude/Grok/ChatGPT adapter, hosted service, model answer or action path.

- DC-002V adds a private human-review comparison of one ready historical
  FileOS v2 generation with the active v1 generation under ADR-128. Both use
  the same bounded lexical query, but their ranks remain separate. It requires
  transition-review, search and evidence scopes and refuses a stale v1 basis.
  This is not exposed in the Brain API or first-party workspace and does not
  activate v2, infer absence or switch FOS-Master.

- UI-001 adds a first-party, read-only question workspace at `/brain` under
  ADR-127. It uses the same scoped current-search and separately authorized
  evidence routes as external clients, shows independent Email/FileOS/archive/
  KnowledgeCore groups and partial coverage, and keeps credentials and turns
  only in browser memory. It provides no generated answer, source effect,
  hosted/live-source acceptance or certified external assistant connection.

- DC-002U adds a private worker-only FileOS v2 generation builder in shared
  DataCore index tables under ADR-126 and migration 0047. SQL binds it to one
  ready document attempt, closes exact item/chunk membership, and refuses v2
  activation. PR #81 merged with exact-head and merged-main CI, strict-runtime
  and populated-restore checks green. This remains synthetic/disposable only;
  no current-read, absence, live acceptance or FOS-Master cutover is claimed.

- DC-002T adds private, worker-scoped FileOS v2 document publication under
  ADR-125 and migration 0046. Bounded source reads recheck the staged digest;
  extracted text publishes on the prepared v2 version with existing chunks and
  provenance. A final exact rescan and immutable complete outcome ledger mark
  an attempt ready or blocked. Hashless rows gain no evidence. PR #79 is merged
  with exact-head and merged-main CI/strict/restore green. This remains
  synthetic/disposable only, with no v2 current index,
  activation, absence, live acceptance or FOS-Master cutover.

- DC-002S adds a private, worker-scoped FileOS v2 baseline completion under
  ADR-124 and migration 0045. After a fresh exact scan it seals the owner-
  authorized stage/prepared evidence as one historical baseline, with a
  compact locator-free private inspection. Hashless rows remain hashless;
  3,000 hashed rows and stale/changed-root refusals are exercised locally.
  No v1 current pointer, public freshness, absence, active index or search is
  switched. Synthetic/disposable only; live parity and rollback acceptance
  remain open. Exact-head verification is tracked in the build receipt.

- DC-002R adds private, human-owner FileOS v2 baseline authorization under
  ADR-123 and migration 0044. It binds the exact reviewed plan and prepared
  evidence to an immutable receipt after a latest-v1 check. Synthetic/disposable
  only: no fresh completion scan, v2 ledger, current read, absence inference,
  live-root authority or FOS-Master cutover. PR #75 merged with exact-head CI,
  strict runtime and populated restore green; details are in the build receipt.
  No version tag is implied by this internal tranche.

- DC-005N changes the private FileOS v1 completion writer to insert run items
  before its receipt; forward migration 0043 keeps the whole-ledger constraint
  but checks it once per receipt and serializes both receipt and item inserts
  under the source lock (ADR-122). PR #73 merged with exact-head CI, strict
  runtime and populated restore green. It removes the measured repeated-scan
  mechanism without changing completed-run, absence or v2 visibility semantics;
  a controlled performance comparison remains in issue #71.
- DC-002Q adds private, worker-scoped FileOS v2 hashed-evidence preparation
  under ADR-121 and migration 0042, merged in PR #70 with exact-head CI,
  strict runtime and populated restore green. After rechecking the current v1 receipt,
  review and historical verification, it scans again under the source lock,
  maps donor candidate IDs to policy-scoped DataCore versions and seals an
  immutable receipt. It does not change v1 current pointers, completion,
  freshness, absence, search or FileOS operation. It is synthetic/disposable
  only; DC-002R supplies owner authorization and DC-002S separately seals a
  private historical baseline. Current publication and rollback remain open.
  Legacy v1 large-completion performance is tracked separately in issue #71.
- ADR-120 adds content-safe fixed-stage diagnostics to the trusted isolated
  processor controller while preserving fail-closed `MimeUnavailable` and
  exact-owned cleanup. This instruments, but does not resolve, intermittent
  hosted large-MIME failure issue #64; no automatic retry or budget change.
- DC-002P adds a private, worker-scoped fresh-root verification of one approved
  FileOS v2 stage under ADR-119 and migration 0041. It rechecks the current
  v1 receipt, scans with the pinned donor policy, and requires exact staged-row
  parity before recording an immutable receipt. No v2 importer at that
  checkpoint, completion,
  freshness, absence, search, API route or cutover consumes that receipt.
- DC-002O adds a private, nonpublishing FileOS v2 transition plan and an
  immutable, human-owner approval receipt under ADR-118 and migration 0040.
  It rechecks the stage and exact latest v1 receipt, binds the decision to a
  plan digest and complete count maps, and refuses hard blockers or stale
  baselines. It is synthetic/disposable only; no v2 completion, freshness,
  absence, search, API, live-root attestation or cutover consumes approval.
- DC-002N adds private, nonpublishing v2 inventory staging under ADR-117 and
  migration 0039. It projects one sealed transition packet into immutable
  hashed, hashless deferred, exclusion and error rows, with SQL count balance
  and exact latest-v1 binding. No v2 completion, freshness, absence, search,
  approval or FileOS cutover consumes the stage.
- DC-002M adds a compact private read of a sealed FileOS transition packet,
  with separately scoped, at-most-50-row locator pages. It checks the stored
  digest and reports whether the latest receipt still matches at read time.
  There is no CLI/API surface, approval, v2 publication or cutover.
- DC-002L adds a private immutable donor-policy review packet, bound to one
  latest exact completed v1 run with an advisory-locked insert. Candidate and
  preview come from one scan; forced RLS, tenant-login fence, replay and
  nonpublication tests use disposable PostgreSQL. This is not a v2 baseline,
  attestation, API route, live-root acceptance or cutover.
- DC-002K adds a private, read-scoped completed-v1 verifier and a before/after
  database-bound donor transition preview. It refuses an imported-only,
  mismatched or stale run, including a newer completion during scanning. It is
  nonpublishing and does not establish v2 persistence, absence or cutover.
- ADR-109 adds opt-in `serve --tenant-db-config` routing through a table-blind
  exact-identity login and separately fenced tenant logins. Real disposable
  PostgreSQL tests cover two-tenant API search and missing/wrong/shared-route
  refusal; private-file tests cover malformed, duplicate, symlink and broad-mode
  configuration. ADR-135 subsequently adds one opt-in tenant-bound private
  FileOS publisher, and ADR-138 adds index/rollback; at that checkpoint other
  workers still used explicit shared DSNs. ADR-139/141 later add opt-in routes
  for the private derivatives and legacy Email worker commands. Credential
  lifecycle/hosted acceptance are not implemented. Issue #7 stays open.
- ADR-108/migration 0037 add an opt-in restrictive RLS fence for a DBA-bound
  one-tenant PostgreSQL login. Synthetic arbitrary-SQL tests cover forged GUCs,
  wrong-tenant read/write, role switching and mapping loss. No worker DSN router,
  production credential lifecycle, live rollout or closure of issue #7 is
  claimed; the older shared login remains vulnerable under arbitrary SQL. See
  [the contract](TENANT_LOGIN_FENCE.md).
- Fastmail read worker resilience (ADR-110, migration 0052): anchored, byte- and
  time-bounded listing that survives mailbox churn; metadata responses over the
  fixed control cap are split by ID before an atomic page commit; oversized mail held as
  accounted `source_too_large` receipts without pausing the account; retained-blob
  reuse for flag-only updates; tolerant `Retry-After`; `lease_lost` outcome.
  Verified with unit and disposable-PostgreSQL tests on synthetic transports; no
  live mailbox has been enrolled.
- Existing `email_brain` capability: Fastmail/JMAP read worker, raw/evidence storage,
  MIME/attachment accounting, PostgreSQL FTS, owner search/read, reviewed rules,
  recovery/quarantine, synthetic mailbox, PDF approval path, and narrow reviewed
  travel/bill memory. Existing detailed guides define exact limits.
- Offline-tested Gmail/Graph libraries and an injected-session IMAP contract.
- MasterBrain package boundary with DataCore read-only file hash, filter, duplicate
  grouping, name grouping and file comparison extracted from FOS-Master.
- Dedicated `masterbrain` CLI for shared hash/compare/duplicate commands and
  deterministic read-only FileOS snapshots; source files are never changed.
- Immutable source/item/version/evidence/provenance contracts with stable opaque IDs,
  safe relative locators, bounded metadata and explicit source-bound evidence.
- Synthetic DataCore unit corpus and live-donor parity harness pinned to FOS-Master
  commit `218d5caec2f20b9047fd3eb8e027dc671acf0c15`.
- Behavior-identical FOS scanner/reconciler inventory classifier with 3,000-path live-donor
  parity. It is not yet wired into FileOS snapshots or dedupe; their different
  exclusion policies require an explicit integration decision.
- Isolated ADR-111 donor-policy shadow scanner uses that classifier without creating
  a publishable manifest. Local pinned-donor comparison matches 3,004 ordinary
  rows on a 3,000-file synthetic corpus, plus replay, one change, explicit
  no-hash metadata rows and sparse 100 MiB/2 GiB boundary tests. It changes no
  snapshot v1, completion, search or FileOS operation. Exact-head and merged-main
  CI/restore are green; hosted product and live-source acceptance are not claimed.
- DC-002H's nonpublishing follow-up binds metadata-only and ordinary shadow stats
  to a no-follow descriptor walk and initial root identity, without opening leaf
  bytes. Synthetic root/ancestor/leaf-swap tests and local 3,000-file pinned-donor
  parity pass; exact-head and merged-main CI/restore are green. Real cloud-
  placeholder acceptance remains pending.
- DC-002I adds a source-bound, nonpublishing donor-policy candidate ledger under
  ADR-112. Hashed rows gain stable candidate item/version identities; `no_hash`,
  `dataless` and `oversize` rows remain deferred with no version or digest. The
  v1 importer rejects the candidate. Focused tests and a local pinned-donor
  3,000-file comparison pass with 3,004 exact hashed and metadata-only matches;
  exact-head and merged-main CI/restore pass via PR #50. Any publishable v2
  transition remains pending.
- DC-002J adds a private, read-only v1-to-donor transition preview under
  ADR-113. On the pinned 3,000-file fictional corpus it accounts for 3,006
  prior v1 items: 3,002 unchanged, four donor-excluded, plus two donor-only
  hashed items. All six policy gaps are explicit; none creates absence evidence.
  A near-bound 10,000-item v1 corpus passes; over-bound stress requests refuse
  before donor loading.
  Local PostgreSQL 17 ran 444 database-marked tests with the full suite at
  2,862 passed and one skipped. The PR #52 code head passed hosted CI, strict
  runtime and populated restore after the account billing gate cleared; the
  final PR head and merged `main` independently passed the same gates. The
  preview is on `main`, but no persisted v2 baseline, completion or FileOS
  switch is claimed.
- Synthetic whole-inventory scanner shadow comparator on an in-memory donor SQLite
  database and temporary fictional root. It verifies common hashes/sizes, six current
  policy gaps, replay/change/removal, no-hash/rehash and donor mass-prune refusal;
  it does not switch snapshot policy or publish evidence.
- Synthetic pinned-donor scanner boundary tests cover sparse 100 MiB/2 GiB limit
  differences, a retained stale row after donor read failure, MasterBrain's
  changed-during-hash refusal and broken/directory symlinks. They do not establish
  dataless, unreadable-directory or live-source parity.
- Further synthetic pinned-donor edge tests expose metadata-only dataless behavior,
  silent donor removal after an unreadable directory, a donor size/hash race and
  valid unusual filename round trips. They do not prove real cloud or platform-wide
  filename behavior and authorize no policy switch.
- ADR-100's isolated FileOS read-hardening branch routes snapshot hashing and
  text/PDF/Office extraction through bounded, descriptor-relative no-follow opens.
  Synthetic symlink-swap and locator-stability regressions pass locally (15
  cases, including an ancestor above the root). Hosted CI and populated restore
  passed on code head `6e2eb8e` in
  PR #25. The 3,000-file pinned-donor shadow passes with 3,002 ordinary
  SHA/size matches; this is not a production FileOS release claim.
- FileOS completion refuses malformed or uncertain snapshot coverage before writing
  a latest-complete receipt or absence event. The private publisher rejects before
  intake; direct storage completion independently enforces the rule. A separate
  completion guard now refuses a clean-looking new run that loses at least 10 prior
  items and at least half the prior inventory; it has no unreviewed bypass. This
  does not protect smaller unexplained losses.
  Hosted PostgreSQL, full CI and populated restore passed on PR #18's runtime head.
  Hosted CI and populated restore passed for the mass-loss guard on PR #19's
  runtime head; the implementation is now on `main` via PR #28.
- New FileOS completion receipts carry a versioned inventory-policy digest and
  refuse consecutive-run absence inference across changed or unknown policies.
  Legacy receipts remain immutable with unknown policy; a reviewed baseline path
  remains pending, while the implementation is on `main` via PR #28. Hosted CI and
  populated restore passed on PR #20's corrected runtime head. This does not
  switch to the donor scanner's exclusions or authorize cutover.
- ADR-097 adds bounded per-locator exclusion accounting and refuses absence
  when a prior indexed file is still present but excluded, or intentionally skipped
  as a no-follow symlink. Hosted CI and populated restore passed on PR #21's
  runtime head; the implementation is on `main` via PR #28. It does not prove a live scanner;
  root binding is separately guarded by ADR-098.
- ADR-098 root binding is implemented in isolated PR #22, with hosted CI and
  populated restore green on the runtime head. New FileOS sources and receipts carry
  an immutable private physical-root digest; wrong-root intake, unknown legacy
  roots and cross-root completion fail closed. This does not certify a live
  scanner, donor-policy parity or FileOS cutover.
- Additive shared DataCore persistence, FileOS text/Markdown/HTML/CSV extraction,
  lexical index and progressive evidence/content/change Brain API.
- Source-bound FileOS PDF/DOCX/XLSX extraction contract and dedicated restricted
  worker image with archive/active-content bounds; hosted container and restore gates green.
- Source-bound, in-memory FileOS ZIP/TAR archive inventory contract and dedicated
  restricted worker image with donor-equivalent cumulative bounds, safe hash-only
  manifests and explicit bomb/duplicate non-publication; live donor, hostile/fault,
  hosted container and restore gates green. It has no persistence or search path.
- Append-only, forced-RLS archive hash-manifest persistence bound to current FileOS
  source and immutable processor versions, with insert-time ledger balance and exact replay;
  hosted PostgreSQL/restore gates green. It stores no member bytes and publishes no
  evidence, documents, chunks or search entries.
- The original archive inventory insert validates a balanced member/skip ledger,
  but migration 0023 alone does not reject a later child insert. ADR-099 and
  migration 0033 add deferred child-side checks and exact receipt/provenance links.
  Hosted PostgreSQL and populated restore passed on PR #24's runtime head;
  the implementation is on `main` via PR #28.
- Hash-bound read of exactly one persisted non-container archive member through a
  separate fixed restricted-image command. Forced-RLS selection requires the current
  FileOS source version; the parent reopens it through no-follow descriptors, verifies
  file identity before/after, and independently verifies the returned member hash and
  size. Output is capped at 8 MiB, remains unscanned and is not persisted or searched;
  hosted PostgreSQL/container/restore gates are green.
- Explicit one-member text/Markdown/HTML/CSV normalization and append-only derived
  evidence publication with deterministic child source/version/evidence identities,
  parent archive plus inventory provenance, idempotent receipts and transaction-time
  current-parent/member revalidation. It stores no raw member bytes and remains absent
  from current-generation search; hosted PostgreSQL/restore gates are green.
- Private `masterbrain fileos archive-text` publication for one explicit persisted
  inventory/member pair, with immutable worker image binding, exact shared scopes,
  non-consuming check mode, repeated reauthentication, content-free output and exact
  replay. It grants no archive enumeration, batch, scheduling, public API, raw-byte
  return or source effect.
- Independently bounded current archive-member lexical search, fenced through the
  current parent archive plus sealed inventory/member and exact derivative identities.
  `/v1/brain/current-search` exposes it separately from immutable active FileOS
  generations with explicit partial coverage; stale parents disappear while retained
  history remains available. Hosted PostgreSQL/container/restore gates are green.
- Private `masterbrain fileos archive-text-plan` read-only preview for one current
  archive inventory. It returns only bounded eligible text-member metadata in sealed
  ordinal pages with already-published labels, constructs no worker, reads no source
  bytes and creates no derivative/key/batch authority. Hosted PostgreSQL/restore gates
  are green.
- Private `masterbrain fileos archive-text-batch` execution of one canonical,
  digest-bound plan containing 1–100 reviewed member locators and caller-supplied
  idempotency keys. It validates without target/worker/key effects, executes in exact
  order, stops on first refusal, reauthenticates sensitive boundaries and resumes only
  through unchanged-plan replay. Output contains indexes/counts rather than locators or
  content; hosted PostgreSQL/container/restore gates are green.
- Explicit one-member archive PDF/DOCX/XLSX extraction through two independently
  restricted immutable images, followed by append-only publication on deterministic
  child evidence. A separate receipt binds parent archive, inventory, member,
  document processor, revision and retry key; the publication transaction rechecks
  current parent/member identity and persists no raw member bytes. Private
  `masterbrain fileos archive-document` provides non-consuming preflight, repeated
  authorization, exact replay and content-free output. Hosted PostgreSQL, populated
  restore and real chained-image PDF/Office gates are green; these derivatives remain
  available to retained-history search and the separately fenced current layer.
- Independently bounded current archive-document lexical search for explicitly
  published PDF/DOCX/XLSX derivatives. It joins the immutable document receipt to the
  sealed inventory/member, exact child evidence/document and still-current parent;
  parent replacement removes current visibility without deleting retained history.
  `/v1/brain/current-search` exposes a distinct rank/limit/coverage layer with opaque
  locators. Hosted PostgreSQL, restore and all restricted-container gates are green.
- Private `masterbrain fileos archive-document-plan` preview for one current archive
  inventory. It returns only exact eligible PDF/DOCX/XLSX metadata and publication
  state in sealed ordinal pages, constructs neither worker, reads no source/member
  bytes and creates no retry or batch authority. Check mode is non-consuming; hosted
  PostgreSQL, restore and restricted-container gates are green.
- Private `masterbrain fileos archive-document-batch` execution of one canonical,
  digest-bound 1–100 item plan. Each reviewed item binds locator, expected PDF/DOCX/
  XLSX format and caller-supplied key. Execution reuses the exact selector, two-worker
  extraction and publication path, stops at first refusal and resumes only through
  unchanged-plan replay. Real PostgreSQL proves partial commit/retry; hosted restore
  and all restricted-container gates are green.
- Dedicated byte-bound raster OCR contract and independently restricted worker for
  single-frame JPEG/PNG/TIFF/BMP/GIF/WebP. It binds suffix/format/signature/hash,
  fully decodes under 8 MiB/25-megapixel limits, caps Tesseract at 20 seconds and
  output at 5,000 characters, exposes no EXIF/path, and uses a 32 MiB in-memory
  scratch area. Real-container OCR, bomb/animation/fault tests and 132 pinned-donor
  golden/stress comparisons are green. It has no archive selection, persistence,
  search, batch or public path.
- Explicit private-config FileOS snapshot publication command with exact worker scopes,
  idempotent replay and repeated authorization; hosted PostgreSQL/restore gates green.
- Append-only FileOS whole-run receipt and Brain API latest-complete freshness endpoint;
  hosted PostgreSQL and populated-restore gates green.
- Exact completed-run item ledger, stale-completion refusal, immutable absence events
  and bounded inventory counts; hosted PostgreSQL and populated-restore gates green.
- Paginated, run-bound deterministic FileOS rebuild preview with no source or index
  effects; hosted PostgreSQL and populated-restore gates green.
- Immutable, latest-completion-bound FileOS lexical generations with database-checked
  readiness, append-only activation/reactivation rollback and active-only API search;
  hosted PostgreSQL and populated-restore gates green.
- Explicit private generation build/activation and activation-only rollback command
  with exact scopes, check mode and reauthentication; hosted PostgreSQL/restore green.
- Explicit cross-source current FileOS search over newest activations while historical
  compatibility search remains unchanged; hosted PostgreSQL/restore green.
- Explicit current-FileOS evidence mode for grouped KnowledgeCore retrieval with
  retained-history default and separate ranks; hosted PostgreSQL/restore green.
- Additive current-Email evidence bridge into shared DataCore source/version/evidence/
  document/chunk identities with opaque locators, exact replay, immutable provenance,
  forced RLS and account-race fencing; hosted PostgreSQL/restore green. Existing Email
  ingestion and search remain authoritative.
- Private `masterbrain email bridge` command for one explicit evidence UUID with exact
  shared worker scopes, non-consuming check mode, safe replay, reauthentication and
  content-free output; hosted PostgreSQL/restore green.
- Explicit `/v1/brain/email-search` read over bridged Email evidence that remains
  current and visible in both shared and legacy state; retained history and legacy
  Email search remain unchanged; hosted PostgreSQL/restore green.
- Additive Email attachment-occurrence bridge with distinct child evidence/parts,
  duplicate occurrence preservation, bounded legacy-text publication and explicit
  zero-document outcomes. Existing Email attachment/document behavior is unchanged;
  hosted PostgreSQL/restore gates green.
- Additive approved Email PDF derivative bridge from one immutable completed legacy
  extraction onto its existing attachment evidence, with exact approval/result/
  processor provenance and no byte access; hosted PostgreSQL/restore gates green.
- Private `masterbrain email bridge-attachment` and `bridge-document` commands using
  the existing closed configuration, exact shared worker scopes, non-consuming checks,
  reauthentication and content-free output; hosted PostgreSQL/restore gates green.
- Explicit `/v1/brain/email-family-search` read with independently bounded/ranked
  message, attachment-text and approved-document layers, each fenced by current legacy
  parent and shared pointers. Existing reads remain unchanged; hosted PostgreSQL/
  restore gates green.
- Explicit `/v1/brain/current-search` grouped read across active FileOS, current Email
  family and reviewed KnowledgeCore results with independent bounds/ranks, partial-
  coverage labels and declared independent-layer consistency; hosted PostgreSQL/
  restore gates green.
- Bounded `/v1/brain/current-coverage` status across registered FileOS and Email
  sources, including active-generation/completed-run comparison and current bridged
  Email family counts/timestamps; hosted PostgreSQL/restore gates green.
- Private, read-only `masterbrain email bridge-plan` command for a cursor-bounded page
  of current visible versions in one explicit account, with already-bridged labels and
  content-free output; hosted PostgreSQL/restore gates green.
- Private `masterbrain email bridge-batch` command for one owner-private, digest-bound
  list of 1–100 current message versions with fixed keys, account fencing, fail-stop
  execution and exact-plan retry; hosted PostgreSQL/restore gates green.
- Private, read-only `masterbrain email bridge-parts-plan` command with separate stable
  attachment and approved-document queues, current parent/dependency fencing and
  content-free output; hosted PostgreSQL/restore gates green.
- Private `masterbrain email bridge-parts-batch` command for one owner-private,
  digest-bound attachment or approved-document plan with fixed keys, batch account
  fencing, fail-stop execution and exact-plan replay; hosted PostgreSQL/restore gates
  green.
- Reviewed KnowledgeCore entities, aliases, relationships, claims, events, projects,
  commitments and corrections with evidence links, temporal history, lexical search,
  exact reads, change feed, forced RLS and append-only enforcement.
- Grouped dual-scope search across DataCore evidence and KnowledgeCore assertions,
  with independent limits/ranks and evidence IDs for progressive drill-down.
- Explicit one-member archive image OCR composition across the existing hash-bound
  archive reader and separate image worker. It preserves exact member identity,
  suffix/signature agreement, sibling exclusion and source immutability; maps blank,
  policy and failure outcomes explicitly; and returns only bounded in-memory text and
  metadata. Complete nonempty results may enter a separate append-only, forced-RLS
  retained-history derivative with exact replay/current fencing and image-specific
  receipt/provenance. Real immutable containers, PostgreSQL and restore are green. It
  added no automatic selection, current search, batch or fan-out at that checkpoint.
- Private `masterbrain fileos archive-image` one-member command with distinct pinned
  OCR image, exact worker scopes, non-consuming check, reauthentication and
  content-free output. Hosted CI/container and populated restore accepted in
  `f658ace`; no live-source or production acceptance is claimed.
- Current-only archive-image OCR lexical search is a separate Brain API layer under
  ADR-107. It rejoins exact image receipt, sealed member, child derivative and
  still-current parent without changing retained history or active generations.
  It has its own bounded limit, within-layer rank and partial-coverage label;
  automatic fan-out and live-source acceptance remain absent.
- Forward-only protected-record TRUNCATE guards on the 56 direct append-only tables,
  protected recovery/document jobs and audited external identity bindings. Focused
  disposable-PostgreSQL catalog, direct/cascade, runtime-privilege, row-transition and
  replay tests passed. Hosted CI (2,669 Python tests, browser and restricted-worker
  gates) and populated restore passed on separate PR #13; the implementation is
  integrated on `main` via PR #28.
- A dedicated non-superuser identity-administration role and exact-key runtime
  resolver replace the former caller-settable identity lookup policy. The runtime
  has no direct identity-table SELECT after migration 0035 and refreshed grants.
  This does not contain arbitrary SQL or a stolen runtime credential because other
  tenant RLS settings remain caller-settable; issue #7 is still open.

## Designed, not implemented

- Automatic Email backfill scheduling, atomic cross-layer snapshots and automated
  source coverage
  accounting and any redirect of legacy Email search.
- Scheduled/incremental FileOS scanning, source cursors, automatic rebuild and
  generation scheduling/global-search cutover. Archive-member image/OCR current
  search, previews, batches and automatic archive fan-out remain follow-on gates.
- Automatic KnowledgeCore extraction, known-answer quality evaluation, graph traversal,
  semantic ranking and Email/FOS knowledge migration.
- Unified cross-source synthesis and external LLM client integrations.
- Hosted operation and production identity/source enrollment.
- Any FileOS write, move, quarantine, dedupe deletion, cutover, fold or retirement.

## Verification boundaries

Most Email tests use synthetic data; PostgreSQL suites require an explicitly disposable
database and local skips do not count. The parity script requires a clean checkout of
the pinned FOS-Master commit. It compares normalized observable scan results and does
  now covers fixture and scale hash/name/both scans, pair comparisons and hashes. It
  does not cover donor CLI text, configuration discovery, logging or file effects.
  See [migration](FOS_MIGRATION.md) for the next gates.
