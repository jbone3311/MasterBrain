# MasterBrain Feature Inventory

ADR-244 makes the Email XLSX bridge provenance revision server-owned and
SQL-guarded; reviewer-supplied code-revision claims are rejected. This does
not turn extracted spreadsheet text into certified financial facts.

ADR-243 adds a private, account-pinned, tenant-bound worker command for one
ADR-242-reviewed synthetic Email XLSX text derivative. It does not authorize
live mail, a first-party review screen or cell-level spreadsheet citations.

ADR-242 update: human XLSX inspection and exact digest/count review now use
two owner-only API calls; a separately scoped private worker publishes the
reviewed text. Migration 0085 enforces the split. Existing ADR-241 feature
rows below describe the resulting document, not a single combined credential.

Updated 2026-10-15 through ADR-212's opt-in reviewed measurement. The current
owner-selected Librarian exchange layout is MasterBrain's ADR-197 Markdown
export; ADR-200/201 can inventory it, but this is not an automatic or lossless
round trip.
For ADR-163, merged-main restore passed, while
full CI and the final strict gate were blocked before execution by hosted
runner acquisition ([#158](https://github.com/jbone3311/MasterBrain/issues/158)).
See [current callable functions](CURRENT_FUNCTIONS.md) and
the [exact-commit receipt](BUILD_RECEIPT.md) for verified checkpoints. This
inventory is broader than a user workflow: a separately available library or
operator is not a hosted product.

Status vocabulary: **implemented** means executable in this repository;
**parity-proven** means identical observable results against a pinned donor corpus;
**integrated** means wired into an end-to-end product path; **accepted** means it has
passed operational, security, and user acceptance gates. Planned rows are not claims.

## Source capabilities

| Area | Feature | Current state | Destination owner |
|---|---|---|---|
| Email | Fastmail/JMAP incremental read, checkpoints, leases, reconciliation | Implemented on synthetic data | Email adapter + DataCore |
| Email | Gmail and Microsoft Graph read libraries | Offline-tested, not durable live connectors | Email adapter |
| Email | IMAP injected-session reader | Contract-tested, not durable live connector | Email adapter |
| Email | Raw MIME, headers, bodies, attachment receipts, calendar parts | Implemented | DataCore evidence/extraction |
| Email | XLSX attachment text through shared isolated DataCore extractor | ADR-232/239/240/241 now take one exact synthetic attachment from approval through isolated extraction to a reviewed normalized document; actual-image and hosted gates remain open | Email adapter + DataCore |
| Email | Human approval for one XLSX extraction attempt | ADR-239 synthetic-only immutable exact-occurrence approval; ADR-240 seals a private result, and ADR-241 requires a separate human digest/count-bound publication | Email adapter + DataCore |
| Email | Isolated XLSX extraction result | ADR-240 one complete, exact-approved synthetic worker result in an immutable private table; ADR-241 can publish its text to currentness-gated Brain search, not cell-level citations or live mail | Email adapter + DataCore |
| Email | Reviewed XLSX document derivative | ADR-241 synthetic-only occurrence receipt, deterministic chunks and provenance; generic and Email-family search gated on current source and grants; no first-party review UI, table index, financial attestation or live acceptance | DataCore + Brain API |
| Email | XLSX physical row-layout proof | ADR-238 binds one retained attachment occurrence's bounded rows to existing text; synthetic-only, no approved extraction, cell API or live mail | Email adapter + DataCore |
| Email | Owner search/read/review/recovery screens | Implemented prototype | Email UI + Brain API |
| Email + FileOS | Fictional PostgreSQL-backed cross-source browser trial | Merged and hosted-test verified; interactive Mac acceptance pending | Brain API + local trial |
| Email | Explicit current-evidence/part bridges, previews and sealed batches | Implemented; hosted SQL/restore green | DataCore operator |
| Email | Reviewed virtual sender rules | Implemented narrow prototype | Email capability |
| Email | Provider drafts, moves, sends, permanent delete | Not implemented | Later reviewed action executor |
| FileOS | In-place domain scanning and unified index | Implemented in FOS-Master donor | FileOS adapter + DataCore |
| FileOS | SHA-256 inventory and read-only duplicate reports | Extracted to DataCore; parity harness present | DataCore |
| FileOS | Scanner/reconciler junk and operational-path classification | Behavior-identical donor module extracted; 3,000-path parity green; snapshot integration pending | FileOS adapter + DataCore |
| FileOS | Whole-inventory scanner shadow | Synthetic donor SQLite versus MasterBrain snapshot, exact common hashes and six reason-coded policy gaps; no integration | FileOS adapter + DataCore |
| FileOS | Audited safe move/rename, collision diversion, quarantine | Donor only | Later effect broker |
| FileOS | Held-out-test and cross-domain dedupe protections | Donor only; required invariant | DataCore policy + effect broker |
| FileOS | Intake classification/routing/preflight | Donor only | FileOS adapter + DataCore |
| FileOS | PDF/DOCX/XLSX text/metadata extraction and indexing | Isolated shared tranche; hosted container/SQL gate green | DataCore |
| FileOS | Donor XLSX tables and row semantics | ADR-233 pins donor behavior; ADR-234 adds a separate nonpublishing bounded row/cell worker whose ordinary and 1,000-row values match the donor. Formula, row-cap, encrypted and `.xlsm` policy differences remain; no indexed tables or reviewed cell citations | DataCore + FileOS adapter |
| FileOS | Current XLSX row replay | ADR-235 confined digest-only re-read, ADR-236 reviewed immutable receipt and ADR-237 private exact command; no searchable table or live-root acceptance | DataCore + FileOS adapter |
| FileOS | ZIP/TAR recursive inventory | Isolated hash-only worker and append-only manifest ledger; exact member reads, text/document derivatives, current text/document search and private batch operators implemented | DataCore |
| FileOS | Archive-contained image OCR | Isolated worker, exact member composition, retained-history derivative, private one-member command and distinct current-only OCR search implemented; no automatic fan-out | DataCore + Brain API |
| FileOS | Authenticated idempotent snapshot publication | Explicit one-shot command; hosted SQL/restore green | DataCore operator |
| FileOS | Explicit index generation and rollback | Private one-shot command; hosted SQL/restore green | DataCore operator |
| FileOS | Private v2 generation in shared index tables | Merged historical builder; exact-head/merged-main gates green; v2 activation and current reads refused | DataCore |
| FileOS | Human-only historical v2 search comparison | Brain API route merged via PR #116 with exact-head/merged-main gates green; compares one ready v2 generation with active v1 under three scopes, without activation or cutover | DataCore + Brain API |
| FileOS | Entity/fact extraction and cross-domain reports | Donor remains the runtime authority; ADR-209/210 compare all five row shapes in an isolated, nonpublishing synthetic harness. Authorized runtime integration and financial truth remain unported | KnowledgeCore |

## DataCore

| Capability | Required behavior | State |
|---|---|---|
| Intake envelope | Stable source/item/version IDs, observed time, actor, policy | Implemented FileOS slice |
| Hashing | Streaming content digests with algorithm/version | Implemented first tranche |
| Dedupe | Exact-content groups; signals distinct from deletion authority | Implemented read-only first tranche |
| Evidence | Immutable original bytes or provider-bound immutable reference | FileOS evidence plus additive current-Email shared bridge implemented |
| File/attachment extraction | Bounded type detection, archive/MIME accounting, isolated workers | File text/PDF/Office, Email attachment occurrence/text and approved PDF derivative bridges; ZIP/TAR member read and text/document publication/search implemented |
| OCR | Explicitly approved, isolated, page/image outputs with confidence | Exact archive-image OCR worker, composition, persistence, private command and current-only search implemented; automatic fan-out pending |
| Normalization | Source-neutral document/message representation | FileOS text plus current Email message, attachment text and approved PDF derivative slices implemented |
| Metadata | Source and extracted metadata, versioned independently | FileOS/Email partial; archive member hash manifests now durable |
| Provenance | Every derivative links source, transform, version, code and time | Implemented FileOS and current Email message/attachment/PDF bridge slices |
| Chunking | Deterministic, versioned chunks retaining evidence offsets | Implemented bounded text slice |
| Indexing | Lexical first, optional vector, rebuildable and freshness-aware | Immutable FileOS generation/activation path implemented; hosted gates green |
| Database primitives | tenancy, audit, jobs, leases, idempotency, outbox, retention | Tenant/RLS, receipts, idempotency and selected job/lease paths implemented; shared outbox and retention lifecycle remain incomplete |

## KnowledgeCore

| Capability | Required behavior | State |
|---|---|---|
| Entities | People, organizations, places, accounts, artifacts; aliases | Reviewed append/read implemented |
| Relationships | Typed, directional, temporal, evidence-backed | Reviewed append/read implemented |
| Facts/claims | Assertion, value, confidence, reviewer, valid/observed time | Reviewed append/read implemented |
| Project fact report | Source-granted current-evidence reviewed statements with citations and uncertainty | ADR-211 provides a bounded predicate-grouped API/client page with divergent-preview and incomplete-comparison flags; ADR-212 adds optional typed measurements and ADR-214 controls names of new facts, but no numeric total, ownership, complete dossier or hosted acceptance |
| Typed project measurements | Exact decimal and unit/currency without a fabricated balance | ADR-212 permits optional quote-backed measurement on new reviewed facts; ADR-213 requires complete quote tokens, and ADR-214 binds new fact names to type/unit definitions. Old facts remain untyped or unregistered; no ownership, FX, complete registry, aggregation or hosted acceptance exists |
| Project-fact vocabulary discovery | Let API clients know which new fact names are accepted | ADR-215 lists bounded latest database revisions and deprecations under a scoped, read-only API/client; old facts may be unregistered, and no alias or vocabulary-edit workflow exists |
| Statement extraction proposals | Separate grouped, exact-decimal rows with evidence and explicit unreviewed state | ADR-172 private ledger and ADR-173 human-only paged source-quote preview on synthetic data; no owner approval, verified holding, other recipe, live source or investment dossier |
| Events/timeline | Event time distinct from ingestion time | Reviewed event records and ADR-160 bounded occurrence timeline implemented; merged-main CI/restore passed. No cross-kind timeline or source freshness claim |
| Projects | State and evidence; future members/milestones/decisions | Reviewed base record and ADR-162 compact exact-project dossier with separately bounded, source-aware linked events and commitments, including undated records, merged with exact-head and merged-main gates green. This is not a state reducer or live-currentness claim. |
| Commitments | Owner, counterparty, due state and evidence | Reviewed append/read and ADR-161 bounded due-window API/client and indexes implemented; merged-main gates passed. No automatic overdue reducer or source freshness claim |
| Corrections | Supersede without erasing history; retain contradictions | Implemented append-only links |
| Unified retrieval | Keyword, metadata, graph and optional semantic ranking | Grouped current FileOS + Email-family + unsuperseded reviewed Knowledge leaves (ADR-159/PR #148 exact-head verified), retained/current FileOS + historical Knowledge, and layered Email lexical slices implemented; graph/semantic planned |
| Freshness | Source sync, extraction, indexing and interpretation freshness separated | Registered-source FileOS readiness and explicit Email bridge coverage implemented; interpretation freshness remains partial |

## Brain API and clients

| Capability | Required behavior | State |
|---|---|---|
| Search | Compact ranked hits across Email and files | Explicit current Email/FileOS routes, grouped current sources + knowledge, retained grouped search and bounded current coverage status implemented |
| Answer | Evidence-backed synthesis with uncertainty and coverage | Bounded local exact-quote selection and separately labelled reviewed KnowledgeCore matches implemented; freeform synthesis, semantic conflict resolution and hosted acceptance remain planned |
| Expand | Fetch selected entity/project/claim/timeline/chunk | Exact DataCore/KnowledgeCore expansion implemented; ADR-162 project dossier is a merged bounded orientation read, with exact expansion still separately scoped. |
| Evidence | Drill from claim/chunk to immutable original | Shared evidence metadata/content plus Email original reader implemented |
| Change feeds | Cursor-based non-consuming updates by layer | DataCore and KnowledgeCore feeds implemented |
| Client neutrality | Same typed contract for Claude, Grok, ChatGPT, other LLMs | Model-neutral REST routes and a read-only reference client implemented; no certified named-assistant adapter or hosted cross-client conformance yet |
| First-party chat | Ask across Email, FileOS and KnowledgeCore through the same scoped Brain API, with cited answers and evidence drill-down | Read-only question workspace shows verified exact source quotes and separate reviewed matches with evidence drill-down. ADR-163's explicit reviewed-project dossier merged with exact-head gates green; original merged-main full CI and final strict gate were blocked by hosted runners (#158), with later main commits green. ADR-164's explicit event/due schedule merged after exact-head and merged-main full CI, strict-runtime and restore passed. No stateful conversation, freeform synthesis or hosted acceptance |
| External assistant access | Separately authorized API/adapter with the same grants, freshness and evidence behavior as first-party chat | Source-scoped REST/reference-client prototype only; ADR-149 denies unfenced legacy Email routes to assistants; no certified Grok/Claude/ChatGPT connection or hosted access |
| Budget controls | max results/bytes/tokens, field selection, continuation | Selected result/text/page bounds implemented; common token/field-budget contract planned |
| Effects | Typed proposal → policy → preview → approval → separate executor, with receipts and recovery | Designed; no source-write authority enabled for chat or external assistants |

## Platform, privacy, and operations

- Tenant/user isolation, least privilege, explicit source grants, audit, retention,
  export, legal hold, backup/restore, key rotation, alerting, and disaster recovery.
- Local-first/private processing is preferred for sensitive content. Remote model use
  is explicit, minimized, redacted where possible, logged, and independently revocable.
- Metrics contain identifiers/status/timing by default, never message/file content.
- Every extractor and model is replaceable; evidence and deterministic retrieval work
  without a model.

## Explicit non-features for the first release

No autonomous sending, permanent deletion, mass file movement, hidden cross-domain
dedupe, general SQL, arbitrary HTTP fetch, arbitrary filesystem access, silent model
training on user data, or claim that FOS-Master has been retired.
