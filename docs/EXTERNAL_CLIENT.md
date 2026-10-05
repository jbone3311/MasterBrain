# Read-only external Brain API client

Status: executable reference client on synthetic/disposable data. It is **not**
a deployed Claude, Grok, ChatGPT or MCP integration, nor permission to send
private content to a model. See [ADR-129](adr/129_read_only_external_brain_client.md)
and [hosted/access prerequisites](USER_INTERFACES.md).

`masterbrain.brain_client.BrainReadClient` is a small provider-neutral transport
over the same Brain API routes used by `/brain`. An operator fixes the API
origin and supplies a separately enrolled bearer credential; neither a model
prompt nor a search result can choose an arbitrary URL. The client has only:

| Method | Brain API route | Server grant |
|---|---|---|
| `current_search(query)` | `POST /v1/brain/current-search` | `brain.search` and `knowledge.search` |
| `evidence(id)` | `GET /v1/brain/evidence/{id}` | `brain.evidence.read` |
| `evidence_content(id, max_chars=4000)` | `POST /v1/brain/evidence/{id}/content` | `brain.content.read` |
| `current_coverage()` | `GET /v1/brain/current-coverage` | `brain.changes.read` |
| `changes(...)` | `GET /v1/brain/changes` | `brain.changes.read` |
| `answer(question)` | `POST /v1/brain/answers` | `brain.search`, `knowledge.search`, `brain.evidence.read`, `brain.content.read`; local exact-quote selection is the default, and the operator may disable it |
| `timeline(start, end, ...)` | `GET /v1/knowledge/timeline` | `knowledge.search`; bounded reviewed-event occurrence window (ADR-160) |
| `commitments_due(start, end, ...)` | `GET /v1/knowledge/commitments-due` | `knowledge.search`; bounded reviewed-commitment due window (ADR-161, merged synthetic read) |

The server remains the authority for identity, tenant, scopes, source visibility
and freshness. In the synthetic bootstrap path, an assistant must be enrolled
for explicit source IDs; routes without reviewed source semantics remain denied.
ADR-133 adds two source-scoped status reads. ADR-134 adds the bounded answer
read over the same current, separately authorized evidence; ADR-144 supplies
a local deterministic default selector and retains explicit disablement.
ADR-145 removes fixed question boilerplate before answer retrieval, while
`current_search(query)` remains literal and the selector receives the original
question. This is lexical cleanup, not synonym search or AI-written synthesis.
ADR-146 adds a separately bounded, validated `reviewed_knowledge` list to
`answer(question)`; it is not a list of exact quotations. The client still
follows selected evidence IDs through the distinct evidence/content grants.
ADR-151 makes `answer(question)` carry `coverage.answer_context_truncated`.
The selector sees at most 2,048 UTF-8 bytes from one passage and 8,192 bytes
of passage text total. The client validates the flag when present; callers
must not read a flagged no-quote answer as a whole-source negative result.
ADR-157 separately limits the returned quote plus reviewed-match text to
8,192 UTF-8 bytes. `coverage.answer_output_truncated` says reviewed display
text was shortened or omitted; exact quotes remain intact. The client rejects
over-budget or malformed responses. This is not a whole-JSON or token budget.
ADR-132 also lets a separately verified OIDC assistant use administrator-owned,
same-tenant source grants, rechecked on each database transaction. Neither
path is certified hosted grant issuance or a named assistant. A
successful search is not a grant to read original evidence.
No client method changes a file or mailbox, proposes or approves an action,
returns provider credentials, or bypasses current-source selection.
The timeline and due-window methods return reviewed interpretations with
direct evidence IDs, not fresh source facts. Their first page establishes a
recorded-time cutoff; later pages need that cutoff and the returned opaque
cursor. The cutoff is not a durable snapshot across requests.

```python
from masterbrain.brain_client import BrainReadClient

# api_origin and bearer_token come from a trusted operator/secret store,
# never a model response or source document.
with BrainReadClient(api_origin, bearer_token) as brain:
    grouped = brain.current_search("Cedar Harbor insurance")
    # Inspect grouped coverage before claiming that all sources were searched.
    for hit in grouped["layers"]["email_messages"]:
        citation = brain.evidence(hit["evidence_id"])
        # Request bounded text only when separately authorized and needed.
        # Keep evidence IDs and source context with any later cited answer.
```

Use HTTPS for a remote service. `allow_insecure_loopback=True` works only with
`127.0.0.1` or `::1` for disposable local tests; it is not a hosting setting.
The client ignores ambient proxy variables, has finite timeouts, rejects
redirects, refuses over-256-KiB decompressed JSON, and does not cache or log
content. Failures expose fixed codes rather than response bodies or tokens.
Returned source text is untrusted and must not be treated as instructions.

The fictional [cross-source trial](CROSS_SOURCE_TRIAL.md) now runs the same
questions through a direct Brain API request and this client, comparing the
exact grouped response, evidence expansion, separate content grant and
cross-tenant denial. This proves the reference transport on a local test
boundary; it does not certify a named assistant, hosted token issuance/revocation,
private hosting, a configured/approved model selector or live sources. The
extractive answer method is not freeform synthesis: it returns only server-verified
quotes and evidence links. The reference client has no source-effect methods.
