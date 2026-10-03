# KnowledgeCore

KnowledgeCore is MasterBrain's reviewed, evidence-linked interpretation layer. The
first runtime slice is additive and append-only: it publishes entities, aliases,
relationships, claims, projects, events, commitments and corrections over immutable
DataCore evidence. It does not call a model, infer facts automatically, or alter an
Email or FileOS source.

## Implemented contract

- Every assertion is tenant-scoped, explicitly reviewed and linked to at least one
  existing `brain_evidence` record from the same tenant.
- Entities, relationships, claims and projects support valid-time intervals and
  explicit supersession. Observed time and database-recorded time remain separate.
- Events preserve event time; commitments preserve state, due time, owners,
  counterparties and project links.
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
| `GET /v1/knowledge/{kind}/{id}` | `knowledge.read` | One tenant-scoped assertion and its evidence links |
| `GET /v1/knowledge/changes` | `knowledge.changes.read` | Bounded chronological change page |

Returned titles, excerpts, values and source quotes are untrusted source-derived
content. Clients must not treat them as instructions. `knowledge.review` cannot be
granted to assistant/service credentials by the bootstrap registry.

## Verification boundary

The PostgreSQL integration suite exercises all seven assertion types, concurrent
idempotent publication, replay conflicts, temporal supersession, contradictory
claims, correction history, API publication/retrieval, RLS isolation and immutable
row enforcement. The synthetic restore drill seeds two tenants with evidence-backed
entities and claims, compares all table hashes after logical restore and repeats
positive and cross-tenant retrieval checks.

This is not yet automatic knowledge extraction or unified cross-source question
answering. Unsuperseded review-chain leaves are not guaranteed true at the
current valid time or fresh against the underlying sources. Known-answer
evaluation, Email memory migration, FOS fact-pipeline parity,
semantic ranking, graph traversal, synthesis, freshness/rebuild workers and live
source acceptance remain later gates.

## Rollback

Stop issuing KnowledgeCore scopes and stop publishing assertions. Migration `0016`
is additive and existing Email/DataCore paths do not depend on its tables. Do not
drop the tables during an operational rollback: they contain immutable reviewed
history and evidence links.
