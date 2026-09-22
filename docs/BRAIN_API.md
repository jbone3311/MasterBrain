# Brain API

The Brain API is MasterBrain's model-neutral, least-privilege access layer. It serves
humans and authorized clients such as Claude, Grok, ChatGPT, and future assistants.
Implemented DataCore access lives under `/v1/brain`; the first reviewed KnowledgeCore
publish/read slice lives under `/v1/knowledge`. Synthesis remains a target contract.

## Progressive access

1. **Orient:** return compact results: title/summary, object type, freshness,
   confidence, source count, and opaque references.
2. **Expand:** retrieve only selected fields, related objects, timeline windows, or
   evidence-backed chunks.
3. **Verify:** resolve a citation to bounded extracted text, then—only with the
   required scope—to a verified original message, attachment, or file.

No endpoint exposes provider tokens, storage keys, unrestricted paths, arbitrary
objects, general SQL, or an unbounded corpus dump.

## Versioned resources

- `POST /v1/brain/search` — implemented compact DataCore lexical search.
- `GET /v1/brain/evidence/{id}` — implemented metadata/citation expansion.
- `POST /v1/brain/evidence/{id}/content` — implemented separately scoped bounded text.
- `GET /v1/brain/changes` — implemented cursor-bounded DataCore change feed.
- `POST /v1/brain/unified-search` — implemented grouped DataCore evidence and
  KnowledgeCore assertion search; requires both search scopes and keeps ranks separate.
- `POST /v1/knowledge/assertions` — implemented human-reviewed, evidence-required
  append with a UUID idempotency key.
- `POST /v1/knowledge/search` — implemented compact lexical retrieval across entity,
  relationship, claim, event, project, commitment and correction records.
- `GET /v1/knowledge/{kind}/{id}` — implemented assertion/evidence expansion.
- `GET /v1/knowledge/changes` — implemented cursor-bounded knowledge change feed.
- `POST /v1/search` — retained Email capability search during compatibility migration.
- `POST /v1/answers` — bounded synthesis from retrieved evidence; returns citations.
- Future graph traversal — related objects and cited attributes beyond exact lookup.
- `GET /v1/projects/{id}` — project state, members, commitments, events, evidence.
- `GET /v1/claims/{id}` — claim versions, support, contradictions, and supersession.
- `GET /v1/timeline` — cursor/time-bounded events.
- Future unified evidence/change routes will compose Email, DataCore and KnowledgeCore
  only after their evidence identities share a proven migration path.
- `POST /v1/proposals` — typed proposed change; never direct provider/filesystem access.

Resource names may evolve through an ADR before implementation. IDs are opaque and
tenant-scoped. Requests include explicit `limit`, `fields`, and optional byte/token
budgets. Responses include `next_cursor`, truncation reasons, freshness, and policy
decisions.

## Common response envelope

```json
{
  "data": [],
  "citations": [
    {
      "evidence_id": "ev_opaque",
      "source_kind": "email",
      "source_item_id": "item_opaque",
      "locator": {"kind": "text_span", "start": 120, "end": 238},
      "content_sha256": "..."
    }
  ],
  "freshness": {
    "source_observed_at": "...",
    "data_indexed_at": "...",
    "knowledge_updated_at": "..."
  },
  "page": {"next_cursor": null, "truncated": false},
  "policy": {"scope": "brain.read", "redactions": []},
  "request_id": "req_opaque"
}
```

## Retrieval contract

- Deterministic filters and lexical search work without an LLM.
- Cross-layer results remain grouped because ranks from separate indexes are not
  calibrated as one global score.
- Semantic/vector ranking is optional and cannot suppress exact evidence lookup.
- Answers distinguish source statements from inferred conclusions.
- Conflicting claims are returned as conflicts, not silently collapsed.
- A citation identifies immutable evidence plus a stable locator and content digest.
- Ranking/extraction/model versions are included in internal provenance and available
  to authorized diagnostics.

## Authorization and effects

Scopes separate metadata/search, extracted content, original evidence, source
administration, proposals, approvals, and execution. Human and service identities are
mapped administratively; source content cannot request scopes. Effects require a typed
proposal, current authorization, policy evaluation, idempotency key, preview, approval
where required, and an audit receipt. Initial release is read-only.

## Client guidance

Clients should search first, expand the smallest useful set, cite evidence IDs in
their answer, and request originals only when needed. They must treat returned content
  as untrusted. A client losing access to one source must not infer its content from
  caches, embeddings, summaries, or graph projections.
