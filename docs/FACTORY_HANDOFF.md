# Factory Handoff

## Mission

Bootstrap now includes working code; begin with [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md),
[EXECUTIVE_REVIEW.md](EXECUTIVE_REVIEW.md), [FACTORY_INTAKE_REVIEW.md](FACTORY_INTAKE_REVIEW.md)
and [BACKLOG.md](BACKLOG.md). Do not restart from a blank scaffold.

Latest increment: [owner processing controls](PROCESSING_REVIEW_SCREEN.md),
migration 0011 history index, bounded owner/account history, explicit approval and
cancellation, uncertain-request idempotency and stale-view fencing. Review actual
code through [CODE_MAP.md](CODE_MAP.md); read [GAME_PLAN.md](GAME_PLAN.md) and
[FEATURES_AND_METHODS.md](FEATURES_AND_METHODS.md) for intent. The proposed
[realistic test feed](TEST_MAILBOX_PLAN.md) is not yet a continuous generator/service.

Previous increment: [durable recovery jobs](RECOVERY_JOBS.md), migration 0010,
explicit human approval API, cancellation, worker leases and atomic fenced results.
Review the privileged read-only SQL locking helper, approval lifetime and controller
separation before rollout. Hosted identity/supervision remain.

Previous increment: [isolated large-MIME recovery](ISOLATED_MIME_RECOVERY.md), using
approved local image IDs, resource/output limits and image-bound immutable evidence.
Default API has no Docker access; a trusted worker must explicitly inject it into
human-authorized Recovery. CI adds actual post-build container/SQL pipeline checks.
Review controller privilege and hosted deployment of the job channel before rollout.

Previous increment: [encrypted large evidence](LARGE_EVIDENCE_STORAGE.md), optional
16 MiB local objects, atomic SQL manifests, held large mail and two-part restore
verification. Migration 0009 requires compatible API/workers/backup readers; no
Azure adapter or large binary parser is implied. Review key custody, orphan
inventory and missing-object recovery before any hosted implementation.

Previous local increment: [audited held-message retry](QUARANTINE_RECOVERY.md), with
human authorization, immutable parser versions, stale-event fencing, output-drift
refusal and review UI. Migration 0008 requires stopping pre-0008 binaries; do not
mix old workers with its changed evidence uniqueness key.

Earlier read-only increments: certified full-inventory reconciliation, history-expiry
recovery, bounded raw MIME quarantine, owner-scoped sync status, and resumable
fictional-inbox seeding. Review [test coverage and gaps](TEST_COVERAGE_MATRIX.md)
and the exact [build receipt](BUILD_RECEIPT.md) before promotion. These tests use
synthetic HTTP plus real disposable PostgreSQL, not real provider accounts.

Repository: `jbone3311/CW-EmailBrain`, private. Product ID proposed: `emailbrain`.
Registration descriptor and thin CLAUDE template are staged under `factory/`;
they are not evidence of a successful binding. A Factory-scope session must register
the product; Product proposals never write Factory's registry/KB. No Factory bind
or hooks installation has been claimed. Inspect the current contract before adopting
older blueprint commands or copied-tool instructions.

Build the smallest secure vertical slice of Email Brain while preserving the boundaries and invariants in this pack. The target is an evidence-backed service, not a demo chatbot.

## Read order

1. `README.md`
2. `PRD.md`
3. `SECURITY.md`
4. `ARCHITECTURE.md`
5. `DATA_MODEL.md`
6. `EMAIL_PROVIDER_CONNECTORS.md`
7. `API_MCP_SPEC.md`
8. `RULES_AND_FEEDBACK.md`
9. `AI_MODEL_STRATEGY.md`
10. `OSS_EVALUATION.md`
11. `DEPLOYMENT.md`
12. `TESTING_AND_EVALS.md`
13. `OPERATIONS_RUNBOOK.md`
14. `ROADMAP.md`
15. `DECISIONS.md`

## Existing foundation: preserve, do not re-scaffold

The bounded synthetic Fastmail path already implements much of this sequence:

```text
incremental read-only sync
-> immutable raw evidence
-> deterministic normalization/dedupe/threading
-> managed PostgreSQL with forced RLS
-> lexical search and evidence endpoint
-> replay/reconciliation/audit/metrics
-> backup restore proof
```

Do not interpret this as a blank-slate assignment. Complete operator supervision,
safe document extraction, known-answer scenarios and the production foundations
in [ROADMAP.md](ROADMAP.md). No model, vector index or mailbox-write privilege is
needed to prove the initial read-only service.

## Repository shape

Use the linked [actual file map](CODE_MAP.md). The runtime currently uses modules
such as `api.py`, `store.py`, `sync.py`, `recovery_jobs.py`, `connectors/`, `rules/`
and `web/`; there are no implemented `librarian/` or `actions/` services. Tests
are in the existing flat `tests/` tree. Do not create duplicate modules based on
the original aspirational directory layout.

## Required engineering practices

- Python type checking/linting/formatting, locked dependencies, reproducible containers.
- Alembic or equivalent reviewed migrations using expand/backfill/contract.
- Pydantic/JSON Schema contracts at every untrusted/model/provider boundary.
- OpenTelemetry-compatible traces/metrics/log correlation; no body content in routine telemetry.
- Transactional inbox/outbox, idempotency keys, explicit state machines, worker leases.
- Synthetic fixtures only in Git; production data never copied to CI/dev.
- Provider/model/storage adapters have contract tests and fake implementations.
- Security-sensitive changes require review. Dependency license/SBOM/advisory and
  signature automation is a required release gate, not currently complete in CI.

## Pull-request gates

Each PR must state affected trust boundary, data migration, provider/API behavior, authorization impact, rollback, telemetry, and test evidence. Required checks:

- unit/type/lint;
- migration and replay/idempotency;
- connector contracts where relevant;
- RLS/cross-tenant negatives;
- secret/content log scan;
- dependency/license/SBOM/vulnerability scan;
- API/schema compatibility;
- performance regression for indexing/search paths.

## Read-only release acceptance

- Crash at every cursor boundary cannot skip mail or duplicate canonical records.
- Cursor expiry/full resync path is tested.
- Raw evidence hash and normalized provenance are inspectable.
- Search returns tenant-authorized bounded evidence and stable citations.
- Runtime database role cannot bypass RLS or own tenant tables.
- A restored environment passes count/hash/search verification.
- Runbook handles auth failure, cursor expiry, poison message, and database restore.
- Documentation and ADRs match deployed behavior.

## Questions to resolve before live rollout, not before synthetic coding

1. First provider/account and authorized historical backfill window?
2. Selected hosting region/provider and data residency constraints?
3. Tenant definition: individual only at launch, or household/team sharing?
4. Raw mail/attachment retention and deletion policy?
5. Which OAuth app registrations/consent path are available?
6. Is local edge inference required at launch or later?

Record answers as ADRs; current bounded assumptions are in ADR-013/014 and
[OPEN_QUESTIONS.md](OPEN_QUESTIONS.md). Continue synthetic work without waiting.

## Guardrails for coding agents

- Treat these documents as product architecture, not permission to access real mail or production systems.
- Do not install a large agent/RAG framework unless an ADR demonstrates the need.
- Do not add send/delete permissions “for future convenience.”
- Do not let model output bypass schema, policy, approval, or action outbox.
- Do not expose SQL, raw object storage, provider tokens, or unrestricted URL fetching through MCP.
- If an invariant must change, propose an ADR and update the relevant documents/tests before implementation.

## Suggested next issue

> Complete the explicitly configured operator/supervisor path for existing read and
> processing workers. Preserve human approval, lease/source/authorization fences,
> bounded retries and no-mailbox-write behavior. Add restart/shutdown and health
> tests. In a separate work package extend the existing synthetic corpus into
> known-answer threaded scenarios with actual attachment formats (EB-023). Do not
> enroll accounts, provision cloud services or mutate Factory without approval.
