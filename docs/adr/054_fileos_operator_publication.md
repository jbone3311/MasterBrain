# ADR-054 — Explicit authenticated FileOS publication

Status: accepted for the additive prototype tranche on 2026-09-22, pending the first
hosted PostgreSQL gate.

## Decision

MasterBrain exposes a narrow `fileos publish` operator command for a previously
created immutable snapshot. It requires an owner-controlled private configuration,
an expiring worker credential with exactly `brain.source.ingest` and
`brain.document.publish`, a runtime-only PostgreSQL DSN, and an explicit UUID
idempotency key. It has no source-effect command or permission.

The configuration binds one stable source ID to one absolute authorized root and one
private manifest. Check mode validates the closed configuration, complete manifest,
credential, root and least-privileged database role without importing or extracting.
Execution imports the exact manifest, reopens/re-hashes each source version, extracts
supported content and publishes only complete results. Local credentials are checked
before intake, before and after every extraction, and after completion. Database
transactions independently re-check owner membership and reject superuser,
`BYPASSRLS` or table-owning connections.

PDF/DOCX/XLSX remain optional: a configuration must provide both an immutable reader
image ID and absolute Docker binary, or neither. The same inspected, networkless
container boundary from ADR-053 applies. Text formats require no parser image.

## Replay and failure

The caller retains the exact snapshot and idempotency key for retry. Intake receipts
bind that key, actor and canonical manifest; reuse with different input fails closed.
Published documents have deterministic identities, so a retry may report the
original intake counts while `changed_publications` is zero. A crash can leave an
accounted prefix, but retrying the exact request converges without duplicate evidence.

Output contains source ID, counts and outcome codes only—never the root, locators,
DSN, token, content or parser diagnostics. A rejected or changed sibling is explicit
and does not authorize a source write. Automated scheduling, live root enrollment,
cursoring and a durable whole-run completion receipt remain later work.

## Rollback

Remove the operator configuration or worker credential and stop invoking the command.
No daemon or source hook remains active. Already committed observations and evidence
stay immutable; FOS-Master remains unchanged and available.
