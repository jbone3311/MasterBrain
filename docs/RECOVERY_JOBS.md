# Durable approved MIME processing

[ADR-030](adr/030_durable_recovery_jobs.md) connects the restricted MIME processor
to a durable request queue. This is an opt-in local/CI workflow, **not hosted
authentication or an automatically provisioned worker**. It does not send, delete,
move or label provider mail, call a model, scan malware or extract binary documents.

## End-to-end flow

1. An operator builds/reviews a local image and fixes its full SHA-256 identity.
2. Configure the API with `recovery_parser_version` equal to the processor's exact
   `sandbox-mime-v1-<64 hex>` version. The developer `serve` command supports
   `--recovery-parser-version`. It defaults to disabled. This value is provenance,
   not a command, image tag or evidence of worker availability.
3. The owner obtains current quarantine metadata and processing capabilities,
   then explicitly approves one receipt with an expected parser and idempotency UUID.
4. A separately configured trusted controller calls `RecoveryJobs.run_once` using
   a worker principal, explicit account and `DockerMimeProcessor`. The API itself
   needs neither Docker access nor encrypted object keys to enqueue/check jobs.
5. The worker reads retained evidence, verifies its hash, runs the restricted parser,
   and atomically commits evidence, a recovery attempt and job completion.
6. The API status reports the outcome. Recovered body/plain/calendar text is
   searchable through existing evidence endpoints. Deferred binary receipts remain
   visibly incomplete; job completion is not proof that every attachment was read.

No daemon loop or secret enrollment is implied by `run_once`. A supervisor should
invoke bounded iterations for explicitly configured accounts, respecting durable
retry deadlines. Hosted identity, controller hosting, credential provisioning,
supervision, UI job controls and operational acceptance remain work to do.

## API contract

| Request | Authority | Result |
|---|---|---|
| `GET /v1/accounts/{account}/processing` | owner + evidence scope | `enabled`, `parser_version`, `worker_online: null` |
| `POST /v1/accounts/{account}/quarantine/{receipt}/jobs` | human owner + review/evidence scopes | 202, bounded job status |
| `GET /v1/accounts/{account}/processing/{job}` | owner + evidence scope | durable status |
| `POST /v1/accounts/{account}/processing/{job}/cancel` | human owner + review/evidence scopes | cancelled status, or unchanged terminal result |

Approval body contains only `expected_parser_version`; the `Idempotency-Key` header
is a UUID. Foreign tenant/account IDs return 404. Missing scopes return 403.
Disabled enqueue, wrong version, stale source or conflicting key reuse returns 409.
The same actor/key/request returns the same job rather than creating another approval.
At most 100 unfinished jobs per account are admitted under the account lock.

Public status contains job/account/receipt IDs, parser, state, claim count,
creation/approval-expiry/retry/completion times, recovery attempt ID, fixed outcome
and `mailbox_effects: false`. It never contains raw mail, object paths, lease tokens,
worker identity, credentials or subprocess exception text.

## Approval versus login

Submitting the request creates a one-hour durable approval, not a saved login token.
Expiry of the submitting bearer token does not cancel a submitted job. Explicit
cancellation, removing the requesting owner's membership, disabling the account,
changing/deleting the source message or approval expiry prevents new publication.
The worker also needs a current owner-bound bootstrap identity with the worker-only
`email.process` scope; a human/assistant credential cannot claim jobs.

Production service-principal grants and OIDC are not implemented here. The server
reconstructs only the exact saved human delegation inside the trusted controller,
never from arbitrary worker-provided human IDs or request payloads. All tenant
tables retain forced RLS. Runtime credentials still must not own tables or bypass RLS.

## Reliability and revocation

States: `queued`, `running`, `retry_wait`, `completed`, `cancelled`, `expired`,
`failed`, `stale`, `revoked`. Completion means a deterministic recovery outcome:
`recovered`, `mime_rejected` or `integrity_failed`. Infrastructure failures instead
retry after 60 seconds per claim, up to three claims. A controller crash leaves a
120-second lease; another controller can reclaim it with a new random token.
Expiry and third-claim exhaustion terminate without a fourth parse.

Job-row fencing, database wall time and account/current-source checks protect both
new and cached recovery. A narrow audited SQL helper locks the two existing owner
memberships and active account against revocation until publication commits, without
granting runtime permission to edit memberships/accounts. The final fence is in
the same transaction as evidence and completion; stale work cannot mark success.
No SQL transaction is held open while parsing untrusted MIME.

## Operations, testing and rollback

Audit event names/outcomes are content-free. Check durable status and retry times;
do not increase budgets, substitute a new image for the approved parser, alter SQL
leases manually or reapprove failures in an unbounded loop. Investigate repeated
`infrastructure_unavailable` outcomes on the isolated worker, with content-free logs.
Cancelled or expired work requires a new explicit approval/idempotency key if needed.

The test suites cover real PostgreSQL authorization, idempotency, cancellation,
fencing, crash/retry limits, source changes and API contracts. The explicit container
suite adds actual API approval -> encrypted source -> restricted image -> completion
-> search. Restore includes completed, cancelled and pending approvals, with exact
SQL hashes and cross-tenant status denial; its synthetic processor is not itself
an isolation test. See [build receipt](BUILD_RECEIPT.md) for executed verification.

Rollback: disable new approvals, stop trusted controllers, preserve migration 0010,
jobs, audit and evidence. Existing job status/cancel remains available without an
enabled parser. Do not downgrade the schema or reroute approved jobs to another
image. Restored pending approvals retain their original expiry; restoring a backup
does not renew consent. Restore with controllers stopped until state is reviewed.
