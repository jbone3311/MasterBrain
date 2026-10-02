# Running the approved-processing worker

Updated 2026-09-20. [ADR-032](adr/032_operator_processing_controller.md).
This is an executable **local/synthetic operator workflow**, not hosted deployment
or live-mail authorization. It turns the [durable job library](RECOVERY_JOBS.md)
into an explicitly configured command. It never creates approvals or connects mail.

This guide covers **MIME recovery only**. ADR-036's separate
[`process-documents` command](DOCUMENT_CONTROLLER.md) requires a different fixed-purpose
configuration and exactly `email.document.process`. Do not add both scopes to a
worker or select a PDF image for this MIME contract. Shared file/polling helpers do
not merge approvals or processor interfaces.

## Prerequisites and privilege separation

- Migrated disposable PostgreSQL with an existing active account and owner membership.
- Non-owner/non-superuser/non-BYPASSRLS runtime DSN in `EMAIL_BRAIN_DSN`.
- A separate worker token/registry entry: `client_kind: worker`, exactly
  `scopes: [email.process]`, existing tenant/owner IDs and a future explicit expiry.
  The demo's human token is intentionally insufficient. Worker/service-principal
  enrollment is not automated; a trusted operator supplies this bootstrap identity.
- An approved, already-built immutable local image ID, matching the API's configured
  `sandbox-mime-v1-<full hash>` parser. Tags/pulls are not supported.
- Trusted Linux controller host with Docker at the configured absolute binary path
  and local UNIX socket `/var/run/docker.sock`. Never give the API or parser that
  socket. [Isolation contract](ISOLATED_MIME_RECOVERY.md) explains resource limits.
- For external source objects: original encrypted objects and independently retained
  tenant keys. A fresh unrelated key cannot recover old evidence.

Put configuration, registry, token and keys in existing **0700 directories**, each
file **0600**, owned by the controller OS user. Use absolute canonical paths with
no symlink components; hard-linked secret files are rejected too. Keep all of them
outside Dropbox and the source checkout. Files are bounded to 64 KiB, token to
512 ASCII characters plus an optional final LF. Use a cryptographically random
token (at least 32 characters); store its SHA-256 digest in the registry, not the
token itself. Never paste real values into Git, terminal arguments or logs.

## Configuration contract

Example shape only—replace the fictional UUID and paths privately. All fields are
closed; there is no shell command, environment interpolation or mail-selected path.

```json
{
  "version": 1,
  "account_id": "00000000-0000-4000-8000-000000000001",
  "image_id": "sha256:<64 lowercase hexadecimal characters>",
  "docker_binary": "/usr/bin/docker",
  "credentials_file": "/srv/email-brain-private/worker-credentials.json",
  "token_file": "/srv/email-brain-private/worker-token.txt",
  "blob_root": "/srv/email-brain-private/objects",
  "keys_file": "/srv/email-brain-private/keys.json"
}
```

Omit **both** `blob_root` and `keys_file` only when approved sources are stored
inline in SQL. External objects without their configured backend cannot process.
Keyring shape (placeholders, not usable key material):

```json
{
  "tenant_id": "00000000-0000-4000-8000-000000000002",
  "keys": [{"key_id": "original-key-id", "key_hex": "<64 lowercase hex characters>"}]
}
```

The tenant must match the authenticated worker. Duplicate key IDs fail. Multiple
historical keys are allowed (up to 100); this read workflow selects no active
encryption/write key. The original object manifests select the required keys.
The registry is the existing list of [bootstrap credentials](../src/email_brain/auth.py),
with token digest, tenant/actor, exact processing scope, worker kind and expiry.

## Check, run, stop

With `EMAIL_BRAIN_DSN` supplied through the trusted process environment:

```sh
email-brain process-jobs --config /srv/email-brain-private/controller.json --check
email-brain process-jobs --config /srv/email-brain-private/controller.json
email-brain process-jobs --config /srv/email-brain-private/controller.json --max-iterations 60 --idle-seconds 5
```

`--check` reads config/credentials/optional keys, verifies current owner/account
through the runtime SQL role and validates the existing private object root. It
does **not** claim a job, parse mail, launch Docker, test an image, decrypt all
objects or certify operational readiness. Output explicitly says
`execution_verified: false`. No missing directories or credentials are created.

For the synthetic opt-in tenant-login fence (ADR-141), supply a DBA-enrolled
single-tenant login as `EMAIL_BRAIN_DSN` and add `--tenant-bound-db` to both
`--check` and execution. The authenticated `email.process` worker tenant,
never the account or job, selects the binding. Shared, owner and wrong-tenant
logins fail before a claim or parser launch; optional encrypted storage uses
the same bound store. Default local mode is unchanged. A passed check is not
hosted credential, container or live-source acceptance. See the
[tenant-login contract](TENANT_LOGIN_FENCE.md).

Default execution polls once. `--max-iterations` accepts 1–1000; `--idle-seconds`
accepts 1–60 and is used **between** polls, including successful polls. Durable
retry deadlines and 120-second leases stay in SQL; sleeping holds no transaction.
An explicitly configured supervisor may reinvoke bounded commands, but no service
is installed/enabled here. One invocation has one account and one fixed parser.

SIGINT/SIGTERM stop new claims and let already-started bounded work finish/clean
up. A signal is not job cancellation; use the owner cancellation API for that.
Hard-killed controllers can leave leases and owned containers: inspect the exact
owned container using the isolation runbook; never prune unrelated resources.
After lease expiry, restart can reclaim only still-approved work. Existing queue
fences prevent stale workers from publishing. Do not reset attempts/expiry manually.

## Results, revocation and incidents

Exit 0 prints JSON with polls, counts of fixed job states, `stopped`, and
`mailbox_effects: false`. `completed` means a persisted processing outcome, not
necessarily recovered text or complete attachments. Inspect job/part history.
`no_result` is **not queue depth or an empty-queue guarantee**: work may be delayed,
leased, assigned another parser, or authorization may have changed.

Exit 1 suppresses configuration/SQL/parser exception details. It does not mean
nothing committed: inspect durable history before retrying. A processing failure
recorded as `retry_wait` is a normal result, not a successful extraction; supervisors
must inspect counts/status instead of relying only on exit 0. No mail, source IDs,
paths, tokens, keys or DSNs are printed. Structured error categories/host metrics
and hosted alerts remain future work.

The controller reopens registry/token files before every poll and before/after
actual parsing; removal, expiry, broad scopes or changed tenant/actor fail closed.
Registry changes take effect without restarting this command (unlike the API's
startup registry). Credential rotation to the same owner/scope is allowed.
The config and encryption keys are fixed per invocation; restart to change them.
File revocation cannot be atomic with a SQL commit. Database owner/account
revocation and explicit job cancellation remain transaction-fenced controls.
Same-OS-user/privileged host compromise is outside the private-file boundary.

On repeated failure: stop supervisor invocations, disable new approvals, inspect
content-free job outcomes, confirm exact image/keys and current grants, then run
the synthetic acceptance tests. Never increase limits, swap parser identities,
reapprove indefinitely or grant administrator SQL access as a workaround.

## Verification and rollback

[Unit tests](../tests/test_processing_controller.py) cover private files/config,
identity, counters, stop signals and redaction; [database tests](../tests/test_processing_controller_postgres.py)
cover actual ownership, approval preservation, execution/restart and revocation.
The explicit [container suite](../tests/container_mime_checks.py) runs a fresh CLI
process from check through encrypted source/actual restricted image to searchable
evidence, then restarts without duplicate work. These use fictional mail only.
Exact executed results belong in [build receipts](BUILD_RECEIPT.md).

Rollback stops invocations and new approvals while preserving jobs, evidence,
keys, audit and schema. No migration is added. Hosted supervisor deployment,
OIDC/service principals, KMS, scanner/binary extraction, real accounts and soak
acceptance remain gates. This command does not claim the product runs unattended
in production.
