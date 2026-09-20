# Read worker: implemented contract and remaining gates

This is a library, tested using synthetic HTTP and real PostgreSQL. It does not
discover credentials, enroll accounts, start a background process or contact a
mailbox on installation. A caller explicitly supplies a read client and a trusted
tenant/owner context with `email.ingest`. No provider write method exists.

## Progress and failure model

1. Acquire a tenant/account lease using the database clock. A configured active
   Fastmail account must have an administrator-set `provider_account_id`.
2. Load the versioned checkpoint and discover the session; reject account mismatch
   before fetching mail. Missing binding is not automatically populated from a token.
3. First step stores an Email-state baseline. Subsequent steps query at most 100
   IDs, fetch metadata/raw MIME, normalize/index and commit evidence plus checkpoint.
4. Every query page must have the same query state and total. If changed, restart
   listing at zero **without replacing the original Email baseline**. This prevents
   a deletion during listing from falling outside the later change replay window.
5. After listing, replay changes from the original baseline. `caught_up` means that
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

- Raw MIME ≤1 MiB each; cumulative downloaded page ≤16 MiB; metadata ≤100 IDs.
  A page exceeding limits pauses; adaptive sub-batching and large encrypted objects
  are not implemented. Binary attachments are still deferred.
- Auth errors pause as `auth_required`; invalid protocol pauses as `protocol_error`;
  parser failures pause as `parse_error`. Failure telemetry never includes bodies,
  tokens, provider URLs or exception text. No durable poison-byte quarantine yet.
- Expired provider cursor pauses as `resync_required`. A complete inventory-diff
  reconciler is required before restarting from a new baseline; blindly resetting
  would leave old deleted messages searchable. **Never manually advance/reset it.**
- Constant query churn can prevent listing completion. Scheduling/watchdog/lag alerts
  must detect this; those operational services are still pending.
- Workers currently share the owner-scoped prototype runtime role; a production
  connector service principal and separate least-privilege role remain required.
- No enrollment/retry/recovery endpoint is exposed. Operator repair must first fix
  the cause, preserve the checkpoint, verify the binding and then resume a paused
  worker under an audited administrative workflow; that workflow remains a gate.

## Migration and rollback

Apply all migrations through `0005_worker_status_compatibility.sql` with the
administrator migrator, then reapply the
explicit runtime grants using `grant_runtime` for the installed runtime role.
The normal API migration command does not silently expand existing role grants.
Fresh demo/CI provisioning already receives the new grants. No existing provider
binding is guessed. Existing plain prototype cursors are not interpreted as worker
checkpoints; they pause for reviewed conversion.

Stop worker callers before code rollback. Do not roll back to a version that treats
these JSON checkpoints as provider cursors. Keep the additive schema and retained
evidence; no destructive down migration. No mailbox compensation is necessary.

Sources: [JMAP query-state rules](https://www.rfc-editor.org/rfc/rfc8620#section-5.5),
[Email changes](https://www.rfc-editor.org/rfc/rfc8621#section-4.2).
