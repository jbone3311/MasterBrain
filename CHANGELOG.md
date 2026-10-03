# Changelog

## Unreleased — after v0.2.0a1

- Added explicit All/Email/FileOS focus to grouped Brain search, extractive
  Ask, `/brain` and `BrainReadClient` (ADR-150). Focused reads skip excluded
  source/knowledge queries, mark unsearched coverage and keep the same grants,
  currentness checks and evidence scopes. No automatic routing or source effect.

- Added a disposable-PostgreSQL Ask regression that removes one of two OIDC
  assistant source grants during quote selection. The in-flight answer must
  refuse disclosure; the next turn may cite only the still-enrolled source.
  This is synthetic authorization evidence, not hosted revocation acceptance.

- Added an opt-in synthetic 3,000-row PostgreSQL benchmark for the FileOS v1
  completion ledger. It compares the current writer with the old per-item
  deferred trigger added back, records checkpoint counts and runs on local
  PostgreSQL plus a dedicated `postgres:17` workflow. It changes no runtime
  behavior, FOS-Master data or cutover authority; issue #71 remains open.

- Denied assistant access to legacy `email.*` compatibility API routes
  (ADR-149). Bootstrap assistant Email scopes are refused, and old OIDC
  Email-only assistant bindings fail transaction recheck. Enrolled assistants
  continue through source-filtered Brain/Knowledge routes. Human/worker Email
  behavior and FOS-Master are unchanged; hosted acceptance remains open.

- Added ADR-148's administrator migration guard: unapplied 0008/0009
  generated-column rewrites now refuse populated tables by default, with a
  nonwaiting writer fence. A deliberately named maintenance override retains
  the old SQL after operator review; it is not an online migration or closure
  of issue #9.

- Exposed the existing historical FileOS v2-versus-active-v1 lexical
  comparison through a bounded, human-only Brain API route (ADR-147). It
  requires transition-review, search and evidence scopes; the v2 result is
  explicitly a preview, and SQL still bars activation. No donor or source
  changes were made.

- Expanded the fictional Email/FileOS trial with conflicting Maple Arcade
  closing dates. A real-PostgreSQL Ask/API/client test requires both exact
  citations and no invented resolution; the launcher self-test checks the
  same disagreement. This is evaluation coverage, not conflict resolution.

- Added separately labelled reviewed KnowledgeCore matches to the read-only
  Ask response and first-party page (ADR-146). The server bounds their text
  and displayed evidence IDs, rechecks all direct links and source grants, and
  keeps them distinct from exact source quotations. The fictional trial now
  includes one reviewed cross-source commitment; no model or source effect was
  added.

- Made extractive Ask retrieve with substantive lexical terms from an ordinary
  question instead of requiring source documents to contain question filler
  words (ADR-145). The original question still drives local quote selection;
  initial and final current-source checks use the same terms. Search only
  remains literal, and no semantic synthesis or remote model was added.

- Enabled the default local, deterministic, verified-quote Ask path (ADR-144)
  with explicit selector disablement. It returns bounded current Email/FileOS
  quotes or an unsupported answer, not an AI-written conclusion; FOS-Master
  and source data are unchanged.

- Added ADR-143's source-scoped direct KnowledgeCore search, assertion expansion
  and change feed for enrolled assistants, plus unified Brain search. Mixed-source
  assertions are hidden in full; hidden change cursors return not found. Forward
  migration 0051 admits the two Knowledge read scopes to administrator-bound
  OIDC grants and retains old-resolver refusal. Hosted and legacy Email gates
  remain open.

- Extended enrolled-assistant access to retained DataCore search, aggregate
  current Email/FileOS search, and exact-source FileOS status/search reads
  (ADR-142). Filtering precedes ranking/limits; hidden source IDs return not
  found. Human reads are unchanged. Unified and direct Knowledge routes,
  hosted identity acceptance and source effects remain separate gates.

- Added ADR-141's opt-in `--tenant-bound-db` mode to the legacy `email-brain`
  `sync-read`, `process-jobs` and `process-documents` commands. The authenticated
  worker tenant selects one DBA-bound SQL login for preflight, encrypted-object
  stores and execution; the read worker preserves that route when reopening
  between polls. Defaults, worker scopes and source effects are unchanged.
  Credential lifecycle and hosted acceptance remain issue #7.

- Corrected the fictional Mac trial launcher to install the locked project
  non-editably and run without a second implicit sync (ADR-140). On this Mac,
  a hidden editable `.pth` file caused imports to fail despite a successful
  dependency sync. The database, fictional seed and Brain API are unchanged.

- Added ADR-139's opt-in `--tenant-bound-db` mode to every private
  `masterbrain email bridge*` and `masterbrain fileos archive-*` command,
  including previews and sealed batches. A shared DataCore worker-store
  primitive binds each authenticated worker tenant to one runtime login.
  Two-tenant PostgreSQL tests refuse shared, owner and wrong-tenant logins;
  bound Email and archive publication/replay leave originals unchanged.
  Legacy workers, hosted credential operations and issue #7 remain open.

- Added ADR-138's explicit `--tenant-bound-db` option to both private FileOS
  index build/activation and activation-only rollback. The authenticated
  worker's tenant must match a DBA-bound PostgreSQL login, including check
  mode; synthetic two-tenant tests reject shared, wrong and owner logins.
  Default local behavior, source files and FOS-Master are unchanged. Other
  private workers and hosted credential operations remain issue #7.

- Corrected the Mac trial command to choose a supported Python 3.13–3.14
  interpreter; `--python 3.12` could select unsupported 3.12.4 and stop before
  the browser opened. The command now forwards explicit trial options so its
  own synthetic self-test can be run end to end.

- Added a disposable local PostgreSQL 17 backend for the fictional cross-source
  browser trial (ADR-137). The launcher still supports Docker, accepts no
  existing database or live source, and runs the same seed and API checks.
  Local cluster cleanup is confirmed before deleting temporary data.

- Made DataCore and KnowledgeCore search excerpts plain text instead of
  exposing PostgreSQL highlight markers (ADR-136). The fictional trial now
  shows bounded source text directly after verifying the selected evidence
  identity, with provenance expandable. Search ranking, grants, original
  evidence and FOS-Master are unchanged.

- Added ADR-135's explicit `--tenant-bound-db` option to the private FileOS
  publisher. Its authenticated worker tenant selects the only permitted
  database binding; shared, unbound and wrong-tenant logins fail before intake.
  The default local mode and other private controllers are unchanged. This
  does not close issue #7, approve hosting or affect FOS-Master.

- Added an optional, read-only extractive answer route, reference client method
  and first-party workspace display (ADR-134). The server bounds input and
  passages, verifies exact quotes and citations, then rechecks current source
  visibility. No model selector is configured by default; the API returns 503
  and the browser falls back to grouped search. A separate Search only control
  preserves search-only credentials without bypassing an answer denial. No hosted model, freeform
  synthesis, source effects or FOS-Master change is included.

- Added source-scoped current-coverage and change-feed reads for enrolled
  assistants (ADR-133, forward migration 0050). OIDC bindings may receive the
  distinct `brain.changes.read` scope only with source enrollment; hidden-source
  results and cursors are excluded before pagination. The provider-neutral
  client now exposes both bounded calls. PR #96 is merged; its exact-head
  and merged-main CI, strict runtime and populated restore passed. This is not
  hosted chat, named-assistant certification or source-write authority.

- Added administrator-owned OIDC Brain source grants (ADR-132, migration 0049):
  an exact identity binding may enroll up to 20 existing same-tenant sources;
  grant changes bump the binding revision, are audited, and invalidate saved
  contexts at the next transaction. Only the three already source-aware Brain
  read routes are admitted for assistants; the legacy identity resolver refuses
  Brain-scoped assistants during a rolling upgrade. PR #91 passed exact-head
  and merged-main CI, strict runtime and populated restore. Hosted/named-assistant
  acceptance, legacy Email assistant source filtering and derived-cache
  revocation remain open.
- Added a forward-only FileOS v2 readiness-query correction (ADR-131,
  migration 0048): exact generation/base chunk comparisons and the reverse
  base count now use indexed probes under the existing five-second database
  statement limit. A fresh full PostgreSQL suite and two populated 3,000-row
  repeats passed locally. PR #90 passed exact-head and merged-main CI, strict
  runtime and populated restore; issue #84 is closed. V2 remains private and
  non-activatable.
- Added synthetic-bootstrap source-scoped assistant reads (ADR-130): explicit
  source enrollment filters the shared current Email/FileOS/archive and
  reviewed-Knowledge search before limits, gates evidence expansion and denies
  unreviewed alternate Brain/Knowledge routes. This does not itself establish
  hosted OIDC grants, a named assistant or source effects.
- Merged a provider-neutral, read-only Brain API client (ADR-129, PR #86)
  for grouped current search and separately scoped evidence/content reads.
  Fictional Email/FileOS client-vs-API parity, exact-head and merged-main CI,
  strict runtime and populated restore passed. This is not a hosted endpoint,
  named assistant integration, generated answer or source-action permission.
- Merged the private FileOS v2 active-v1-versus-historical-v2 search comparison
  (ADR-128, PR #85). Its bounded, human-only result keeps separate rankings;
  it does not activate v2 or change FOS-Master. Intermittent populated-database
  readiness latency was subsequently corrected under ADR-131/PR #90.
- Added a first-party read-only MasterBrain question workspace (ADR-127) over
  the existing scoped current-search and evidence routes. It groups indexed
  Email, FileOS, archive and KnowledgeCore results with partial-coverage
  notice, holds turns/credentials only in browser memory, and has no model
  answer or source effects. Hosted and named-assistant acceptance remain.
- Merged the private FileOS v2 shared index-generation tranche (ADR-126,
  migration 0047, PR #81). Exact-head and merged-main CI, strict runtime and
  populated restore passed. V2 activation and current reads remain prohibited;
  FOS-Master is unchanged.
- Clarified the final product contract: a first-party MasterBrain chat and
  approved external assistants use the same scoped Brain API; a central private
  service holds authoritative state, while later Email/FileOS changes require
  typed previews, separate execution grants, approval and audit. This is a
  roadmap/documentation change, not an implemented chat, hosted deployment or
  source-write capability.
- Reworked FileOS v1 completion-ledger validation (ADR-122, migration 0043):
  run items precede the receipt in one transaction, whose deferred check now
  scans the final ledger once. An immediate source-locked guard rejects late
  rows; replay, immutability, RLS and absence semantics remain unchanged.
- Added a private, worker-scoped FileOS v2 hashed-evidence preparation path
  (ADR-121, migration 0042). It rescans the approved stage, maps donor IDs
  to policy-scoped DataCore versions and preserves hashless rows without
  changing v1 current state, search, freshness or absence. A test caught and
  prevented v1 version-metadata collision; v2 completion and publication
  remain separate.
- Added fixed-code failure-stage warnings for the trusted restricted-container
  controller (ADR-120) and secret-scrubbing regressions. `MimeUnavailable`,
  isolation limits and retry policy remain unchanged; issue #64 stays open.
- Added worker-scoped, fresh-root verification of one approved FileOS v2
  staged inventory (ADR-119, migration 0041). Exact source, policy, count and
  row matching yields an immutable historical receipt; no v2 publication,
  current-read change, deletion inference or donor switch follows.
- Added a private FileOS v2 transition review plan and immutable human-owner
  approval receipt (ADR-118, migration 0040), bound to the exact staged
  packet, latest completed v1 receipt, plan digest and acknowledged counts.
  Hard blockers refuse approval. This is not a v2 publication, deletion
  inference, live-source approval or donor cutover.
- Added an immutable, nonpublishing FileOS v2 staging ledger (ADR-117,
  migration 0039). It retains hashed, metadata-only deferred, excluded and
  error observations separately without fabricating versions or changing v1
  freshness, absence, search, source files or FOS-Master.
- Added a private, bounded read of sealed FileOS transition packets (ADR-116):
  locator-free summary, separately authorized detail pages, digest verification
  and read-time latest-receipt status. No API route, approval or cutover.
- Added an immutable, nonpublishing FileOS donor-policy transition review
  packet (ADR-115, migration 0038). One donor scan supplies its candidate and
  completed-v1 comparison; a locked latest-run check fences insertion. It has
  tenant RLS and no v2 publication, FileOS cutover or FOS-Master change.
- Added a read-scoped, exact completed-v1 baseline verifier and a private
  before/after database-bound FileOS donor transition preview (ADR-114). A
  newer completion during scanning invalidates the report. No v2 publication,
  absence inference, source effects or FOS-Master change.

## v0.2.0a1 — synthetic-only alpha checkpoint (2026-10-01)

- Tagged exact `main` commit `c0a531d8a7d0991be0a0f1ea717479c07cc20feb`
  after full CI, strict-runtime, populated PostgreSQL restore and a local
  3,000-file pinned-donor DataCore parity run passed. This version is for
  fictional inputs and disposable PostgreSQL only; interactive Mac acceptance,
  live sources, production security/operations and FileOS cutover remain open.

- Added a private, nonpublishing v1-to-donor FileOS policy transition preview
  (ADR-113). It classifies stable/changed hashes, deferred or excluded prior
  items, scan errors, donor-only items and unobserved prior locators without
  creating deletion evidence or changing v1 completion.
- Added a source-bound, nonpublishing FileOS donor-policy candidate ledger
  (ADR-112). Hashed observations carry candidate item/version identities;
  hashless and dataless rows are deferred without invented evidence. The v1
  importer rejects this ledger; no donor-policy switch or FOS-Master edit.
- Bound FileOS donor-policy shadow metadata observations to no-follow directory
  descriptors and the initial root identity; root/ancestor/leaf swaps fail closed
  without opening placeholder bytes. This is nonpublishing and changes neither
  snapshot v1 nor FOS-Master.
- Added a separate, nonpublishing FileOS donor-policy shadow inventory (ADR-111).
  A pinned synthetic FOS-Master comparison now matches 3,004 ordinary file rows
  without changing snapshot v1, completion, search, or the donor repository.
  Metadata-only and fault outcomes remain explicit; no FileOS cutover is implied.
- Added opt-in two-stage API database routing: a table-blind exact-identity login
  resolves verified claims, then one tenant-bound login performs tenant SQL
  (ADR-109). Synthetic two-tenant API tests and private-file validation pass;
  private workers, credential lifecycle and hosted acceptance remain open.
- Added an opt-in DBA-bound, one-tenant PostgreSQL login fence with restrictive
  policies over existing forced-RLS tables (ADR-108, migration 0037). The shared
  runtime credential is unchanged; issue #7 and hosted isolation remain open.
- Added independently ranked current archive-image OCR search through exact
  receipt/parent/member fencing (ADR-107, migration 0036). Retained history and
  FileOS source behavior are unchanged; no hosted or cutover claim.
- Removed direct runtime SELECT on identity bindings and the caller-settable
  identity-lookup RLS policy; an exact, active-only resolver now supplies the
  verified-token path (ADR-106, migration 0035). Arbitrary-SQL/tenant-context
  containment remains open in issue #7.
- Added a separate non-superuser identity-administration role under forced RLS
  (ADR-105, migration 0034) with a protected audit trigger and real PostgreSQL
  regression. Runtime still cannot manage bindings; live enrollment remains gated.
- Merged the cumulative MasterBrain synthetic baseline (#28), fail-loud strict
  sender-parser runtime gate (#31), privacy-safe API failure correlation (#33),
  disposable fictional Email/FileOS browser trial (#32), and reconciled build
  receipts (#30). The exact documentation-merge `main` commit `1e081ea` passed
  full CI, strict-runtime and populated restore. At that historical checkpoint
  the tag was pending; the interactive Mac trial, live sources and production
  acceptance remain open.
- Added a current callable-function map and recast the roadmap around unresolved
  security/migration findings, user trial, operational quality and donor cutover
  gates. This documentation update does not add API routes, source effects or
  assistant integrations.

- Consolidated the tested MasterBrain Email/FileOS stack into a test-only release
  boundary. At that earlier point, the version remained a candidate until the
  cumulative `main` commit passed CI and populated restore and was tagged.
- Adds a reproducible [alpha test guide](docs/ALPHA_TESTING.md), exact-head
  branch/PR/merge/tag decision (ADR-101), and updated product identity/status.
- Extends the `main` restore trigger to shared MasterBrain source, bounds CI run
  time and cancels superseded PR runs (but not `main` runs), reports the collected/
  executed/skipped PostgreSQL-test denominator, and ignores local dump files. No
  runtime permission, schema or FileOS donor change.
- Remaining: live-source authorization, hosted operations, production acceptance,
  complete KnowledgeCore and LLM-client contract, plus separate FileOS cutover
  proof. The pinned FOS-Master donor remains untouched.

## Unreleased — through 2026-09-22

The package remains version 0.1.0, a synthetic-data prototype. These entries do
not announce a production release. [Build receipts](docs/BUILD_RECEIPT.md) retain
exact tested commits and results.

### MasterBrain foundation (ADR-047)

- Established MasterBrain as the final product, retaining EmailBrain as the internal
  Email capability and FOS-Master as an unchanged donor/reference.
- Defined DataCore, KnowledgeCore and Brain API ownership; added product identity,
  manifest, feature inventory, architecture, data model, security, deployment,
  roadmap, migration and acceptance documentation.
- Extracted FOS-Master's dependency-free read-only hash/dedupe behavior into
  `masterbrain.datacore` with pinned provenance, synthetic tests and a live-donor
  parity harness. No file move/delete behavior or FileOS cutover was added.
- Added shared `masterbrain` hash/compare/duplicates/snapshot commands, immutable
  source/evidence/provenance contracts, safe read-only FileOS manifests and expanded
  3,000-file donor parity plus fault/symlink/no-mutation stress coverage.
- Added completion-bound immutable FileOS lexical generations, database-validated
  readiness, append-only activation/rollback receipts and active-generation Brain API
  reads (ADR-058). FOS-Master and source files remain unchanged; hosted verification
  is recorded only after the branch gates pass.
- Added an explicit private FileOS index command for build-and-activate or activation-
  only rollback, with exact per-operation worker scopes, non-consuming check mode,
  reauthentication and scrubbed receipts (ADR-059). It is not a scheduler or cutover.
- Added an explicitly current FileOS search across each source's latest activated
  generation while preserving existing historical compatibility search (ADR-060).
- Extended grouped DataCore/KnowledgeCore retrieval with an explicit current-FileOS
  evidence mode; retained history remains the compatibility default (ADR-061).

### Tools discussion (documentation only)

- Added the [ranked tools discussion](docs/TOOLS_DISCUSSION.md), including
  KItinerary, Docling, Tika, OCRmyPDF, MimeKit, Mailpit and pgvector; source links,
  dated repository metadata, license caveats, trial gates and open questions.
- Linked it from both reading guides and the OSS evaluation. No dependency,
  fixture import, runtime change or integration approval is included.

### Owner email reader (ADR-045)

Latest addition: [ADR-046 structured memory](docs/STRUCTURED_MEMORY.md) implements
reviewed trip/flight/hotel/bill records, immutable source-linked revisions,
non-consuming change cursors, partial freshness summaries, labelled-format
candidates and a separate developer editor. Additive migration 0014; no new
dependency, provider writes, live model or automatic interpretation claim.

The later [ADR-045 owner reader](docs/MESSAGE_READER.md) adds complete selected
body text for MIME up to 1 MiB, bounded headers and explicit human-only verified
original/leaf-part downloads. Large messages keep explicit projection limits;
no in-API large parsing or active HTML. New unit/API/SQL/Node/preview tests and a
[user test guide](docs/USER_TESTING.md) accompany the feature. No migration,
dependency or mailbox privilege; exact verification is in the build receipt.

### Review corrections (ADR-044)

- Signing-key refresh no longer holds the cache lock during network I/O. Valid
  cached requests proceed; cold/unknown/expired waiters are bounded and single-flight.
- Normalization preserves sender ambiguity as ineligibility rather than silently
  selecting the first author. Search and simulation require exact snapshot proof,
  including attachment/PDF hits. Legacy records remain readable but cannot match
  sender rules until explicitly reprocessed. Ordinary parser advances to v5.
- Added concurrency, malformed-header, strict worker-envelope and real SQL regression
  cases. No migration, dependency, mailbox authority or real service is added.

### Private browser-mode TLS startup (ADR-043)

- Added explicit `serve --browser-config --tls-cert --tls-key` and browser-only
  non-consuming `--check`. Conflicting modes and incomplete settings fail closed.
- Verify private files, certificate validity, exact SAN, key strength and pairing;
  reject encrypted keys without prompting. Preserve loopback binding, TLS 1.2
  minimum, disabled access logs and disabled proxy-header trust.
- Generated-certificate/CLI tests cover malformed/private material, conflict and
  scrubbed-error boundaries. No issuer, certificate trust, public ingress or new
  schema/dependency is provisioned. Owner UI and browser acceptance remain next.

### API identity foundation (ADR-040)

- Pressure review corrected key-response buffering that could postpone elapsed-time
  checks during a slow drip; a regression test fails the prior buffered path.
  Ambiguous duplicate Authorization headers now fail before verification, and
  missing credentials receive a plain Bearer challenge.

- Added explicitly configured RFC access-token/Entra v2 verification with fixed
  issuer/audience/client, bounded discovery/key cache and no bootstrap fallback.
- Added migration 0013 administrator-owned identity mappings, immutable binding
  identity, monotonic revisions, forced lookup RLS and minimal administrator audit.
  Every mapped Store transaction rechecks current scopes/kind/expiry and ownership.
- Added private `serve --oidc-config`, fake-issuer/security and real SQL/API tests,
  populated-upgrade coverage and two-tenant identity restore/revocation checks.
  Adopted pinned MIT PyJWT 2.14.0; maintained source/operating/rollback documentation.
- No browser login/session, MFA enforcement, real issuer enrollment, team sharing,
  service-principal lifecycle, public ingress or mailbox privilege was added.

### Browser session backend (ADR-042)

- Added optional fixed code/PKCE exchange, one-use browser-bound state, human SQL
  identity resolution, opaque bounded process sessions and cookie/Origin/CSRF REST
  boundaries. API tokens are discarded, not sent to browser storage.
- Added expiry/logout/current-revocation and concurrent request/callback tests;
  cancelled/replaced flows cannot publish late sessions. The key reader now also
  checks elapsed time after EOF and validates size before extending its buffer.
- At this increment default CLI/owner UI were unchanged; ADR-043 subsequently
  supplies private operator/TLS wiring. Owner UI and actual browser acceptance
  remain next. No ID/refresh-token flow, MFA policy, real issuer,
  new dependency/schema/grant, mailbox or hosted listener was introduced.

### Response streaming correction (ADR-041)

- Fastmail, Gmail, Graph and Ollama now check incoming chunks without extra
  fixed-size buffering, accumulate within existing byte caps and check deadlines
  after EOF. Sixteen synthetic transport cases cover slow drips, delayed empty
  replies, fragmented success, overflow and closure. Five cases fail the prior
  implementation. These are cooperative checks, not hard process deadlines.

### Evidence, processing and review

- Added separate owner PDF selection/approval, bounded history/status/cancel,
  cited page evidence and opt-in document search (ADR-038). Closed response and
  source/processor validation, same-key uncertain retry and stale-context fences
  keep consent explicit. Existing MIME permissions stay separate. No new schema,
  worker privilege, browser storage, scanner/live policy or hosted service.
- Corrected the owner screen to recognize the original attachment receipt's
  `not_scanned` status separately from PDF-result `unscanned`. Real SQL/API-to-UI
  tests exposed the mismatch; offline fixtures now match the stored contract and
  reject invented safe/clean scan claims. Immutable source records are unchanged.

- Added `process-documents` with separate fixed-purpose/policy private configuration,
  exact PDF-worker scope, synthetic-account preflight, fresh credentials and bounded
  polling. Added an explicit loopback server channel option. MIME permissions remain
  separate. That command increment added no owner UI; ADR-038 above now supplies
  it. Hosted supervision and live-mail authority remain separate gates.
- Fixed demo-owner registry generation to allowlist human scopes and validate before
  saving; the new document-worker scope can no longer invalidate the generated owner.

- Added a separate synthetic-only PDF approval API/library, worker scope, fenced
  durable jobs, immutable extraction revisions, opt-in document FTS and bounded
  page evidence. Migration 0012 protects receipts/results and approval identity.
  That increment added no document UI/CLI; ADR-036 above supplies the separate CLI.
  ADR-038 above supplies the owner UI; scanner, live-mail policy and hosted service remain unfinished.

- Added separate source-bound restricted PDF worker/image and strict page-level
  contract, with hash/part validation, partial/deferred/failed outcomes and explicit
  unscanned status. At that initial increment there was no approval-job/SQL/FTS
  integration; the subsequent ADR-035 entry above adds it. Ordinary ingestion still
  defers binary documents. PDF dependency stays out of the default API/MIME image.

- Added certified inventory reconciliation and durable malformed/oversized MIME
  quarantine, with human retry and immutable parser-versioned evidence.
- Added optional tenant-bound encrypted local source objects up to 16 MiB and
  combined SQL/object/key restore verification; hosted Blob/KMS remain pending.
- Added restricted large-MIME processing, image-bound provenance, durable expiring
  approvals, leases, cancellation and fenced atomic publication.
- Added owner processing history/approval/cancellation UI and a bounded operator
  CLI with private configuration, preflight, credential refresh and graceful stop.
- Added reviewed sender-rule simulation, explicit activation, immutable rollback
  and virtual search labels. No provider folders or mailbox contents are changed.
- Added bounded calendar text extraction and attachment receipts/FTS; production
  PDF intake, Office/OCR/archive extraction and malware scanning remain unfinished.

### Providers, models and test data

- Added `sync-read` with private non-consuming preflight, explicit provider-read
  flag, exact ingest-worker identity, fixed account/secret binding, per-request/step
  guards, bounded counters/stop and existing encrypted storage. No enrollment,
  pause reset, schema/grant change, hosted supervisor or live acceptance (ADR-039).
- Added offline-tested Gmail/Graph read libraries and an injected-session IMAP
  contract. Only Fastmail has durable database worker orchestration; no live account.
- Added opt-in candidate-only local-model library and fake-response boundary tests;
  no actual-model quality claim, automatic ingestion hook or remote inference.
- Added seeded coherent conversations, actual synthetic document formats, hashes
  and answer keys, exclusive packet export and bounded paced/resumable SQL replay.
  Independent PDF/Office readers verify generated files; Office readers remain
  development-only and pypdf is additionally available in the dedicated optional
  PDF image, never the default API/MIME image. No external mail delivery is enabled.
- Extended real PostgreSQL, UI-contract, actual-container and disposable restore
  testing. Results at `4286504`: 1,392 standard Python, 52 Node and five additional
  container cases passed; these are not live-provider, model-quality or soak results.

### Documentation and delivery plan

- Refined the GitHub landing page with a one-minute product/delivery map, explained
  identity versus permission, and aligned roadmap/backlog/Factory priority on the
  next identity foundation. Kept completed read/PDF/operator work separate from
  remaining browser, scanner, hosted and live gates; preserved legacy document
  links and historical verification/research. No authentication or runtime change.

- Added a plain-language methods guide and a specific next owner-workflow outcome.
  Strengthened offline documentation checks to cover required guides and GitHub
  issue/PR templates, local paths and supported section links, with synthetic
  regression tests (ADR-037). Updated navigation and corrected ambiguous MIME/PDF
  command wording. No product runtime, dependency, schema or permission changes.

- Audited current PDF/search/security/roadmap claims against ADR-035 and corrected
  stale standalone-only descriptions. Expanded the game plan and feature methods,
  expanded the contributor guide, added release acceptance, and made GitHub build/review templates
  require explicit evidence and remaining limits. No runtime permissions changed.

- Added a worked owner scenario covering arrival, attachment formats, evidence,
  corrections, learning and future actions, plus documented failure behavior.
- Added status vocabulary, authoritative-document ownership and a per-feature
  documentation checklist. Aligned database/vector and remote-escalation language
  with the lexical-first, explicit-permission plan; corrected standalone versus
  integrated PDF claims and managed-cloud versus disposable-CI wording.

- Refreshed the owner game plan, feature/method walkthrough, current code map,
  roadmap, test scope and Factory handoff; distinguished current behavior from targets.
- Corrected stale “planned generator” and already-completed next-work descriptions.
- Identified the next design boundary: approved extraction for deferred documents
  in ready messages, without misusing the quarantine queue or hiding valid body search.
- Preserved dated OSS observations and exact-commit receipts rather than relabeling
  historical measurements as new research or production acceptance.

### Earlier read-worker increment — 2026-09-20

- Added resumable Fastmail read-worker library, database-clock leases, stale-worker
  fencing, account-binding checks, query-state pagination and baseline-preserving restart.
- Added bounded retry deadlines, content-free operational outcomes and explicit
  auth/protocol/parser/cursor-expiry pauses; no live scheduler or enrollment.
- Added current mailbox/keyword metadata without replacing raw-body evidence.
- Hardened provider URL, response, metadata and checkpoint validation.
- Added synthetic HTTP-to-PostgreSQL, competing worker, crash/replay, malformed
  provider and failure tests; retained real-mailbox and full reconciliation gates.
- Corrected database infinity timestamps after CI caught status-decoding failures.
- Refined build order, migration/rollback guidance and honest release boundaries.

## 0.1.0 — 2026-09-19

- Published private GitHub architecture/product pack and bounded implementation.
- Added Postgres evidence/version/search/control schemas, forced RLS and composite ownership keys.
- Added atomic page ingestion with idempotency, stale-cursor checks and immutable event/evidence history.
- Added owner-only scoped API authentication, evidence/search, typed proposals and human review.
- Added browser review UI with text-only mail display and memory-only token handling.
- Added attachment receipts/events, duplicate links, bounded text extraction and explicit deferred outcomes.
- Added read-only JMAP protocol slice, inference validation/routing and rank-fusion helpers.
- Added real PostgreSQL CI tests, dependency lock, developer container and local run instructions.
- Reviewed Factory intake patterns; staged five Factory improvement proposals without changing Factory.
- Refreshed OSS activity/license caveats and compared AWS/Supabase/Neon hosting.

At the original 0.1.0 publication (historical, not current status), not shipped:
live mailbox synchronization, sending/deletion, approved-rule application,
production auth/deployment, binary extraction sandbox, MCP transport or live model adapters.
