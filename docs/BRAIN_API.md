# Brain API

The Brain API is MasterBrain's model-neutral, least-privilege access layer. It serves
humans and authorized clients such as Claude, Grok, ChatGPT, and future assistants.
Implemented DataCore access lives under `/v1/brain`; the first reviewed KnowledgeCore
publish/read slice lives under `/v1/knowledge`. Synthesis remains a target contract.
The first-party read-only workspace at `/brain` uses these same scoped resources;
it is not a second, privileged retrieval or action backend. It displays grouped
lexical results, verified exact source quotes and separately labelled reviewed
KnowledgeCore matches, not generated conclusions. Full chat synthesis
and external-client acceptance remain targets [documented separately](USER_INTERFACES.md).
ADR-147 exposes ADR-128's FileOS v2 comparison through one human-only,
historical-preview route. It is not current v2 visibility or cutover.

ADR-241/242 add a synthetic-only, separately human-reviewed Email XLSX
derivative behind existing Brain search and Email-family search. Its result
is bounded text citing the attachment occurrence; generic search, evidence
content and Email-family search hide it if the exact parent/source ceases to
be current. A human-only `POST /v1/brain/email-xlsx-results/{approval_id}/inspect`
returns a bounded untrusted text page and exact digest/counts; a separate
`POST /v1/brain/email-xlsx-results/{approval_id}/publication-reviews` seals
those values for one hour without publication. Both require Email review and
evidence-read scopes. Each inspection page also carries the exact source
identity (`account_id`, `attachment_id`, `parent_version_id`, `safe_filename`,
`part_path`, `part_sha256`); clients must reject a change across pages. These
are identifiers and display metadata, not original workbook bytes. The worker
publication service is private and needs
DataCore ingest/document scopes. ADR-243 makes that private service callable
through one account-pinned, tenant-bound worker command. ADR-247 adds a
human-only `POST /v1/accounts/{account_id}/attachments/{receipt_id}/xlsx-approvals`
for one current synthetic attachment. It requires an idempotency UUID and a
separately configured `serve --xlsx-document-processor-version` pin; neither
the browser nor caller can choose the image. It returns an `xapp_` approval ID
without running extraction. There is no public endpoint to invoke the worker
bridge, fetch original XLSX bytes or assert cell-level financial truth.
ADR-246's first-party screen can inspect and review an existing synthetic
approval ID after validating the complete displayed text digest. ADR-248 adds
an inspected-evidence source-selection control and an explicit approval click
using ADR-247's route. Neither screen operation runs extraction or publishes
a document.
Actual-browser, real-image and hosted gates remain open.

ADR-244 removes caller-supplied `code_revision` from the publication-review
request. The server records its own semantic bridge revision, and the database
rejects new review/receipt rows claiming another revision. Unknown request
fields return 422; a human review cannot attest the executing code.

## Progressive access

1. **Orient:** return compact results: title/summary, object type, freshness,
   confidence, source count, and opaque references.
2. **Expand:** retrieve only selected fields, related objects, timeline windows, or
   evidence-backed chunks.
3. **Verify:** resolve a citation to bounded extracted text, then—only with the
   required scope—to a verified original Email message or attachment. Original
   FileOS-byte access is not exposed by the current Brain API.

No endpoint exposes provider tokens, storage keys, unrestricted paths, arbitrary
objects, general SQL, or an unbounded corpus dump.

## Versioned resources

- `POST /v1/brain/search` — implemented compact retained DataCore lexical
  search; enrolled assistants are filtered by source in SQL before ranking and
  limit (ADR-142).
- `GET /v1/brain/evidence/{id}` — implemented metadata/citation expansion.
- `POST /v1/brain/evidence/{id}/content` — implemented separately scoped bounded text.
- `GET /v1/brain/changes` — implemented cursor-bounded DataCore change feed.
  Enrolled assistants with `brain.changes.read` see only granted sources;
  ungranted event cursors return not found (ADR-133).

ADR-185 applies the current Email mailbox-exclusion state to these retained
Brain routes before ranking/pagination. Excluded direct evidence/content IDs
and change cursors return not found; reviewed KnowledgeCore results grounded
in excluded Email evidence are also hidden. This does not delete history or
change privileged historical Email routes, and is synthetic-only proof.
- `GET /v1/brain/sources/{source_id}/freshness` — implemented latest fully accounted
  FileOS run or explicit `no_completed_run`; requires `brain.changes.read`.
- `GET /v1/brain/sources/{source_id}/inventory` — implemented latest completed
  membership/new-absence counts; preserves evidence and requires `brain.changes.read`.
- `GET /v1/brain/sources/{source_id}/rebuild-preview` — implemented paginated,
  read-only deterministic document/chunk verification for the latest complete run.
- `GET /v1/brain/sources/{source_id}/index` — implemented active immutable FileOS
  generation status; requires `brain.changes.read`.
- `POST /v1/brain/sources/{source_id}/search` — implemented bounded lexical search
  against only that source's active generation; requires `brain.search`.
- `POST /v1/brain/sources/{source_id}/v2-search-preview` — implemented
  human-only, read-only comparison of one named ready historical v2 generation
  against the source's active v1 generation. A closed request carries
  `generation_id`, `query` and `limit` (1–50 per generation). Requires
  `brain.fileos.transition.review`, `brain.search` and
  `brain.evidence.read`; assistants are denied. Results are independently
  ranked and the candidate is labelled `historical_preview`. Missing or
  wrong-source generations return 404, stale v1/root basis returns 409, and
  invalid input returns generic 422. This does not activate v2 or establish
  FileOS parity/cutover (ADR-147).
- `POST /v1/brain/sources/{source_id}/v2-later-search-preview` — implemented
  human-only comparison of one named, ready historical later-run generation
  against active v1. The closed request uses `generation_id`, `query` and
  `limit` (1–50 per layer); the response separates `active_v1` and
  `candidate_v2_later`, names the completed run and its review flags, and
  labels the candidate `historical_preview`. It requires the same three
  transition-review/search/evidence scopes as baseline v2 preview. Missing
  or ungranted sources and wrong-source generations return 404; stale or
  paused basis returns 409. Neither hits nor non-hits establish current
  FileOS state or absence, and no activation occurs (ADR-259).
- `POST /v1/brain/sources/{source_id}/v2-later-review-rows` — implemented
  human-only inspection of the exact prior-row classifications behind one
  named ready historical later generation. The closed request takes
  `generation_id`, optional exact `state`, `offset` (0–20,000) and `limit`
  (1–100). It returns deterministic relative-locator pages, total and
  `next_offset`, all classification counts and run review flags. It uses the
  same three scopes and fresh source/run/closure checks as the historical
  search comparison. Rows are untrusted; `absence_authorized` and
  `current_read_active` are always false. Each row can include its latest
  historical decision, but this does not promote it to current evidence
  (ADRs 260–261).
- `POST /v1/brain/sources/{source_id}/v2-later-row-decisions` — implemented
  human-only append-only disposition of 1–100 exact prior classification rows
  in one named ready historical generation. Each item supplies a UUID
  `idempotency_key`, exact `locator`, `state`, nullable `prior_version_id`,
  and one of `investigate`, `dispute_classification` or
  `acknowledge_historical_observation`. Duplicate keys/locators fail. Exact
  replay returns `replayed_count`; a correction needs a new key. The same
  three review/search/evidence scopes and source grant apply. The existing
  32 KiB request-body cap may limit practical batch size. It returns fixed
  no-absence/no-current/no-source-effect flags (ADR-261).
- `POST /v1/brain/sources/{source_id}/v2-later-row-decision-history` —
  implemented human-only, source-bound bounded history for one exact prior
  `locator` in a ready generation. Request fields are `generation_id`,
  `locator`, `offset` and `limit`; response includes total, ordered decision
  events and `next_offset`. It does not expose source bytes or activate v2.
- `POST /v1/brain/sources/{source_id}/v2-later-review-summary` — implemented
  human-only compact summary of one named ready historical generation. The
  closed request contains only `generation_id`; the response binds run and
  closure to a canonical `decision_snapshot_sha256`, counts required prior
  rows with missing, held or acknowledged latest decisions and lists true
  review flags requiring later explicit acknowledgement. It uses the same
  three scopes, source grant and fresh source/run/closure checks as ADR-261.
  `row_decisions_complete` is **not** run signoff; fixed flags deny absence,
  current search and file effects (ADR-262).

ADR-142 admits enrolled assistants to the previously defined five exact-source
FileOS **current-read** routes and the aggregate/retained Brain searches, not
to the human-only historical preview or decision routes above. An ungranted source is
indistinguishable from an unknown source (not found); the check occurs after
transaction-time OIDC revocation validation. It does not grant original bytes,
source effects or an alternate route through KnowledgeCore.
- `POST /v1/brain/fileos-search` — implemented current FileOS search across the newest
  activated generation of every authorized source; requires `brain.search`.
  Enrolled assistants see only granted sources.
- `POST /v1/brain/email-search` — implemented current-only search across explicitly
  bridged Email versions that remain current and visible in the legacy Email state;
  requires `brain.search`. Enrolled assistants see only granted sources.
- `POST /v1/brain/email-family-search` — implemented current-only, independently
  bounded message/attachment/approved-document layers with within-layer ranks;
  requires `brain.search`. Enrolled assistants see only granted sources.
- `POST /v1/brain/current-search` — implemented grouped active-FileOS, explicitly
  published current archive-text, archive-document and archive-image OCR,
  current-Email-family and reviewed-KnowledgeCore
  lexical read with independent limits/ranks, explicit partial coverage and
  independent-layer consistency; requires both search scopes. `archive_member_limit`
  and `archive_image_limit` are independently 1–20; archive result locators are opaque.
  Synthetic bootstrap and administrator-bound OIDC Brain assistants require
  explicit source enrollment: all current
  layers are filtered before ranking/limit, and `coverage.source_access` reports
  `enrolled_sources_only` without enumerating hidden sources. Human owners retain
  tenant-wide bootstrap reads. OIDC grant removal invalidates saved contexts at
  the next transaction; hosted issuer enrollment and derived-cache revocation
  are not accepted.
  Optional `source_focus` is `all` (default), `email`, or `fileos` (ADR-150).
  A focused call does not query excluded source or KnowledgeCore layers; those
  response groups remain present but empty, and `coverage.source_focus` plus
  `coverage.knowledge=not_searched` distinguishes exclusion from no matches.
  Focus narrows retrieval only; it never broadens scopes or source grants.
  ADR-168 adds `coverage.source_availability` for independent optional Email
  and FileOS sources. Each kind is `registered`, `not_registered` (tenant-wide
  human only), `not_available` (enrolled assistant with no visible grant), or
  `not_searched` (focus-excluded). `registered` means a visible MasterBrain
  source record exists; it does not certify current indexed evidence, provider
  connectivity or a query match. Use `/v1/brain/current-coverage` for per-source
  current bridge/generation readiness. Empty layers with `registered` mean no
  hits in the bounded query, not necessarily an empty source.
  ADR-159 makes the all-source Knowledge layer a source-grant-aware
  `unsuperseded` review-chain leaf projection before rank/limit and labels
  `coverage.knowledge=reviewed_unsuperseded_assertions`. It does not resolve
  competing leaves, check valid time or certify live-source freshness.
- `POST /v1/brain/answers` — optional ADR-134 extractive answer over the same
  current grouped search and separately authorized evidence/content reads.
  Requires `brain.search`, `knowledge.search`, `brain.evidence.read` and
  `brain.content.read`, plus assistant source enrollment. A configured selector
  may choose at most four exact quotes from at most eight bounded passages;
  the server verifies citations and rechecks current visibility.
  ADR-165 additionally reopens each selected evidence
  body and source under the caller's grants after selection, refusing changed
  bytes, digest, metadata or revoked access before returning a quote. This is
  a bounded race check, not a durable snapshot or live-source freshness proof.
  ADR-144 makes
  a local deterministic excerpt selector the default; explicit `None` disables
  it and returns 503. ADR-145 removes fixed question boilerplate before both
  current-search calls; the original question reaches the selector, and Search
  only retains literal query behavior. ADR-146 adds at most four separately
  labelled `reviewed_knowledge` matches, each with at most five direct evidence
  IDs and its full link count. Every assertion and full link set is rechecked
  against current source grants before disclosure. Reviewed interpretations
  are not exact source quotes. It has no effect grant,
  freeform model-authored answer or hosted/named-assistant acceptance.
  It accepts the same `source_focus`; quote selection and final currentness
  recheck must remain within that focus. Focused Ask returns no reviewed
  KnowledgeCore matches, while still requiring its existing scopes.
  Ask carries the same `coverage.source_availability` map as current-search.
  ADR-151 additionally caps selector-visible passage text at 2,048 UTF-8
  bytes per passage and 8,192 bytes total. `coverage.answer_context_truncated`
  is true if the upstream character cap or this byte budget shortened text,
  or if a candidate was omitted by the byte budget;
  a no-quote result then does not imply that all current source text was read.
  ADR-157 separately caps returned exact quotes plus reviewed title/excerpt
  strings at 8,192 UTF-8 bytes. Exact quotes are never shortened for this
  budget; reviewed text is shortened or omitted in stable result order, with
  `coverage.answer_output_truncated` set. The prior per-item 1,200-character
  reviewed excerpt cap also sets that output flag when it shortens text.
  This is not a model-token, total JSON or whole-response budget.
- `GET /v1/brain/current-coverage` — implemented bounded status for registered FileOS
  generation readiness and explicitly bridged current Email family coverage; requires
  `brain.changes.read`, is cursor-bounded and does not enumerate providers or paths.
  Enrolled assistants see only granted sources; ungranted source cursors return
  not found (ADR-133). The reference read client supports both status routes.
- `POST /v1/brain/unified-search` — implemented grouped DataCore evidence and
  KnowledgeCore assertion search; requires both search scopes, keeps ranks separate,
  and accepts explicit `retained` or `current_fileos` evidence visibility.
  Enrolled assistants see only granted DataCore sources and Knowledge assertions
  whose direct evidence is wholly granted (ADR-143).
- `POST /v1/knowledge/assertions` — implemented human-reviewed, evidence-required
  append with a UUID idempotency key.
- `POST /v1/knowledge/projects/{project_id}/artifacts` — ADR-193 human-only
  reviewed association of one exact project to one exact DataCore evidence
  occurrence. Requires `knowledge.review`, `brain.content.read` and a UUID
  idempotency key. A distinct basis evidence ID and exact quote justify the
  association; both evidence IDs and the project must be current and fully
  granted. It does not fetch a provider, move a file or approve an inference.
- `GET /v1/knowledge/projects/{project_id}/artifacts` — ADR-193 bounded
  source-scoped page of 1–25 reviewed link-history rows under
  `knowledge.search`. Results contain relation/status, source kind and exact
  artifact/basis evidence IDs, not text or paths. `recorded_cutoff_at` and
  `after` bind paging; a hidden cursor is not found. Only currently active,
  nonexcluded evidence from granted sources is shown. Evidence expansion
  retains its separate scope. The cutoff is not source freshness or a durable
  cross-request snapshot; retractions remain explicit history and do not
  automatically negate a previous row.
- `POST /v1/knowledge/projects/{project_id}/facts` — ADR-195 synthetic
  human-only, source-stated fact about one exact reviewed project. Requires
  `knowledge.review`, `brain.content.read`, a UUID idempotency key and an
  exact quote in one current, granted, nonexcluded DataCore evidence item;
  every direct evidence item must also be current and granted. A SQL guard
  repeats currentness and quote checks, while forced RLS and immutable
  receipts protect tenant-scoped history. No model proposal, inferred fact or
  source effect is admitted.
- `GET /v1/knowledge/projects/{project_id}/facts` — ADR-195 bounded 1–25
  source-scoped page under `knowledge.search`. It returns predicate, typed
  value preview, status, source-stated label, quote-basis and direct evidence
  IDs, not the quote itself. An aware cutoff and visible cursor bind paging;
  hidden evidence and successors are filtered before limit. A quote still
  needs export-time verification before appearing as a Markdown citation.
- `POST /v1/knowledge/evidence/{evidence_id}/source-tier-reviews` — ADR-217
  human-only document-authority classification. Requires `knowledge.review`,
  `brain.content.read` and a UUID idempotency key. The closed body pins the
  current evidence/source version and SHA-256, selected normalized document
  and text SHA-256, exact source quote and matching T1/T2/T3 authority kind.
  This is not source-byte attestation or financial-fact approval.
- `GET /v1/knowledge/evidence/{evidence_id}/source-tier-reviews` — ADR-217
  `knowledge.search` plus `brain.content.read`, current granted/unexcluded
  evidence only. Returns at most 25 historical human classifications and a
  truncation flag, without quotes or a computed winning tier. Conflicting
  reviews are not resolved; old/stale evidence is filtered before limiting.
  `BrainReadClient.source_tier_reviews()` validates the closed response and
  refuses any upgraded financial-truth meaning.
- `GET /v1/knowledge/fact-predicates` — ADR-215 read-only, bounded catalog of
  the database's latest project-fact predicate revisions, including
  deprecations. Requires `knowledge.search`; an assistant also needs ordinary
  source enrollment. It contains no tenant/source facts, but is marked
  untrusted, noncacheable and scoped only to **new** project-fact writes.
  Historical unregistered facts and lack of alias mapping are explicit.
  `BrainReadClient.project_fact_predicates()` validates the closed response.
- `GET /v1/knowledge/projects/{project_id}/facts/report` — ADR-211 groups one
  current-authorized reviewed fact page by predicate under `knowledge.search`.
  Each fact keeps its source IDs and status. Page-local divergent asserted
  previews and disputed/retracted rows are signals for review, not certified
  contradictions. Continuation, prior cursor and truncated values mark
  comparison incomplete. It explicitly performs no amount aggregation and
  is not an investment balance or complete dossier. Enrolled assistants see
  only their granted sources; `BrainReadClient.project_fact_report` validates
  the closed response before use. ADR-212 adds an optional exact-decimal
  measurement with unit and currency code to newly reviewed rows here only;
  old/untyped rows carry `measurement: null`. Even typed figures are source-
  stated, not verified holdings, and the route still never sums them.
- `GET /v1/knowledge/projects/{project_id}/facts/markdown` — ADR-196
  synthetic-only, bounded **fact fragment**, requiring both
  `knowledge.search` and `brain.content.read`. It rechecks the complete
  current source-grant/exclusion set and full quote in the quote evidence's
  current normalized body before limiting. The JSON response contains at most
  25 one-line, Markdown-escaped facts with a JSON-escaped value and short quote
  excerpt, exact evidence ID, cutoff and visible next cursor. The output is
  untrusted data, never a prompt or a complete dossier. It exports no
  events, commitments, members, related artifacts or inferred statements;
  source freshness and real-world truth are not certified. The reference
  client's `project_fact_markdown` validates closed metadata and the bound.
- `POST /v1/knowledge/search` — implemented compact lexical retrieval across entity,
  relationship, claim, event, project, commitment, member and correction records.
  ADR-158 adds an optional `visibility` of `retained` (default) or
  `unsuperseded`. The latter excludes correction records and review-chain
  predecessors before rank/limit, considering only source-authorized successors,
  corrections and replacements. Members also require grants to their linked
  project and entity assertions.
  It is not a real-world-current or valid-time guarantee. ADR-159 later
  selects this mode only in grouped Brain current-search and Ask; direct
  search still defaults to retained history.
- `GET /v1/knowledge/timeline` — ADR-160 candidate for occurrence-dated,
  reviewed events. Requires `knowledge.search` and an aware `start`/`end`
  window `[start,end)` of at most 366 days. Optional `project_id`,
  `visibility=unsuperseded` (default) or `retained`, and a 1–50 result limit
  apply before paging. Results are ordered by event start and opaque ID, with
  direct evidence IDs for expansion. An `after` event cursor must carry the
  first page's `recorded_cutoff_at`; a hidden or mismatched anchor returns not found.
  Undated events are excluded and coverage says source freshness is not
  asserted. The cutoff excludes later-recorded rows but is not a durable
  cross-request MVCC snapshot if an earlier insert commits late. Assistant
  source grants cover both the event and its linked project before limit.
  `BrainReadClient.timeline` is an opt-in read-only reference transport with
  closed request bounds and response-shape checks; it does not add an assistant
  enrollment or turn this into a hosted capability. Local disposable PostgreSQL
  and executed implementation-commit CI, strict-runtime, container and restore
  verification passed; exact runs are in the build receipt.
- `GET /v1/knowledge/commitments-due` — ADR-161 read-only due-window view of
  reviewed commitments. Requires `knowledge.search`, an aware `[start,end)`
  window no wider than 366 days, and optional exact `project_id`, `state`,
  `visibility` (`unsuperseded` default or `retained`) and 1–50 result limit.
  Orders by `(due_at,id)` and returns a compact description preview, state,
  related IDs and direct evidence IDs. A later page supplies the first page's
  `recorded_cutoff_at` and an opaque commitment-ID `after` anchor; hidden or
  mismatched anchors return not found. Source grants cover direct commitment
  evidence and each linked project, owner and counterparty before limiting.
  Undated commitments stay in search/history. The cutoff is not a durable MVCC
  snapshot, and the view does not infer overdue status, source freshness or
  real-world truth. `BrainReadClient.commitments_due` validates the transport.
  ADR-164's merged `/brain` Reviewed schedule panel makes explicit,
  date-bounded calls to these existing timeline and due routes with fixed
  10-item pages. Next-page requests carry the returned cutoff and cursor;
  they do not establish a durable snapshot, current truth or new API grant.
- `GET /v1/knowledge/projects/{project_id}/dossier` — ADR-162 compact,
  read-only context for one reviewed project assertion and its linked events,
  commitments, ADR-183 reviewed members/roles, ADR-194 reviewed artifact
  link history and ADR-195 source-stated project facts. Requires `knowledge.search`;
  each list has an independent
  1–25 limit (default 10), a truncation flag and direct evidence IDs. The
  artifact section has its own `artifact_limit` and `artifacts_truncated`;
  it returns artifact and separately quoted-basis evidence IDs but no quote,
  path or bytes. Its links are filtered under current grants, active/version
  and exclusion state before limiting; it is retained link history regardless
  of the dossier visibility switch, not a current file roster. The independent
  `fact_limit` and `facts_truncated` cover only current-authorized source-stated
  fact previews, and honor the dossier's retained/unsuperseded choice. An
  optional aware recorded-time cutoff applies to every list; `unsuperseded`
  (default) or `retained` visibility applies to events, commitments, members
  and facts, but not artifact-link history. The project is always the exact
  requested reviewed assertion, not automatically redirected to a successor.
  Results are ordered by recording
  time, not occurrence/due time; undated links are included. Assistants must
  have grants to the project, every returned assertion and every referenced
  commitment owner/counterparty, every member's linked project and entity,
  and both evidence occurrences of each artifact link.
  Roles are descriptive assertions, never permission grants. A hidden, missing
  or cutoff-invisible project
  returns not found. This is reviewed context, not a project-state reducer,
  source-freshness claim or durable cross-request snapshot.
  `BrainReadClient.project_dossier` validates the bounded response.
- `GET /v1/knowledge/projects/{project_id}/dossier/markdown` — ADR-197
  synthetic-only, fail-closed cited export for one exact reviewed project.
  It requires `knowledge.search` and `brain.content.read`. Each of events,
  commitments, members, related artifact occurrences and source-stated facts
  has an independent 1–25 bound. The read checks current source grants,
  exclusion and exact stored quote spans before emitting any Markdown;
  an overfull or uncitable section returns a generic conflict with no export.
  The response gives counts, an aware recorded cutoff, explicit coverage and
  a 64-KiB cap. Older reviewed assertion derivation is unspecified. This is
  not a source-freshness or truth certificate, a durable database snapshot,
  an inferred-fact exporter, or a complete Librarian import/export round trip.
  `BrainReadClient.project_dossier_markdown` validates the response envelope;
  returned Markdown remains untrusted data.
  ADR-163's first-party `/brain` control explicitly requests this same route
  from a reviewed project match with fixed five-item limits for each linked
  list, including artifacts and facts under ADR-194/195. It does not fetch on page load,
  add a privileged API, or interpret
  the reviewed project state as live truth. PR #156 merged after exact-head
  gates passed. Merged-main restore passed; full CI and the final strict gate
  were blocked before execution by hosted-runner acquisition
  ([#158](https://github.com/jbone3311/MasterBrain/issues/158)).
- `GET /v1/knowledge/projects/resolve?name=...&limit=25` — ADR-182
  candidate-only lookup of a reviewed project's canonical title or typed
  aliases. Names are Unicode-normalized, casefolded and punctuation-separated;
  a duplicate name across projects returns ambiguous candidates, never an
  automatic merge. Source grants cover the project and each returned alias
  before limit. Existing pre-alias projects retain exact case-insensitive title
  fallback. Results are retained reviewed history, not a current-project
  reducer. `BrainReadClient.resolve_project_alias` validates the bounded read.
- `GET /v1/knowledge/{kind}/{id}` — implemented assertion/evidence expansion;
  enrolled assistants cannot resolve mixed or hidden-source assertions.
- `GET /v1/knowledge/statement-proposals/{proposal_id}` — ADR-173 owner-only,
  read-only inspection of one unreviewed ADR-172 proposal. Requires both
  `knowledge.read` and `brain.content.read`; assistants/workers are denied.
  `after` is an ordinal cursor (-1 initially), `limit` is 1–25, and quotes are
  capped at 300 characters with visible truncation. The route rechecks current
  source grants/version and stored hashes; hidden IDs return 404 and stale or
  inconsistent evidence returns 409. Every row is labeled proposed extraction,
  not a reviewed holding or investment total. No source effect or approval is
  available here.
- `POST /v1/knowledge/proposal-batches` — ADR-186 human-only staging of 1–50
  source-stated assertions under `knowledge.review` and a UUID idempotency key.
  No `reviewed` marker is accepted in a proposal. Every evidence ID must be
  current, granted and nonexcluded; the exact quote must occur in linked
  normalized text. Staging creates no reviewed assertion.
- `POST /v1/knowledge/dossier-markdown/inspect` — ADR-201 human-only,
  read-only inspection of the owner-selected ADR-197 Markdown format. Requires
  `knowledge.review` and `brain.content.read`; the closed body contains only
  bounded Markdown. Every claimed citation/escaped quote preview must match
  its own current, granted, nonexcluded normalized evidence in one transaction.
  Any mismatch returns a generic conflict with no partial inventory. The
  response is untrusted candidate context, explicitly not a full-quote,
  source-freshness or truth certificate and never a staged proposal.
- `POST /v1/knowledge/dossier-markdown/proposal-batches` — ADR-202/205
  synthetic-only, human-only staging of 1–50 explicitly selected project,
  event, commitment or member rows from the exact ADR-197 Markdown format. Requires
  `knowledge.review`, `brain.content.read` and a UUID idempotency key. Each
  selected typed payload must supply the full source quote, observation time,
  confidence and evidence IDs omitted by Markdown; visible fields must match
  the selected line exactly. The write transaction rechecks the full quote on
  the *specifically cited* current, granted, nonexcluded evidence and binds an
  immutable digest of the Markdown/selection context to the private ADR-186
  batch. New imports also retain the exact cited evidence IDs for stage,
  preview and review rechecks. A member needs an existing local project and
  person/organization entity; the displayed entity name, full quote and its
  separate citation must match that local entity. Same actor/key with changed
  input conflicts. This route stages no
  reviewed assertion; the separate human batch-review route decides every
  row. Claimed IDs are source-row selectors, not reserved publication IDs;
  approved rows receive new MasterBrain IDs. Event and commitment selections
  require an already existing local project ID. Facts are staged through
  the separate ADR-206 route below; artifact links use ADR-207's separate
  route. A
  member role never grants access.
- `POST /v1/knowledge/dossier-markdown/fact-proposal-batches` — ADR-206
  synthetic-only, human-only staging of 1–50 selected `fact` rows from the
  same bounded dossier format. Requires `knowledge.review`,
  `brain.content.read`, a UUID idempotency key and a closed typed sidecar
  for each selected fact. Sidecars supply the full quote, complete direct
  evidence, value type, confidence and observed time that Markdown omits;
  `reviewed`, inferred derivation, supersession and unrendered valid-time
  fields are rejected. The exact line, cited quote evidence, current local
  project and all evidence grants are checked before an immutable private
  batch is staged. Claimed `pfact_...` IDs are selectors, not publication IDs.
  An unknown predicate may be staged privately but cannot be published until
  a reviewed registry version defines its name/type/unit; staging is not
  vocabulary approval.
- `GET /v1/knowledge/fact-proposal-batches/{batch_id}` — human-only private
  preview with both scopes, current project/evidence rechecks, untrusted
  proposed payloads, ordered decision status and `registry_status` (`active`,
  `unknown`, `shape_mismatch`, `deprecated` or `version_mismatch`), checked
  against the latest database revision. Ordinary search, dossier
  and assistant reads never expose unreviewed facts.
- `POST /v1/knowledge/fact-proposal-batches/{batch_id}/review` — human-only
  explicit approve/reject decision for **every** fact in one transaction,
  binding the exact batch digest and a UUID key. Approval uses the reviewed
  project-fact publication path and issues a new ID; rejection stores only
  a reason. An unknown or mismatched predicate cannot be approved; one invalid
  row rolls back all decisions and publications. No
  live source, artifact association or inferred fact is authorized.
- `POST /v1/knowledge/dossier-markdown/artifact-proposal-batches` — ADR-207
  synthetic-only, human-only staging of 1–50 selected `artifact link` lines
  from the existing dossier. A closed typed sidecar supplies the full basis
  quote and observation time omitted by Markdown. Exact line, current local
  project, artifact occurrence, separately cited basis occurrence, source
  kind, grants and full quote are checked before private immutable storage.
  The claimed ID only selects a row; it is not the publication ID.
- `GET /v1/knowledge/artifact-proposal-batches/{batch_id}` — human-only
  private preview with `knowledge.review` and `brain.content.read`; rechecks
  both evidence occurrences and the project under current grants.
- `POST /v1/knowledge/artifact-proposal-batches/{batch_id}/review` — explicit
  approve/reject decision for every row in one transaction, binding the
  batch digest and a UUID key. Approval uses ADR-193's reviewed publication
  path and issues a new link ID; rejection publishes no link. A bad row
  aborts the entire batch. No assistant approval, live source or FileOS
  source effect is authorized.
- `GET /v1/knowledge/proposal-batches/{batch_id}` — human-only private preview
  requiring `knowledge.review` and `brain.content.read`. Rechecks current
  evidence/grants and returns ordered untrusted proposals plus decision status;
  never available to assistant search or ordinary Knowledge reads.
- `POST /v1/knowledge/proposal-batches/{batch_id}/review` — human-only atomic
  decision over every row, binding the exact batch digest and a UUID key.
  Approval uses the existing reviewed publication path; rejection records a
  reason. One invalid row rolls back the entire decision. That review route
  does not parse Markdown, approve inferred claims or operate a live source.
- `GET /v1/knowledge/changes` — implemented cursor-bounded knowledge change
  feed; enrolled assistants see only directly source-authorized assertions and
  cannot use an ungranted event as a cursor.
- `POST /v1/search` — retained Email capability search during compatibility
  migration. ADR-149 excludes assistants from this and other legacy `email.*`
  compatibility routes; assistants use enrolled, source-filtered Brain reads.
- Future freeform cited synthesis — not implemented; the existing
  `/v1/brain/answers` route is limited to verified extractive quotes.
- Future graph traversal — related objects and cited attributes beyond exact lookup.
- Future project reducer — reconcile project versions, members, milestones,
  contradictory branches and valid-time state beyond ADR-162's exact dossier.
- `GET /v1/claims/{id}` — claim versions, support, contradictions, and supersession.
- Future cross-kind timeline — commitments, project milestones and other
  temporal objects beyond the reviewed-event route above.
- Future unified evidence/change routes will compose Email, DataCore and KnowledgeCore
  only after their evidence identities share a proven migration path.
- `POST /v1/proposals` — typed proposed change; never direct provider/filesystem access.

Resource names may evolve through an ADR before implementation. Current IDs are
opaque and tenant-scoped; individual implemented routes enforce their documented
bounds, scopes and pagination. Uniform `fields`, token budgets, response envelopes,
and synthesis are target contracts, not guarantees of every current route.

## Common response envelope

The JSON below is a **target design**, not a promise that every implemented route
already emits this uniform envelope. The individual route schemas and tests govern
current responses; common field selection and token budgets remain planned.

```json
{
  "data": [],
  "citations": [
    {
      "evidence_id": "ev_opaque",
      "source_kind": "email",
      "source_item_id": "item_opaque",
      "locator": {"kind": "text_span", "start": 120, "end": 238},
      "content_sha256": "..."
    }
  ],
  "freshness": {
    "source_observed_at": "...",
    "data_indexed_at": "...",
    "knowledge_updated_at": "..."
  },
  "page": {"next_cursor": null, "truncated": false},
  "policy": {"scope": "brain.read", "redactions": []},
  "request_id": "req_opaque"
}
```

## Retrieval contract

- Deterministic filters and lexical search work without an LLM.
- Cross-layer results remain grouped because ranks from separate indexes are not
  calibrated as one global score.
- Current FileOS, published archive-member and bridged-Email searches are explicit.
  Compatibility DataCore search retains historical evidence unless the client selects
  a current-only route.
- Grouped search defaults to retained-history compatibility. Clients may explicitly
  select current FileOS generations without changing the KnowledgeCore layer.
- Semantic/vector ranking is optional and cannot suppress exact evidence lookup.
- Answers distinguish source statements from inferred conclusions.
- Conflicting claims are returned as conflicts, not silently collapsed.
- A citation identifies immutable evidence plus a stable locator and content digest.
- Ranking/extraction/model versions are included in internal provenance and available
  to authorized diagnostics.

## Authorization and effects

Scopes separate metadata/search, extracted content, original evidence, source
administration, proposals, approvals, and execution. Human and service identities are
mapped administratively; source content cannot request scopes. Effects require a typed
proposal, current authorization, policy evaluation, idempotency key, preview, approval
where required, and an audit receipt. Initial release is read-only.

An opt-in local service configuration resolves a verified identity through a
table-blind lookup login and routes its tenant to a distinct DBA-bound data login.
The route is server-owned; API fields cannot select a DSN. The older single-DSN
prototype remains available but is not hosted multi-tenant containment. See
[ADR-109](adr/109_tenant_database_routing.md) and
[the tenant-login contract](TENANT_LOGIN_FENCE.md).

## Client guidance

There is no deployed MCP server or certified Claude, Grok or ChatGPT adapter yet.
The [provider-neutral read client](EXTERNAL_CLIENT.md) is an executable
read-only reference over the same REST routes used by `/brain`; it passes a
fictional cross-source conformance test. Use it only with a separately
authorized credential. Passing local API/client tests does not establish
assistant integration or hosted acceptance.
ADR-130's bootstrap assistant and ADR-132's OIDC Brain assistant can call the
source-scoped current-search, evidence/content, ADR-133 coverage/change and
ADR-142 directly source-filtered search/FileOS status routes, with an explicit
source allowlist. ADR-134 also permits bounded
extractive answers, subject to all four read scopes; ADR-144 selects local
exact quotes by default and permits explicit disabling. ADR-143 adds directly source-filtered Knowledge
and unified Brain reads for enrolled assistants. Hosted issuer enrollment,
named-assistant conformance and derived-cache revocation
remain open in [issue #88](https://github.com/jbone3311/MasterBrain/issues/88).
ADR-149 deliberately keeps unfenced legacy Email compatibility routes outside
assistant access instead of treating their operation scopes as source grants.

Clients should search first, expand the smallest useful set, cite evidence IDs in
their answer, and request originals only when needed. They must treat returned content
  as untrusted. A client losing access to one source must not infer its content from
  caches, embeddings, summaries, or graph projections.
