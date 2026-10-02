# MasterBrain Implementation Status

Updated 2026-10-01. Tagged synthetic checkpoint `v0.2.0a1` is
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
  returns exact evidence citations after a current-source recheck. Without an
  owner-approved selector the route returns 503 and the workspace retains its
  grouped-search fallback. This is not a configured model, freeform synthesis,
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
  FileOS publisher; other workers still use explicit shared DSNs. Credential
  lifecycle/hosted acceptance are not implemented. Issue #7 stays open.
- ADR-108/migration 0037 add an opt-in restrictive RLS fence for a DBA-bound
  one-tenant PostgreSQL login. Synthetic arbitrary-SQL tests cover forged GUCs,
  wrong-tenant read/write, role switching and mapping loss. No worker DSN router,
  production credential lifecycle, live rollout or closure of issue #7 is
  claimed; the older shared login remains vulnerable under arbitrary SQL. See
  [the contract](TENANT_LOGIN_FENCE.md).
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
