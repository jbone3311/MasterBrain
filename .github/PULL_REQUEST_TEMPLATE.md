## Outcome

What user/system outcome does this change deliver?

- Backlog ID / governing ADR:
- Current capability versus target after this change:
- Explicit exclusions and remaining launch gates:

## Scope and trust boundary

- Components and data classes touched:
- Provider/model/network behavior:
- Authorization/RLS/secret impact:

## Contracts and migration

- API/schema/event/rule changes:
- Database migration/backfill:
- Compatibility plan:

## Safety and recovery

- Failure modes:
- Rollback/compensation:
- Telemetry and alerts:

## Verification

- [ ] Synthetic fixtures only
- [ ] Unit/contract/replay/security tests updated
- [ ] Deployment gate passes
- [ ] Documentation/ADR updated
- [ ] No secret or private mailbox data in diff/logs

Record the exact tested Git SHA, commands, environment and result links. Separate
local passes/skips, real PostgreSQL, actual restricted containers, Node contracts,
browser checks, restore, live-provider tests and soak. Do not count mocks as live
acceptance or reuse an older run as proof of changed behavior.

- [ ] Status, feature/method explanation, roadmap/backlog and Factory next task agree
- [ ] Operations/configuration/rollback notes match the implemented behavior
- [ ] Dependency/license/advisory/SBOM impact assessed; unfinished gates named
- [ ] Relevant [release gates](https://github.com/jbone3311/CW-EmailBrain/blob/main/docs/RELEASE_ACCEPTANCE.md) addressed or explicitly pending

See [contributing](https://github.com/jbone3311/CW-EmailBrain/blob/main/CONTRIBUTING.md). No checkbox authorizes real mail, spending,
remote disclosure, new mailbox privileges or changes to Factory-owned configuration.
