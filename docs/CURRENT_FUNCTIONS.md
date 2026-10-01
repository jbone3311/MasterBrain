# Current MasterBrain functions

Updated 2026-10-01; use the [build receipt](BUILD_RECEIPT.md) for exact-commit
verification. “Available” below means executable in this repository with
synthetic/disposable inputs; it does **not** mean hosted, connected to real accounts,
approved for private data, or production accepted. The exact-commit gates are in
[BUILD_RECEIPT.md](BUILD_RECEIPT.md); current limitations are in
[IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md).

## What a tester can do now

| Function | Working path | Boundary |
|---|---|---|
| Search fictional Email and FileOS together | [cross-source browser trial](CROSS_SOURCE_TRIAL.md) and `POST /v1/brain/current-search` | Real PostgreSQL and Brain API, fictional data; grouped layers have separate ranks and partial coverage. No generated answer. |
| Open a result and verify its source | `GET /v1/brain/evidence/{id}` then separately scoped `POST /v1/brain/evidence/{id}/content` | Bounded content with opaque provenance; original Email downloads require the distinct human reader permission. |
| Check what is current or missing | `GET /v1/brain/current-coverage`, source freshness, inventory and index routes | Only completed FileOS runs, activated generations and explicitly bridged Email are represented; a partial result is not whole-source completeness. |
| Search reviewed knowledge | `POST /v1/knowledge/search`, `GET /v1/knowledge/{kind}/{id}` | Human-reviewed, evidence-linked assertions; no automatic entity resolution or model-generated synthesis. |
| Review Email evidence | Legacy `/v1/search`, selected-message reader, quarantine/retry, approved PDF jobs, narrow virtual sender rules, and travel/bill memory | Local/synthetic prototype; no provider send, move or delete. |

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
  changes. These are base records, not a finished project-management system.

The private DataCore library also supports `stage_fileos_v2_inventory` for one
sealed donor transition packet. It stores a nonpublishing v2 row ledger with
hashless observations kept distinct from evidence versions. It has no CLI or
Brain API route and does not alter any current FileOS read.
`FileOSV2TransitionReview` can also produce a locator-free, exact staged plan
and record one synthetic/disposable human-owner approval receipt. This has no
Brain API/CLI route, no live-source acceptance and no v2 publication consumer.

## Operator and shared processing functions

The preferred `masterbrain` command is defined in
[cli.py](../src/masterbrain/cli.py). Its commands are **not** exposed as assistant
tools or API routes.

| Command family | Available operations | Authority boundary |
|---|---|---|
| `masterbrain datacore` | `hash`, `compare`, `duplicates` | Read-only local hash/dedupe; pinned FOS-Master parity covers the adopted generic behavior. |
| `masterbrain fileos` | `snapshot`; explicit `publish` and `index`; selected archive `archive-text`, `archive-document`, `archive-image`; text/document preview and sealed-batch commands | Snapshot reads source files; publication/indexing write only authorized MasterBrain records. Private configuration, exact scopes, idempotency and check mode are required. No source file effects or watcher. |
| `masterbrain email` | One-message/attachment/approved-document bridges; cursor-bounded message/part plans and sealed batches | Explicit migration of current eligible evidence into shared DataCore. It does not ingest from a provider, change mailbox state or automatically bridge an account. |
| `email-brain` compatibility CLI | Local synthetic seed, migration, loopback service and bounded Email worker/processing commands | Retained Email capability, not the final product name or a production deployment command. |

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
authority. That packet has a compact private library read and a separately
authorized, paged locator-detail read for review; neither is an approval.
Current-only archive-image OCR search is a separate
bounded layer; automatic archive fan-out is not implemented. See the
[feature inventory](MASTERBRAIN_FEATURE_INVENTORY.md) and
[FOS migration ledger](FOS_MIGRATION.md) for tranche-level limits.

## Not yet callable or accepted

- `POST /v1/answers`, automatic cited synthesis, graph traversal and broad
  project/timeline views are designs, not routes in the current API.
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
