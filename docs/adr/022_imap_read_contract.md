# ADR-022 — Injected read-only IMAP contract

Accepted 2026-09-20 for a synthetic-tested library only. No socket, password,
dependency installation, mailbox enrollment, database migration or worker activation.

Use a caller-owned, exclusively borrowed IMAPClient-compatible UID session. Select
folders read-only and request MIME with BODY.PEEK, never mutating flags or expunging.
Scope every UID to a folder and UIDVALIDITY. Reset local selection and incomplete
inventory on disconnect, reselection or protocol failure.

Enumerate bounded numeric UID windows below the selection's UIDNEXT high-water
mark. Only a fully traversed, same-validity inventory may report absent previously
known UIDs. Partial scans and missing FETCH rows never authorize tombstones.
Certificates and cursors are process-local; durable replay remains worker work.

Raw fetches use size preflight and bounded partial BODY.PEEK, with explicit complete
byte-count validation. The injected library materializes protocol responses, so
hostile-wire byte enforcement, TLS verification and timeouts remain transport gates.

Tests cover UID resets, incomplete inventories, mutable sequence numbers, malformed
responses, bounded fetches, expunge races and no-write behavior. Rollback is simply
stop using this additive library; no provider compensation or down migration.

Sources: [IMAPClient API](https://imapclient.readthedocs.io/en/3.0.1/api.html),
[IMAP standard](https://www.rfc-editor.org/rfc/rfc9051.html),
[Apple iCloud settings](https://support.apple.com/en-us/102525).
