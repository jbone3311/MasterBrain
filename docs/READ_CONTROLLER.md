# Bounded read-worker operator

Implemented under [ADR-039](adr/039_read_worker_controller.md). Exact verification
is recorded in [BUILD_RECEIPT.md](BUILD_RECEIPT.md). Tests use fictional HTTPS
responses and disposable SQL, not a live Fastmail mailbox or cloud deployment.

## Purpose and authority

`sync-read` runs the existing [read worker](READ_WORKER.md) for one already
configured Fastmail account. It adds no enrollment, token discovery, OAuth flow,
provider writes, background service installation or administrative pause reset.
`--allow-provider-read` must be supplied for execution; it is an invocation guard,
not permission from the owner to connect a real account. Obtain that permission
and complete the live-pilot gates before using real credentials.

This is distinct from `process-jobs` (approved MIME recovery) and
`process-documents` (approved synthetic PDFs). Its worker identity has **exactly
`email.ingest`**, never combined search/review/processing scopes. It still uses
the owner-bound prototype database role; hosted service principals remain a gate.

## Private configuration

Keep configuration, registry, worker token, provider token, keyring and objects
outside Git/Dropbox in owner-only directories (`0700`), files `0600`. Paths must
be absolute, with no symlink traversal. The runtime DSN comes separately from
`EMAIL_BRAIN_DSN`, never a CLI argument or printed configuration. Do not use the
migration administrator as the runtime user.

Illustrative shape only, not an enrollment recipe or real credential:

```json
{
  "version": 1,
  "job_kind": "fastmail-read",
  "account_id": "00000000-0000-4000-8000-000000000001",
  "provider_account_id": "fictional-provider-account",
  "provider_secret_ref": "synthetic:fictional-reference",
  "credentials_file": "/private/operator-state/read-credentials.json",
  "token_file": "/private/operator-state/read-worker-token",
  "provider_token_file": "/private/operator-state/provider-token",
  "max_raw_bytes": 1048576
}
```

The account UUID, provider account ID and secret reference must match the existing
active Fastmail row. A secret reference is compared, not resolved through a vault
or interpreted as a path. The separate private provider-token file supplies the
actual token. Session discovery must match the pinned provider account before
mail is fetched. The transport retains its fixed Fastmail HTTPS host/read-method
allowlist; no endpoint/proxy/transport configuration is exposed by this command.
Fastmail token permissions may exceed the adapter's allowed methods; do not infer
a provider-side read-only scope from this code's read-only behavior.

Optional encrypted preservation requires **all three** `blob_root`, `keys_file`
and `active_key_id`. The existing private root must already exist. The keyring
shape is `{"tenant_id":"<UUID>","keys":[{"key_id":"<ID>","key_hex":"<64 lowercase hex>"}]}`.
IDs must be unique, tenant must match, and the active key must exist. This selects
an encryption write key, unlike the read-only key maps used by processing commands.
Retain prior keys for historical reads/restore. Never put an actual key in Git.

The download bound is 1–16 MiB, with values above 1 MiB requiring encrypted storage.
With object storage the worker uses one-ID pages; the configured transport bound
still applies to each download. Larger preservation is not larger parser permission:
mail above the ordinary 1 MiB parser budget remains held. No PDF/model execution.

## Check, run and stop

```sh
email-brain sync-read --config /private/operator-state/read.json --check
```

Preflight reads configuration/credentials, checks current ownership, enrollment,
runtime role and keyring/root. It performs **zero provider requests and zero lease
claims**, writes no enrollment/checkpoint/object and constructs no HTTP client.
`configuration_valid` is not a provider-login, connectivity, full-key-recovery or
hosted-security certificate. A paused worker may pass preflight and still need repair.

After separately authorized enrollment and acceptance, an explicit bounded run is:

```sh
email-brain sync-read --config /private/operator-state/read.json --allow-provider-read --max-iterations 10 --idle-seconds 5
```

Iterations default to 1, range 1–1000; wait defaults to 5 seconds, range 1–60.
Each step remains subject to the existing database retry deadline/lease/pause.
`not_due` does not call the provider and does not mean the mailbox is current.
SIGINT/SIGTERM stop subsequent steps; the in-flight cooperative bounded page can
finish. This is neither a forever-running supervisor nor a hard network kill.

Output contains fixed counts only: `progress`, `caught_up`, `retry`, `not_due`,
`lease_lost` (another worker replaced this lease mid-step; nothing was published
or recorded), `paused`, `auth_required`, `protocol_error`, `parse_error`,
`resync_required`, plus
poll count, stop and attention flags and `mailbox_effects: false`. An already paused
account increments `paused` without executing a step, so that count is separate
from `polls`. No bodies, IDs, tokens, paths, DSNs or exception strings are printed.

Exit 0 means a preflight/bounded run completed, **not** that backfill is complete;
read the counters and owner sync status. Exit 2 means a persisted pause needs
operator attention. Exit 1 is a scrubbed configuration/authorization/operation
failure. Retry outcomes stay scheduled in SQL; supervisors must inspect counters
and database state rather than interpreting exit 0 as healthy mail coverage.

## Revocation and recovery

Worker identity/expiry and account/provider/secret binding are rechecked around
HTTP requests and before ingestion. Provider token bytes are pinned for one step;
mid-step rotation stops it without publishing that page. Same-identity worker and
provider-token rotation can be loaded at the next step/run. Keyring reload occurs
between steps; changing the config itself, including active key, requires restart.

Private-file revocation is not atomic with SQL commit and cannot retract an
already committed page. Existing current-owner/account and lease fences remain
authoritative. A guard failure can leave its lease to expire normally (90 seconds),
not create a malformed-MIME pause. Do not manually advance a cursor or reset a
pause/lease to make a test look healthy. Administrative enrollment/resume remains
a separately audited workflow to implement.

Existing `sync_runs` and audit events supply content-free outcomes; page evidence
and cursor commit atomically, while the final run receipt is a separate transaction.
Crash after commit can therefore leave missing operational telemetry but durable
progress. Restart uses the stored checkpoint; no new controller checkpoint file.

## Deployment and rollback

No migration, dependency or SQL grant change. Apply the repository's full migration
set/grants using the existing administrator workflow. API and processing-worker
permissions do not expand. Keep this command's provider token out of the API and
document/MIME workers. Stop the command to disable reads, preserve objects/keys and
checkpoints, and deploy only a checkpoint-compatible worker; no down-migration.

Tests cover configuration, private files, scopes, flag/preflight, stop, token changes,
scrubbed output, actual fake-HTTPS-to-SQL restart/search, pauses/retries, source
binding/lease loss and encrypted large messages. Hosted supervision, explicit
service identity, enrollment/resume UX, alerts, OIDC, cloud storage/key recovery,
disposable live acceptance and sustained soak are still required.
