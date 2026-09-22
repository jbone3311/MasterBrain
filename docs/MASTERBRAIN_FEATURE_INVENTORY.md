# MasterBrain Feature Inventory

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
| Email | Owner search/read/review/recovery screens | Implemented prototype | Email UI + Brain API |
| Email | Explicit current-evidence/part bridges, previews and sealed batches | Implemented; hosted SQL/restore green | DataCore operator |
| Email | Reviewed virtual sender rules | Implemented narrow prototype | Email capability |
| Email | Provider drafts, moves, sends, permanent delete | Not implemented | Later reviewed action executor |
| FileOS | In-place domain scanning and unified index | Implemented in FOS-Master donor | FileOS adapter + DataCore |
| FileOS | SHA-256 inventory and read-only duplicate reports | Extracted to DataCore; parity harness present | DataCore |
| FileOS | Audited safe move/rename, collision diversion, quarantine | Donor only | Later effect broker |
| FileOS | Held-out-test and cross-domain dedupe protections | Donor only; required invariant | DataCore policy + effect broker |
| FileOS | Intake classification/routing/preflight | Donor only | FileOS adapter + DataCore |
| FileOS | PDF/DOCX/XLSX text/metadata extraction and indexing | Isolated shared tranche; hosted container/SQL gate green | DataCore |
| FileOS | ZIP/TAR recursive inventory | Isolated hash-only worker plus append-only manifest ledger; live donor/hosted SQL/restore green; no member reads/search | DataCore |
| FileOS | Authenticated idempotent snapshot publication | Explicit one-shot command; hosted SQL/restore green | DataCore operator |
| FileOS | Explicit index generation and rollback | Private one-shot command; hosted SQL/restore green | DataCore operator |
| FileOS | Entity/fact extraction and cross-domain reports | Donor only | KnowledgeCore |

## DataCore

| Capability | Required behavior | State |
|---|---|---|
| Intake envelope | Stable source/item/version IDs, observed time, actor, policy | Implemented FileOS slice |
| Hashing | Streaming content digests with algorithm/version | Implemented first tranche |
| Dedupe | Exact-content groups; signals distinct from deletion authority | Implemented read-only first tranche |
| Evidence | Immutable original bytes or provider-bound immutable reference | FileOS evidence plus additive current-Email shared bridge implemented |
| File/attachment extraction | Bounded type detection, archive/MIME accounting, isolated workers | File text/PDF/Office, Email attachment occurrence/text and approved PDF derivative bridges implemented; ZIP/TAR hash-only inventory implemented, member reads/search planned |
| OCR | Explicitly approved, isolated, page/image outputs with confidence | Planned |
| Normalization | Source-neutral document/message representation | FileOS text plus current Email message, attachment text and approved PDF derivative slices implemented |
| Metadata | Source and extracted metadata, versioned independently | FileOS/Email partial; archive member hash manifests now durable |
| Provenance | Every derivative links source, transform, version, code and time | Implemented FileOS and current Email message/attachment/PDF bridge slices |
| Chunking | Deterministic, versioned chunks retaining evidence offsets | Implemented bounded text slice |
| Indexing | Lexical first, optional vector, rebuildable and freshness-aware | Immutable FileOS generation/activation path implemented; hosted gates green |
| Database primitives | tenancy, audit, jobs, leases, idempotency, outbox, retention | Strong Email foundation; extraction planned |

## KnowledgeCore

| Capability | Required behavior | State |
|---|---|---|
| Entities | People, organizations, places, accounts, artifacts; aliases | Reviewed append/read implemented |
| Relationships | Typed, directional, temporal, evidence-backed | Reviewed append/read implemented |
| Facts/claims | Assertion, value, confidence, reviewer, valid/observed time | Reviewed append/read implemented |
| Events/timeline | Event time distinct from ingestion time | Reviewed event records implemented |
| Projects | State and evidence; future members/milestones/decisions | Reviewed base record implemented |
| Commitments | Owner, counterparty, due state and evidence | Reviewed append/read implemented |
| Corrections | Supersede without erasing history; retain contradictions | Implemented append-only links |
| Unified retrieval | Keyword, metadata, graph and optional semantic ranking | Grouped current FileOS + Email-family + reviewed knowledge, retained/current FileOS + knowledge, and layered Email lexical slices implemented; graph/semantic planned |
| Freshness | Source sync, extraction, indexing and interpretation freshness separated | Registered-source FileOS readiness and explicit Email bridge coverage implemented; interpretation freshness remains partial |

## Brain API and clients

| Capability | Required behavior | State |
|---|---|---|
| Search | Compact ranked hits across Email and files | Explicit current Email/FileOS routes, grouped current sources + knowledge, retained grouped search and bounded current coverage status implemented |
| Answer | Evidence-backed synthesis with uncertainty and coverage | Designed |
| Expand | Fetch selected entity/project/claim/timeline/chunk | Exact DataCore/KnowledgeCore expansion implemented |
| Evidence | Drill from claim/chunk to immutable original | Shared evidence metadata/content plus Email original reader implemented |
| Change feeds | Cursor-based non-consuming updates by layer | DataCore and KnowledgeCore feeds implemented |
| Client neutrality | Same typed contract for Claude, Grok, ChatGPT, other LLMs | Designed |
| Budget controls | max results/bytes/tokens, field selection, continuation | Designed |
| Effects | Typed proposal → policy → preview → approval → executor | Designed; no broad effects enabled |

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
