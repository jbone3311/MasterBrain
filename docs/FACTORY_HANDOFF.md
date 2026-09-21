# Factory Handoff

## Mission

Bootstrap now includes working code; begin with [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md),
[EXECUTIVE_REVIEW.md](EXECUTIVE_REVIEW.md), [FACTORY_INTAKE_REVIEW.md](FACTORY_INTAKE_REVIEW.md)
and [BACKLOG.md](BACKLOG.md). Do not restart from a blank scaffold.

Latest read-only increment: certified full-inventory reconciliation, history-expiry
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

## First implementation epic

Choose one provider and deliver:

```text
incremental read-only sync
-> immutable raw evidence
-> deterministic normalization/dedupe/threading
-> managed PostgreSQL with forced RLS
-> lexical search and evidence endpoint
-> replay/reconciliation/audit/metrics
-> backup restore proof
```

No model, vector index, mailbox write, or broad MCP tool is required for the first success. Those are later vertical increments.

## Repository shape

```text
email-brain/
  AGENTS.md
  README.md
  docs/adr/
  src/email_brain/
    api/
    auth/
    connectors/
    evidence/
    normalization/
    rules/
    retrieval/
    inference/
    librarian/
    actions/
    storage/
    observability/
  migrations/
  tests/
    unit/
    contract/
    replay/
    security/
    evals/
    fixtures/synthetic/
  deploy/
  scripts/
```

## Required engineering practices

- Python type checking/linting/formatting, locked dependencies, reproducible containers.
- Alembic or equivalent reviewed migrations using expand/backfill/contract.
- Pydantic/JSON Schema contracts at every untrusted/model/provider boundary.
- OpenTelemetry-compatible traces/metrics/log correlation; no body content in routine telemetry.
- Transactional inbox/outbox, idempotency keys, explicit state machines, worker leases.
- Synthetic fixtures only in Git; production data never copied to CI/dev.
- Provider/model/storage adapters have contract tests and fake implementations.
- Security-sensitive changes require review; dependency licenses/SBOM checked in CI.

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

## Definition of done: phase 1

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

## Suggested kickoff issue

> Implement a read-only connector-to-search vertical slice for the selected provider. Use synthetic/disposable test data, immutable raw evidence, idempotent incremental synchronization, PostgreSQL RLS, lexical retrieval, evidence citations, reconciliation, audit, metrics, and restore verification. Exclude models, vectors, and mailbox writes. Demonstrate crash recovery and tenant isolation in automated tests.
