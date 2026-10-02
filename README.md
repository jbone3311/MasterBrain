# MasterBrain

MasterBrain is an evidence-first personal and organizational knowledge system. It
combines Email and FileOS source capabilities behind shared ingestion and knowledge
layers, then gives Claude, Grok, ChatGPT, and other authorized assistants compact,
progressive access with drill-down to original evidence.

**Status:** [`v0.2.0a1`](https://github.com/jbone3311/MasterBrain/tree/v0.2.0a1)
is a tagged, synthetic-only alpha checkpoint at `c0a531d` (2026-10-01).
That exact `main` commit passed full CI, strict runtime, populated restore and
local pinned-donor DataCore parity. The fictional cross-source browser trial is
merged, but interactive Mac acceptance is still pending. See
[current functions](docs/CURRENT_FUNCTIONS.md) and the
[exact-commit receipt](docs/BUILD_RECEIPT.md). The
Email capability has executable read-only ingestion, evidence storage, search,
review, recovery, and narrow structured-memory functions. Shared DataCore also
has read-only FileOS intake, extraction, archive derivatives, lexical retrieval,
and a pinned-donor parity harness. These paths are tested on fictional inputs and
disposable PostgreSQL; MasterBrain is not a hosted or live-source product, and
FOS-Master has not been replaced, renamed, or modified. See the
[alpha test guide](docs/ALPHA_TESTING.md) for the precise trial boundary.

The GitHub repository is now [`jbone3311/MasterBrain`](https://github.com/jbone3311/MasterBrain).
The internal `email_brain` package remains for compatibility and identifies the
original Email capability, not the final product. New source-neutral code enters
through `masterbrain.datacore`, `masterbrain.knowledge`, and the Brain API
boundaries.

## Product shape

```text
Email sources ─┐
               ├─> DataCore ─> KnowledgeCore ─> Brain API ─> authorized LLM clients
FileOS sources ┘       │              │                │
                      └──── immutable evidence <───────┘
```

- **Email capability:** provider change capture, MIME/attachment preservation,
  read-only sync, mailbox search, review, and future reviewed actions.
- **FileOS capability:** in-place file inventory, audited organization, extraction,
  dedupe, metadata, and file search, migrated from FOS-Master only after parity.
- **DataCore:** source-neutral intake, content hashing/dedupe, file and attachment
  extraction, OCR orchestration, normalization, metadata, provenance, chunking,
  indexing, and common database primitives.
- **KnowledgeCore:** evidence-backed entities, relationships, facts/claims, events,
  timelines, projects, commitments, corrections, and unified retrieval.
- **Brain API:** one scoped service for the first-party read-only workspace and
  future authorized external assistants; compact summaries first, explicit
  expansion second, original evidence last. Reviewed effects are a later,
  separate grant.

## Current truth

| Capability | State |
|---|---|
| Email ingestion, evidence, PostgreSQL FTS, review/recovery | Working synthetic prototype |
| Fictional Email/FileOS browser trial with citation drill-down | Hosted-test verified; Docker-free local PostgreSQL self-test passed; interactive owner acceptance pending |
| Provider-neutral external Brain API read client | Reference transport for current-search/evidence and source-scoped coverage/change status; synthetic and administrator-bound OIDC Brain assistants require explicit source enrollment. No hosted or named-assistant integration |
| First-party and external extractive question answering | Optional ADR-134 API returns server-verified source quotes with citations; no model selector is enabled by default and the browser falls back to search. No freeform synthesis, hosted model or source writes |
| Privacy-safe API failure correlation | Implemented; production log collection and alerting pending |
| Opt-in tenant-routed database access | Synthetic two-tenant API path with separate exact-lookup and bound data logins; every database-backed private `masterbrain` Email bridge and FileOS publish/index/archive command can require its worker's tenant-bound login. Legacy workers, credential lifecycle and hosted acceptance pending |
| Typed reviewed travel/bill memory | Working narrow prototype |
| File hashing and read-only duplicate discovery in DataCore | Extracted; donor parity harness added |
| FileOS scanner/reconciler inventory classifier | Behavior-identical donor extraction; 3,000-path parity, not yet wired into snapshots |
| FileOS whole-inventory shadow comparison | Synthetic donor scanner versus MasterBrain snapshots; six explicit policy gaps and mass-loss divergence, no cutover |
| File text/Markdown/HTML/CSV extraction | Working shared prototype |
| Isolated FileOS PDF/DOCX/XLSX extraction | Implemented; hosted container and restore gates green |
| Authenticated one-snapshot FileOS publication command | Implemented; hosted PostgreSQL and restore gates green |
| FileOS completion receipts and source freshness | Implemented; hosted PostgreSQL and restore gates green |
| Completed FileOS inventory and absence reconciliation evidence | Implemented; hosted PostgreSQL and restore gates green |
| Deterministic FileOS rebuild preview | Implemented; hosted PostgreSQL and restore gates green |
| Immutable FileOS index generations, activation and rollback | Implemented; hosted PostgreSQL and restore gates green |
| Private FileOS v2 generation in shared index tables | Merged; exact-head and merged-main gates green; v2 activation/current reads refused |
| Private FileOS generation/rollback operator | Implemented; hosted PostgreSQL and restore gates green |
| Cross-source current FileOS search | Implemented; hosted PostgreSQL and restore gates green |
| Current FileOS + KnowledgeCore grouped retrieval | Implemented; hosted PostgreSQL and restore gates green |
| Current Email evidence bridge into DataCore | Implemented additive library path; hosted PostgreSQL and restore gates green |
| Private Email message/attachment/document bridge commands | Implemented; hosted PostgreSQL and restore gates green |
| Private Email bridge backfill preview | Implemented; hosted PostgreSQL and restore gates green |
| Sealed Email message bridge batches | Implemented; hosted PostgreSQL and restore gates green |
| Email attachment/document bridge preview | Implemented; hosted PostgreSQL and restore gates green |
| Sealed Email attachment/document batches | Implemented; hosted PostgreSQL and restore gates green |
| FileOS archive inventory, exact member read and text publication | Implemented; donor/container/PostgreSQL/restore gates green |
| Private archive-member preview and sealed text batches | Implemented; hosted PostgreSQL and restore gates green |
| Exact archive-contained PDF/DOCX/XLSX publication and private command | Implemented; chained-container/PostgreSQL/restore gates green |
| Current archive-document search | Implemented as a separate exact-current layer; PostgreSQL/restore gates green |
| Private archive-document preview | Implemented; metadata-only PostgreSQL/restore gates green |
| Sealed archive-document batches | Implemented; fail-stop exact-retry PostgreSQL/restore gates green |
| Exact archive-contained image OCR | Implemented through retained-history persistence; chained-container/PostgreSQL/restore gates green |
| Private archive-image OCR command | Implemented; hosted CI/container and populated restore gates green |
| Current-only bridged Email Brain API search | Implemented; hosted PostgreSQL and restore gates green |
| Email attachment occurrence/text bridge | Implemented additive library path; hosted PostgreSQL and restore gates green |
| Approved Email PDF derivative bridge | Implemented additive library path; hosted PostgreSQL and restore gates green |
| Current-only layered Email-family Brain API search | Implemented; hosted PostgreSQL and restore gates green |
| Grouped current FileOS + Email-family + KnowledgeCore search | Implemented; hosted PostgreSQL and restore gates green |
| Current-source coverage/readiness status | Implemented; hosted PostgreSQL and restore gates green |
| Reviewed KnowledgeCore assertions and lexical retrieval | Working shared prototype |
| Progressive Brain API and grouped retained/current DataCore + KnowledgeCore search | Working shared prototype |
| First-party read-only question workspace | Implemented prototype at `/brain`; grouped indexed evidence, not generated answers or live acceptance |
| Certified external-AI clients and cited answer synthesis | Planned; neither is deployed or accepted |
| Email/FileOS effects through preview, approval and audited execution | Planned; source-write authority is disabled |
| Hosted identity, operations, live sources | Not accepted |
| FOS-Master cutover or retirement | Explicitly prohibited before parity |

Documentation is authoritative about status only where it distinguishes
**implemented**, **parity-proven**, **integrated**, and **accepted**. A design or
roadmap item is not an implementation claim.

## Documentation map

- [Product contract](PRODUCT.md)
- [Repository rename and branch consolidation](docs/REPOSITORY_CONSOLIDATION.md)
- [Current callable functions and limits](docs/CURRENT_FUNCTIONS.md)
- [Complete feature inventory](docs/MASTERBRAIN_FEATURE_INVENTORY.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Data model](docs/DATA_MODEL.md)
- [Brain API](docs/BRAIN_API.md)
- [Read-only external client](docs/EXTERNAL_CLIENT.md)
- [Chat, external assistants and reviewed actions](docs/USER_INTERFACES.md)
- [Security and privacy](docs/SECURITY.md)
- [Deployment](docs/DEPLOYMENT.md)
- [Roadmap](docs/ROADMAP.md)
- [FOS-Master migration and parity plan](docs/FOS_MIGRATION.md)
- [FOS-Master common tool/test inventory](docs/FOS_TOOL_INVENTORY.md)
- [FileOS inventory classifier extraction and parity](docs/FILEOS_JUNK_POLICY.md)
- [FileOS whole-inventory shadow comparison](docs/FILEOS_INVENTORY_SHADOW.md)
- [Incremental execution plan](docs/EXECUTION_PLAN.md)
- [Current build progress](docs/BUILD_PROGRESS.md)
- [Synthetic alpha test guide](docs/ALPHA_TESTING.md)
- [Fictional cross-source browser trial](docs/CROSS_SOURCE_TRIAL.md)
- [Shared DataCore/FileOS commands](docs/DATACORE_COMMANDS.md)
- [Source and provenance contract](docs/SOURCE_PROVENANCE.md)
- [DataCore persistence and lexical retrieval](docs/DATACORE_PERSISTENCE.md)
- [FileOS read-only extraction](docs/FILEOS_EXTRACTION.md)
- [FileOS PDF and Office extraction](docs/FILEOS_DOCUMENT_EXTRACTION.md)
- [FileOS archive donor audit and extraction plan](docs/FILEOS_ARCHIVE_EXTRACTION.md)
- [Archive manifest persistence plan](docs/ARCHIVE_MANIFEST_PERSISTENCE.md)
- [Hash-bound archive member read contract](docs/ARCHIVE_MEMBER_READ.md)
- [Archive member text derivative contract](docs/ARCHIVE_MEMBER_TEXT.md)
- [Private archive-member text operator contract](docs/ARCHIVE_MEMBER_OPERATOR.md)
- [Current archive-derivative search contract](docs/ARCHIVE_DERIVATIVE_SEARCH.md)
- [Private archive-member publication preview contract](docs/ARCHIVE_MEMBER_PREVIEW.md)
- [Sealed archive-member text batch contract](docs/ARCHIVE_MEMBER_BATCH.md)
- [Archive-member PDF and Office derivative contract](docs/ARCHIVE_MEMBER_DOCUMENT.md)
- [Current archive-document search contract](docs/ARCHIVE_DOCUMENT_SEARCH.md)
- [Private archive-document preview design](docs/ARCHIVE_DOCUMENT_PREVIEW.md)
- [Sealed archive-document batch design](docs/ARCHIVE_DOCUMENT_BATCH.md)
- [Archive image/OCR donor inventory and closed contract](docs/ARCHIVE_IMAGE_OCR.md)
- [One-member archive image/OCR composition](docs/ARCHIVE_MEMBER_IMAGE_OCR.md)
- [Archive-member image OCR persistence](docs/ARCHIVE_MEMBER_IMAGE_PERSISTENCE.md)
- [Private archive-image OCR operator](docs/ARCHIVE_MEMBER_IMAGE_OPERATOR.md)
- [KnowledgeCore reviewed assertions](docs/KNOWLEDGECORE.md)
- [Acceptance criteria](docs/RELEASE_ACCEPTANCE.md)
- [Implementation status](docs/IMPLEMENTATION_STATUS.md)
- [Code map](docs/CODE_MAP.md)
- [Email capability documentation](docs/README.md)

## Migration rule

FOS-Master remains the battle-tested donor and operational reference. Migration is
incremental: inventory a candidate and its tests, preserve provenance, extract it
without intentional behavior change, compare both implementations on a golden
corpus, integrate behind DataCore, then prove operational parity. Only after those
gates may FileOS switch to shared DataCore; folding or renaming FOS-Master is a later,
separately approved decision.

The source-facing commands remain intentionally read-only:

```sh
uv run python scripts/datacore_parity.py --fos-repo ../FOS-Master
uv run pytest -q tests/test_datacore_dedup.py tests/test_datacore_contracts.py \
  tests/test_fileos_snapshot.py tests/test_masterbrain_cli.py tests/test_datacore_stress.py
uv run masterbrain fileos snapshot /authorized/root --source-id files_primary
```

The parity harness compares hash, name, and combined duplicate scans, hashes and pair
comparisons against FOS-Master commit
`218d5caec2f20b9047fd3eb8e027dc671acf0c15`. No deletion or file movement code was
copied.

## Develop and verify

```sh
uv sync --locked --extra dev
uv run ruff check .
uv run mypy src
uv run pytest -q
node --test tests/web_session.test.cjs tests/web_processing.test.cjs tests/web_documents.test.cjs
node --test tests/web_reader.test.cjs tests/web_memory.test.cjs
uv run python scripts/deployment_gate.py
uv run python scripts/check_docs.py
uv run masterbrain --help
```

PostgreSQL tests require a disposable `email_brain_test*` database because the
Email capability retains its existing compatibility identifiers. CI supplies it;
local skips are not passes. Never commit real messages, files, credentials, dumps,
private embeddings, or content-bearing logs. Test fixtures must be synthetic.

Private proprietary product; dependency licenses remain separate.
