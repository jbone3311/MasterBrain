# Current MasterBrain functions

Updated 2026-10-14; use the [build receipt](BUILD_RECEIPT.md) for exact-commit
verification. “Available” below means executable in this repository with
synthetic/disposable inputs; it does **not** mean hosted, connected to real accounts,
approved for private data, or production accepted. The exact-commit gates are in
[BUILD_RECEIPT.md](BUILD_RECEIPT.md); current limitations are in
[IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md).

## What a tester can do now

| Function | Working path | Boundary |
|---|---|---|
| Search fictional Email and FileOS together or explicitly focus one source kind | [cross-source browser trial](CROSS_SOURCE_TRIAL.md) and `POST /v1/brain/current-search` | Real PostgreSQL and Brain API, fictional data; plain-text excerpts, grouped layers with separate ranks and partial coverage. All-source Knowledge matches use ADR-159's verified unsuperseded review-chain leaves; focused calls skip knowledge and report `not_searched`. No generated answer. |
| Ask for verified source quotes and reviewed matches | `POST /v1/brain/answers`, `BrainReadClient.answer`, and `/brain` | A local deterministic selector returns exact current-source excerpts from at most 8,192 UTF-8 bytes of passage text and flags shortened context. Returned quote plus reviewed-match text has a separate 8,192-UTF-8-byte ceiling with visible output truncation; reviewed KnowledgeCore matches and evidence links appear only under All focus. Ask removes fixed question boilerplate before lexical retrieval. Neither reviewed text nor source quotes are freeform synthesis. Explicitly disabling selection returns 503 and grouped-search fallback. |
| Open a result and verify its source | `GET /v1/brain/evidence/{id}` then separately scoped `POST /v1/brain/evidence/{id}/content` | Bounded content with opaque provenance; original Email downloads require the distinct human reader permission. |
| Check what is current or missing | `GET /v1/brain/current-coverage`, source freshness, inventory and index routes | Only completed FileOS runs, activated generations and explicitly bridged Email are represented; a partial result is not whole-source completeness. |
| Publish or index one approved synthetic FileOS run with a tenant-bound database login | `masterbrain fileos publish --tenant-bound-db --check` or `masterbrain fileos index --tenant-bound-db --check`, then the same command without `--check` | Private worker-only options, including activation-only rollback. Require a DBA-enrolled login for the authenticated worker tenant; hosted credential lifecycle remains open. No file mutation. |
| Bridge Email evidence or publish selected archive derivatives with a tenant-bound login | Add `--tenant-bound-db` to any private `masterbrain email bridge*` or `masterbrain fileos archive-*` check and execution | The authenticated worker tenant selects the only database binding. Includes previews and sealed batches; hosted credential lifecycle remains open. No Email or file source mutation. |
| Run a legacy Email worker with a tenant-bound database login | Add `--tenant-bound-db` to `email-brain sync-read`, `process-jobs` or `process-documents`, for check and execution | The authenticated worker tenant selects the only SQL login. ADR-110's read-only Fastmail worker uses anchored listing, bounded metadata batches and held oversized mail; provider-read opt-in, exact worker scopes and approved-processing gates remain separate. No hosted/live-source acceptance is implied. |
| Run a synthetic scoped Fastmail read | Use private `email-brain sync-read` version-2 config with one exact UTC mailbox/date `read_scope` matching an administrator-pinned unused account; optionally set sorted `excluded_mailbox_ids` | ADR-178 checks the SQL pin before provider I/O, uses ADR-176's filtered inventory worker and preserves ADR-177's lease/cursor fence. ADR-184 suppresses mixed private-mailbox membership before any byte lookup and hides an older current projection without purging history; ADR-185 also hides its retained Brain and reviewed Knowledge reads. Fictional HTTPS/disposable PostgreSQL only; no live-provider acceptance. Version 1 remains account-wide. |
| Check, enroll or disconnect a private pinned Fastmail source locally | `email-brain fastmail-source --config <private-file> --check`, then `--enroll` or `--disconnect` with exact account, scope and full-binding confirmations | ADR-179 requires a human-only management credential and current owner membership, creates only a new pinned row or disconnects the exact row, and makes no provider request. No real mailbox has been enrolled or accepted; disconnect does not revoke its token or delete/hide retained evidence. |
| Search reviewed knowledge | `POST /v1/knowledge/search`, `GET /v1/knowledge/{kind}/{id}`, `GET /v1/knowledge/projects/{project_id}/dossier`, event timeline and due commitments | Human-reviewed, evidence-linked assertions. Search defaults to retained history; explicit `unsuperseded` returns source-authorized review-chain leaves. ADR-162's merged dossier includes separately bounded linked events and commitments, including undated links; exact-head and merged-main gates passed. No valid-time truth, automatic resolution or model-generated synthesis. |
| Stage and decide fictional Knowledge proposals | `POST /v1/knowledge/proposal-batches`, `GET /v1/knowledge/proposal-batches/{batch_id}`, then `POST /v1/knowledge/proposal-batches/{batch_id}/review` | ADR-186 human-only 1–50 source-stated rows with current granted evidence and exact quotes. Preview requires content scope; every row needs an explicit approve/reject choice in one atomic transaction. Unreviewed rows stay outside search; no Markdown import, inference or live source. |
| Resolve a reviewed deal name to project candidates | `GET /v1/knowledge/projects/resolve`, `BrainReadClient.resolve_project_alias` | ADR-182 returns all visible matches up to a bounded limit, with ambiguity/truncation labels and alias evidence. New project aliases require human review; old projects retain exact-title fallback. No automatic merge or current-project truth. |
| Inspect one proposed statement extraction | **Open proposed row** in the fictional [browser trial](CROSS_SOURCE_TRIAL.md), or `GET /v1/knowledge/statement-proposals/{proposal_id}` with `after` and `limit` | The trial uses one synthetic current FileOS document and fetches only on click. API is human-only, requires both Knowledge read and Brain content read. At most 25 exact-decimal rows and 300 characters of source quote per row; current source/grant/digests rechecked. Unreviewed proposal only, not a holding, approval or assistant route. |
| Seal a private fictional FileOS statement text replay | `StatementFileOSReplayStore.record_current_text_replay` in a worker with one exact source root and proposal ID | Uses a no-follow bounded read, checks current source and root before and after, and writes an append-only tenant-fenced receipt. No CLI/API route, public verified flag, reviewed holding, Email/PDF/OCR proof or live-source acceptance. |
| Compare six fictional donor statement recipes | Run the isolated statement parity tests, optionally pointing `FOS_MASTER_STATEMENT_EXTRACT` at the exact pinned donor source file | Streetbeat, Fidelity, OCR bank, Morgan Stanley, Jefferies and Wells Fargo savings have fictional goldens and 1,000-row stress. Only Streetbeat has a separate typed private proposal path; no recipe output is a verified investment or live intake feature. |
| Open a reviewed project in the first-party workspace | Explicit **Open reviewed project** on a project match in `/brain` Ask or Search only | ADR-163 merged through PR #156 after exact-head full CI, strict-runtime and restore passed. Merged-main restore passed; full CI and final strict gate were blocked before execution by hosted runners (#158). It reuses the scoped ADR-162 read with fixed five-item linked lists, validates the response, and offers separately authorized evidence controls. Focus/token/session changes clear stale reads. No automatic project fetch or live project state. |
| Browse a reviewed schedule in the first-party workspace | Explicit UTC date window, then **Events** or **Commitments due** in `/brain` | ADR-164 merged through PR #159 after exact-head and merged-main full CI, strict-runtime and restore passed. It reuses ADR-160/161's scoped APIs with ten-item pages, cutoff/cursor continuation, direct evidence controls and complete response validation. Focus/date/token/session changes clear stale pages. Undated rows, live status and source freshness are not asserted. |
| Review Email evidence | Legacy `/v1/search`, selected-message reader, quarantine/retry, approved PDF jobs, narrow virtual sender rules, and travel/bill memory | Human/operator compatibility prototype, not an assistant entrance (ADR-149); no provider send, move or delete. |
| Call the same reads from a separately authorized external program | `BrainReadClient.current_search`, `.evidence`, `.evidence_content`, `.current_coverage`, `.changes`, `.answer`, `.timeline`, `.commitments_due`, `.project_dossier`, `.resolve_project_alias`; direct Brain search and FileOS source status/search routes | Provider-neutral client; synthetic and administrator-bound OIDC assistants must enroll source IDs. Direct routes are source-filtered under ADR-142; the answer route requires four read scopes and selects local quotes by default. No hosted issuer enrollment, named assistant integration or source effect. |

The trial is the quickest owner-facing entry point. Its
[known-answer guide](CROSS_SOURCE_TRIAL.md) states expected counts and how to report
a result. It has not yet completed the owner's interactive Mac acceptance.

## Shared Brain API functions

The actual route definitions live in [api.py](../src/email_brain/api.py); their
scopes, limits and response shapes are in [BRAIN_API.md](BRAIN_API.md).

- DataCore: compact lexical search, evidence metadata, separately authorized
  bounded text, and a cursor-bounded change feed.
- FileOS: completed-run freshness/inventory, read-only rebuild preview, active
  generation status, one-source search and current search across authorized
  activated sources.
- Email: explicit current-message search and separately ranked current message,
  attachment-text and approved-PDF layers. Legacy Email ingestion/search remain
  authoritative while the bridge is additive.
- Cross-source: grouped current Email/FileOS/KnowledgeCore retrieval, grouped
  retained/current DataCore plus KnowledgeCore retrieval, and partial coverage.
  Results are not a single calibrated score or an AI-written answer.
- KnowledgeCore: reviewed append-only entities, relationships, claims, events,
  projects, commitments and corrections; lexical search, exact expansion and
  changes. ADR-182 adds source-scoped candidate resolution for reviewed project
  aliases. ADR-160 adds a merged, bounded, recorded-cutoff-paged reviewed-event
  occurrence timeline. ADR-161 adds a merged due-window commitment read;
  ADR-162 adds a merged, exact-project dossier of bounded linked records.
  Enrolled assistants are
  limited to assertions with wholly granted
  direct evidence, including expansion and change cursors (ADR-143). These are
  base records, not a finished project-management system.

The private DataCore library also supports `stage_fileos_v2_inventory` for one
sealed donor transition packet. It stores a nonpublishing v2 row ledger with
hashless observations kept distinct from evidence versions. It has no CLI or
Brain API route and does not alter any current FileOS read.
`FileOSV2TransitionReview` can also produce a locator-free, exact staged plan
and record one synthetic/disposable human-owner approval receipt. This has no
Brain API/CLI route, no live-source acceptance and no v2 publication consumer.
`FileOSV2BaselineVerifier` separately rechecks that approval against a fresh
bounded root scan and records an immutable verification receipt. It is worker-
only, has no API/CLI route, and leaves current v1 reads and policy untouched.
`FileOSV2EvidencePreparer` takes a third exact scan under the source lock and
prepares only hashed observations as policy-scoped DataCore versions/evidence,
with an immutable donor-to-prepared mapping. It is private and worker-only;
hashless rows stay hashless, and no completed v2 or current search state changes.
`FileOSV2BaselineAuthorizer` separately lets a human owner bind one exact
prepared stage to a future baseline attempt. It has no API/CLI route or
live-source acceptance and does not publish v2 or change current reads.
`FileOSV2BaselineCompleter` performs a fresh exact source scan before sealing
a private historical completion receipt. Its separate compact inspection
shows counts and whether the prior v1 run is still latest, not locators or
content. This does not switch current FileOS search/freshness, create absence
or grant live-source/cutover authority.
`FileOSV2DocumentPublisher` processes hashed rows of that completed baseline
through the existing confined text and optional isolated PDF/Office path,
publishes deterministic normalized documents on prepared v2 evidence and
records a complete ready/blocked attempt after a final exact rescan. Hashless
rows remain unversioned. It has no CLI/API route; neither it nor its receipt
activates current v2 FileOS reads or infers absence.
`FileOSV2IndexBuilder` makes a ready, immutable historical generation in the
shared DataCore index without activating it. `FileOSV2SearchReviewer` privately
compares a named ready v2 generation with that source's active v1 generation
using the same bounded lexical query. It requires a human transition reviewer
with search and evidence grants and labels v2 results historical. ADR-147 exposes
that comparison at the human-only
`POST /v1/brain/sources/{source_id}/v2-search-preview` API route; there is no
CLI command, live-source attestation, current-read effect or cutover authority.

## Operator and shared processing functions

`StatementProposalStore.project_current_document` is a private worker library
function for one explicitly selected, current normalized Email/FileOS document.
It records immutable exact-decimal Streetbeat proposal rows under the worker's
tenant and emits a content-free audit event. It is not a CLI/API command,
assistant read, reviewed holding, live-source pilot or FileOS cutover.

The preferred `masterbrain` command is defined in
[cli.py](../src/masterbrain/cli.py). Its commands are **not** exposed as assistant
tools or API routes.

| Command family | Available operations | Authority boundary |
|---|---|---|
| `masterbrain datacore` | `hash`, `compare`, `duplicates` | Read-only local hash/dedupe; pinned FOS-Master parity covers the adopted generic behavior. |
| `masterbrain fileos` | `snapshot`; explicit `publish` and `index`; selected archive `archive-text`, `archive-document`, `archive-image`; text/document preview and sealed-batch commands | Snapshot reads source files; publication/indexing write only authorized MasterBrain records. Private configuration, exact scopes, idempotency and check mode are required. No source file effects or watcher. |
| `masterbrain email` | One-message/attachment/approved-document bridges; cursor-bounded message/part plans and sealed batches | Explicit migration of current eligible evidence into shared DataCore. It does not ingest from a provider, change mailbox state or automatically bridge an account. |
| `email-brain` compatibility CLI | Local synthetic seed, administrator migration, loopback service and bounded Email worker/processing commands | Retained Email capability, not the final product name or a production deployment command. Unapplied 0008/0009 populated heap rewrites refuse by default under ADR-148; a named maintenance override is not an online upgrade. |

DBA-only Python helpers `grant_tenant_runtime(conn, role, tenant_id)` and
`grant_identity_lookup(conn, role)` provision distinct data and exact-lookup
logins. The compatibility `email-brain serve --tenant-db-config` option can
route a verified identity to a configured fenced tenant login on a
disposable/staging database. See the [tenant-login contract](TENANT_LOGIN_FENCE.md).
This is not a credential manager or a worker-DSN router; the legacy shared
runtime login remains unfenced.

Under these interfaces, DataCore has source-bound hashes, immutable evidence and
provenance, deterministic text chunks, lexical index generations, isolated
PDF/DOCX/XLSX and ZIP/TAR processing, and exact selected archive-image OCR
derivatives. The donor inventory classifier is parity-tested but **not** adopted as
the live snapshot policy. An internal read-only library can preview v1-to-donor
policy differences; its database-backed variant requires the exact latest
completed v1 run before and after scanning. Neither variant has CLI/API
publication or cutover authority. An internal operator function can seal the
one-scan candidate and comparison as an immutable private review packet after
an advisory-locked latest-run recheck; it also has no CLI/API or publication
authority. ADR-156's v2 nonpublishing shadow/candidate treats every symlink as
uncertain coverage without probing its target; old v1 packets need a fresh
scan and review before new staging. The packet has a compact private library
read and a separately authorized, paged locator-detail read for review; neither
is an approval.
Current-only archive-image OCR search is a separate
bounded layer; automatic archive fan-out is not implemented. See the
[feature inventory](MASTERBRAIN_FEATURE_INVENTORY.md) and
[FOS migration ledger](FOS_MIGRATION.md) for tranche-level limits.

## Not yet callable or accepted

- Freeform cited synthesis, graph traversal, project-state reducers and broad
  cross-kind timeline views
  are designs, not routes in the current API. The default extractive
  `/v1/brain/answers` route selects local source quotes only.
- No MCP server or certified Claude, Grok or ChatGPT connection exists. Assistants
  can use the documented REST contract only after separate identity, adapter and
  client conformance work.
- Gmail/Graph read libraries and injected IMAP are offline contracts, not enrolled
  durable live sources. Fastmail has a bounded read worker but no approved live
  enrollment or hosted supervision.
- There is no production identity lifecycle, managed deployment, retention/purge
  workflow, automatic send/move/delete, or FileOS cutover.
- FOS-Master remains unchanged. Donor parity on selected functions is not full
  operational replacement.

Next work and its dependency gates are in the [roadmap](ROADMAP.md); production and
cutover require the separate [release criteria](RELEASE_ACCEPTANCE.md).
