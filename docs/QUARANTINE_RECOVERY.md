# Held-message recovery

An explicit trusted worker can now use an [isolated image-bound MIME processor](ISOLATED_MIME_RECOVERY.md)
for retained mail up to 16 MiB. This is an operator/library path, not an HTTP image
selector; the default UI/API behavior below stays at 1 MiB. Successful isolated
recovery creates separately versioned evidence and leaves binary attachments deferred.

The local owner review screen can retry parsing one current held message from its
retained MIME. This does not contact a provider, accept invitations, scan malware,
execute binary attachments, run a model, or modify the source mailbox.

With [encrypted storage](LARGE_EVIDENCE_STORAGE.md), migration **0009** is also
required. Retained mail above the parser's 1 MiB limit stays held as
`mime_too_large`; retry returns 409 without an attempt. Missing backend/key/object
or encrypted integrity failure returns 503 `evidence_storage_unavailable`, also
without a cached attempt. Restore storage before retrying. Existing inline evidence
continues to use the checks below; no raw-download endpoint is introduced.

## Operator workflow

1. Sign in with a human owner bootstrap credential carrying `email.review` and
   `email.evidence.read` (plus `email.search` for the status screen).
2. Refresh the account's held-message list. It displays the deployed retry parser.
3. Explicitly click **Retry parsing** for a receipt. The original bytes are hash
   checked, then the bounded parser runs independently of synchronization.
4. Refresh/search after a successful outcome. A failure stays held; same-version
   retries return the stored attempt, rather than repeatedly processing poison mail.
   A corrected parser must ship with a new version before another attempt.

`recovered` means that attempt published a projection. It is a historical outcome,
not a promise that no newer provider update/deletion has since arrived. The screen
refreshes current account state after the response. `mime_rejected` means parsing
still failed; `integrity_failed` means retained bytes failed the size/hash checks.
Never bypass integrity failure by rewriting a hash. Escalate to the operator and
restore/integrity investigation; preserve evidence. Unexpected parser failures
return a scrubbed 503 and leave no partial publication.

## API

`GET /v1/accounts/{account_id}/quarantine` still returns bounded metadata only.
It now includes `reprocessing: true` and `retry_parser_version` at the top level.

`POST /v1/accounts/{account_id}/quarantine/{receipt_id}/retry` accepts only:

```json
{"expected_parser_version":"stdlib-mime-v5"}
```

The example version is not a permanent API constant: use the version from the
refreshed list. It cannot select arbitrary code. Human identity and both scopes
are checked in the API/library, and owner membership in each database transaction.
The natural idempotency key is `(tenant, receipt UUID, parser version)`; no separate
client key is needed. The returned attempt includes its ID, receipt, parser,
fixed outcome, optional immutable evidence ID, timestamp, `historical_outcome: true`
and `mailbox_effects: false`. No raw bytes or exception text are returned.

Missing/foreign/inactive account or receipt: 404. Missing scope/human membership:
403. Changed parser or superseded/non-current receipt: 409. Invalid schema: 422.
Unexpected parser failure: 503. A previously completed request can return its
historical result after later provider changes; it never re-applies that result.

## Concurrency and evidence

Parsing happens outside transactions. Publication takes the same account lock as
ingestion and verifies the latest provider event still identifies this quarantine.
Provider deletion, newer mail or reconciliation during parsing prevents publication.
Membership/account activity is rechecked. No worker lease, sync cursor, raw object,
provider event or historical quarantine receipt is updated by recovery.

Each successful parser version has its own immutable evidence/attachment receipts.
Same-parser, same-byte recovery reuses existing evidence, rejects output drift,
and does not duplicate intake receipts. Current search matches raw hash **and**
parser version; historical citations retain their old content. Old quarantines
without source metadata publish thread/folder/keyword metadata as unknown rather
than copying a stale message projection.

## Migration and rollback

Stop old API/worker binaries, apply migration **0008**, and reapply runtime grants.
The migration preserves old snapshot UUIDs and adds generated parser provenance,
version-aware uniqueness, captured quarantine metadata and immutable RLS-protected
`recovery_attempts`. It refuses pre-existing mismatches between current and stored
parser provenance; these need a separately reviewed evidence repair, not a blind
UPDATE of historical records.

Pre-0008 binaries are incompatible with the new uniqueness key. Disable the retry
route if needed and use a forward-compatible release; do not run old workers or
delete migration/history. Reversing a successful recovery, bulk historical
reprocessing, binary extraction and hosted operational acceptance remain future
work. This feature is not a production-launch certificate.

See [ADR-027](adr/027_quarantine_recovery.md), [security](SECURITY.md),
[restore drill](RESTORE_DRILL.md), and [implementation status](IMPLEMENTATION_STATUS.md).
