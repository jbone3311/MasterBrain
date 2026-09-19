# API and MCP Specification

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
