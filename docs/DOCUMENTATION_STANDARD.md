# Keeping the product documentation accurate

Updated 2026-09-21. Maintenance convention for this repository; no runtime,
permission, deployment or Factory-policy change.

## One place owns each kind of truth

| Question | Primary record |
|---|---|
| What should the ultimate product do? | [PRD](PRD.md) |
| How does it work for an owner? | [Worked walkthrough](PRODUCT_WALKTHROUGH.md), [features/methods](FEATURES_AND_METHODS.md) |
| What is executable now? | [Implementation status](IMPLEMENTATION_STATUS.md), linked source/contracts |
| What passed, at which revision? | [Build receipt](BUILD_RECEIPT.md), linked exact-commit CI/restore runs |
| What comes next and why? | [Roadmap](ROADMAP.md), [backlog](BACKLOG.md), [Factory handoff](FACTORY_HANDOFF.md) |
| Why was a boundary chosen? | [Accepted decisions](DECISIONS.md) and applicable ADR |
| What still needs the owner? | [Open questions](OPEN_QUESTIONS.md) |
| How healthy was an external dependency when inspected? | [OSS health](OSS_HEALTH.md), with its actual measurement date |

Security invariants and applicable accepted ADRs govern behavior. Source and tests
show the implementation; a contradiction with an approved contract is a defect to
resolve, not permission to silently change the contract. Do not use a newer prose
date to override an older exact-commit verification result.

## Status vocabulary

- **Planned:** a requirement/design, not a callable capability.
- **Groundwork / offline contract:** a component exists, but the user workflow or
  live integration is incomplete. Name the missing connection explicitly.
- **Implemented prototype:** executable within stated synthetic/local/CI limits.
- **Verified at commit:** specific checks passed at the linked revision. Report
  skips and warnings; separate mocks, real SQL, actual containers and browser tests.
- **Live accepted / production released:** use only with explicit authorization,
  environment-specific acceptance, operational ownership and recorded evidence.

Do not collapse imported, preserved, searchable, extracted, scanned, interpreted,
approved and executed into “processed.” Do not call proposed schemas existing
tables, proposed MCP tools registered tools, or generic proposal approval execution.

## Update checklist for every feature change

1. Classify the change; write the required ADR before a new schema, integration,
   API, workflow, permission or security behavior.
2. Update the implementation contract and tests alongside code/migrations.
3. Update status, feature/method explanation, code map and changelog. Adjust PRD
   only when requirements change; do not turn current limitations into the vision.
4. Update roadmap/backlog/handoff so the next assignment does not rebuild a finished
   component. Explain prerequisites, acceptance evidence and remaining gaps.
5. Update deployment/runbook notes for configuration, telemetry, upgrade sequencing,
   cancellation, rollback/forward repair and restore implications.
6. Record actual validation with exact commit and environment. Keep old receipts;
   do not overwrite historical counts or claim a later docs commit was the runtime
   revision tested earlier.
7. Check local links and required files, inspect the rendered GitHub reading path,
   and review for secrets/real mail before publishing.

Run the repository checks in [AGENTS.md](../AGENTS.md). The current
`scripts/check_docs.py` checks required inventory and local link **paths**. It does
not validate heading fragments, external URL availability, factual accuracy,
source freshness or rendered accessibility. Those require separate review; a green
documentation check alone is not proof that every claim is correct.

## Research and citations

Link primary sources adjacent to technical claims. Mark community experiences as
anecdotes rather than benchmarks. For external packages, retain license/version,
maintenance measurement date, actual metrics and reuse-versus-pattern rationale.
Recheck volatile prices, plans, model availability and API behavior before adopting
them. Updating our docs does not mean every external project was rescanned.

The 2026-09-21 documentation review rechecked PostgreSQL RLS, pgvector's retrieval
options, Azure Container Apps overview and official MCP security guidance. It did
not refresh OSS popularity/activity counts, obtain a cloud quote or certify any
assistant client. References remain beside the relevant architecture/interface
claims. Source-only downloads must exclude credentials, environments, private data,
logs and database/object backups.
