# Microsoft Graph read contract

Status: offline-tested library, not an enrolled connector or deployed webhook.
Decision: [ADR-020](adr/020_graph_read_contract.md). Source is
[`graph.py`](../src/email_brain/connectors/graph.py); tests use intercepted HTTP only.

## Implemented boundary

- Explicit Graph user binding, global-cloud `graph.microsoft.com` only, GET only.
- TLS, certificate verification, no redirects or inherited environment proxies,
  20-second request/5-second connect timeouts, cooperative 30-second response
  deadline, 1 MiB streamed response cap and 100 delta entries per page.
- Folder delta parser retains the exact opaque next/delta URL, after checking its
  account/folder path. Query parameters are not decoded or reconstructed. Exactly
  one continuation is required; same-next-link loops fail closed. Empty pages with
  a new continuation are valid. The caller must bound multi-page cycles/work.
- Immutable-ID preference accompanies every request. IDs remain case-sensitive.
  This preserves identity through moves inside one mailbox, not moves to an archive
  mailbox or export/re-import. [Microsoft immutable-ID contract](https://learn.microsoft.com/en-us/graph/outlook-immutable-id).
- Delta results are fetch hints, not ordered last-write events. Duplicate IDs stay
  visible. A `membership_removed` result means absent from that folder, **not**
  globally deleted; its ID must never flow directly into the current account-wide
  tombstone ingestion path. Folder membership and account-wide evidence need a
  dedicated reconciler. Delta is folder-scoped, and a removed entry can represent
  a move. [Message delta reference](https://learn.microsoft.com/en-us/graph/api/message-delta?view=graph-rest-1.0).
- MIME download returns exact bounded bytes for later evidence ingestion. It does
  not parse attachments or run models. [Microsoft MIME retrieval](https://learn.microsoft.com/en-us/graph/outlook-get-mime-message).
- HTTP 401/403 requires authorization repair; 429 returns bounded retry metadata;
  410 requires full folder resync; 404 identifies an unavailable resource without
  asserting global deletion. Other failures are scrubbed, typed errors. Exception
  messages never include response bodies, tokens or opaque cursors.
  [Delta replay and reset guidance](https://learn.microsoft.com/en-us/graph/delta-query-overview).

## Webhook contract

Only basic notifications are accepted by the pure parser. Trusted server-side
bindings determine the local account/folder. Subscription ID, Graph tenant ID,
expiry, resource prefix and constant-time client-state comparison must all pass.
The returned hint contains only the bound local account/folder; resource data never
authorizes actions or supplies evidence. Duplicate hints coalesce within a batch.
An invalid item rejects the entire batch before any hints are returned.

Endpoint validation is separate: a bounded, once-decoded query token is echoed as
plain text only when the server has a pending registration. The echo is not proof
that later notifications are authentic. A future HTTP endpoint must enforce body
limits, rate limiting, HTTPS and durable enqueue before success; scheduled delta
catch-up remains necessary. Microsoft documents prompt acknowledgments, validation
echoes and client-state checks. [Webhook delivery guidance](https://learn.microsoft.com/en-us/graph/change-notifications-delivery-webhooks).

No public callback, subscription creation/renewal, lifecycle-notification handler,
rich-notification JWT validation/decryption or notification persistence exists.
The configured resource prefix must match the provider's returned basic resource
format exactly; unusual formats fail closed pending explicit conformance testing.

## Integration and production gates

1. Consent/enrollment with the smallest sufficient delegated read scope; distinguish
   basic metadata access from body/MIME access. No Mail.ReadWrite or Mail.Send.
2. Discover and bind folders, implement mailbox-scoped identity/membership records,
   durable per-folder checkpoint transactions, generation recovery and reconciliation.
3. Add scheduling, retries, cycle budgets, status telemetry and authenticated
   subscription lifecycle management. Do not log cursors, MIME or client state.
4. Test disposable mailboxes with explicit operator permission, including moves,
   expired cursors, deleted folders, unusual URL/resource forms and large mail.

The strict same-endpoint URL policy deliberately rejects unsupported alternate URL
shapes, sovereign clouds and beta endpoints. Only HTTP 410 is currently interpreted
as cursor expiry; other provider error-code variants require explicit fixtures and
typed handling before live activation. Old checkpoints must never be discarded or
advanced because a partial import failed. The existing Fastmail worker does not
automatically use this module.

## Verification and rollback

Synthetic tests cover hostile URL/account/folder overrides, no credential forwarding
on redirects, malformed/oversized JSON, duplicate keys, no-progress paging,
case-sensitive IDs, folder-removal ambiguity, raw MIME preservation, scrubbed
errors, spoofed/expired notifications and plain-text endpoint validation.

This change is additive and has no migration or provider side effects. Rollback
means stop using the library; retain any future persisted evidence/checkpoints.
