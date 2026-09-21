# ADR-039 — Explicit bounded Fastmail read operator

Accepted 2026-09-21 for implementation and synthetic verification. No live-account
access, enrollment, cloud resource or new provider/SQL permission is authorized.

## Decision

Add `sync-read --config <private-file>` over the existing Fastmail `ReadWorker`.
`--check` validates local private credentials, existing active enrollment, current
owner/runtime role, configured provider identity/secret reference and optional
encrypted storage without constructing a client, claiming a lease or fetching mail.
Execution additionally requires `--allow-provider-read`; it is an explicit invocation
guard, not a substitute for owner-approved enrollment and disposable live acceptance.
No endpoint, transport, token discovery, OAuth enrollment or automatic service install.

Closed versioned configuration identifies only Fastmail, one account, expected
provider account and existing secret reference, private worker/token/provider-token
files, and optional existing encrypted object root/keyring/active key. Never accept
an image, shell command, arbitrary URL, admin credential or mailbox action. Runtime
DSN remains a separate environment variable. All files follow the existing no-follow,
owner-only bounded reader; no runtime state in the checkout or Dropbox.

Reuse private-file and identity mechanics through a narrow credential-file protocol;
the read identity must be worker-kind with exactly `email.ingest`. MIME and PDF
worker identities retain their existing exact scopes. No new scopes or grants.

## Revocation, progress and failure

- Reauthenticate before each bounded step, each HTTP request and after each request,
  and immediately before ingestion. Recheck current owner/account/provider/secret
  binding. Pin the provider token for one step; rotation during the step stops it,
  while the next explicit run/iteration can load a new token for the same identity.
- File checks cannot be atomic with SQL commit. Existing database owner/account and
  lease fences remain authoritative; file revocation prevents subsequent observed
  work but cannot retract an already committed page. No checkpoint editing or
  rollback of retained source. A guard failure may leave a lease to expire normally.
- Reuse existing database-clock retries, 90-second leases and 60-second cooperative
  step budget. Add no network transaction or alternate progress state. A bounded
  loop (1–1000 iterations, 1–60 seconds between steps) does not override `not_due`,
  retry deadlines or paused state. Stop on fixed pause outcomes; expose content-free
  counters and `attention_required`, not a false success claim about complete sync.
- SIGINT/SIGTERM stop subsequent steps; an in-flight bounded page can finish. This
  is not a hard deadline or forced cancellation. Always close the per-step client.
- Optional encrypted storage uses an explicitly selected existing active key and
  1–16 MiB download/storage bound. Larger preservation still quarantines mail above
  the ordinary parser limit. No binary-reader or model permissions are added.

## Proof, operations and rollback

Test closed config, private paths, exact scopes, flag/check behavior, counters,
stop/rotation/revocation and scrubbed errors offline. Use fake HTTPS plus real SQL
for non-consuming preflight, restart, known-answer search, provider/account drift,
lease loss, retry/pause, encrypted large evidence and no partial checkpoint on denial.
No test contacts Fastmail or uses a real token. Existing worker/container/restore
tests remain required. Record exact verification; no live acceptance inferred.

Update operator guide, command/code map, security, deployment/runbook, status and
Factory handoff together. Existing sync receipts/audit supply telemetry; no token,
source, DSN, provider ID or exception detail enters command output. No migration.
Rollback stops the command and uses a checkpoint-compatible worker; retain evidence,
keys and SQL. Hosted supervision, service identities, enrollment/resume administration,
alerts, live acceptance and soak remain separate work.
