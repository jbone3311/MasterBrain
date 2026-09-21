# API and MCP Specification

Updated 2026-09-21. Implemented REST sections below map to [api.py](../src/email_brain/api.py).
MCP, entity/state and action examples are target contracts, not callable tools.
No Grok/ChatGPT/Claude end-to-end connection is certified by this specification.
See [status](IMPLEMENTATION_STATUS.md) and [features/methods](FEATURES_AND_METHODS.md).

## Reading this contract

Implemented routes must be checked against [api.py](../src/email_brain/api.py),
its generated OpenAPI and route tests. Target tool names, example identifiers and
pagination conventions later in this document are design sketches, not requests
that can be sent to the bootstrap service. Existing recovery history uses bounded
UUID keysets; it is not the future signed-cursor protocol.

MCP implementation must follow the official [security guidance](https://modelcontextprotocol.io/docs/tutorials/security/security_best_practices),
including audience validation and no upstream token passthrough. Rechecked
2026-09-21; this does not implement OAuth/MCP or establish client compatibility.
See the [worked feedback flow](PRODUCT_WALKTHROUGH.md#what-learning-means) for the
owner intent behind these interfaces.

## Durable isolated processing jobs

ADR-035 adds a **separate** [document approval/result API](DOCUMENT_PROCESSING.md):
account document capabilities, attachment jobs, bounded job history/status/cancel
and `GET /v1/documents/{document_id}`. Search accepts `include_documents: true`
(default false). Human review/evidence approval and worker-only
`email.document.process` are distinct; no HTTP execution or arbitrary upload.

[Processing history and owner controls](PROCESSING_REVIEW_SCREEN.md) add
`GET /v1/accounts/{account_id}/processing/jobs`, before the dynamic job-ID route.
Owner/evidence scope, limit 1–50, same-account UUID cursor, immutable time/ID order;
unknown/foreign anchors return 404. Public projection only; no new execution scope.

The opt-in [processing-job API](RECOVERY_JOBS.md) supports human approval, bounded
status and cancellation. The operator fixes the exact parser version at startup.
The client cannot choose images, commands, sockets or storage. A separate
owner-bound worker claims jobs through the library, not an HTTP execution endpoint.
The ordinary synchronous retry route remains unchanged. No MCP transport is added.

These MIME grants target quarantine receipts, not deferred parts of ready messages.
The new document channel above handles approved synthetic PDFs independently.
Neither channel exposes arbitrary file upload, passwords or binary worker selection.
The synthetic packet/export/replay tooling is CLI-only, not an API/MCP addition.

## External evidence storage

The [isolated large-MIME processor](ISOLATED_MIME_RECOVERY.md) is injected only by
a trusted operator/worker into the Recovery library. Default HTTP/UI retry does
not launch it, accept image IDs or grant daemon privileges. Its future hosted job
control now has a scoped bootstrap job API; production authorization is still gated.

Opt-in [large evidence storage](LARGE_EVIDENCE_STORAGE.md) adds quarantine reason
`mime_too_large`; retry is 409 while retained mail exceeds the parser budget.
Unavailable/corrupt encrypted storage returns scrubbed 503
`evidence_storage_unavailable`, without a cached recovery attempt. No raw-download,
key-management, object-inventory or storage-configuration HTTP/MCP endpoint is added.

## Calendar attachment evidence

Existing search/evidence responses now include bounded extracted source text from
newly ingested supported `text/calendar` parts, including unnamed body alternatives.
The receipt reason `bounded_calendar_v1` means source extraction only, not invitation
acceptance, timezone/recurrence evaluation or a malware scan. Unsupported/malformed
parts retain explicit deferred/failed outcomes. No calendar action route is added.
See [calendar contract](CALENDAR_ATTACHMENTS.md).

## Implemented reviewed sender rules

The [reviewed rules contract](REVIEWED_RULES.md) adds list, simulation, explicit
human activation and expected-revision rollback. Search returns virtual labels and
rule provenance. Review alone still applies nothing; no provider action or MCP
transport is enabled by this addition.

## Implemented held-message review

`GET /v1/accounts/{account_id}/quarantine?limit=50&after={receipt_uuid}` requires
`email.evidence.read` and current owner membership. Returns only current unresolved
receipt metadata: ID, provider ID, SHA-256, fixed reason, parser version and time.
`results` has at most 50 entries; `next_after` is null or a receipt UUID. This is
a live UUID-keyset list, not a stable export snapshot. New receipts can appear
before an existing cursor; refresh from the first page after changes. Unknown or
foreign accounts return 404, absent scope 403, invalid cursor/limit 422.
Responses declare `raw_access: false`, `reprocessing: true` and the current
`retry_parser_version`. Historical failure
receipts remain stored after repair/deletion but leave this current queue. There
are no dismiss, raw-download or delete routes. An explicit human owner can call
`POST /v1/accounts/{account_id}/quarantine/{receipt_id}/retry` with only
`expected_parser_version`; both review and evidence scopes are required.
The receipt/parser pair is the natural idempotency key. This retries retained
bounded MIME, not provider ingestion or a mailbox action. See the complete
[recovery contract and errors](QUARANTINE_RECOVERY.md).

## Implemented sync status

`GET /v1/accounts/{account_id}/sync-status` requires `email.search` and current
owner membership. Returns account ID, content-free worker outcome/pause/retry state
(or null before enrollment), message counts by ready/quarantined/deleted,
`review_required` for current quarantines, and `mailbox_writes: false`. Unknown
and cross-tenant accounts return 404; missing scopes return 403. Counts do not
imply complete backfill, binary extraction, or live-provider acceptance. No raw
object access or resume/reprocess capability is exposed.

## Implemented bootstrap surface (v0.1)

The actual bounded service exposes the additions above, the rule routes in
[REVIEWED_RULES.md](REVIEWED_RULES.md), and the core routes below. Sections after
the bootstrap examples describe the target, not implemented MCP/actions:

| Method/path | Required scope | Behavior |
|---|---|---|
| `GET /healthz` | none | Process liveness only; not DB readiness |
| `GET /readyz` | `email.search` | Verifies runtime DB access/current owner membership |
| `POST /v1/search` | `email.search` | Lexical message/attachment search, opt-in document text, optional account filter, limit 1–50 |
| `GET /v1/evidence/{uuid}` | `email.evidence.read` | Version-stable excerpt/hash, attachment receipts/accounting; no raw download |
| `POST /v1/proposals` | `email.proposal.create` | Closed discriminated payload; UUID `Idempotency-Key` header required |
| `GET /v1/proposals` | `email.proposal.read` | Latest 50 proposals; full pagination pending |
| `POST /v1/proposals/{uuid}/reviews` | `email.review` + human credential | Expected-version approve/reject; **applies nothing** |

All content routes also require an existing owner membership. No tenant/user IDs
are accepted in payloads. Auth is expiring server-bound bootstrap tokens, not the
target OIDC system. Requests cap at 32 KiB before JSON decoding; schemas reject
extra fields. Evidence excerpts cap at 4,000 characters plus bounded per-attachment
excerpts. Validation errors do not echo input. No action/send/delete/raw SQL/MCP
transport endpoint exists. The service is loopback-only and not Internet-ready.

Example project proposal:

```json
{
  "payload": {"kind": "project", "name": "Melron", "description": "Track the investment"},
  "reason": "Owner requested a dedicated project",
  "source": "owner-review-ui",
  "evidence_ids": []
}
```

`evidence_ids` means immutable message-version UUIDs returned by search, not
provider IDs or current message IDs. A correction additionally identifies its
current internal message UUID. REST schemas are available at `/openapi.json`.

## Principles

- REST/JSON is the stable service contract; MCP is a narrow adapter over it.
- All requests are authenticated, tenant-scoped, versioned, rate-limited, and assigned a correlation ID.
- Reads and mutations use separate scopes. Mutation endpoints accept idempotency keys.
- Evidence is returned by reference and bounded excerpt, never unlimited raw mailbox dumps.
- Errors use stable codes, retryability, and safe details; no secrets or message bodies in diagnostics.

## Authentication and scopes

Representative scopes:

```text
email.search email.evidence.read email.state.read
email.proposal.create email.review
email.draft.create email.mailbox.label email.mailbox.move
email.send email.delete.permanent
email.admin.accounts email.admin.rules email.audit.read
```

User-delegated tokens include tenant, subject, scopes, audience, and expiry. Service principals are bound to a tenant/account/job class. Remote MCP follows audience-bound OAuth and no token passthrough per [MCP authorization security considerations](https://github.com/modelcontextprotocol/modelcontextprotocol/blob/main/docs/specification/2026-07-28/basic/authorization/security-considerations.mdx).

## REST surface (v1)

### Read

```text
POST /v1/search
GET  /v1/messages/{id}
GET  /v1/threads/{id}
GET  /v1/entities/{id}
GET  /v1/people/{id}/brief
GET  /v1/projects/{id}/brief
GET  /v1/obligations?status=open
GET  /v1/attention
GET  /v1/rules
GET  /v1/changes
```

`POST /search` accepts query, structured filters, modes (`lexical|semantic|hybrid`), limit ≤50, and optional answer request. Response includes candidates, score components, stable evidence citations, truncation flags, and retrieval/version metadata.

### Feedback/control

```text
POST /v1/proposals/rules
POST /v1/proposals/facts
POST /v1/proposals/relationships
POST /v1/proposals/folder-mappings
POST /v1/proposals/features
POST /v1/corrections
POST /v1/feedback/relevance
GET  /v1/proposals
POST /v1/proposals/{id}/reviews
POST /v1/proposals/{id}/apply
POST /v1/rules/{id}/rollback
```

Every proposal carries `reason`, evidence references, desired outcome, confidence, source client, schema version, and optional expiry. The server—not the assistant—assigns effective risk and required approvals.

### Mailbox effects

```text
POST /v1/actions/preview
POST /v1/actions
GET  /v1/actions/{id}
POST /v1/actions/{id}/approve
POST /v1/actions/{id}/cancel
POST /v1/actions/{id}/compensate
POST /v1/drafts
```

Example proposed action:

```json
{
  "type": "move_or_label",
  "targets": [{"message_id": "...", "expected_version": "..."}],
  "parameters": {"canonical_mailbox": "review_delete"},
  "reason": "matched rule promo-known-vendor:v3",
  "idempotency_key": "uuid"
}
```

Approval binds to the canonical request hash and expires; any target/version change invalidates it.

## MCP tools

Expose small tools with tight schemas:

```text
email_search
email_get_thread
email_get_person_brief
email_get_project_brief
email_list_attention
email_list_obligations
email_get_evidence
email_propose_rule
email_propose_fact_update
email_record_correction
email_propose_feature
email_create_draft
email_preview_action
email_submit_action
```

Default clients receive read + proposal scopes only. `email_submit_action` is unavailable unless explicitly granted and still cannot bypass policy/approval. Do not expose general SQL, arbitrary object reads, provider APIs, or unrestricted HTTP fetch.

## MCP resources

Resources are safe, cacheable summaries—not live secrets:

```text
email://taxonomy/current
email://rules/active
email://people/{id}/brief
email://projects/{id}/brief
email://proposals/pending
```

Use stable ETags/version fields. Never put tenant content into tool descriptions or discovery metadata.

## Pagination, concurrency, and limits

- Cursor pagination; cursors are opaque, signed, tenant-bound, and expiring.
- Optimistic concurrency via `expected_version`/ETag.
- Search limits: candidate pools, returned excerpts, attachment bytes, date range, and total token estimate.
- Async jobs return `202` + job ID for bulk imports, exports, rebuilds, and action batches.
- Webhooks from providers are authenticated/validated, acknowledged quickly, deduplicated, and used only to enqueue sync.

## Evidence citation shape

```json
{
  "evidence_id": "ev_...",
  "message_id": "msg_...",
  "thread_id": "thr_...",
  "received_at": "2026-09-19T12:00:00Z",
  "source": {"provider": "gmail", "account_id": "acct_..."},
  "excerpt": "...",
  "excerpt_hash": "sha256:...",
  "offsets": [120, 244]
}
```

## Versioning

Version HTTP schemas, MCP tool schemas, rule DSL, model extraction schemas, and event types independently. Additive changes remain compatible; destructive changes require a migration window and contract tests.
