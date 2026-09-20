# Email Provider Connectors

## Shared contract

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
transport with mock tests. Not yet a scheduler, OAuth enrollment flow, full backfill
or reconciliation implementation. No real mailbox was contacted. Fastmail's `mail`
OAuth scope covers read/manage: do not assume a universal read-only OAuth scope.
The adapter excludes `set` and submission methods. Use the least capable token
actually available. Distributed OAuth apps need Fastmail client registration;
personal API-token testing is a separate path.

Never substitute `queryState` for an `Email/changes` state. Capture a baseline
Email state before full listing and validate query-state stability during paging;
ordinary positional paging can miss untouched items when earlier items are deleted.

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

Each adapter must pass recorded/synthetic fixtures for bootstrap pagination, empty changes, duplicate notifications, cursor expiry, deletes, moves, label/flag changes, drafts, rate limits, crashes before/after checkpoint, and Unicode/MIME anomalies. Live tests operate only in disposable test mailboxes/folders.
