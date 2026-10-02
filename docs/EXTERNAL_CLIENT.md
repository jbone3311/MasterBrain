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

The server remains the authority for identity, tenant, scopes, source visibility
and freshness. In the synthetic bootstrap path, an assistant must be enrolled
for explicit source IDs; its other Brain/Knowledge routes are denied. This is a
static test credential, not hosted grant issuance or immediate revocation. A
successful search is not a grant to read original evidence.
No client method changes a file or mailbox, proposes or approves an action,
returns provider credentials, or bypasses current-source selection.

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
private hosting, grounded answer synthesis or live sources.
