# iCloud / IMAP read contract

Status: an injected-session library with offline tests, not an enrolled iCloud
connector. [ADR-022](adr/022_imap_read_contract.md) records scope and rollback.
Implementation: [`imap.py`](../src/email_brain/connectors/imap.py).

## Implemented

The caller supplies an exclusively borrowed IMAPClient-compatible session with
UID mode enabled. The adapter never creates sockets, authenticates, installs a
package, writes flags, moves mail, sends mail, or expunges. It selects folders with
`readonly=True`; it rejects an explicit read-write result. IMAPClient provides this
API and returns UID-indexed fetch mappings when UID mode is enabled.
[IMAPClient API](https://imapclient.readthedocs.io/en/3.0.1/api.html).
Its parser consumes the UID field into the outer dictionary key and retains SEQ
inside the row. The adapter accepts that shape; an optional retained inner UID
must agree with the outer key. [IMAPClient parser source](https://github.com/mjs/imapclient/blob/3.0.1/imapclient/response_parser.py).

Every reference contains folder, UIDVALIDITY and UID. Mutable message sequence
numbers are ignored. The adapter verifies validity before and after inventory and
body operations, and forgets all local state after transport failure, protocol
failure, explicit reset or reselection. Sharing/reselecting the underlying session
outside this adapter is unsupported: the caller must preserve exclusive ownership.

MIME reads first request size, then bounded `BODY.PEEK[]<0.N>` with an extra byte
to detect size inconsistencies. Complete byte count and UID must agree. Flags are
read, not changed. Original MIME remains untouched for the evidence pipeline;
empty MIME is returned for that pipeline to quarantine. BODY.PEEK avoids implicit
Seen changes. UID identity is only valid within the same mailbox and UIDVALIDITY.
[IMAP protocol](https://www.rfc-editor.org/rfc/rfc9051.html).

## Inventory, expunges and moves

Selection captures UIDNEXT minus one as a fixed high-water UID. Inventory scans
numeric windows of at most 1,000 UIDs, without wildcard/reversed ranges. Each page
must exactly follow the preceding local cursor. Limits are 10,000 recorded UIDs
and 4,096 windows per inventory; exceeding either discards incomplete state and
produces no absence certificate. These are prototype budgets, not mailbox capacity
claims. Sparse high-UID folders can exhaust the window budget with few messages.

Only a completed inventory can produce absent-UID candidates. Certificates are
bound to the exact local client generation and cannot survive reselection or
disconnect. Known references must match folder/validity; UIDs above the captured
high-water mark are never considered absent. Missing FETCH rows are separately
reported as unavailable, not converted to deletion.

An expunge during scanning may remain in an already-read page until the next
reconciliation. New arrivals beyond the high-water mark wait for the next scan.
This favors stale presence over false absence. Absence means this folder/UID no
longer contains the item, not global destruction or permission to erase evidence.
Moves generally require delete/add correlation across folders; that worker logic
is not implemented. No durable checkpoint or database tombstone is written here.

## Transport and deployment gates

Apple documents iCloud's IMAP host `imap.mail.me.com`, port 993 and SSL, with
account-specific authentication requirements. This library does not connect to
that host or manage its credentials. [Apple server settings](https://support.apple.com/en-us/102525).

Before live activation the caller must enforce verified TLS, approved host/account
binding, secret storage, finite connection/read timeouts, request deadlines and
hostile-server response/literal limits. An IMAPClient-style API materializes parsed
responses before returning them: this adapter's post-response byte validation
alone is **not** a hard network memory bound. Partial PEEK requests reduce expected
body size but do not constrain a malicious server's wire behavior.

Remaining work includes a pinned mature IMAP implementation, consented enrollment,
folder discovery/Unicode naming acceptance, persisted UIDVALIDITY-scoped leases
and cursors, metadata/flag reconciliation, backfill budgets, IDLE hint scheduling,
credential recovery, and disposable-mailbox acceptance. No SMTP path exists.

## Testing, telemetry and rollback

Fake sessions exercise selection mode, sequence/UID confusion, UIDVALIDITY races,
UIDNEXT regression, cursor replay, incomplete inventories, new arrivals, expunges,
size limits, malformed response fields, disconnect scrubbing and no-write commands.
The adapter exposes typed failures and no logging. A future worker should count
outcomes/pages without logging folder names, raw bytes, flags or credentials.

Rollback is to stop using the additive library. No migrations, installed dependency,
mailbox side effects or persisted state were introduced. Retain any future evidence
and checkpoint records rather than treating rollback as permission to delete them.
