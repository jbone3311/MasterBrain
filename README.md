# MasterBrain

MasterBrain is an evidence-first personal and organizational knowledge system. It
combines Email and FileOS source capabilities behind shared ingestion and knowledge
layers, then gives Claude, Grok, ChatGPT, and other authorized assistants compact,
progressive access with drill-down to original evidence.

**Status:** [v0.2.0a2](https://github.com/jbone3311/MasterBrain/releases/tag/v0.2.0a2)
is a tagged synthetic-only alpha, not a live or production release. It points
to `89bd8a1`; subsequent `main` work is unreleased. The earlier tagged
[v0.2.0a1](https://github.com/jbone3311/MasterBrain/tree/v0.2.0a1)
checkpoint remains at `c0a531d`. The package, API and manifest share the
`0.2.0a2` identity; neither tag implies live-source acceptance.

Today, fictional data can flow through read-only Email and FileOS intake,
shared DataCore extraction and indexing, reviewed KnowledgeCore records, and a
scoped Brain API. On the open development PR, one separately approved
synthetic Email XLSX can be published as an occurrence-cited DataCore text
document after a human-only digest/count review and separate worker
publication (ADR-242), now reachable through a private, account-bound worker
command (ADR-243); the server owns the bridge provenance revision (ADR-244).
ADR-246 adds a first-party human screen to inspect and review an existing
synthetic XLSX result. ADR-247 adds a separate human-only API approval of one
current synthetic attachment using a server-pinned XLSX image; ADR-248 lets
the owner select that attachment in the Email screen and explicitly approve
it. ADR-249 supplies the separately scoped private exact-approval extraction
command; neither browser approval nor review runs a worker or publishes the
document. ADR-250 now tests that entire fictional owner/API → two private
workers → cited retrieval sequence, including source-pause invalidation; its
restricted processor is simulated, so actual-image and hosted gates remain.
This is not live Fastmail, a cell-level citation or financial review. Local
populated restore passed; actual-image and hosted CI gates remain open. The
first-party `/brain` workspace and
provider-neutral client can search current evidence, show exact source quotes,
and drill down to the
original; reviewed events, due commitments and project dossiers are separate
read-only views. Reviewed project aliases can return multiple source-scoped
deal candidates; they do not merge projects or select a current truth. The
reviewed project dossier also shows bounded, evidence-linked people and
organizations with roles; these are historical assertions, not a current
roster or access permissions. A separately authorized API read can export a
bounded, citation-rechecked Markdown fragment of source-stated project facts;
ADR-197 also adds a synthetic-only, fail-closed, bounded Markdown view of an
exact reviewed project with verified citations across the linked sections.
Neither export is a complete Librarian import/export round trip, a source-
freshness certificate, or a live-source test. The
pinned FOS-Master donor remains untouched and its FileOS
shadow comparison is nonpublishing.
The development branch also has a private, synthetic-only FileOS v2 baseline
and later-observation path (ADRs 251–255): a completed-baseline-bound scan,
immutable observation packet, exact historical row-coverage closure and
source-bound evidence for matching later hashed rows. These are historical
inputs, **not** a completed later run, absence authority, current
FileOS read switch or FOS-Master replacement. The next gate is terminal
per-row document processing with replay and rollback, followed by owner-reviewed live
shadow and hosted validation. See [implementation status](docs/IMPLEMENTATION_STATUS.md)
and [FileOS migration plan](docs/FOS_MIGRATION.md).

Email and FileOS are independently optional: a tenant can register either,
both or neither. Current-search and extractive Ask still respond when one is
absent and report visible source-kind registration in scoped coverage. A
registered source does not imply a live connector, current index or query match.

This is a testable prototype, **not** a hosted service, live mailbox or folder
enrollment, AI-written conversation, source-write API, or FileOS replacement.
ADR-208 adds a separate [disposable combined-source demo](docs/LOCAL_DEVELOPMENT.md)
that starts the real loopback API, bridges fictional Email, publishes one
fictional FileOS text file and exposes a cited project. The older Email-only
demo remains unchanged; neither is a private live pilot.
The owner still needs to complete the
[fictional cross-source browser trial](docs/CROSS_SOURCE_TRIAL.md). See
[current functions](docs/CURRENT_FUNCTIONS.md), the
[roadmap](docs/ROADMAP.md), [changelog](CHANGELOG.md) and
[exact-commit build receipt](docs/BUILD_RECEIPT.md) for details and limits.
The owner chose **synthetic-only Fastmail testing for now** on 2026-10-14.
No real account or mailbox pilot is authorized; FileOS roots remain subject to
their own separate approval. Work can continue on fictional/disposable
source-scope and exclusion tests and on FOS-Master statement/financial-
intelligence parity; see the
[live-alpha integration assessment](docs/LIVE_ALPHA_AND_FOS_PRESERVATION.md).
ADR-175/176 add a synthetic scoped-query worker, ADR-177 adds a database
scope/lease fence, and ADR-178 connects one exact pinned window to private
`sync-read` version-2 configuration. ADR-179 adds a local owner-reviewed,
administrator-assisted way to create a new pinned source or disconnect it,
with no provider request. Version 1 remains account-wide and refuses pinned
accounts. A real folder/date pilot is deferred and would require a new explicit
owner authorization, disposable live acceptance and operational/retention
decisions.
The [Librarian Markdown interop review](docs/LIBRARIAN_INTEROP.md) now records
the twelve corrected gaps and the owner-selected exchange format. ADR-197
exports a bounded cited project dossier; ADR-200/201 parse and inspect that
format; ADR-202/205 can stage selected project, event, commitment and member
rows as private proposals with exact current evidence checks. ADR-186's
1–50-row queue requires explicit atomic human decisions. This is **not** a
lossless round trip: ADR-206/207 separately stage selected source-stated project
facts and artifact links for explicit human review on an open PR. Inference
without a direct quote is unsupported, and proposals are never
exposed to assistants or automatically approved.

The GitHub repository is now [`jbone3311/MasterBrain`](https://github.com/jbone3311/MasterBrain).
Its `main` branch requires full CI, strict-runtime and populated-restore checks
on PRs, including for administrators (ADR-153); this is not a production-release
or live-source approval.
The internal `email_brain` package remains for compatibility and identifies the
original Email capability, not the final product. New source-neutral code enters
through `masterbrain.datacore`, `masterbrain.knowledge`, and the Brain API
boundaries.
Assistant access to Email is through explicitly enrolled, source-scoped Brain
routes; legacy `email.*` compatibility routes are reserved for human/operator
clients ([ADR-149](docs/adr/149_assistant_legacy_email_denial.md)). This is
authorization hardening, not hosted assistant acceptance.

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
  timelines, projects, reviewed members/roles, commitments, corrections, and
  unified retrieval.
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
| First-party and external extractive Ask | The default local selector returns server-verified Email/FileOS source quotes and separately labelled, source-scoped reviewed KnowledgeCore matches. Fixed question boilerplate is removed before lexical retrieval; source passage text is byte-bounded and truncation is visible. ADR-165 rechecks selected cited evidence under the caller's grants before disclosure. No freeform synthesis, hosted model or source writes |
| Privacy-safe API failure correlation | Implemented; production log collection and alerting pending |
| Opt-in tenant-routed database access | Synthetic two-tenant API path with separate exact-lookup and bound data logins; every database-backed private `masterbrain` Email/FileOS command and the three legacy `email-brain` worker commands can require the authenticated tenant's bound login. Private library caller routing, credential lifecycle and hosted acceptance remain open |
| Typed reviewed travel/bill memory | Working narrow prototype |
| File hashing and read-only duplicate discovery in DataCore | Extracted; donor parity harness added |
| FileOS scanner/reconciler inventory classifier | Behavior-identical donor extraction; a local pinned-donor comparison also passed at the 10,000-item v1 bound, but policy acceptance and snapshot integration remain open |
| FileOS whole-inventory shadow comparison | Synthetic donor scanner versus MasterBrain snapshots; six explicit policy gaps and mass-loss divergence, no cutover |
| File text/Markdown/HTML/CSV extraction | Working shared prototype |
| Isolated FileOS PDF/DOCX/XLSX extraction | Implemented; hosted container and restore gates green |
| Authenticated one-snapshot FileOS publication command | Implemented; hosted PostgreSQL and restore gates green |
| FileOS completion receipts and source freshness | Implemented; hosted PostgreSQL and restore gates green |
| Completed FileOS inventory and absence reconciliation evidence | Implemented; hosted PostgreSQL and restore gates green |
| Deterministic FileOS rebuild preview | Implemented; hosted PostgreSQL and restore gates green |
| Immutable FileOS index generations, activation and rollback | Implemented; hosted PostgreSQL and restore gates green |
| Private FileOS v2 generation in shared index tables | Merged; exact-head and merged-main gates green; v2 activation/current reads refused |
| Human-only FileOS v2 search comparison API | Merged and hosted-verified via PR #116; one named historical generation versus active v1 with exact scopes and stale-baseline refusal; no activation or cutover |
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
| Pinned donor statement recipe comparison | Five fictional baselines: Streetbeat, low-confidence Fidelity, OCR bank, Morgan Stanley and Jefferies. Optional exact-hash FOS-Master replay; isolated from runtime and not verified holdings |
| Private statement proposal ledger | Worker-only, additive exact-decimal rows for one current normalized Email/FileOS document; exact-head and merged-main PostgreSQL/restore gates passed; storage itself creates no reviewed holding or live source |
| Owner statement proposal preview | Human-only, paged API read of current, source-rechecked unreviewed rows and bounded source quotes; the fictional browser trial now opens one proposed row on explicit click. No assistant access, approval, investment total or live source |
| Private Knowledge proposal batch and review | Human-only, source-stated 1–50 rows with exact current evidence quotes; selected project/event/commitment/member Markdown rows stage in the generic queue, while facts and artifact links use separate private queues. Typed sidecars and atomic explicit decisions are required. No inferred claim, assistant proposal read or live source |
| Private project-fact Markdown proposal batch | Separate synthetic-only fact queue and fact-specific receipt; exact selected line, full cited quote and current project/evidence bases are rechecked at stage, preview and explicit atomic human review. No automatic approval, artifact association, inferred fact or live source |
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
