# ADR-030 — Durable human-approved isolated MIME jobs

## Decision

Connect ADR-029 to an opt-in database-backed job channel. The API may enqueue a
human-approved retained-message retry, but never imports a Docker controller,
receives an image choice from mail, or receives daemon privileges. Operator
configuration supplies one exact `sandbox-mime-v1-<64 lowercase hex>` version.
The request echoes that version and carries a UUID idempotency key. Default API
configuration leaves this channel disabled; ordinary synchronous retry is unchanged.

Approval is a durable, one-hour grant for one tenant/account/receipt/parser, not a
saved bearer credential. Both review and evidence scopes and current human owner
membership are required. Token expiry after submission does not retract an already
approved job: explicit cancellation, membership revocation, account disablement,
receipt replacement/deletion, approval expiry or lease loss prevent publication.
No worker may create approval by presenting its own worker credential as a human.

## Storage and authorization

Migration 0010 adds tenant-RLS `recovery_jobs` with immutable approval identity,
tenant/account/receipt composite references, actor-bound idempotency key, parser,
created/expiry timestamps, status, lease token/deadline, worker actor, attempts,
retry deadline and optional immutable recovery-attempt link. Runtime has no DELETE.
An immutable trigger protects approval fields; mutable execution state is checked
in SQL and service code. Enqueue/cancel/claim/retry/completion append content-free
audit events. API output excludes lease tokens, worker credentials and raw content.

PostgreSQL row-share locking requires UPDATE permission, which runtime must NOT
have on memberships/accounts. A narrow SECURITY DEFINER boolean helper locks only
the explicitly specified account and two owner memberships within the transaction's
tenant. It uses a fixed `pg_catalog` search path, fully qualified table names,
UUID-only parameters, deterministic membership lock ordering and no dynamic SQL,
data return or mutation. PUBLIC execution is revoked; runtime receives only EXECUTE.
This prevents admin revocation/disablement racing final publication without giving
the runtime authority to grant itself membership. A compromised arbitrary-SQL
runtime remains outside the RLS threat boundary, as documented in SECURITY.md.

Natural recovery idempotency remains receipt/parser; job request idempotency is
tenant/requesting actor/key. Conflicting reuse is 409. At most 100 nonterminal jobs
per account are admitted under the existing account lock. No bulk approval.

## Worker

A separately configured trusted controller runs bounded `run_once` with a worker
principal having `email.process`, current owner membership, and an explicit account
binding. It uses a configured processor whose version must match the job channel.
There is no HTTP claim/execute endpoint and no discovery of tenants, secrets,
accounts, images or Docker sockets from job payloads. Production service-principal
roles remain a separate deployment gate; owner-bound bootstrap workers are local/CI.

Claims use database time, `FOR UPDATE SKIP LOCKED`, random lease tokens, a 120-second
lease and at most three claims. Expired leases may be reclaimed; infrastructure
failure backs off 60 seconds per attempt, then fails. Expired approvals and exhausted
crash attempts terminate without parsing. Each invocation does at most one job.
Unavailability is not deterministic MIME rejection and cannot cache an attempt.

Recovery rechecks the job and both actors before reading/processing and publication.
The job row is locked only within short database transactions, never during parsing.
Its final lease/approval check and completion update share the transaction with
evidence publication and immutable recovery attempt. Cancellation or replacement
of the lease fences stale workers; a crash after commit leaves a completed job and
replay cannot duplicate evidence. Existing provider-current and account fences stay.

## API

- `GET /v1/accounts/{account_id}/processing`: evidence scope, reports configured
  parser or null and disabled/enabled status; does not attest a worker is online.
- `POST /v1/accounts/{account_id}/quarantine/{receipt_id}/jobs`: human review plus
  evidence scopes, `expected_parser_version`, UUID `Idempotency-Key`; returns 202.
- `GET /v1/accounts/{account_id}/processing/{job_id}`: evidence scope, bounded status.
- `POST /v1/accounts/{account_id}/processing/{job_id}/cancel`: human review plus
  evidence scopes, cancellation of an unfinished job; terminal jobs are unchanged.

Unknown/foreign accounts/jobs remain 404. Disabled channel, wrong parser or stale
receipt returns 409. Output contains no source mail, storage references or failures'
exception text. The UI and scheduler integration may follow this executable API.

## Verification and rollback

Test real PostgreSQL RLS, approval immutability, concurrent claim/idempotency,
cancellation/revocation/provider-change during parsing, expiry/lease loss, three
crashes/retries, parser drift, exact provenance and atomic completion. Add actual
container -> encrypted evidence -> API/job -> search coverage in CI. Restore must
include queued/completed/cancelled jobs and verify restored authorization/state.

Rollback disables enqueue and stops controllers. Preserve jobs, audit and evidence;
never down-migrate or execute old pending work under a different parser image.
No cloud account, live mailbox, send/delete, binary extractor or model is enabled.
Hosted OIDC, queue supervision, separate service identities, signed images, scanning
and cloud operational acceptance remain required.

Sources: [PostgreSQL locking SELECT](https://www.postgresql.org/docs/17/sql-select.html),
[RLS](https://www.postgresql.org/docs/17/ddl-rowsecurity.html),
[date/time functions](https://www.postgresql.org/docs/17/functions-datetime.html).
