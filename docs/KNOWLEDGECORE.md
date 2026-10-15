# KnowledgeCore

KnowledgeCore is MasterBrain's reviewed, evidence-linked interpretation layer. The
first runtime slice is additive and append-only: it publishes entities, aliases,
relationships, claims, projects, events, commitments, project members and corrections over immutable
DataCore evidence. It does not call a model, infer facts automatically, or alter an
Email or FileOS source.

ADR-171's exact-decimal statement candidates begin as a separate in-memory
projection. ADR-172 stores selected current-document proposals privately, and
ADR-173 lets a human owner inspect bounded rows and source quotes through a
source-rechecked API. These rows remain unreviewed extraction, not KnowledgeCore
assertions or live investment analysis. Independent source-byte-to-text proof,
source tier, other vendor recipes, explicit human approval and publication as
reviewed facts remain open gates; assistants cannot use the proposal preview.

## Implemented contract

- Every assertion is tenant-scoped, explicitly reviewed and linked to at least one
  existing `brain_evidence` record from the same tenant.
- Entities, relationships, claims and projects support valid-time intervals and
  explicit supersession. Observed time and database-recorded time remain separate.
- ADR-182 adds reviewed project title/address/legal-entity/folder aliases, each
  with a direct supporting evidence ID and quote. The alias set is bound to
  the immutable project row. Exact lookup returns all visible candidates and
  never auto-merges a shared name; retained review-chain versions can coexist.
- Events preserve event time; commitments preserve state, due time, owners,
  counterparties and project links.
- ADR-183 adds human-reviewed, evidence-backed person/organization roles on an
  exact project assertion. Valid-time intervals, disputed/retracted status,
  supersession and correction preserve history. Role slugs are bounded but the
  later registry is not yet enforced; a role never confers access. The project
  dossier returns a separately limited member list. Source-scoped reads require
  the member and both linked assertions to be visible before limit or cursor.
- ADR-193 adds a separate reviewed association from one exact project to one
  exact Email/FileOS evidence occurrence, with a distinct exact-quoted basis.
  It is not a general Knowledge assertion kind or automatic project match.
  A bounded link-history API filters project, artifact and basis source grants
  before paging. Same-hash attachment occurrences remain separate IDs.
- ADR-194 includes that same currently authorized retained link history in
  the exact-project dossier as a fourth independently bounded list. It does
  not infer a current file roster, export quotes or original FileOS bytes.
- ADR-195's synthetic candidate adds a separate, human-reviewed project-fact
  assertion with one exact quoted evidence occurrence and a frozen 1–20-item
  evidence set. It never recasts a project as an entity or accepts an inferred
  fact. Current, active, nonexcluded evidence and the project grant are checked
  before fact paging and dossier limits; only a visible same-kind successor
  suppresses a predecessor. The compact result contains a value preview and
  evidence IDs, not a source quote or export-ready citation. This branch is
  still pending exact-head/merged-main acceptance.
- Corrections link an old assertion to a replacement without updating or deleting
  either assertion. Conflicting claims can coexist and are returned independently.
- All knowledge and evidence-link tables use forced PostgreSQL row-level security,
  runtime grants and immutable update/delete triggers.
- Publication uses actor-scoped UUID idempotency keys and immutable receipts.
- Lexical retrieval is bounded to 50 results and can filter by object kind. Reads
  include evidence IDs; object expansion includes the full evidence link.
- Direct lexical search defaults to retained history. ADR-158 adds an explicit
  `unsuperseded` read mode that omits corrected targets and same-kind
  supersession predecessors before ranking and limit. Multiple review-chain
  leaves remain visible. This is not valid-time truth or contradiction
  resolution. ADR-159 uses that explicit mode in grouped Brain current-search
  and Ask; direct and unified retained-history reads remain available.
- A cursor-bounded append-only change feed allows consumers to discover new
  assertions without scanning the knowledge tables.
- ADR-160 adds a bounded, recorded-cutoff-paged occurrence timeline for reviewed
  events with non-null `starts_at`, an explicit date window, optional project
  filter and direct evidence IDs. It defaults to unsuperseded review-chain
  leaves; retained history is explicit. A linked project must also satisfy
  assistant source grants. Undated events remain in exact/search/history
  reads. The implementation and merged-main CI, strict-runtime and restore gates
  passed. It is not an event extraction pipeline, source freshness or valid-time
  truth guarantee.
- ADR-161 adds a bounded, recorded-cutoff-paged due-window read for reviewed
  commitments with non-null `due_at`. It defaults to unsuperseded leaves and
  allows exact project/state filters. Source-scoped callers need visibility of
  direct evidence and every referenced project/owner/counterparty. Undated
  commitments remain in search/history. Exact-head and merged-main gates passed
  on synthetic inputs; this is not an overdue-state reducer or freshness guarantee.
- Enrolled assistants may search, expand and page changes only for assertions
  whose directly linked evidence is nonempty and entirely in their granted
  sources (ADR-143). Mixed-source assertions are hidden in full; an ungranted
  change cursor returns not found. OIDC grant removal is rechecked at each
  transaction. This is not a semantic noninterference guarantee for the text
  of a human-reviewed assertion or its opaque references to other assertions.

## API

| Route | Scope | Behavior |
|---|---|---|
| `POST /v1/knowledge/assertions` | `knowledge.review` | Human-only reviewed append; UUID `Idempotency-Key` required |
| `POST /v1/knowledge/search` | `knowledge.search` | Compact lexical results with evidence IDs; explicit `retained` (default) or `unsuperseded` visibility |
| `GET /v1/knowledge/timeline` | `knowledge.search` | Bounded occurrence-window event page, recorded-time cutoff/cursor, direct evidence IDs; ADR-160 candidate |
| `GET /v1/knowledge/commitments-due` | `knowledge.search` | Bounded due-window commitment page, recorded-time cutoff/cursor, direct evidence IDs; ADR-161 |
| `GET /v1/knowledge/{kind}/{id}` | `knowledge.read` | One tenant-scoped assertion and its evidence links |
| `GET /v1/knowledge/changes` | `knowledge.changes.read` | Bounded chronological change page, with member linked-source filtering |
| `GET /v1/knowledge/projects/{project_id}/dossier` | `knowledge.search` | Independently bounded reviewed events, commitments, members and artifact-link history; no current-roster claim |
| `GET /v1/knowledge/projects/resolve` | `knowledge.search` | Bounded, source-scoped reviewed candidates for an exact normalized alias; ambiguous names are not merged |
| `POST /v1/knowledge/projects/{project_id}/artifacts` | `knowledge.review` + `brain.content.read` | Human-only exact evidence-occurrence link and quoted basis; idempotent append |
| `GET /v1/knowledge/projects/{project_id}/artifacts` | `knowledge.search` | Current-authorized, cutoff-paged reviewed link history; evidence IDs/source kind only |
| `POST /v1/knowledge/projects/{project_id}/facts` | `knowledge.review` + `brain.content.read` | Human-only, exact-quoted source-stated project fact; UUID idempotency key |
| `GET /v1/knowledge/projects/{project_id}/facts` | `knowledge.search` | Current-authorized, cutoff-paged reviewed project facts with evidence IDs and previews only |

Returned titles, excerpts, values and source quotes are untrusted source-derived
content. Clients must not treat them as instructions. `knowledge.review` cannot be
granted to assistant/service credentials by the bootstrap registry.

## Verification boundary

The PostgreSQL integration suite exercises the reviewed assertion types, concurrent
idempotent publication, replay conflicts, temporal supersession, contradictory
claims, correction history, API publication/retrieval, RLS isolation and immutable
row enforcement. The synthetic restore drill seeds two tenants with evidence-backed
entities and claims, compares all table hashes after logical restore and repeats
positive and cross-tenant retrieval checks.

This is not yet automatic knowledge extraction or unified cross-source question
answering. The event timeline is not a cross-kind timeline. Unsuperseded
review-chain leaves are not guaranteed true at the
current valid time or fresh against the underlying sources. Known-answer
evaluation, Email memory migration, FOS fact-pipeline parity,
semantic ranking, graph traversal, synthesis, freshness/rebuild workers and live
source acceptance remain later gates.

For file-based Librarian exchange, [ADR-169](adr/169_code_first_librarian_interop.md)
requires deterministic parsing and proposal-only import before any reviewed
publication. The [twelve-gap review](LIBRARIAN_INTEROP.md) separates already
implemented FileOS CSV/XLSX and Email attachment occurrence evidence from the
missing table locators, inference basis, proposal queue and Markdown export.
ADR-182/183/193 implement aliases, reviewed roles and project-artifact links;
the other proposed behaviors remain outside runtime. Human review and source-
grant checks remain mandatory.

## Rollback

Stop issuing KnowledgeCore scopes and stop publishing assertions. Migration `0016`
is additive and existing Email/DataCore paths do not depend on its tables. Do not
drop the tables during an operational rollback: they contain immutable reviewed
history and evidence links.
