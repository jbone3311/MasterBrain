# Operations Runbook

Updated 2026-09-21. The opening sections describe current local/CI recovery.
Daily checks, incident playbooks and SLOs below are production requirements;
their dashboards, alert delivery, OIDC and provider-action controls are not all
implemented. [Status](IMPLEMENTATION_STATUS.md) is the capability boundary.

For owner-facing symptoms, see [failure examples](PRODUCT_WALKTHROUGH.md#what-failures-should-look-like).
Report import freshness, attachment extraction, scanning and interpretation
separately. A responsive API or completed MIME job does not establish that all
documents are understood, a worker is online, or the provider is current.

## Owner processing screen

The [document job API/library](DOCUMENT_PROCESSING.md) has independent approval,
history, cancellation and result reads, now exposed by the separate
[owner PDF screen](DOCUMENT_REVIEW_SCREEN.md), never `process-jobs`.
Inspect document `status` separately from extraction outcome and
scan status. Stopping a worker does not cancel saved consent; disabling configuration
only prevents new approvals. Cancel pending jobs explicitly and retain immutable
results. Restore and expiry rules apply to both channels without merging permissions.
The separate [document operator command](DOCUMENT_CONTROLLER.md) now runs approved
PDF work. Its preflight checks synthetic account/configuration, not worker readiness;
keep its worker credentials/configuration distinct from MIME recovery.

Choose the account and refresh processing history manually. Approve only the
displayed receipt/parser; inspect fixed status/outcomes and each attachment result.
If submission is uncertain, retry with the retained key in the unchanged context
or inspect history before creating another approval. A page reload loses browser
keys, not the saved job. Cancel explicitly; completion winning the race must be
shown as completion. No polling daemon or worker-health guarantee is implied.
See [PROCESSING_REVIEW_SCREEN.md](PROCESSING_REVIEW_SCREEN.md).

## Durable processing approvals

See [RECOVERY_JOBS.md](RECOVERY_JOBS.md). A configured parser does not mean a worker
is online. Watch queued age, retry deadlines, attempts and fixed terminal outcomes;
the current API does not claim worker liveness. Investigate repeated infrastructure
failures without logging MIME or subprocess output. Cancel outstanding approvals
to revoke them; bearer-token expiry alone does not retract durable consent.
During restore, stop controllers until pending approvals and image versions are
reviewed. Original one-hour expiries remain unchanged. Never manually renew leases,
edit approval identity or reset claim counters to force work through.

## Isolated MIME controller

The new [PDF worker](PDF_WORKER.md) is a separate synthetic test/library profile,
not an option in `process-jobs`. Do not pass its image as the configured MIME
processor, manually rewrite a job parser ID or fabricate a held-message receipt.
The reader itself has no persistence; ADR-035's separate document channel does. Parser
text is unscanned, and source/contract/container errors are not cached document failures.

Use [the operator command](PROCESSING_CONTROLLER.md) for private preflight and
bounded job polling. Check success does not certify Docker readiness; exit 0 can
include retry/terminal failure results. SIGINT/SIGTERM finish in-flight bounded
work and stop new claims, not cancel approvals. Registry changes are checked per
poll and around parsing; SQL membership/account/cancellation fences remain stronger
than file revocation. No supervisor is installed by this command.

Run only on an explicitly trusted local worker/controller with an approved immutable
image; never mount Docker into the API. Inspect [worker contract](ISOLATED_MIME_RECOVERY.md)
before invoking library recovery. Timeouts, unavailable images, oversized/malformed
output or failed ownership-checked cleanup leave mail held with no cached attempt.
Do not raise limits silently. Verify no owned orphan remains after a killed host
process; never prune or delete unrelated containers. A successful recovery does
not mean binary attachments were extracted or scanned: inspect receipt accounting.

If an ordinary searchable message has a deferred PDF/Office attachment, this is
an unsupported extraction capability, not necessarily a stalled recovery job.
Do not quarantine the message manually, invent a receipt or raise parser limits.
Keep its body searchable and record the deferred part. Eligible synthetic PDFs
can use the separate [document API/library](DOCUMENT_PROCESSING.md), operator CLI
and owner PDF screen. Live policy and Office processing remain unavailable. Do not reinterpret
an existing MIME approval as consent to use that separate channel.

## Encrypted evidence failures

For the opt-in [local object backend](LARGE_EVIDENCE_STORAGE.md), preserve SQL,
ciphertext and key custody. Storage failures cause bounded worker retry with no
cursor advance; retry API returns scrubbed 503 without caching an attempt. Restore
missing bytes/keys and verify hashes before resuming. A 409 for `mime_too_large`
means the current parser cannot handle retained mail, not that bytes were lost.
Owner-scoped `Store.object_inventory` is read-only and non-snapshot: missing or
unreferenced names are investigation signals, never permission to delete objects.
Back up both stores with separately recoverable keys; database-only restore fails.

## Executable prototype recovery checks

For a repeatable [known-answer mailbox](TEST_MAILBOX_PLAN.md), export to a new
directory or replay into an unenrolled synthetic account. Resume only the same
manifest; never edit/reset cursors to force another dataset into an account.
The summary distinguishes scheduled deliveries from new committed provider events.
Stop signals finish in-flight work; a failed command may have committed a previous
event. Check SQL progress by rerunning the same bounded command. Do not point this
at a real/enrolled account or treat generated semantic targets as evaluated accuracy.

Run the [synthetic logical restore drill](RESTORE_DRILL.md) on a disposable Docker
runner. It creates fresh synthetic source/target databases, verifies recovered
contents and tenant isolation, then removes its owned test container and temporary
archive. It accepts no production database or input archive. Success is not proof
of managed-service PITR, offsite encryption, retention or regional failover.

For an incorrect sender label, use [rule revision rollback](REVIEWED_RULES.md), then
refresh search. Never edit historical rule/evidence rows. Local-model candidates
can be disabled simply by not invoking the opt-in library; no model is automatically
enabled in the service.

## Current worker implementation

The worker library stores `sync_workers` state and append-only `sync_runs` outcomes;
it is not scheduled or connected to real accounts. See [READ_WORKER.md](READ_WORKER.md)
for lease expiry, retry deadlines, paused errors and migration/grant instructions.
Expired history now triggers a certified full inventory rebuild; old JSON v1
checkpoints restart safely. A previously paused `resync_required` account is not
silently unpaused on upgrade: review its cause and migrate under operator control.
Inspect the authenticated sync-status endpoint for current quarantine counts.
Quarantined MIME remains in raw storage with append-only receipts; never delete
receipts, edit cursor text, or label deferred attachments as successfully extracted.
Independent, human-requested bounded quarantine retry is available in the review
screen; follow [recovery](QUARANTINE_RECOVERY.md). Monitor fixed audit outcomes
`recovery.recovered`, `recovery.mime_rejected`, `recovery.integrity_failed` and
`recovery.read`; no content is logged. Same-parser failures are cached, not retried
automatically. Operator worker-resume UI and alert delivery remain unimplemented.
No manual cursor advancement, baseline replacement or silent error clearing.

## Daily checks

- Sync lag and last successful cursor per account/scope.
- Notification/subscription/watch expiry and renewal status.
- Queue depth/oldest age, retries, dead letters, action backlog.
- Provider 4xx/5xx/throttle and auth failures.
- Database/storage capacity, replica/PITR health, object-write failures.
- Local/remote model latency, schema failures, escalation/cost, denied actions.
- Cross-tenant/auth anomalies and RLS/policy denials.

Dashboards show tenant-safe metadata; operators do not see bodies by default.

## Global safety controls

Controls must be independently usable:

1. Disable all mailbox writes.
2. Set one tenant/account read-only.
3. Disable remote-model calls.
4. Pause connector or action worker class.
5. Revoke one provider credential or assistant client.
6. Put public API into authenticated read-only mode.

## Incident: sync stopped or lagging

1. Confirm provider/auth/quota vs internal queue/database failure.
2. Pause only the affected account if poison data repeats.
3. Do not advance cursor manually.
4. Reauthorize/renew subscription as required; replay from stored cursor.
5. If cursor expired, run documented scoped full resync through idempotent ingestion.
6. Reconcile provider IDs/counts and close only after lag/drift returns to target.

Gmail watches require renewal and notifications can be delayed/dropped, so periodic history sync remains necessary ([Google push guide](https://developers.google.com/workspace/gmail/api/guides/push)).

## Incident: wrong labels/moves

1. Engage mailbox-write kill switch.
2. Identify command IDs, rule/model/policy versions, targets, provider results.
3. Deactivate offending rule/version; preserve audit/evidence.
4. Simulate compensation and inspect protected messages.
5. Execute approved compensating commands; reconcile provider state.
6. Add regression examples and review whether similar rules require suspension.

## Incident: suspected prompt injection/model compromise

1. Disable mailbox writes and affected model route/client.
2. Preserve request/action/audit IDs and hashes; avoid spreading hostile content into tickets/logs.
3. Determine whether untrusted content crossed from reader to actor or secrets/network tools.
4. Revoke/rotate potentially exposed provider/model/service credentials.
5. Search for related proposals/actions and quarantine them.
6. Patch policy/parser/prompt/runtime, add adversarial fixture, red-team, then staged restore.

## Incident: cross-tenant exposure

1. Treat as highest severity; disable implicated endpoint/client and consider API read-only.
2. Preserve immutable audit; involve security/privacy/legal owners.
3. Determine affected tenants/records/timestamps and whether caches, model providers, or logs received data.
4. Fix API/RLS/cache key root cause; rotate credentials if necessary.
5. Validate with negative tests and independent review before re-enable.
6. Follow applicable notification and contractual requirements.

## Incident: provider credential compromised

Revoke at provider, disable account, rotate vault secret, invalidate sessions, inspect provider/audit logs and mailbox changes, reconcile from last trusted point, and reauthorize with minimum scope. Apple app-specific passwords can be individually revoked and are revoked when the primary password changes ([Apple](https://support.apple.com/en-gb/102654)).

## Restore procedure

1. Open isolated recovery environment with fresh credentials and no mailbox-write egress.
2. Restore PostgreSQL to chosen point and object-store manifest/version set.
3. Run migrations compatible with restored application version.
4. Verify tenant counts, constraints, cursor states, hashes, samples, FTS/vector availability.
5. Rebuild disposable derived indexes if needed.
6. Start read-only; reconcile provider changes since recovery point.
7. Re-enable writes only after approval and idempotency/outbox review.
8. Record measured RPO/RTO and gaps.

## Routine maintenance

- Weekly: dead-letter review, credential/subscription expiries, rule rollback/denial spikes, dependency advisories.
- Monthly: capacity forecast, least-privilege review, model/retrieval drift sample, tenant deletion completion.
- Quarterly: restore drill, incident tabletop, secret rotation sample, RLS/security regression, provider live conformance.
- Before upgrades: read changelogs/licenses, stage replay corpus, shadow/canary, snapshot/rollback, monitor.

## SLO candidates

- 99.9% query API availability after stabilization.
- 99% of provider changes indexed within 10 minutes when provider is healthy.
- 100% action commands auditable and idempotent under retry tests.
- No unresolved high-severity tenant-isolation finding.

Error budgets pause feature rollout when exhausted.
