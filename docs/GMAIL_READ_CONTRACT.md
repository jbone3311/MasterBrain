# Gmail read contract — library, not an enrolled connector

## Implemented

`GmailReadClient` provides profile discovery, bounded message listing, history
pages, raw MIME and minimal metadata reads. Immutable result objects contain
provider identifiers; they do not carry tenant authorization or write privileges.
All tests use synthetic bytes and HTTP mocks. No real mailbox was contacted.

The caller supplies one OAuth access token and the stored primary account email.
`discover()` compares Google's profile address before allowing mail reads. All
URLs use the fixed HTTPS `gmail.googleapis.com` origin and `/users/me`, with no
caller-selectable account path. Profile refresh failures and authentication errors
invalidate the binding. Token refresh must create/reverify a client; this adapter
does not store refresh tokens. Google documents `me` and profile history/address
fields in [getProfile](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users/getProfile).

## Pagination and evidence semantics

- `history(start_history_id, page_token)` keeps the original start history ID
  across pages. IDs are strings, not consecutive counters. Numeric comparisons
  validate order only; code never invents the next ID. A terminal page offers a
  **candidate** checkpoint, not permission to commit before previous pages and
  current evidence are durable. History 404 raises `GmailHistoryExpired`; message
  404 raises the distinct `GmailMessageGone`. [History API](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.history/list).
- Specific history change fields preserve additions, deletions and label changes.
  Adding the `TRASH` label is not a deletion event. Generic entries not represented
  by specific changes become `refresh` hints for fetch/reconciliation; duplicated
  generic entries do not double-apply a specific change. The future worker must
  refetch current state rather than assume within-record change order.
- Listing includes Spam and Trash. Page tokens are opaque query values. The API's
  `resultSizeEstimate` is **not an exact count or a snapshot certificate**, and is
  deliberately absent from the typed listing result. [Messages list](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages/list).
- Full synchronization and expired-history recovery require a separate durable
  worker, stable-baseline/reconciliation design and database tests. This library
  never marks local mail absent after a partial listing. [Sync guide](https://developers.google.com/workspace/gmail/api/guides/sync).
- `message(id)` requests raw format, validates the returned ID, strictly decodes
  bounded base64url MIME and preserves exact bytes, including malformed MIME for
  downstream quarantine. `include_raw=False` requests minimal metadata and returns
  the distinct `GmailMinimalMessage` type. Google's minimal format guarantees ID
  and labels, not full evidence metadata: absent thread/history/time fields remain
  `None`; any present fields are validated. Raw reads still require validated
  thread/history/time and raw bytes in `GmailMessage`. Wrong IDs are rejected in
  both modes, and a minimal result cannot supply an invented ingestion timestamp
  or checkpoint. [Format contract](https://developers.google.com/workspace/gmail/api/reference/rest/v1/Format).
  Raw bytes
  are not rendered, executed or sent to a model. [Message get](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages/get).

## Transport and failure bounds

GET only; no redirects, environment proxies, custom hosts, URL fetching, `watch`,
modify, draft, send or delete capability. Connect timeout is 5 seconds, other
network-operation timeouts 20 seconds, plus a checked 30-second elapsed deadline.
The elapsed deadline is cooperative between reads, not a hard interrupt of a
running socket operation. Responses cap at 2 MiB JSON and decoded raw MIME at
1 MiB. Compressed responses fail closed. Pages cap at 100 records, history output
at 1,000 changes, labels at 100, and all identifiers/tokens are length-bounded.
JSON parsing rejects duplicate keys at every depth and nonfinite numbers,
including numeric overflow, in provider responses and decoded notification data.
Notification envelopes supplied as already-parsed objects still require strict
outer JSON parsing by the eventual authenticated ingress.

401 and unknown/permission 403 invalidate account verification. A bounded 403
error body containing only `rateLimitExceeded`/`userRateLimitExceeded` reasons
is throttling and preserves an already verified account binding. Mixed or malformed
reasons fail closed. Both quota 403 and 429 expose only a bounded numeric retry
delay, capped at one hour; other failures are scrubbed typed exceptions.
There is no retry loop. A future scheduler must apply bounded retry policy and
persist content-free telemetry. [Gmail error semantics](https://developers.google.com/workspace/gmail/api/guides/handle-errors).
No raw response,
token, exception URL or message body is returned in error text.

## Notifications and OAuth gates

`decode_untrusted_hint` only parses a bounded Pub/Sub envelope and matches expected
address/subscription. It returns `UntrustedGmailHint`, not an authenticated request
or checkpoint. A syntactically valid forged notification remains untrusted. The
function neither enqueues jobs nor makes requests. Future ingress must validate
JWT signature/issuer/audience, expected service-account identity and subscription
authorization first. [Pub/Sub authentication](https://docs.cloud.google.com/pubsub/docs/authenticate-push-subscriptions).

Even authenticated notifications only wake a sync from the stored cursor. Watch
renewal and polling fallback remain necessary; notifications can be delayed or
dropped. No watch or Pub/Sub resources have been created. [Gmail push guide](https://developers.google.com/workspace/gmail/api/guides/push).

Future enrollment should request `gmail.readonly`, not modify/send/full-mail scopes.
It is a restricted scope; external deployment may require verification and a
security assessment depending on use and data handling. The adapter does not
inspect or prove the actual token scope. [Google scope policy](https://developers.google.com/workspace/gmail/api/auth/scopes).

## Verification and remaining gates

Synthetic tests cover pages, cursor expiry, label/delete distinction, generic
history fallback, byte preservation, malformed JSON/schema/base64, path injection,
wrong accounts, timeouts, redirects, throttling, compressed/oversized responses,
untrusted hints and credential-safe errors. Run `pytest -q tests/test_gmail.py`.

Not implemented: tenant-bound token vault, OAuth consent/refresh, Gmail database
worker/checkpoints, certified inventories, cross-page cycle detection, durable
retry/telemetry, Pub/Sub JWT verification, watch renewal, large encrypted object
storage or live-provider acceptance. Callers must bound full-loop page counts and
detect longer token cycles. Do not advertise Gmail as production sync yet.

No migration is needed. Roll back by removing/stopping library callers; there is
no provider effect to compensate. See [ADR-019](adr/019_gmail_read_contract.md).
