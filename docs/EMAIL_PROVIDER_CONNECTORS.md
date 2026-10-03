# Email Provider Connectors

Updated 2026-09-21. See [FEATURES_AND_METHODS.md](FEATURES_AND_METHODS.md) for
owner-facing behavior and [TEST_MAILBOX_PLAN.md](TEST_MAILBOX_PLAN.md) for the
separate MIME/mock-provider/disposable-live replay layers. SMTP is not a substitute
for any provider's synchronization protocol.

## Shared contract

This section describes the target contract, not active provider enrollment.
Implemented offline library slices: [Gmail](GMAIL_READ_CONTRACT.md),
[Microsoft Graph](GRAPH_READ_CONTRACT.md), and [IMAP](IMAP_READ_CONTRACT.md).
Only Fastmail currently has database-backed worker orchestration. No provider
has been connected to a real account in this build. Read slices expose no writes;
the target action methods below remain separately gated.

Every connector implements:

```text
discover_capabilities
bootstrap(account, policy) -> page + cursor
changes(cursor) -> events + next_cursor
fetch_message(id, version) -> raw evidence
list/reconcile(scope, watermark)
ensure_canonical_mailbox(role)
preview_action(command)
execute_action(command, idempotency_key)
create/update_draft
health/auth_status
```

Provider IDs/cursors remain opaque. Notifications enqueue synchronization but never replace cursor-based reconciliation. Read and write credentials are separated when the provider allows it.

## Fastmail: JMAP first

Implemented: read-only JMAP protocol and bounded HTTPS session/metadata/blob
transport and a resumable worker library with synthetic HTTP-to-database tests.
Stable-query listing, certified inventory reconciliation, incremental pages, leases,
bounded quarantine and retries are implemented. Expired history starts a fresh
certified inventory before absence inference. Explicit encrypted storage and larger
Fastmail downloads preserve up to 16 MiB, holding mail beyond the parser budget;
see [storage limits](LARGE_EVIDENCE_STORAGE.md). Scheduler, credential enrollment,
hosted storage and live acceptance are not implemented.
See [worker contract](READ_WORKER.md). No real mailbox was contacted. The Fastmail
read operator is now exposed by [explicit bounded CLI](READ_CONTROLLER.md), with
non-consuming preflight and pinned account/secret binding; no enrollment or service
is installed. Tests use fictional transport only. Fastmail's `mail`
OAuth scope covers read/manage: do not assume a universal read-only OAuth scope.
The adapter excludes `set` and submission methods. Use the least capable token
actually available. Distributed OAuth apps need Fastmail client registration;
personal API-token testing is a separate path.

Never substitute `queryState` for an `Email/changes` state. Capture a baseline
Email state before full listing and page by `anchor` with an explicit sort;
ordinary positional paging can miss untouched items when earlier items are deleted,
and restarting on every query-state change never finishes on a busy mailbox
([ADR-110](adr/110_fastmail_sync_resilience.md)). Mail larger than the storage
budget is held as an accounted receipt without bytes rather than pausing the
account; an unchanged blob is not downloaded again for a flag-only update.
The 1 MiB control-response cap remains: a metadata batch that exceeds it is
bisected by ID and fully validated before the cursor advances. An unsplittable
single row or malformed response still fails closed.

Use Fastmail JMAP for Email, Thread, Mailbox, SearchSnippet, and submission/drafts; Fastmail documents its JMAP session endpoint and supported mail types ([API docs](https://www.fastmail.com/dev/)). Follow `Email/changes`, `Mailbox/changes`, or query-state change methods defined by JMAP; RFC 8621 specifies mail synchronization and `Email/queryChanges` ([RFC](https://www.rfc-editor.org/rfc/rfc8621)).

Design notes:

- Store JMAP account IDs, capability URNs, state strings, blob IDs, email/thread IDs, mailbox IDs, and keyword maps.
- Use method-call batching and backreferences where safe.
- Apply mailbox membership/keyword patches with expected state when available; handle state mismatch by refetching.
- Prefer separate Fastmail API tokens for read, change, and send capability if operationally available.

## Gmail: History API + Pub/Sub hint

Bootstrap with messages/threads and store a recent `historyId`. Incrementally call `users.history.list(startHistoryId=...)`; Google says history outside the available range yields HTTP 404 and requires full synchronization ([sync guide](https://developers.google.com/workspace/gmail/api/guides/sync)).

Gmail push uses Cloud Pub/Sub and returns a mailbox history ID; watches must be renewed at least every seven days and Google recommends daily renewal. Notifications can be delayed/dropped, so periodic `history.list` remains required ([push guide](https://developers.google.com/workspace/gmail/api/guides/push)).

Map canonical folders to Gmail labels. A “move” generally adds/removes labels; preserve system-label semantics. Use the smallest OAuth scopes and separate draft/send scope from read/modify where deployment permits.

## Microsoft 365: Graph delta + change notification hint

Track messages per mail folder because message delta is folder-scoped. Follow every `@odata.nextLink` unchanged until an `@odata.deltaLink` is returned; persist the entire opaque delta link. Microsoft notes that moves/deletions may appear as `@removed` entries and ordering is not guaranteed ([message delta](https://learn.microsoft.com/en-us/graph/api/message-delta?view=graph-rest-1.0)).

Use change notifications to enqueue a folder/account sync, then delta to establish truth. Renew subscriptions before expiry and run scheduled catch-up. Keep immutable IDs if supported/configured, and test move behavior explicitly. Use delegated permissions for user-facing operations unless a documented app-only use case and admin consent justify broader access.

## iCloud: IMAP with reconciliation

Apple exposes iCloud Mail over IMAP/SMTP with TLS; IMAP is `imap.mail.me.com:993` and third-party access may use an app-specific password ([Apple settings](https://support.apple.com/en-ie/102525)). There is no Gmail/Graph-equivalent change API.

- Track per-folder `UIDVALIDITY`, UID high-water mark, known flags, and mailbox delimiter/special-use mappings.
- Use IDLE as a latency hint, not a durable event log.
- On `UIDVALIDITY` change, rebuild that folder mapping safely.
- Periodically reconcile UIDs/flags and detect moves as delete+add when necessary.
- Prefer IMAPClient for a thin, mature protocol layer; it handles UIDs and parsed responses ([project](https://github.com/mjs/imapclient)). `imap-tools` is ergonomic for higher-level mailbox operations and IDLE ([project](https://github.com/ikvk/imap_tools)); benchmark both against iCloud edge cases.
- SMTP/send is outside v1; create provider drafts or keep draft content internal until explicitly implemented.

## Failure and throttling behavior

SMTP is outbound, not synchronization. Email Brain does not run a replacement mail
server. If sending is separately approved later, prefer provider-native drafts and
submission; SMTP would require its own approval/idempotency/uncertain-delivery
adapter. No SMTP credentials or sending capability are currently added.

- Respect `Retry-After`, provider quota headers, and exponential backoff with jitter.
- Quarantine malformed MIME/provider payloads while allowing cursor progress only when the event and failure record are durable.
- A credential/auth failure pauses the account and alerts the owner; do not spin retries.
- Full-resync writes into the same idempotent pipeline and never bulk-deletes local data merely because a partial listing failed.
- Daily reconciliation compares counts/samples/provider versions and emits drift metrics.

## Conformance suite

`tests/test_attachment_provider_formats.py` now passes nine identical synthetic
attachment-bearing messages through Gmail raw/base64url JSON, Graph MIME `$value`,
Fastmail JMAP blob downloads and IMAP fetched literals, checking byte preservation.
These mocked transports do not certify live servers or additional durable workers.
See [fixture coverage](CALENDAR_ATTACHMENTS.md).

`tests/test_synthetic_mailbox_providers.py` additionally replays the coherent
known-answer mailbox sources through those four mocked contracts (48 cases in
the verified build). This tests format preservation with connected scenarios;
it does not add notification ingress, durable workers or live-provider acceptance.

Each adapter must pass recorded/synthetic fixtures for bootstrap pagination, empty changes, duplicate notifications, cursor expiry, deletes, moves, label/flag changes, drafts, rate limits, crashes before/after checkpoint, and Unicode/MIME anomalies. Live tests operate only in disposable test mailboxes/folders.
