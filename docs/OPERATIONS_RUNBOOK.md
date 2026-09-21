# Operations Runbook

## Executable prototype recovery checks

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
Independent quarantine reprocessing and operator resume UI remain unimplemented.
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
