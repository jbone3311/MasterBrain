# ADR-019 — Bounded Gmail read contract

Accepted for the synthetic library boundary, 2026-09-20. This does not authorize
live accounts, OAuth enrollment, mailbox effects, or a deployed webhook.

Implement a GET-only client with a fixed `gmail.googleapis.com` origin and `/me`
account routing. Verify the authenticated profile against the caller's stored
account address before reading. Separate history IDs from pagination tokens;
only a terminal history page offers a candidate checkpoint, which a future worker
must commit atomically with all covered evidence. A history 404 means full resync,
whereas a message 404 means that individual message is unavailable. Neither means
that an incomplete inventory may delete existing local data.

Bound response bytes, decoded MIME bytes, page sizes, identifiers and elapsed
request time. Disable redirects and environment proxies; scrub provider failures.
Use immutable typed results and synthetic HTTP fixtures. Raw bytes remain evidence,
not instructions. No extra dependency, database migration, credential persistence,
send/delete method, watch setup, or durable Gmail worker is introduced.

Notifications are untrusted hints even after structural/address/subscription
matching. Cryptographic Pub/Sub authentication is deliberately not implemented
here. A later ingress must verify JWT signature, issuer, audience and service-account
identity and authorize the subscription before enqueueing a bounded sync job.
Notification history IDs must never advance the database checkpoint.

Rollback: stop callers and remove this unused adapter; no persistent state changes
or provider compensation exist. Later worker integration requires separate ADR,
inventory reconciliation, checkpoint/crash tests and disposable-account approval.

Sources: [history API](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.history/list),
[synchronization guide](https://developers.google.com/workspace/gmail/api/guides/sync),
[push guide](https://developers.google.com/workspace/gmail/api/guides/push).
