# Current MasterBrain functions

Updated 2026-10-03; use the [build receipt](BUILD_RECEIPT.md) for exact-commit
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
| Search reviewed knowledge | `POST /v1/knowledge/search`, `GET /v1/knowledge/{kind}/{id}` | Human-reviewed, evidence-linked assertions. Search defaults to retained history; explicit `unsuperseded` returns source-authorized review-chain leaves without claiming valid-time truth or switching grouped Brain current-search. No automatic entity resolution or model-generated synthesis. |
| Review Email evidence | Legacy `/v1/search`, selected-message reader, quarantine/retry, approved PDF jobs, narrow virtual sender rules, and travel/bill memory | Human/operator compatibility prototype, not an assistant entrance (ADR-149); no provider send, move or delete. |
| Call the same reads from a separately authorized external program | `BrainReadClient.current_search`, `.evidence`, `.evidence_content`, `.current_coverage`, `.changes`, `.answer`; draft `.timeline`; direct Brain search and FileOS source status/search routes | Provider-neutral client; synthetic and administrator-bound OIDC assistants must enroll source IDs. Direct routes are source-filtered under ADR-142; the answer route requires four read scopes and selects local quotes by default. Timeline transport is local-contract tested only, with PostgreSQL/PR gates pending. No hosted issuer enrollment, named assistant integration or source effect. |

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
  changes. ADR-160 adds a candidate bounded, recorded-cutoff-paged reviewed-event
  occurrence timeline (PostgreSQL/PR gates pending). Enrolled assistants are
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

- Freeform cited synthesis, graph traversal and broad project/cross-kind timeline views
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
