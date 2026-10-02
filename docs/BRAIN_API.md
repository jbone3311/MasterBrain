# Brain API

The Brain API is MasterBrain's model-neutral, least-privilege access layer. It serves
humans and authorized clients such as Claude, Grok, ChatGPT, and future assistants.
Implemented DataCore access lives under `/v1/brain`; the first reviewed KnowledgeCore
publish/read slice lives under `/v1/knowledge`. Synthesis remains a target contract.
The first-party read-only workspace at `/brain` uses these same scoped resources;
it is not a second, privileged retrieval or action backend. It displays lexical
search results in conversation form, not generated answers. Full chat synthesis
and external-client acceptance remain targets [documented separately](USER_INTERFACES.md).
ADR-128's FileOS v2 search comparison is an internal, human-review method, not
a Brain API route or evidence of current v2 visibility.

## Progressive access

1. **Orient:** return compact results: title/summary, object type, freshness,
   confidence, source count, and opaque references.
2. **Expand:** retrieve only selected fields, related objects, timeline windows, or
   evidence-backed chunks.
3. **Verify:** resolve a citation to bounded extracted text, then—only with the
   required scope—to a verified original Email message or attachment. Original
   FileOS-byte access is not exposed by the current Brain API.

No endpoint exposes provider tokens, storage keys, unrestricted paths, arbitrary
objects, general SQL, or an unbounded corpus dump.

## Versioned resources

- `POST /v1/brain/search` — implemented compact retained DataCore lexical
  search; enrolled assistants are filtered by source in SQL before ranking and
  limit (ADR-142).
- `GET /v1/brain/evidence/{id}` — implemented metadata/citation expansion.
- `POST /v1/brain/evidence/{id}/content` — implemented separately scoped bounded text.
- `GET /v1/brain/changes` — implemented cursor-bounded DataCore change feed.
  Enrolled assistants with `brain.changes.read` see only granted sources;
  ungranted event cursors return not found (ADR-133).
- `GET /v1/brain/sources/{source_id}/freshness` — implemented latest fully accounted
  FileOS run or explicit `no_completed_run`; requires `brain.changes.read`.
- `GET /v1/brain/sources/{source_id}/inventory` — implemented latest completed
  membership/new-absence counts; preserves evidence and requires `brain.changes.read`.
- `GET /v1/brain/sources/{source_id}/rebuild-preview` — implemented paginated,
  read-only deterministic document/chunk verification for the latest complete run.
- `GET /v1/brain/sources/{source_id}/index` — implemented active immutable FileOS
  generation status; requires `brain.changes.read`.
- `POST /v1/brain/sources/{source_id}/search` — implemented bounded lexical search
  against only that source's active generation; requires `brain.search`.

ADR-142 admits enrolled assistants to the five exact-source FileOS reads above
and the aggregate/retained Brain searches. An ungranted source is
indistinguishable from an unknown source (not found); the check occurs after
transaction-time OIDC revocation validation. It does not grant original bytes,
source effects or an alternate route through KnowledgeCore.
- `POST /v1/brain/fileos-search` — implemented current FileOS search across the newest
  activated generation of every authorized source; requires `brain.search`.
  Enrolled assistants see only granted sources.
- `POST /v1/brain/email-search` — implemented current-only search across explicitly
  bridged Email versions that remain current and visible in the legacy Email state;
  requires `brain.search`. Enrolled assistants see only granted sources.
- `POST /v1/brain/email-family-search` — implemented current-only, independently
  bounded message/attachment/approved-document layers with within-layer ranks;
  requires `brain.search`. Enrolled assistants see only granted sources.
- `POST /v1/brain/current-search` — implemented grouped active-FileOS, explicitly
  published current archive-text, archive-document and archive-image OCR,
  current-Email-family and reviewed-KnowledgeCore
  lexical read with independent limits/ranks, explicit partial coverage and
  independent-layer consistency; requires both search scopes. `archive_member_limit`
  and `archive_image_limit` are independently 1–20; archive result locators are opaque.
  Synthetic bootstrap and administrator-bound OIDC Brain assistants require
  explicit source enrollment: all current
  layers are filtered before ranking/limit, and `coverage.source_access` reports
  `enrolled_sources_only` without enumerating hidden sources. Human owners retain
  tenant-wide bootstrap reads. OIDC grant removal invalidates saved contexts at
  the next transaction; hosted issuer enrollment and derived-cache revocation
  are not accepted.
- `POST /v1/brain/answers` — optional ADR-134 extractive answer over the same
  current grouped search and separately authorized evidence/content reads.
  Requires `brain.search`, `knowledge.search`, `brain.evidence.read` and
  `brain.content.read`, plus assistant source enrollment. A configured selector
  may choose at most four exact quotes from at most eight bounded passages;
  the server verifies citations and rechecks current visibility. ADR-144 makes
  a local deterministic excerpt selector the default; explicit `None` disables
  it and returns 503. ADR-145 removes fixed question boilerplate before both
  current-search calls; the original question reaches the selector, and Search
  only retains literal query behavior. It has no effect grant,
  freeform model-authored answer or hosted/named-assistant acceptance.
- `GET /v1/brain/current-coverage` — implemented bounded status for registered FileOS
  generation readiness and explicitly bridged current Email family coverage; requires
  `brain.changes.read`, is cursor-bounded and does not enumerate providers or paths.
  Enrolled assistants see only granted sources; ungranted source cursors return
  not found (ADR-133). The reference read client supports both status routes.
- `POST /v1/brain/unified-search` — implemented grouped DataCore evidence and
  KnowledgeCore assertion search; requires both search scopes, keeps ranks separate,
  and accepts explicit `retained` or `current_fileos` evidence visibility.
  Enrolled assistants see only granted DataCore sources and Knowledge assertions
  whose direct evidence is wholly granted (ADR-143).
- `POST /v1/knowledge/assertions` — implemented human-reviewed, evidence-required
  append with a UUID idempotency key.
- `POST /v1/knowledge/search` — implemented compact lexical retrieval across entity,
  relationship, claim, event, project, commitment and correction records.
- `GET /v1/knowledge/{kind}/{id}` — implemented assertion/evidence expansion;
  enrolled assistants cannot resolve mixed or hidden-source assertions.
- `GET /v1/knowledge/changes` — implemented cursor-bounded knowledge change
  feed; enrolled assistants see only directly source-authorized assertions and
  cannot use an ungranted event as a cursor.
- `POST /v1/search` — retained Email capability search during compatibility migration.
- Future freeform cited synthesis — not implemented; the existing
  `/v1/brain/answers` route is limited to verified extractive quotes.
- Future graph traversal — related objects and cited attributes beyond exact lookup.
- `GET /v1/projects/{id}` — project state, members, commitments, events, evidence.
- `GET /v1/claims/{id}` — claim versions, support, contradictions, and supersession.
- `GET /v1/timeline` — cursor/time-bounded events.
- Future unified evidence/change routes will compose Email, DataCore and KnowledgeCore
  only after their evidence identities share a proven migration path.
- `POST /v1/proposals` — typed proposed change; never direct provider/filesystem access.

Resource names may evolve through an ADR before implementation. Current IDs are
opaque and tenant-scoped; individual implemented routes enforce their documented
bounds, scopes and pagination. Uniform `fields`, token budgets, response envelopes,
and synthesis are target contracts, not guarantees of every current route.

## Common response envelope

The JSON below is a **target design**, not a promise that every implemented route
already emits this uniform envelope. The individual route schemas and tests govern
current responses; common field selection and token budgets remain planned.

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
- Current FileOS, published archive-member and bridged-Email searches are explicit.
  Compatibility DataCore search retains historical evidence unless the client selects
  a current-only route.
- Grouped search defaults to retained-history compatibility. Clients may explicitly
  select current FileOS generations without changing the KnowledgeCore layer.
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

An opt-in local service configuration resolves a verified identity through a
table-blind lookup login and routes its tenant to a distinct DBA-bound data login.
The route is server-owned; API fields cannot select a DSN. The older single-DSN
prototype remains available but is not hosted multi-tenant containment. See
[ADR-109](adr/109_tenant_database_routing.md) and
[the tenant-login contract](TENANT_LOGIN_FENCE.md).

## Client guidance

There is no deployed MCP server or certified Claude, Grok or ChatGPT adapter yet.
The [provider-neutral read client](EXTERNAL_CLIENT.md) is an executable
read-only reference over the same REST routes used by `/brain`; it passes a
fictional cross-source conformance test. Use it only with a separately
authorized credential. Passing local API/client tests does not establish
assistant integration or hosted acceptance.
ADR-130's bootstrap assistant and ADR-132's OIDC Brain assistant can call the
source-scoped current-search, evidence/content, ADR-133 coverage/change and
ADR-142 directly source-filtered search/FileOS status routes, with an explicit
source allowlist. ADR-134 also permits bounded
extractive answers, subject to all four read scopes; ADR-144 selects local
exact quotes by default and permits explicit disabling. ADR-143 adds directly source-filtered Knowledge
and unified Brain reads for enrolled assistants. Hosted issuer enrollment,
legacy Email assistant source filtering and derived-cache revocation
remain open in [issue #88](https://github.com/jbone3311/MasterBrain/issues/88).

Clients should search first, expand the smallest useful set, cite evidence IDs in
their answer, and request originals only when needed. They must treat returned content
  as untrusted. A client losing access to one source must not infer its content from
  caches, embeddings, summaries, or graph projections.
