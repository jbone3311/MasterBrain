# Roadmap

EB-005 now has an opt-in encrypted filesystem backend, immutable SQL manifests,
16 MiB preservation with explicit parser-budget quarantine and coordinated
synthetic object/database restore checks. Next: hosted Blob/KMS, independent key
recovery, hosted supervision for the approved isolated MIME job channel, and binary
extraction. The worker recovers text/receipts, not PDF/Office/OCR content.
See [storage contract](LARGE_EVIDENCE_STORAGE.md).

The roadmap is gated by verified outcomes. Dates depend on team size and provider approval; phases are sequential where safety requires it.

Current progress: a bounded portion of Phases 0–2 is executable with synthetic
data, including real PostgreSQL CI, attachment accounting/search and a review
queue, bounded MIME quarantine and certified inventory recovery. No phase is
complete: live sync, hosted object/key recovery, production identity
and cloud setup remain gates. [BACKLOG.md](BACKLOG.md) is the concrete work queue.
Tenant isolation starts now; Phase 7 expands sharing rather than retrofitting tenancy.

## Refined next-build order

The read-worker library now has durable import/change checkpoints, fenced leases,
query-churn restart, retries, quarantine and certified inventory recovery. The next
gates, in dependency order:

1. Validate the implemented human quarantine retry under extended soak; add
   inventory retention policy, alerting and bulk historical reprocessing.
2. Extend encrypted local storage to hosted Blob/KMS; deploy the approved isolated-MIME
   job channel, add binary extraction and independent offsite/key recovery.
3. Audited enrollment/recovery, scheduler/lag alerts, disposable-mailbox conformance.
4. Production identity, member/account grants, infrastructure and restore acceptance.
5. Persistent rules/state and evaluation-backed inference; then controlled actions.

Do not promote on test count alone. Each gate needs failure injection, negative
authorization tests, actual acceptance evidence and a documented rollback path.

## Phase 0 — Decisions and threat model

Deliver:

- Confirm tenant model, first provider/account, deployment region/provider, retention, and OAuth consent model.
- Synthetic corpus and disposable provider accounts.
- Threat model, data-flow diagram, dependency/license review, baseline metrics.
- Repository scaffolding, CI, migrations, service interfaces, and decision log.

Exit: security owner accepts boundaries; no unresolved choice blocks the vertical slice.

## Phase 1 — Read-only vertical slice

Deliver:

- One provider connector with bootstrap, incremental cursor, expiry recovery, reconciliation.
- Immutable raw archive, MIME normalization, canonical messages/participants/threads.
- Managed Postgres/RLS, FTS search, evidence API, audit, health metrics.
- Replay/crash/idempotency tests and restore rehearsal.

Exit: no skipped/duplicated messages across fault injection; top evidence can be inspected; cross-tenant tests pass.

## Phase 2 — Deterministic organization

Deliver:

- Rule DSL/versioning/simulation/trace.
- Categories, canonical folder mappings, people/organizations/projects basics.
- Read-only recommendations for `_GrokBot/Review`, `Review Delete`, and `Needs Reply`.
- Correction and relevance-feedback capture.

Exit: offline precision targets met for review queues; no mailbox writes yet.

## Phase 3 — Controlled mailbox actions

Deliver:

- Action preview, policy engine, approval, transactional outbox, executor, reconciliation.
- Create labels/folders; label/move/flag/archive; draft creation where provider supports it.
- Kill switch, per-account read-only mode, rollback/compensation, operator playbooks.

Exit: duplicate/reordered/retried commands have one effect; bulk/high-risk actions cannot bypass approval; live testing confined to disposable mailboxes.

## Phase 4 — Local inference

Deliver:

- Ollama or llama.cpp adapter, schema validation, extraction cache, model registry.
- Classification, entity/request/obligation candidates, injection quarantine.
- Gold-set harness, calibration, abstention, model/route dashboards.
- Local embeddings only if retrieval evaluation justifies them.

Exit: measured quality/cost/latency thresholds; malformed or injected content cannot reach action credentials.

## Phase 5 — State and Librarian

Deliver:

- Temporal facts/evidence, identity resolution and reversible merges.
- Thread/project/person briefs, obligations, decisions, waiting-on state.
- Fact/rule/relationship proposals and review UI/API.
- Rebuildable projections and correction propagation.

Exit: sampled facts have valid evidence; stale/superseded facts behave correctly; reviewers can reverse merges/rules.

## Phase 6 — Remote escalation and multi-provider

Deliver:

- Approved remote-model adapter with disclosure policy/redaction/cost limits.
- Remaining Fastmail, Gmail, Microsoft, and iCloud connectors with conformance tests.
- Hybrid retrieval/reranking and cross-account canonicalization.

Exit: provider parity matrix passes; remote disclosure/audit verified; lexical-only degraded mode remains functional.

## Phase 7 — Multi-user hardening

Deliver:

- Roles/resource grants/shared projects, invitation/revocation, tenant export/deletion.
- Device-aware admin access, immutable audit export, SLOs/on-call, capacity tests.
- Optional tenant-scoped encrypted edge replica.

Exit: external security review, restore drill, load test, privacy/retention signoff, and zero cross-tenant findings.

## Phase 8 — Carefully expanded automation

Candidates only after longitudinal evidence:

- Auto-apply safe metadata rules.
- Time-limited `Review Delete` retention with explicit opt-in.
- Calendar/task handoffs or additional data sources.
- Graphiti/graph-engine pilot if relational temporal queries prove insufficient.

Automatic sending and permanent deletion require separate product/security decisions; they are not implied by completing earlier phases.

## Workstreams throughout

Security/privacy, connector correctness, observability/cost, evaluation corpus, documentation/ADRs, dependency maintenance, user review experience, and recovery drills run in every phase.
