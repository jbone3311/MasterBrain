# ADR-036 — Explicit PDF operator command and channel configuration

Accepted 2026-09-21 for synthetic/local/CI execution only. This implements the
operator portion of ADR-035; owner-screen controls remain a separate increment.

## Decision

Add `email-brain process-documents` with a closed private configuration identifying
`job_kind: pdf-document`, the fixed `synthetic-unscanned-pdf-v1` policy, one account,
an immutable local PDF image ID and explicit private worker/optional object-key
paths. Neither MIME config nor MIME credentials can select this channel. Require
worker kind and exactly `email.document.process`; reject missing/broader/mixed
scopes and changes of tenant/actor during execution. No new scope or SQL grant.

Reuse the already-tested private-file, tenant-key, bounded polling and stop-signal
primitives from the MIME controller. Keep separate command/configuration and
processor constructors: no arbitrary import, command, URL or image-profile registry.
The PDF command invokes only `DocumentJobs` and the fixed `DockerPdfProcessor`.
Preflight additionally requires an active unenrolled synthetic account. Existing
job fences recheck current source, account, owners and approval/lease at execution.

`--check` validates private configuration, identity, SQL ownership/account and
optional existing object/key storage only. It claims no job, launches no container,
creates no storage/credential and explicitly reports execution unverified. Run one
poll by default, at most 1,000 with 1–60 seconds between polls. Return fixed counts;
never print document text, resource IDs, paths, DSN, keys or exceptions.

Reauthenticate before every claim and before/after extraction, including token
expiry/removal and same-identity credential rotation. File revocation is not atomic
with SQL publication; current membership/account/job-cancellation fences remain
the transactional controls. SIGINT/SIGTERM stop new claims and finish bounded
in-flight work, not cancel durable consent. Failed work can have committed a retry
or outcome: operators inspect durable history rather than infer success from exit 0.

Expose `serve --document-processor-version` as an explicit loopback bootstrap option
for ADR-035's existing API configuration. It enables no worker or Docker access,
and human approval still binds exact source/processor/policy. No automatic consent,
UI behavior, raw download, provider enrollment, hosted supervision or live-mail
policy is added. The ordinary MIME command stays unchanged in capability.

Fix demo-owner provisioning to use an explicit human-scope allowlist. Deriving it
by subtracting older worker scopes from the global scope set inadvertently included
the new worker-only document scope and made generated credentials invalid. Validate
the generated credential registry before persisting it; future worker scopes must
not silently become human authority.

## Verification and operations

Test private files/closed config, cross-channel/mixed scopes, nonclaiming check,
synthetic-account/owner/runtime-role denial, bounded results, graceful stop,
credential rotation/revocation around extraction, restart, encrypted source access
and redacted failures. Run a fresh actual CLI process through restricted PDF image,
real SQL publication and cited search, with preflight and repeat invocation proving
no duplicate extraction. Test the actual demo-generated registry and server option.
Retain the existing MIME controller regressions and SQL/restore suites.

No migration/dependency is added; migration 0012 and its grants remain prerequisites.
Existing fixed `document.job_*` events and controller result counts are telemetry;
host/service health and alerting are not implemented by this CLI. Rollback stops
invocations and disables new channel approvals, explicitly cancels pending consent
where appropriate, and retains jobs/results/keys/audit. No expiry reset or downgrade.

References: [ADR-032](032_operator_processing_controller.md),
[ADR-035](035_approved_document_processing.md),
[security](../SECURITY.md), [document processing](../DOCUMENT_PROCESSING.md).
