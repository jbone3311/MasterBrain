# Changelog

## Unreleased — through 2026-09-21

The package remains version 0.1.0, a synthetic-data prototype. These entries do
not announce a production release. [Build receipts](docs/BUILD_RECEIPT.md) retain
exact tested commits and results.

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
