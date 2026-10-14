# Read worker: implemented contract and remaining gates

This library now has a separate [bounded operator command](READ_CONTROLLER.md),
`sync-read`, with private preflight and explicit execution. Tests use synthetic
HTTP and real PostgreSQL; the command is not live-accepted or a hosted supervisor.
ADR-176 adds a distinct synthetic-only scoped library mode: version-4 cursors
bind the exact mailbox/date filter, repeated filtered inventories replace
account-wide changes, and every metadata row is checked before bytes. It is not
wired to `sync-read` or a database enrollment fence, so no real folder/date
pilot is authorized. The rest of this document describes the existing
account-wide operator.
The library does not
discover credentials, enroll accounts, start a background process or contact a
mailbox on installation. A caller explicitly supplies a read client and a trusted
tenant/owner context with `email.ingest`. No provider write method exists.

## Progress and failure model

1. Acquire a tenant/account lease using the database clock. A configured active
   Fastmail account must have an administrator-set `provider_account_id`.
2. Load the versioned checkpoint and discover the session; reject account mismatch
   before fetching mail. Missing binding is not automatically populated from a token.
3. First step stores an Email-state baseline. Subsequent steps list up to 50 IDs
   in explicit ascending `receivedAt` order, paged by `anchor` from the last
   committed ID, fetch metadata and raw MIME, normalize/index and commit evidence
   plus checkpoint. A page commits the prefix it fetched once the 16 MiB byte
   budget or a 40-second fetch budget would be exceeded; the next step continues
   from the last committed ID. If a valid metadata batch exceeds the separate
   1 MiB control-response limit, its IDs are bisected and validated before
   the page commits. A malformed response or unsplittable single row does not
   advance the cursor.
4. Mail created or destroyed elsewhere in the mailbox does not move the anchor, so
   listing neither restarts nor skips. Only a deleted anchor (`anchorNotFound`)
   restarts listing in a fresh inventory generation **without replacing the
   original Email baseline**; deletions during listing are replayed from that
   baseline afterwards. A stored positional (version 2) listing checkpoint is
   relisted the same way. See [ADR-110](adr/110_fastmail_sync_resilience.md).
5. Seal the inventory with the worker's own durable count of listed IDs; the
   provider total is advisory because it moves while the mailbox changes.
   Reconcile absent local IDs in batches of eight; then replay changes from the
   original baseline. Provider mail and historical evidence are never deleted.
   An update naming an unchanged blob with a matching reported size reuses the
   retained bytes instead of downloading; ingestion still verifies the digest.
   `caught_up` means that
   page reported no further changes at that instant, not permanent consistency.
6. Record content-free outcomes and release the lease. Caught-up accounts wait at
   least 60 seconds; temporary failures use capped exponential backoff/jitter and
   bounded `Retry-After`. The step never sleeps or spins.

Explicit `notFound` in an otherwise fully accounted-for metadata response hides
that object's current search projection, just as a provider tombstone does; it may
mean inaccessible, not permanently deleted. Retained evidence is not erased. Missing
IDs without an explicit `notFound` are protocol errors, never silent omissions.

## Lease and crash guarantees

Leases last 90 seconds and renew between requests. The worker has a 60-second
step budget checked between requests; HTTP has separate connect/read timeouts and
a streamed-response deadline (checked as chunks arrive). These are cooperative
bounds, not a hard process kill. No network call runs in a DB transaction.

The commit locks and validates the current lease token and rechecks its stored
provider-account binding against current enrollment before writing. A replaced
or expired process cannot commit; direct ingestion without a token is also denied
once that account has a worker row. The DB transaction's row lock prevents takeover
during the short commit. Crash after commit/before outcome logging leaves the durable
cursor intact: the next worker resumes it after lease expiry. The page audit is
atomic with evidence; the operational outcome receipt is a separate transaction
and can be absent after such a crash. Do not treat run counts as ingestion truth.

## Limits and explicit unfinished behavior

- Default raw MIME ≤1 MiB each; cumulative page ≤16 MiB; listing pages ≤50 IDs
  split by bytes and time; change pages ≤16 IDs (1 with the 16 MiB encrypted
  store, because a change page cannot be split). Explicit encrypted Store plus
  separately configured Fastmail download supports ≤16 MiB per message with an
  unchanged 1 MiB control JSON limit and adaptive metadata batching. Provider
  sizes through 2^53−1 are accepted for accounting; above the storage budget
  they are held without allocation. Above the 1 MiB parser bound is preserved/held,
  not parsed. See [large evidence](LARGE_EVIDENCE_STORAGE.md). Binary attachments
  remain deferred.
- Auth errors pause as `auth_required`; invalid protocol pauses as `protocol_error`;
  known MIME parser rejections within the byte bound are retained byte-for-byte in
  quarantine and advance the checkpoint. Invalid updates hide old searchable
  projections but retain historical evidence; later valid input resolves current
  quarantine status without erasing receipts. A message whose reported or
  streamed size exceeds the configured storage/download budget is held as a
  `source_too_large` receipt with no retained bytes and advances the checkpoint;
  it is revisited under a larger budget at the next full listing. Blob/key/disk
  failures use bounded retry without cursor advancement. A replaced or expired
  lease returns `lease_lost` without recording an outcome. Failure telemetry omits
  bodies, tokens and exception text.
- Expired history starts a new baseline/full inventory. No missing-ID inference
  occurs until that inventory is certified complete. v1 checkpoints similarly
  restart; corrupt/unknown checkpoints fail closed. Never manually advance cursors.
- The owner-scoped sync-status endpoint exposes processing counts and worker state.
  `caught_up` is not proof all content is extracted: inspect `review_required`
  for current quarantine and per-evidence attachment accounting separately.
- Constant query churn can prevent listing completion. Scheduling/watchdog/lag alerts
  must detect this; those operational services are still pending.
- Workers currently share the owner-scoped prototype runtime role; a production
  connector service principal and separate least-privilege role remain required.
- No enrollment/retry/recovery endpoint is exposed. Operator repair must first fix
  the cause, preserve the checkpoint, verify the binding and then resume a paused
  worker under an audited administrative workflow; that workflow remains a gate.

## Migration and rollback

Apply the complete repository migration set with the
administrator migrator, then reapply the
explicit runtime grants using `grant_runtime` for the installed runtime role.
The normal API migration command does not silently expand existing role grants.
Fresh demo/CI provisioning already receives the new grants. No existing provider
binding is guessed. Existing plain prototype cursors are not interpreted as worker
checkpoints; they pause for reviewed conversion.

Stop worker callers before code rollback. Do not roll back to a version that treats
these JSON checkpoints as provider cursors. Keep the additive schema and retained
evidence; no destructive down migration. No mailbox compensation is necessary.
The API must also retain the quarantined-projection exclusion: a pre-0006 search
implementation would incorrectly show an old current projection after a failed
update. Roll back only to a forward-compatible worker and API pair.

Sources: [JMAP query-state rules](https://www.rfc-editor.org/rfc/rfc8620#section-5.5),
[Email changes](https://www.rfc-editor.org/rfc/rfc8621#section-4.2).
