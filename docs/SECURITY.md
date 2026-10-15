# MasterBrain Security and Privacy

MasterBrain processes highly sensitive email and files. Its threat model includes
malicious source content, compromised client/model output, parser exploits, confused
deputy actions, cross-tenant access, credential theft, poisoned indexes, data
exfiltration, destructive file/mail effects, and leakage through logs/backups.

## Trust boundaries

ADR-175's typed Fastmail `Email/query` mailbox/date filter and separate
`Email/get` metadata check are now used by ADR-176's synthetic-only scoped
worker. That worker avoids `Email/changes` and refuses out-of-scope metadata
before any blob read. ADR-177 adds an account-level SQL scope/lease/cursor
fence; ADR-178 binds version-2 private `sync-read` to it while version 1
remains account-wide and refuses pinned accounts. ADR-179 adds a local
human-owner-scoped, administrator-assisted check/enroll/disconnect path that
creates only a fresh pinned source and never contacts Fastmail. Both worker
modes retain exact credentials and guarded requests. Live-provider acceptance,
hosted enrollment and provider-token revocation remain absent, so this is not
a real pilot.

ADR-184 checks an exact excluded-mailbox set in validated `Email/get` metadata
before retained-byte lookup or provider download. The set changes the pinned
scope fingerprint, and an excluded message has no new raw/content record. A
previously current projection is hidden transactionally while its immutable
evidence remains under existing privileged, audited historical access. The
tenant-isolated reconciliation ledger must retain the opaque provider ID;
public sync status reports only an excluded count. This is not a retroactive
purge or a general sender/path policy, and the owner has selected synthetic-only
testing for now.

ADR-185 additionally hides an older excluded message's retained Brain
evidence/content/change results and any reviewed KnowledgeCore assertion
grounded in that evidence. SQL filters apply before ranking or pagination,
alongside source grants, and use tenant-RLS-respecting receipt links for parent,
attachment and approved-document evidence. This is a visibility rule, not a
purge: the explicitly human-scoped historical Email evidence route remains
available under its existing audit/retention policy pending an owner decision.

ADR-186 keeps Knowledge proposal batches in private forced-RLS tables, outside
reviewed search, dossiers and assistant routes. Human staging, preview and
atomic row-by-row review recheck current source grants, excluded evidence and
an exact quote in normalized text. Preview additionally requires content-read
scope. A proposed row is untrusted and cannot authorize its own publication;
the reviewer must make every decision explicitly. This is synthetic-only and
does not establish a safe Markdown parser or source-byte derivation proof.

ADR-189 adds a separate, synthetic-only FileOS statement replay boundary. A
worker, never a public API reader, selects one current proposal under tenant
and source grants, then uses the no-follow bounded FileOS reader and ADR-188's
exact text transform. It rechecks source version and root before sealing an
append-only receipt, and never stores raw bytes or paths in that receipt.
The general runtime SQL login could still forge a same-basis receipt if
compromised; issue #7 and a dedicated worker attestation/login boundary remain
open. Consequently no public verified-source or investment claim is exposed.

- Email, files, archives, metadata, OCR, extracted text, links, and model output are
  untrusted data. They cannot grant permission or select credentials/tools.
- ADR-171's private statement candidates are likewise untrusted proposals. Their
  exact extracted-text spans and digest do not prove the source-byte-to-text
  derivation, current source grant, source tier, independent corroboration or a
  financial holding. ADR-172 adds a worker-only, tenant-fenced immutable proposal
  ledger with current-document and source-hash checks; it does not prove the
  source-byte-to-text transform, independently verify currency, or promote a row
  to a reviewed holding. It does not itself grant an API read path; stored offsets
  must be rechecked under the reader's current grants before disclosure.
- ADR-173 is that separate human-only disclosure boundary: it requires both
  Knowledge read and Brain content read, rechecks the current source and hashes,
  pages immutable rows and caps source quotes. Assistants and workers cannot use
  it. The text remains untrusted; a preview is not approval or financial truth.
- Source adapters, extraction workers, DataCore, KnowledgeCore, Brain API, and effect
  executors use separate identities and least-privilege scopes.
- Brain API clients receive typed operations only—never general SQL, arbitrary HTTP,
  provider tokens, storage credentials, unrestricted paths, or raw object keys.

## Privacy principles

- Collect only authorized sources and retain only what an explicit policy requires.
- Prefer deterministic/local processing; remote inference is optional, minimized,
  redacted where practical, disclosed, logged, and revocable.
- Do not use user content to train a model without a separate explicit opt-in.
- Separate metadata/search permission from extracted content and original evidence.
- Support export, retention, purge, and legal hold with auditable receipts.
- Telemetry excludes content by default; logs use opaque IDs, states, counts, timings,
  and bounded sanitized errors.

## First-party read workspace

ADR-127's `/brain` page is an unauthenticated static shell, not a data grant.
It calls the same scoped Brain API as other clients: current search requires
search scopes, evidence metadata and extracted text require separate scopes.
Its credential, questions and results stay only in page memory and clear when
the credential changes. Same-origin fetches omit cookies, reject redirects and
disable caching; strict CSP disallows external scripts. Untrusted excerpts and
content become text nodes, not HTML. Stale requests are aborted/ignored. It
has no direct model call, source-effect control, stored transcript, direct SQL or
provider credential. These controls do not establish hosted identity,
revocation across future derived caches or live-source acceptance.
ADR-163's project-dossier control is only available on a reviewed project
match, makes no automatic request, and uses ADR-162's same source/tenant-
filtered read route. The page validates the complete bounded response before
rendering, inserts returned text inertly, and aborts/ignores an in-flight read
when the token, source focus or session changes. It grants no additional scope;
hidden or malformed responses reveal no dossier content.
ADR-164's schedule controls require an explicit valid UTC window and All focus.
They use the existing `knowledge.search` source-filtered routes, fixed ten-item
pages and cutoff-bound cursors. The browser validates each complete response
before inert rendering, clears its page on date/token/focus/session changes,
and keeps evidence expansion separately authorized. A malformed or denied page
does not render partial rows or fall back to another read. No source effect,
provider credential or new grant is introduced.

ADR-136 also keeps the fictional trial's excerpts as text nodes, omits generated
PostgreSQL highlight markup and verifies that both metadata and bounded content
name the selected evidence before displaying source text. That trial remains
synthetic and does not establish a production browser identity boundary.
ADR-166 lets that loopback-only trial reveal its temporary read-only code only
after an explicit click, for manual entry into the separate `/brain` workspace.
The launcher still does not print the code; neither page persists it, and the
workspace never accepts it from a URL. A displayed code should be hidden when
finished. This is not a hosted credential handoff pattern.

ADR-134 adds an optional read-only answer route. An explicitly configured
selector receives only bounded, currently authorized excerpts, with no tool or
effect authority. Server-side checks require exact quoted substrings and
recheck current search before disclosure. ADR-144 enables a local deterministic
exact-quote selector by default, without network or source effects; explicit
disablement makes the first-party workspace fall back to grouped search only
on the fixed unavailable response. ADR-145 removes fixed question filler words
before both current searches; it does not grant semantic or cross-source
authority. ADR-146 shows reviewed KnowledgeCore matches as a separate,
bounded, untrusted list, only after rechecking their full evidence-link sets
against current source visibility. It does not treat reviewed text as an exact
source quote. Access denial, malformed citations and stale data do not
trigger fallback. A distinct Search only button preserves the preexisting
search-only grant without converting an answer denial into a search. This does
not approve sending private content to a remote
model or establish semantic truth beyond the quoted source text.
ADR-151 imposes an 8,192-UTF-8-byte total selector passage budget and a
2,048-byte per-passage cap. The server truncates at a valid Unicode boundary,
reports `answer_context_truncated` for an upstream character or byte cap, and
does not read further candidates once
the aggregate cap is full. It rejects invalid Unicode adapter text. This
limits future model exposure but is not a total prompt/token, response, hosted
egress or remote-model approval.

ADR-157 also caps aggregate untrusted text returned by Ask: exact source quotes
plus reviewed KnowledgeCore titles/excerpts total at most 8,192 UTF-8 bytes.
The server preserves exact quotes, then clips or omits reviewed display text
with an explicit `answer_output_truncated` flag after full currentness and
direct-link rechecks. The reference client and browser reject over-budget
responses; the browser counts Unicode code points for citation offsets.
This does not cap the complete JSON envelope or approve model egress.

ADR-128's FileOS v2 search comparison is not in the first-party workspace.
ADR-147 exposes only that existing comparison through a human-only Brain API
route. It requires transition-review, search and evidence grants, binds one
ready historical generation to the latest v1 baseline under the source lock,
emits a content-free audit event, and labels v2 results as a preview. Invalid
requests and stale baselines fail with generic errors; assistants cannot call
this route. It cannot activate v2 or bypass current-search policy.

ADR-129's external reference client fixes one operator-supplied origin, defaults
to HTTPS, disallows redirects and ambient proxies, bounds responses and exposes
only current search and separately scoped evidence reads. It does not store a
transcript, log tokens/content, cache revoked data or supply model tools by
itself. A future named assistant must not receive the bearer credential as
prompt content or treat retrieved text as instructions; its separate
prompt-injection and revocation acceptance is still open.

ADR-130 adds a synthetic-bootstrap assistant source allowlist for the three
client-facing Brain reads. SQL filters current source and evidence results before
limits; mixed-source knowledge is omitted; at that checkpoint alternate
Brain/Knowledge routes were denied to that assistant. Human owner reads are
unchanged. A static bootstrap
credential is **not** a dynamically revocable hosted grant. ADR-132 adds a
separate forced-RLS grant table for administrator-bound OIDC Brain assistants;
its same-tenant source foreign key, exact resolver and revision recheck stop
future transactions after grant removal. Legacy Email assistant routes, hosted
issuer enrollment, derived-cache invalidation and legacy Email assistant-route
coverage remain [issue #88](https://github.com/jbone3311/MasterBrain/issues/88).
ADR-142 extends the same enrolled-source boundary to retained DataCore search,
aggregate current Email/FileOS searches and exact-source FileOS status/search.
The retained search predicate runs before ranking and limits; hidden source
status and search return not found. OIDC source revocation is rechecked at the
read transaction. Direct Knowledge, unified and legacy Email routes remain
denied to assistants at that checkpoint. ADR-143 later admits direct
Knowledge and unified reads after filtering every directly linked evidence
source, including assertion expansion and change-feed cursors. It does not
prove semantic noninterference for human-authored text or approve hosted use;
legacy Email assistant routes remain denied. ADR-149 makes that denial
explicit across `email.*` API dependencies, bootstrap credential issuance
and OIDC transaction rechecks. An older Email-only assistant binding now
fails authentication rather than using unfenced compatibility reads. Human
and worker Email paths are unchanged; hosted issuer and derived-cache
acceptance remain open.

ADR-168's optional-source status follows the visible-source filter: an
assistant with no granted Email or FileOS source receives `not_available`,
never a tenant-wide `not_registered` assertion or hidden-source count. The
status only states MasterBrain registration, not live provider connectivity.

ADR-158's optional unsuperseded KnowledgeCore search checks the full direct
source-grant set on each predecessor, successor, correction and replacement
before a newer record may suppress an older result. A hidden-source update
must not change the visible review-chain projection solely by being added.
Returned hits still require the direct-link filter before rank and limit.
This is synthetic read behavior, not a semantic noninterference proof for
human-authored text or hosted assistant acceptance.
ADR-159 applies that same filtered projection to the Knowledge layer of
grouped Brain current-search and Ask. A correction or successor hidden by
source grants cannot suppress a visible older match. Ask still rechecks the
selected review matches before returning them. This does not establish
real-world truth, valid-time currency or source freshness.
ADR-160's reviewed-event timeline requires a bounded aware-date window and
recorded-cutoff cursor. Source-filtered assistants must see every direct event
evidence link and, when present, the linked project's full direct evidence
set. Hidden or filter-mismatched cursors return not found. The audit records
only a fixed operation code, never event text, dates or project identities.
Its cutoff excludes later-recorded rows, not late commits of earlier inserts;
it is not a durable MVCC snapshot, source freshness or truth guarantee.
ADR-161 applies the bounded window, recorded-cutoff cursor and pre-limit grant
checks to reviewed commitments. Assistants must see all direct commitment
evidence and the direct evidence of every referenced project, owner and
counterparty. Hidden successors, corrections and replacements cannot suppress
a visible older commitment. The audit uses a fixed operation code and does not
record descriptions, due dates or linked identities. No source write is granted.
ADR-162's project dossier checks the exact project's full evidence grant before
reading separately bounded linked events and commitments. Each linked record
is source-filtered before limiting; a commitment also checks its owner and
counterparty grants. Hidden review-chain updates cannot suppress visible
older links. Unknown and hidden project IDs share not-found behavior. Only a
fixed dossier-read audit code is recorded, never project text or IDs. A
recorded-time cutoff is not source freshness or a cross-request snapshot.

ADR-193's project-artifact write is human-only and requires review plus
content-read authority. It verifies the exact project grant, both current
evidence occurrences and the basis quote; replay rechecks them after grant
or exclusion changes. The bounded read checks project and both evidence
grants, currentness and exclusion before pagination, returns no quote, source
path or bytes, and rejects a hidden cursor. The append-only tenant-fenced
table and SQL trigger refuse stale/excluded evidence and invented quotes;
they do not make a compromised database owner harmless. Existing evidence
drill-down remains separately scoped and no source effect is authorized.
ADR-194 reuses that current, source-grant, exclusion and exact-quote predicate
inside the dossier's tenant-bound read transaction before its independent
artifact limit. The browser validates the full bounded artifact section and
renders labels as inert text; it does not receive paths, quotes, bytes or a
source-effect grant. Retraction remains history, not automatic roster removal.

ADR-195's separate project-fact write requires a human review scope plus
content-read authority and an exact quote in a current, active, nonexcluded
evidence item's normalized text. The immutable fact row freezes every direct
evidence ID so a later append cannot widen its grant set. The SQL guard
rechecks currentness, quote membership and same-project/predicate/type
supersession; the application additionally refuses a supersession whose prior
fact is hidden from the reviewer. Tenant RLS, login fencing and no-truncate
triggers protect both
fact and receipt tables. Reads check the exact project's established grant
predicate plus every fact evidence item's current source grant, exclusion and
quote presence before sorting or limiting. Hidden successor rows cannot
suppress a visible predecessor; a hidden cursor is not found. The browser
rejects malformed responses before rendering source-derived previews as inert
text. This is synthetic-only, not a semantic noninterference proof, hosted
identity acceptance, inferred-basis authorization, or a Markdown export-time
citation verifier.

## Privacy-safe failure observability

The REST boundary records a server-generated request ID, fixed route template,
status, stable error code and exception *class* for infrastructure and unexpected
failures. It never logs URL parameters, request bodies, source paths, exception
messages, tracebacks, SQL diagnostics, credentials or original evidence. A generic
500 response retains the request ID and security/cache headers for operator
correlation. Expected authorization and validation refusals retain their bounded
status codes without exposing inputs. These local process logs are not a durable
centralized incident trail; protected collection, retention, alerts and production
monitoring remain release gates. See [ADR-104](adr/104_privacy_safe_error_observability.md).

ADR-120 adds a warning from the trusted isolated-processing controller with
only fixed profile/stage/reason codes. Raw MIME, filesystem paths, container
or image IDs, commands, stdout/stderr, exception messages and tracebacks remain
excluded. The public `MimeUnavailable` response is unchanged; a warning is
diagnostic evidence, not proof of a safe retry or a resolved failure.
The image-validation stage distinguishes the daemon security-options check
from inspection of the immutable image, still without logging Docker output
or changing its timeout.

## Required controls

- Strong human/service identity, short-lived credentials, explicit enrollment and
  current authorization checks.
- Identity binding administration uses a separate non-login role with a
  non-superuser login granted membership by a DBA; runtime cannot mutate bindings.
  The audit trigger records the connecting login without granting it direct audit
  writes. This closes the forced-RLS enrollment gap in issue #6, not issue #7's
  arbitrary-SQL/session-context threat. See [ADR-105](adr/105_identity_admin_enrollment.md).
- Runtime identity resolution uses an exact-key definer function instead of direct
  identity-table SELECT or caller-settable lookup policy. A compromised runtime DSN
  can still set tenant-context GUCs protecting other tables; issue #7 remains open
  and hosted containment is not claimed. See [ADR-106](adr/106_identity_resolver_boundary.md).
- Migration 0037 adds an opt-in one-tenant database-login fence: a DBA-owned
  mapping keyed by `session_user` and restrictive policies on every existing
  forced-RLS tenant table. Forged GUCs cannot widen an enrolled login's rows.
  ADR-109 adds opt-in API routing through an identity-only login and distinct
  tenant-bound data logins, with per-connection binding checks and a private
  configuration file. ADR-135 adds an explicit tenant-bound mode for one private
  FileOS publisher using the authenticated worker tenant and a single-tenant
  DSN. ADR-138 adds the same opt-in fence for FileOS index build and
  activation-only rollback. ADR-139 adds the same opt-in fence to private
  `masterbrain` Email bridge and FileOS archive derivative commands, including
  previews and sealed batches. ADR-141 adds the same opt-in bound-login mode to
  legacy `email-brain` Fastmail read, MIME recovery and synthetic PDF worker
  commands. Their default shared-runtime mode remains GUC-driven, as do private
  library callers that have not opted in; credential operations and a hosted
  adversarial run are not implemented. See [ADR-108](adr/108_tenant_login_rls_fence.md),
  [ADR-109](adr/109_tenant_database_routing.md) and the
  [tenant-login contract](TENANT_LOGIN_FENCE.md); issue #7 remains open.
  ADR-154 extends the disposable logical restore with newly provisioned,
  two-tenant bound logins and forged-context SQL checks after restoration.
  Role objects and secrets are not restored, and this is not hosted credential
  lifecycle acceptance. ADR-155 moves the target to a second fresh container
  and retires orphan source-role mappings before enrolling new target logins;
  managed-host recovery, role-secret escrow and session draining remain open.
- Tenant/source isolation in application code and forced database RLS.
- Encryption in transit and at rest; managed key rotation and recovery procedures.
- Network isolation for databases/object storage; no public administrative endpoints.
- Sandboxed parsers with type/size/time/memory/depth limits, malware policy, and
  quarantine. Unsupported/partial content remains visible.
- Hash verification before and after sensitive reads/effects where applicable.
- Append-only audit and transactional receipts for access, policy and effects.
- Protected evidence, approval jobs and identity bindings reject direct/cascaded
  whole-table `TRUNCATE` as well as their existing row-level protections. Runtime
  roles hold no `TRUNCATE` privilege; a malicious database owner remains outside
  the trigger-only trust boundary and requires administrative audit/backups.
- Backups encrypted separately and restore-tested; retention applies to derivatives,
  indexes, caches, exports, and backups.

## FileOS document parser controls

ADR-152 removes `os.walk` from the nonpublishing donor-policy shadow. Each
directory is opened through no-follow descriptors from the authorized root;
a swapped descendant link yields a directory coverage error instead of
enumerating outside filenames. This does not change the publishable v1
snapshot, approve donor policy or establish live-source safety. Existing
symlink-directory classification could still inspect a target's type without
listing or opening it. ADR-156 removes that probe: all symlinks are coverage
errors before no-follow directory classification, and the shadow/candidate
versions advance so older packets cannot be silently reused as new-policy
evidence. Live-root privacy and cloud-placeholder behavior remain separate gates.
ADR-167 also refuses surrogate-escaped, non-UTF-8 FileOS names before
classification or byte reads. It records only an encodable parent coverage
error, blocks v1 completion and donor-transition candidacy, and never sends
the malformed name to IDs, SQL, API output or logs. This is a fail-closed
platform boundary, not pinned-donor parity or live-root acceptance.

ADR-100 requires FileOS snapshot hashing and text/PDF/Office extraction to read
through the authorized root with no-follow directory/file descriptors. Pathname
prechecks and digest mismatch alone do not prevent an outside-root read after a
symlink swap. The new reader bounds bytes and verifies open-file plus locator
identity before publication. The bounded reader is integrated on `main` through
PR #28, with hosted and donor verification on its exact baseline; it adds no source
effect or FOS-Master cutover authority.

PDF, DOCX and XLSX are accepted only when suffix and declared media type agree. The
adapter reopens and hashes the source immediately before processing. A dedicated image
with pinned reader dependencies runs with no network, read-only root, dropped Linux
capabilities, bounded CPU/memory/processes/output and no source mount. Returned data is
validated against a closed contract and rebound to the expected source version,
locator, digest, size and media type before publication.

The worker rejects encrypted PDFs, PDF actions/attachments/forms/annotations beyond
the supported subset, encrypted or macro-enabled Office packages, unsafe or duplicate
ZIP paths, excessive members/expansion/compression ratios, DTD/entity declarations and
external Office relationships. Page, sheet, row, column, cell, stream and extracted
text limits are enforced. Rejected or incomplete documents remain accounted as
unsupported, deferred or failed; they do not silently publish partial text. See
[FileOS document extraction](FILEOS_DOCUMENT_EXTRACTION.md).

The FileOS publication command accepts secrets only from owner-private files and a
runtime environment DSN. Its credential is an expiring worker identity with exactly
the two DataCore write scopes. Check mode performs no intake or extraction; execution
revalidates the local identity around each item. PostgreSQL independently rejects
privileged/owning roles and rechecks owner membership under forced RLS. Results omit
paths, filenames, content, credentials and diagnostics.

FileOS completion receipts are append-only, forced-RLS records bound to the intake
actor/request/manifest digest. Closed outcome counts must cover every item and match
published documents. Freshness reads expose only the latest complete run and never a
partial prefix, root or locator.

Completed FileOS inventories are independently balanced in PostgreSQL against their
receipt counts. Per-source serialization and monotonic observation time prevent stale
completion from replacing newer state. Absence is inferred only between two completed
ledgers; it retains evidence and does not authorize hiding, deletion or any file effect.
ADR-122 keeps this complete-ledger check deferred on the receipt but performs it
only once per run. New items must precede the receipt in the same transaction;
a source-locked immediate trigger rejects post-receipt inserts, and the deferred
foreign key rejects orphan items at commit. A database trigger also locks
receipt insertion, including direct SQL, so an uncommitted receipt cannot race
with a competing item writer.
Completion additionally refuses malformed snapshot error ledgers or uncertain
directory/file/race coverage before absence inference. A deliberate no-follow
symlink skip is the sole tolerated snapshot error (ADR-094). ADR-095 refuses the
donor-equivalent mass-loss threshold before completion, without a force bypass;
smaller unexplained losses remain an unsatisfied cutover gate.
ADR-096 adds a versioned policy digest to new completion receipts and refuses
completion across unknown or changed policies. Historical policy remains unknown;
there is no silent backfill or force override. ADR-098 now guards accidental
root changes; live scanner parity remains a separate cutover gate.
An unchanged policy alone cannot distinguish a real deletion from a previously
indexed file becoming oversize or newly excluded; a small such loss can fall below
the mass-loss threshold. ADR-097 adds a bounded exclusion ledger to new snapshots.
Completion now refuses
to turn a prior item covered by an exclusion or intentional no-follow symlink skip
into absence evidence; malformed or overflowing ledgers fail closed. This is not
proof against a forged manifest, root mismatch or a live scanner race.
ADR-098 adds a versioned physical-root digest to new FileOS sources and completion
receipts. The private publisher checks the root before intake and after extraction;
the database refuses a changed source binding or silent legacy claim. This reduces
accidental root-switch risk but is not malicious-scanner attestation or live donor
cutover proof. The digest stays within private manifest/database boundaries.

The sealed donor transition packet has a compact, locator-free read requiring
`brain.changes.read`. Locator-level detail additionally requires
`brain.evidence.read`, is limited to 50 fixed-shape rows per page, and fails
closed on a packet-digest mismatch. A read-time latest-receipt match is not
proof of live root state, approval or FileOS cutover authority (ADR-116).

The v2 staging ledger (ADR-117) is private, append-only and forced-RLS with a
tenant-login fence. Its deferred rows have no fabricated content digest or
version, and a deferred database constraint balances all four row kinds.
Staging requires the exact latest completed-v1 receipt under the source lock;
it grants no v2 publication, absence, search or source-effect authority.

The FileOS v2 transition review (ADR-118) is a private library operation,
not an LLM-facing route. A read returns only opaque identities, canonical
digests, counts and fixed blocker codes. Approval requires a human principal,
current owner membership, both `brain.fileos.transition.review` and
`brain.evidence.read`, the exact plan digest and both exact count maps. A
source lock fences the latest v1 receipt check; forced RLS, a tenant-login
fence and immutability protect the receipt. The receipt neither attests the
live filesystem nor authorizes publication, deletion inference or cutover.

ADR-119 adds a distinct worker-only `brain.fileos.transition.verify` scope
plus `brain.changes.read`. Under the source lock it rechecks approval and the
latest v1 receipt, then compares a fresh bounded no-follow scan of the
explicit root against every approved staged row. Its append-only receipt is
RLS- and tenant-login-fenced; audit uses opaque identities. A matching scan
is not continuing root attestation or permission to publish, infer absence,
switch policy, or expose source bytes through an assistant route.

ADR-121 adds worker-only `brain.fileos.transition.prepare` plus existing
`brain.source.ingest` and `brain.changes.read` requirements. It rechecks the
review/verification and scans again under the source lock before inserting
policy-scoped hashed evidence and an immutable, forced-RLS, tenant-login-fenced
mapping receipt. No current pointer, v1 completion, change feed, index, search,
absence or source effect is written. Prepared source-bound evidence is not an
original byte copy or permission to publish a v2 baseline.

ADR-123 adds a separate human-only `brain.fileos.transition.authorize` scope
plus evidence-read permission. Under the source lock it rechecks the exact
latest v1 receipt, reviewed stage and prepared evidence digest before sealing
one immutable, forced-RLS, tenant-login-fenced owner receipt. This is authority
for a future explicitly designed baseline attempt only; it does not attest
current root bytes, complete v2, change reads or infer deletion.

ADR-124 adds a distinct worker-only `brain.fileos.transition.complete` scope.
The worker rechecks that exact owner authorization and prepared evidence,
then performs a new no-follow donor-policy scan under the source lock before
sealing a private v2 baseline receipt. Composite foreign keys and a locked SQL
trigger bind the stage, preparation and authorization and reject stale v1 or
incomplete ledgers. A compact private read exposes counts and read-time v1
match but no locators or content. Neither receipt nor read grants current
search, absence, source effects, live-root acceptance or FOS-Master cutover.

ADR-125 adds worker-only `brain.fileos.transition.publish` to process hashed
rows of that completed baseline through existing confined/isolated extractors.
Every opened file is hash-rechecked against staged evidence; a final full
donor-policy rescan and source-locked SQL outcome ledger prevent drift or a
partial crash prefix from being labelled ready. Forced RLS, tenant-login
fencing, immutability and protected truncation apply. Ready/blocked attempts
are historical; current v1 visibility and absence authority do not change.
Retained-history search can expose successfully published v2 derivatives under
its existing authorization, so clients must not present that layer as current.

ADR-126 adds a worker-only `brain.fileos.transition.index` scope for building
an exact v2 generation in the existing DataCore index tables. PostgreSQL binds
it to the ready attempt and source-locked latest-v1 baseline, validates every
hashed item and published chunk at readiness, and rejects direct-SQL v2
activation. It does not reopen source files, grant a new read route or infer
absence. The private builder remains synthetic/disposable until full gates
pass; FOS-Master remains the unchanged operational donor.

Rebuild preview is bounded to 50 current-ledger items and returns opaque identities,
dispositions and counts without paths or text. It uses the source completion lock and
run-bound cursor to prevent mixed-run plans. Both source and DataCore effects are false.

Index generation is separately authorized and transactionally bound to the latest
completed run. Its immutable identity includes the exact item plan, code revision and
chunker version. PostgreSQL refuses incomplete readiness, post-ready append, mutation
and cross-tenant access. Activation uses a distinct scope and idempotency receipt;
rollback reactivates a prior ready generation without deleting evidence or derivatives.

The index operator reads credentials only from owner-private files and the DSN only
from the runtime environment. Build-and-activate requires exactly the publish and
activation scopes; rollback requires exactly activation. It reauthenticates between
build and activation and after completion, returns no paths/content/secrets, and has
no source, Docker or scheduling authority.
In `--tenant-bound-db` mode, check and execution require that DSN to be a
DBA-enrolled login bound to the authenticated worker tenant (ADR-138).

The Email bridge operator uses the same private-file and safe-runtime checks with
exactly the shared ingest and document-publication scopes. It accepts one explicit
legacy message, attachment or approved-extraction UUID, reauthenticates around the
transaction and returns only opaque identities/counts/status. It has no Email ingest,
document approval, provider, original-content, mailbox-write, scan, scheduler or
automatic batch-discovery authority. Separately reviewed sealed batch commands
exist; they retain the same worker scopes and fail-stop behavior. The bridge
transactions share the Email account advisory lock so a current version cannot
become historical during publication.
ADR-139's `--tenant-bound-db` mode checks the authenticated worker's DBA-bound
login before check or execution for single-target, preview and sealed-batch
bridges. A plan or Email content cannot choose a database tenant route.
Current bridged-Email search independently rejoins the receipt to the legacy current
message on every query and excludes deleted/quarantined state. It returns bounded
untrusted excerpts and opaque identities only; it does not expose raw MIME or grant
Email/source authority.

The attachment bridge requires a current visible bridged parent, shares its account
lock and never reads MIME bytes. Each occurrence remains distinct even when its digest
matches another attachment. Only already-bounded legacy extracted text is published;
all other statuses remain explicit evidence/accounting with no document or chunk.
Embedded bytes are source-bound to the retained parent MIME, not mislabeled as a
separately retained object.

The approved-PDF derivative bridge additionally requires an immutable extraction with
a completed approval job and the existing current attachment bridge. It publishes
only bounded legacy page text, records the exact result digest and processor/policy,
and never opens attachment bytes or grants document-approval authority.

The private archive-image OCR command uses the existing exact-scope worker identity,
private configuration and least-privileged database preflight. One current archive
member is selected through forced RLS, then separately restricted archive and image
workers process only that hash-bound member. Check mode does not select or read it.
The controller reauthenticates around execution and the 5B publication transaction
rechecks current parent/member identity, processor provenance and idempotency. Only
complete nonempty OCR text may publish; normal output contains opaque identities and
counts, never source locators, OCR content, image metadata, raw faults or credentials.
The command passed hosted CI/container and populated restore at revision `f658ace`;
live-source and production acceptance remain separate gates.
ADR-139 applies the same opt-in bound-login check to every private archive
text/document/image command and preview/batch. It does not change the isolated
parser's lack of database or source authority.

## Dedupe and file safety

ADR-099 adds a forward-only database guard for archive inventory history:
late member/skip inserts must preserve the sealed count/byte ledger, provenance
outputs must name an existing normalized document, and each archive derivative
receipt must name its own inventory's parent source version. Migration preflight
refuses historical inconsistencies rather than silently rewriting evidence.
Hosted PostgreSQL and populated restore passed on PR #24's runtime head; the
change is integrated on `main` via PR #28. This is not
a substitute for parser containment, backup/audit or live FileOS acceptance.

Duplicate detection is read-only in DataCore. A matching hash does not authorize
deletion. Cross-domain/cross-source matches require review. Held-out `TEST - */`
corpora remain excluded from destructive dedupe. Future file effects must re-hash
keeper and candidate at execution, quarantine instead of unlink where possible,
respect legal hold, cap batches, log intent before action, reconcile the index, and
support rollback.

## LLM and prompt-injection controls

Retrieved content is delimited and labelled with provenance. Models return closed,
schema-validated proposals. Deterministic policy, current identity and explicit
approval decide effects. Models cannot choose a tool outside the caller's grant or
expand their own evidence scope. Cached summaries/embeddings are purged or made
inaccessible when source access is revoked.

## Incident posture

Fail closed on authorization/provenance ambiguity and fail loud on incomplete work.
Support credential revocation, worker fencing, source pause, evidence quarantine,
audit preservation, blast-radius analysis, rebuild from immutable evidence, and
documented notification/recovery. Live-source use requires security review and the
[release gates](RELEASE_ACCEPTANCE.md).
