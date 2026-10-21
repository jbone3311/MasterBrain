# Changelog

- Make source-tier reviews reachable past the first page with a cursor and
  all-page tier counts; approve an imported dossier fact or artifact claim
  once; bind fact-proposal approvals to the exact published fact and the
  current reviewer (ADR-266, migration 0095).

- Fix three review findings (ADR-265): historical later-FileOS reads compare
  locators in byte order so en-US databases no longer reject valid attempts;
  XLSX extraction reads the true sheet extent so an understated dimension
  cannot hide cells or formulas; reviewed facts under retired or unregistered
  predicates stay correctable (migration 0094). Populated restore-seed tests
  move to `tests/test_restore_drill_postgres.py`. The XLSX review view marks
  invisible formatting characters so the reviewed text cannot hide them.

- Add an explanatory `docs/concepts` institutional-knowledge layer and connect
  repository navigation, contributor guidance and documentation ownership. Preserve
  canonical PRD/architecture/ADR authority and dated research; describe future RFC
  triggers without creating an RFC system. Documentation only.

- Add a compact, human-only historical FileOS review summary that hashes the
  exact latest row-decision snapshot and counts unresolved coverage without
  recording run signoff or changing current FileOS state (ADR-262).

- Add human-only append-only decisions on exact historical FileOS later-run
  classifications, with latest-decision and bounded history reads. Migration
  0093 enforces tenant/actor/exact-row binding and immutability. The decisions
  do not authorize absence, current search, file effects or donor cutover.

- Add bounded human inspection of exact historical later FileOS prior-row
  classifications, including possible-missing candidates. Results are
  source-bound, revalidated, read-only and explicitly nonauthoritative for
  absence, current search or file effects.

- Add a human-only, source-bound comparison of a ready historical later
  FileOS generation with active v1 search, including run review flags and
  distinct result layers. Harden baseline-v2 preview against paused or
  ungranted sources. This changes no current search or donor files.

- Add an exact, nonactivating shared DataCore index generation for a
  completed historical later FileOS v2 run. Database guards close hashed
  item and chunk membership and refuse direct activation. A 3,000-file
  synthetic stress case exposed and then verified a fix for the inherited
  readiness-count timeout. Current FileOS search and FOS-Master remain
  unchanged.

- Add a synthetic-only historical FileOS v2 later-run completion bound to a
  ready exact-row document attempt and a fresh donor-policy scan. Its
  possible-absence/mass-loss/coverage review flags and source lock are
  database-checked. It does not activate current reads, infer absence, mutate
  files or change the FOS-Master donor.

- Add retryable historical FileOS v2 document attempts: a failed extraction
  is sealed as blocked, while only one ready attempt may complete an exact
  later evidence preparation. Normalized derivatives remain historical.

- Add one disposable synthetic XLSX alpha round-trip test across owner Email
  search/evidence, exact approval, isolated-worker simulation, bounded result
  inspection, explicit review, separate publication worker and cited Brain
  retrieval. Pausing the source hides the derivative; no live data is used.

- Add `masterbrain email extract-approved-xlsx` for one account-pinned,
  human-approved synthetic attachment. A separate worker identity and
  tenant-bound login run the pinned isolated extractor; check mode reads no
  selected MIME and execution seals only a private result, not a document.

- Add first-party source-attached selection and explicit approval for one
  eligible synthetic Email XLSX. Selection alone does not write; approval
  returns an `xapp_` ID for a separately scoped extraction worker. The screen
  cannot run extraction, publish or change sources.

- Expose human-only, idempotent approval of one current synthetic Email XLSX
  attachment through the API. A new server-side XLSX processor pin is distinct
  from the existing PDF pin. Approval does not run extraction or publish.

- Add a first-party synthetic XLSX result-review screen for an existing
  approval ID. It displays every bounded text page, recomputes the complete
  UTF-8 SHA-256 in the browser, and requires a separate explicit human review
  click. It cannot create the approval, run or impersonate a worker, publish
  a document, or change mail/files. The local populated restore and full
  disposable-PostgreSQL suite passed before this UI slice; hosted/image and
  actual-browser gates remain open.

- Add a native two-cluster PostgreSQL 17 synthetic dump/restore drill and
  populate it with an approved, reviewed and published fictional XLSX.
  The restored document is retrievable, its review/receipt is preserved and
  a foreign tenant cannot read it. This complements, not replaces, the
  hosted Docker restore gate.

- Add a separate human-authorized synthetic Email XLSX DataCore bridge. It
  publishes only a complete exact-approved result with reviewer-supplied
  digest/counts, immutable occurrence receipt, deterministic chunks and
  provenance. Generic and Email-family reads recheck currentness; no
  cell-level or financial claim, live mail or FOS cutover is enabled.

- Recheck the approving owner's membership and caller authorization before
  reading retained Email XLSX MIME or replaying a cached extraction result.
  Add revoked-owner and replay tests plus a collected actual-image
  approval-to-result test; no publication boundary changes.

- Seal one exact-approved synthetic Email XLSX extraction through the pinned
  isolated DataCore worker in a separate immutable result table. The result
  remains private; no Brain search, live mailbox or financial claim is enabled.

- Add a separate, human-only synthetic Email XLSX extraction approval bound
  to an exact current bridged attachment, parent MIME, source event and pinned
  processor. Protected SQL and disposable PostgreSQL tests pass; this does not
  run extraction, publish text or enable live Fastmail. PDF jobs stay PDF-only.

- Expand the pinned FOS-Master XLSX comparison with sparse/multi-sheet and
  exact row-cap cases; preserve the donor and explicit policy differences.

- Add a fictional cross-source conflicting-price API acceptance case: two
  exact-cited Email/FileOS `loi.price` statements remain separate, the owner
  sees a disagreement without any total, and an Email-scoped assistant cannot
  see or infer the FileOS row. No ownership or investment truth is claimed.

- Make the pinned FOS-Master donor-policy shadow repeatable at the 9,994-file
  v1 transition capacity. The exact-donor local run and new test compare
  9,998 ordinary rows across replay/change/metadata paths and retain the six
  explicit blockers; no source policy or FileOS cutover changed.

- Exercise the published `masterbrain demo seed` command in the PostgreSQL
  regression, in addition to its underlying service. A fresh disposable
  command-to-loopback-API walkthrough verified migration, initialization,
  idempotent seed, both-source search/focus and cited Markdown inspection.

- Expand the disposable combined-source dossier with exact-quote, replay-safe
  event, proposed reply request, source-stated note and generated-file link.
  The request's relative due date remains unresolved and no person/role is
  invented. The real Brain API test verifies one row per section after replay.

- Correct the fictional combined-source project so its cited Melron phrase
  occurs in both the linked email and file. The demo v2 marker requires fresh
  disposable state instead of silently rewriting a v1 fixture; tests verify
  the original evidence bodies through the Brain API.

- Complete and activate the fictional FileOS search generation in the
  combined-source demo. Its current Brain search now returns both Email and
  FileOS, and the exported dossier passes the owner-only Markdown citation
  inspection API. Disposable PostgreSQL regression tests cover replay and
  both-source coverage; no live source is enabled.

- ADR-231: closed the reviewed Email PDF account-status race with the shared
  tenant/account advisory lock and a narrow tenant-bound account row-lock
  function. Synthetic concurrent, privilege, migration and recovery tests
  pass; live mail and real-container gates remain closed.

- ADR-230: added a restricted, tenant-bound Email attachment PDF replay
  command with exact account/review, pinned image and no-selected-MIME-read
  check mode. Fictional controller/CLI and command-to-PostgreSQL tests pass;
  real-container and hosted gates remain, and no live mail or financial claim
  is enabled.

- ADR-229: sealed one current reviewed Email attachment PDF text-layer replay
  in an occurrence-specific, tenant-fenced immutable digest receipt after
  retained-MIME proof and final checks. Fictional PostgreSQL/RLS tests pass;
  ADR-230 later adds a restricted operator command; no live mail or financial
  claim is enabled.

- ADR-228: added a nonpublishing, exact retained-MIME/part Email PDF text-layer
  replay proof through the pinned isolated worker, with fictional complete,
  changed, partial and same-hash occurrence tests. No receipt or live mail.

- Prepared an explicit CI check that replays a fictional reviewed FileOS PDF
  through the actual pinned document image into its protected PostgreSQL
  receipt. The container result remains pending until hosted jobs start.

- ADR-227: exposed one current reviewed FileOS PDF text-layer replay through
  a tenant-bound, exact-source operator command with no-selected-PDF-read
  check mode, pinned image config and final worker reauthentication. Fictional
  command-to-database tests pass; no live root or financial claim is involved.

- ADR-226: added a worker-only, digest-only reviewed FileOS PDF replay receipt
  with final current-source/authorization recheck, protected migration 0078
  and fictional PostgreSQL fault tests. No operator command, OCR, live root or
  financial publication is implied.

- ADR-225: added a nonpublishing confined FileOS PDF byte-to-text replay
  primitive, bound to the exact restricted document processor and its image
  normalizer. Fictional digest, source-change, symlink, image-only and
  invented-text regressions pass; no receipt or financial claim is created.

- ADR-224: exposed one reviewed retained-Email text replay through a
  tenant-bound operator command with exact worker scopes, account binding,
  no-MIME-read check mode, optional private encrypted storage and final
  credential recheck. Fictional inline/encrypted command paths are tested.

- ADR-223: added a worker-only, point-in-time retained-MIME replay for one
  current reviewed Email message. It recomputes the exact pinned-parser
  DataCore text from inline or encrypted bytes and stores a digest-only
  immutable receipt; no live mail or financial claim is involved.

- ADR-222: fixed encrypted Email-to-DataCore bridging by using the retained
  object's generated byte size rather than its nullable inline MIME column.
  Fictional encrypted and inline bridge regressions protect source identity.

- ADR-221: DataCore now defers formula-bearing XLSX workbooks and overlong
  cells rather than silently omitting uncached formulas or truncating cell
  text while reporting successful extraction.

- ADR-220: DataCore now defers a mixed text/image-only PDF instead of
  publishing an incomplete-looking extracted document. A fictional two-page
  closed-contract regression protects the behavior; PDF/OCR completeness
  remains a separate gate.

- ADR-219: added a tenant-bound, document-only worker command for one reviewed
  FileOS text replay, with no-read check mode, source-ID binding, scrubbed
  failures and final-transaction credential recheck. Only fictional local
  execution has been tested.

- ADR-218: extracted a shared DataCore confined FileOS byte/text replay and
  added an immutable worker-observed replay receipt for current human
  source-tier reviews. Statement replay behavior remains tested; no source
  file or financial claim is changed.

- ADR-217: added append-only, human-reviewed source-tier classifications tied
  to current evidence/version/document hashes and exact source quotes, with
  source-scoped Brain API reads. These are not independent byte attestations
  or approvals of financial facts.

- ADR-216: added exact-hash synthetic FOS fact-verifier parity for tier
  heuristics, numeric variants and confirmation status; documented why these
  donor outcomes cannot certify MasterBrain financial claims.

- ADR-215: fixed project-fact catalog retirement so the latest deprecated
  revision cannot revive an older active one. Added a bounded, database-
  authoritative Brain API discovery route and strict external client;
  private proposal previews now reflect latest SQL status.

- ADR-214: added a versioned, guarded project-fact predicate catalog in code
  and migration 0073. New reviewed facts require a registered name, value
  type and measurement unit; historical rows remain unchanged. The broader
  name-proposal/alias registry remains open.

- ADR-213: tightened reviewed measurement citation checks from substrings to
  complete amount and unit/currency quote tokens in both the write model and
  additive migration 0072. Existing typed rows are validated without rewrite;
  a misleading old row blocks migration for explicit review.

- ADR-212: added opt-in exact-decimal amount, unit and currency metadata to
  newly reviewed project facts via additive migration 0071. App and SQL
  require matching value and literal source-quote tokens; the scoped report
  exposes a source-stated typed field but still computes no financial total.

- ADR-211: added a current-evidence, source-granted project fact report route
  and validated external read client. It groups one reviewed page, flags
  divergent previews and disputed rows, and refuses numeric aggregation or
  investment-truth claims; no donor or source data changed.

- ADR-210: compared the remaining three pinned FOS intelligence-report row
  shapes on fictional data, with direct local DuckDB donor replay, a 1,000-row
  repeat and corrected half-away rounding. No runtime report, verified balance,
  live source or FileOS cutover.

- Pin FOS-Master's coverage/timeline intelligence-report semantics in an
  isolated fictional ADR-209 parity seed. Exact-hash local donor replay and
  1,000-row comparison preserve its status counts and year-prefix behavior;
  no certified freshness or investment total is enabled. ADR-210 later adds
  the other three report row shapes without a runtime report.

- Add a separate synthetic MasterBrain demo initializer/seed (ADR-208) that
  bridges fictional Email into DataCore, publishes one fictional FileOS text
  occurrence and exposes a cited cross-source project through the running
  Brain API. Keep the older Email-only demo and its narrow token unchanged;
  no real provider/root, worker authority or source effect is enabled.

- Hold shared source-item and source-status row locks during private Knowledge
  proposal review, including every linked project/entity citation behind a
  proposed member role. Synthetic concurrent revocation tests cover direct
  proposal evidence and the separate entity citation. This does not change
  generic direct publication, Email exclusion-policy serialization or live
  provider state.

- Hold shared PostgreSQL locks on each checked source item and source-status
  row through direct and proposal-reviewed fact/artifact publication. A
  concurrent current-version or active-status update now waits until the
  validation transaction commits; synthetic mid-review revocation tests
  cover both paths. This does not serialize every Email exclusion change or
  prove external provider freshness.

- Extend the fictional Cedar Harbor Email/FileOS acceptance trial through
  MasterBrain's current Markdown export, separate private fact/artifact-link
  proposal APIs, explicit human approval, reviewed dossier reads, original
  evidence drill-down and file-only assistant denial. No automatic import or
  live-source approval is implied.

- Add ADR-207's synthetic-only selected artifact-link Markdown proposal queue,
  human-only stage/preview/atomic review routes and migration 0070. Separate
  current artifact and cited-basis occurrences, full quotes and grants are
  rechecked; approved rows use the transaction-bound reviewed link publisher.
  Extend the populated logical-restore fixture with pending and approved
  fictional batches. Hosted acceptance, live import and FileOS cutover remain
  open.

- Extend synthetic-only dossier import to selected, cited project-member roles
  as private proposals (ADR-205). Keep the specific member and entity citation
  IDs immutable and recheck their current evidence at preview and human
  review; no automatic approval, role permission or live source.

- Extended the disposable Cedar Harbor cross-source trial with a reviewed
  project dossier joining an appraisal event, Email/FileOS commitment,
  source-stated loan amount and linked term-sheet artifact (ADR-204). Added
  API/client/Markdown/evidence and file-only assistant denial acceptance;
  no live source, model inference or FOS-Master cutover.

- Add a ninth isolated FOS-Master supplied-text statement baseline for Charles
  Schwab brokerage (ADR-203). Fictional old-template holdings, Cash-and-Bank-
  Sweep, symbol mismatch, signed transactions, empty redesigned/scanned text
  and 1,000-row exact-hash donor parity do not publish financial knowledge.

- Add ADR-202's synthetic-only project/event/commitment Markdown-to-private-
  proposal stage. Exact rows, full cited quotes, current source grants and an
  immutable import digest are required; human review remains a separate step.

- Add ADR-201's synthetic-only owner inspection route for imported MasterBrain
  dossier Markdown. It refuses altered, stale, excluded or ungranted citation
  previews as a whole; it does not stage proposals or approve knowledge.

- Add ADR-200's bounded, read-only candidate inventory for the owner-selected
  MasterBrain dossier Markdown format. Fictional exporter-to-parser tests prove
  the shape; claimed citations remain unverified and no Knowledge proposal is
  staged or approved.

- Add an eighth isolated FOS-Master statement text-recipe baseline for Wells
  Fargo Priority Credit Line (ADR-199). Fictional two-layout, debt-sign,
  linked-bank exclusion and 1,000-row cases compare exactly to the pinned
  donor; no PDF derivation, verified balance or FileOS switch is claimed.

- Rebuild the local non-editable MasterBrain package when starting the fictional
  cross-source trial. A stale same-version wheel could omit newer modules and
  fail before the trial opened; the launcher now refreshes just that package.

- Add a seventh isolated FOS-Master statement recipe baseline for Wells Fargo
  brokerage (ADR-198), with fictional cash/lot/reconciliation goldens,
  exact-hash donor replay and 1,000-row repeatability. This is nonpublishing
  comparison code, not a verified holding or a FileOS cutover.

## Unreleased — after v0.2.0a2

- Add a synthetic-only, fail-closed Markdown view of one bounded reviewed
  project (ADR-197). Each displayed older assertion must have a currently
  authorized exact source span; an uncitable or overfull section produces no
  export. This does not add a Librarian importer, inferred facts or live data.

- Add a synthetic-only, citation-rechecked Markdown fragment for one page of
  source-stated reviewed project facts (ADR-196). It requires separate
  content-read authority, escapes untrusted text, preserves source-scoped
  pagination and labels partial coverage. It is not a complete Librarian
  dossier, an inferred-fact export or a live-source acceptance result.

- Add synthetic-only, human-reviewed source-stated project facts and an
  independently bounded, current-authorized project-facts dossier/API view
  (ADR-195). New writes require an exact normalized-source quote and frozen
  evidence set; hidden-source successors cannot suppress visible facts.
  Inference, generic Knowledge search inclusion and a complete Markdown
  dossier remain separate gates.

- Add a fourth, independently bounded reviewed-artifact section to exact
  project dossiers and the owner workspace (ADR-194). Current source grants,
  exclusion and basis quote are rechecked before limiting. This is retained
  link history, not a current file roster or complete Markdown export.

- Add reviewed project-to-artifact evidence-occurrence links and a bounded,
  source-scoped Brain API page (ADR-193). A human selects the link and exact
  quoted basis; duplicate-content occurrences remain distinct. This is link
  history, not automatic matching, a Markdown exporter or a file effect.

- Require each proposed project alias quote to appear exactly in its own
  current, granted evidence at stage, preview and review (ADR-192). This
  closes one proposal-citation hole; historical direct publications are not
  retroactively certified and the Markdown dossier remains unimplemented.

- Pin a sixth, nonpublishing FOS-Master recipe baseline for Wells Fargo savings
  (ADR-191). Fictional daily-balance, mixed-sign and low-confidence goldens,
  exact-hash donor replay, and 1,000-row stress do not establish bank truth.

- Exercise the private FileOS statement source replay in the disposable
  cross-source browser trial (ADR-190). Startup fails if the fictional file
  cannot be replayed; the owner row remains an unreviewed proposal.

- Add a private, append-only worker-observed current FileOS text replay receipt
  for one statement proposal (ADR-189), using the exact byte transform from
  ADR-188. Neither operation proves PDF/OCR/Email derivation, a separately
  attested worker, a reviewed investment or live-source acceptance.

- Pin a fifth, nonpublishing FOS-Master statement recipe baseline for Jefferies
  (ADR-187). Fictional goldens preserve negative cash, category-versus-security
  detail, multi-lot subtotals and wrapped transaction limits; no investment
  claim or live-source read follows.

- Add private, source-stated KnowledgeCore proposal batches with exact-evidence
  quotes and one atomic, explicit human decision per row (ADR-186). This is a
  synthetic-only staging/review path, not Markdown import or inference approval.

- Hide retained Brain results and reviewed KnowledgeCore assertions grounded in
  subsequently mailbox-excluded Email, including parent/attachment/document
  evidence (ADR-185). Synthetic SQL proof only; history and privileged
  historical Email access are not purged.

- Add synthetic scoped-mailbox exclusion before provider download or retained
  byte reuse (ADR-184). An explicit excluded status hides older current Email
  and Brain search results without claiming deletion or purging history; no
  live Fastmail access or FileOS policy change is authorized.

- Add reviewed, immutable person/organization roles on exact projects
  (ADR-183), with valid-time/supersession history, transitive source-grant
  filtering, and bounded dossier/client/browser views. Roles are not access
  permissions or a computed current roster; no live source was used.

- Add evidence-linked, human-reviewed project aliases and a bounded,
  source-scoped candidate lookup for multiple names of one deal (ADR-182).
  Ambiguous names never auto-merge; existing projects retain exact-title
  fallback without rewriting history.

- Add a fourth pinned, nonpublishing FOS-Master statement recipe baseline for
  Morgan Stanley OCR text and cash-detail double-count protection (ADR-181).
  Fictional donor replay and 1,000-row stress do not enable investment claims.

- Preserve a third pinned FOS-Master statement recipe baseline for OCR-derived
  bank text, with fictional wrapped-amount, year-rollover and mismatch goldens
  plus donor replay (ADR-180). No runtime bank ingestion or facts are enabled.

- Add a local, human-owner-scoped `fastmail-source` check/enroll/disconnect
  workflow for a brand-new exact pinned account (ADR-179). Fictional CLI/SQL
  tests cover no-provider preflight, binding refusals and mid-download
  disconnect. No live account was enrolled or mail read.

- Add version-2 private scoped Fastmail read configuration, exact SQL-pin
  preflight and guarded fictional HTTPS/PostgreSQL restart, exclusion and
  revocation proof (ADR-178). Version 1 remains account-wide; no live mail was
  read or approved.

- Bind synthetic scoped Fastmail worker leases and cursors to an
  administrator-pinned, previously unused account in PostgreSQL; old
  `sync-read` refuses a pinned account before provider I/O (ADR-177).
  At that checkpoint, private scoped operation and live acceptance were pending;
  ADR-178 adds synthetic scoped operation but not live acceptance.

- Add a synthetic-only scoped Fastmail inventory worker with scope-bound
  version-4 checkpoints, repeated filtered scans, and pre-download metadata
  refusal (ADR-176). At that checkpoint, `sync-read` remained account-wide;
  no live pilot is approved.

- Pinned a second fictional FOS-Master statement recipe baseline (Fidelity)
  with its known low-confidence and missed-row behavior; it is not a runtime
  holding extractor (ADR-174, PR #194).
- Added a typed, synthetic-only Fastmail mailbox/date JMAP query and independent
  metadata scope check (ADR-175). The existing read worker remains account-wide;
  no private pilot is authorized by this primitive.

- Current-search and extractive Ask now report Email and FileOS registration
  independently, including absent, focus-excluded and assistant-unavailable
  kinds (ADR-168). Either source can be omitted without breaking read queries.
  Registration is not provider connectivity or current-index readiness; the
  per-source coverage read remains available for those details.

## v0.2.0a2 — synthetic-only alpha checkpoint (2026-10-06)

- Consolidates the read-only first-party Ask workspace, grounded Email/FileOS
  quotes, reviewed KnowledgeCore timeline/commitment/project views, and the
  provider-neutral Brain API client. The fictional insurance-certificate trial
  now rejects a citation whose selected quote omits the requested passage.
- Includes private, nonpublishing FileOS v2 comparison and expanded pinned-donor
  filename/fault parity gates. FOS-Master remains unchanged; no FileOS cutover.
- Removes a duplicate full Python-suite invocation in CI while retaining the
  standalone exhaustive deployment gate. Exact release-commit CI and restore
  run IDs belong in the prerelease record after tagging, not in this candidate.
- Still excludes live-source enrollment, hosted production identity, source
  effects, model-written answers, and owner interactive acceptance.

- Added an ADR-161 bounded, recorded-cutoff-paged reviewed-commitment due view,
  with additive lookup indexes, source-aware related-object filtering, compact
  API results and a validated read client. PR #152 exact-head and merged-main
  CI, strict-runtime and restore checks passed. It does not compute overdue
  state or enable source actions.

- Added an ADR-160 bounded, recorded-cutoff-paged reviewed-event
  occurrence timeline with source-aware project filtering, explicit retained
  history and evidence drill-down. Implementation commit `d52b167` passed
  PostgreSQL, full CI, strict-runtime and restore gates, and merged-main
  gates passed after PR #151 merged;
  this is not source freshness or a cross-kind timeline.

- Selected unsuperseded reviewed KnowledgeCore leaves in grouped Brain
  current-search and Ask (ADR-159), with explicit coverage labeling and
  source-grant-aware suppression. Retained direct and unified searches remain
  available; this is not valid-time truth or hosted acceptance.

- Added an explicit source-grant-aware `unsuperseded` visibility option to
  direct KnowledgeCore lexical search (ADR-158), with indexes for successor
  and correction lookups. Retained history remains the default, and grouped
  Brain current-search did not switch in that initial tranche; ADR-159 later
  selects it. Multiple review-chain leaves remain distinct; this is not
  temporal truth resolution.

- Bounded extractive Ask's returned exact quote plus reviewed-match text to
  8,192 UTF-8 bytes (ADR-157). Exact quotes stay intact; reviewed output is
  shortened or omitted in stable order with a separate visible flag. The
  browser now counts Unicode code points like the API for citations and text
  limits. Full JSON, token and hosted-model budgets remain open.

- Removed symlink-target type inspection from the synthetic, nonpublishing
  FileOS donor shadow (ADR-156). Directory links now block coverage instead
  of becoming exclusions; v2 profile/candidate versions require a fresh
  review. Current FileOS, source files and FOS-Master are unchanged.

- Moved the synthetic two-tenant logical restore rehearsal to a second fresh
  PostgreSQL 17 container (ADR-155). Source roles must be absent in the target;
  their restored mappings are retired before new bound logins pass forged-SQL
  isolation checks. This is not managed-host or credential-lifecycle acceptance.

- Extended the synthetic PostgreSQL 17 logical restore drill to provision
  separate tenant-bound logins before and after restore and test forged SQL
  tenant settings, foreign reads/writes and identity-role refusal (ADR-154).
  No live credential lifecycle or hosted isolation is claimed.

- Added a stable strict-runtime aggregate check and a versioned main-branch
  protection policy (ADR-153). The three always-on CI gates must pass before
  merge once GitHub protection is applied and independently verified. This is
  governance, not live-product acceptance.

- Bounded extractive Ask's selector-visible passage text to 2,048 UTF-8 bytes
  per passage and 8,192 in total (ADR-151), with an explicit truncation flag
  in the API/client and visible `/brain` warning. No model-token or total
  response budget, remote inference or source effect is implied.

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
- Integrated synthetic Fastmail read-worker resilience (ADR-110,
  migration 0052): listing pages by JMAP anchor with an explicit sort instead of
  restarting on every query-state change; oversized messages become accounted
  `source_too_large` quarantine receipts and advance the cursor instead of pausing
  the account; flag-only updates reuse retained bytes for an unchanged blob; a
  non-ASCII `Retry-After` is ignored; a lost lease is a `lease_lost` outcome.
  Oversized metadata control responses are split by ID, and valid reported
  source sizes beyond 2 GiB are held without allocation. A single unsplittable
  control row still fails closed. Live acceptance remains a separate gate; no
  mailbox write or scheduler is added.
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
