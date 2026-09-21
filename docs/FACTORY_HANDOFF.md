# Factory Handoff

## Mission

Handoff refreshed 2026-09-21. Exact tested revisions and limits are in the
[build receipt](BUILD_RECEIPT.md); this is not a Factory bind or production release.

Bootstrap now includes working code; begin with [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md),
[EXECUTIVE_REVIEW.md](EXECUTIVE_REVIEW.md), [FACTORY_INTAKE_REVIEW.md](FACTORY_INTAKE_REVIEW.md)
and [BACKLOG.md](BACKLOG.md). Do not restart from a blank scaffold.

## Start here: the next delivery

Build the [browser sign-in/session lifecycle](#suggested-next-issue) on ADR-040's
existing token/mapping foundation, beginning with its own ADR and acceptance tests. The
[backlog slice](BACKLOG.md#eb-007-next-production-identity-foundation) and
[roadmap](ROADMAP.md#next-build-packages) agree on this priority. A signature
verifier alone does not finish browser login, sharing or hosted operation.

Preserve the working read/MIME/PDF operator paths, owner review and test mailbox.
No new cloud registration, real account or mailbox privilege is authorized. After
identity, the next delivery work is hosted storage/key recovery, supervision and
operational acceptance; live promotion has its own [gate record](RELEASE_ACCEPTANCE.md).

## Completed increments to review, not rebuild

Latest correction: [ADR-041/response streaming](adr/041_stream_deadline_checks.md)
removes application chunk buffering from Fastmail/Gmail/Graph/Ollama deadline
checks and bounds accumulation. Sixteen controlled-clock cases include five
regression failures demonstrated against the old implementation. Review the
cooperative timeout limitation; no new live/network acceptance is claimed.

Latest feature increment: [ADR-040/API identity](IDENTITY_AUTH.md), migration 0013 and
PyJWT 2.14.0. Review fixed RFC/Entra profiles, exact discovery/key trust, bounded
cache/outage semantics, administrator-only mappings/audit and fresh transaction
revocation. Restore now includes populated identity bindings. No browser login,
real issuer enrollment, team grants, worker authority or public ingress is added.

Previous runtime increment: [ADR-039](adr/039_read_worker_controller.md) adds the
[bounded read command](READ_CONTROLLER.md). Review exact ingest-only worker
identity, non-consuming preflight, fixed provider/secret binding, per-request/step
authority guards, encrypted write-key selection, stop and pause/retry semantics.
It grants no enrollment, hosted supervision, mailbox writes or live acceptance.

Previous runtime increment: [ADR-038](adr/038_document_owner_review.md) adds the
[owner PDF screen](DOCUMENT_REVIEW_SCREEN.md): explicit selection/approval,
bounded history/cancel, opt-in search and own-document citations. Review source/
processor binding, separate MIME state, same-key uncertainty, stale callback fences
and closed response validation. Node contracts and a real SQL/API-to-DOM bridge
are distinct from pending browser/accessibility and live/scanner acceptance.

Previous documentation/tooling increment: [ADR-037](adr/037_documentation_verification.md)
adds the [methods guide](METHODS_GUIDE.md) and regression-tested inventory/local-link/
heading checks, including hidden GitHub templates. It changes no product runtime.
That increment's identity assignment now has the ADR-040 foundation above;
the next assignment is browser/session lifecycle, not another verifier.

Previous runtime increment: [document operator command](DOCUMENT_CONTROLLER.md), ADR-036.
Review fixed purpose/policy, exact document-worker scope, private file/key boundary,
synthetic-account preflight, fresh authentication around extraction and shared
polling without shared approval authority. The loopback server exposes an explicit
channel option; demo-owner generation now allowlists human scopes. No schema,
dependency, hosted supervision, owner PDF UI or live-mail policy is added.

Previous increment: [approved document jobs/search](DOCUMENT_PROCESSING.md), ADR-035,
migration 0012. Review separate worker scope, synthetic policy, fresh source/owner/
lease fences, immutable revisions and latest-result FTS selection. UI was absent
at that increment; ADR-038 now supplies it. Live/scanner and browser acceptance
remain open; do not rebuild the integrated backend or owner screen.

Previous increment: [source-bound restricted PDF worker](PDF_WORKER.md), ADR-034.
Review the dedicated image, hash/part binding, strict result validation, shared
fixed-profile container controller and partial/unscanned semantics. That increment
had no SQL/HTTP integration; ADR-035 above now supplies a separate channel while
preserving ready-body search and never inventing quarantine.

Previous increment: [known-answer mailbox](TEST_MAILBOX_PLAN.md), ADR-033,
coherent conversations/document corrections, real formats, independent dev-only
readers, manifest/export and bounded paced SQL feed. Review restart/checkpoint and
unenrolled-account safeguards; no binary intake/parser permission is added.

Previous increment: [bounded operator processing](PROCESSING_CONTROLLER.md), ADR-032,
explicit private configuration, owner-scoped worker identity, non-claiming preflight,
fixed counts and graceful stop. Review the privileged host/file boundary and
credential revocation timing. No new schema/grants or installed service.

Previous increment: [owner processing controls](PROCESSING_REVIEW_SCREEN.md),
migration 0011 history index, bounded owner/account history, explicit approval and
cancellation, uncertain-request idempotency and stale-view fencing. Review actual
code through [CODE_MAP.md](CODE_MAP.md); read [GAME_PLAN.md](GAME_PLAN.md) and
[FEATURES_AND_METHODS.md](FEATURES_AND_METHODS.md) for intent. The
[realistic test feed](TEST_MAILBOX_PLAN.md) is bounded and synthetic, not a hosted service.

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
-> PostgreSQL with forced RLS (disposable CI, not managed cloud yet)
-> lexical search and evidence endpoint
-> replay/reconciliation/audit/metrics
-> backup restore proof
```

Do not interpret this as a blank-slate assignment. Complete operator supervision,
safe document extraction, broader held-out scenarios and the production foundations
in [ROADMAP.md](ROADMAP.md). No model, vector index or mailbox-write privilege is
needed to prove the initial read-only service.

## Repository shape

Use the linked [actual file map](CODE_MAP.md). The runtime currently uses modules
such as `api.py`, `store.py`, `sync.py`, `recovery_jobs.py`, `connectors/`, `rules/`
and `web/`; there are no implemented `librarian/` or `actions/` services. Tests
are in the existing flat `tests/` tree. Do not create duplicate modules based on
the original aspirational directory layout.

## Required engineering practices

Use [CONTRIBUTING.md](../CONTRIBUTING.md) for local checks and review preparation;
[release acceptance](RELEASE_ACCEPTANCE.md) consolidates the evidence needed to
promote an increment, disposable pilot or production capability. These guides do
not grant Factory bind, live account, paid-resource or mailbox-write authority.

Use the [worked product scenario](PRODUCT_WALKTHROUGH.md) to review user-visible
behavior and the [documentation standard](DOCUMENTATION_STANDARD.md) for each
increment. Update current status and next work without rewriting historical receipts.
The original read-order filenames above refer to this `docs/` directory; the root
README, PRODUCT and AGENTS files supply repository entry points and working rules.

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

> Build the browser sign-in/session lifecycle on ADR-040, with a new ADR before
> implementation: fixed registered client/redirect configuration, authorization
> code + PKCE/state/nonce handling as applicable, server-controlled session storage,
> cookie/CSRF boundaries, logout/expiry/revocation and no browser token persistence.
> Exercise a fake authorization server, malicious callbacks, stolen/stale sessions,
> token/issuer failures and real SQL isolation. Preserve current database mappings;
> never auto-enroll unknown identities or substitute ID tokens for API access tokens.
> Define enrollment/admin and worker boundaries separately. No real app registration,
> public ingress, identity enrollment, paid resource, mailbox access or team sharing
> without separate approval. Browser acceptance remains a separate proof.

ADR-034 supplies the reader; ADR-035 supplies durable approval/publication/search;
ADR-036 supplies `process-documents` and loopback channel configuration; ADR-038
supplies its separate owner review/search/evidence screen.
ADR-039 supplies bounded `sync-read`; do not rebuild it or mix its ingest identity
with MIME/PDF scopes.
`process-jobs` still supports only MIME recovery. Do not select a PDF image for
that incompatible MIME contract or broaden credentials to cover both channels.

The operator recovery command and bounded known-answer generator already exist;
do not reimplement either. Hosted supervision, production identity/storage and
enrollment/resume administration remain distinct work packages. A documentation plan
does not approve a new schema, API or processing privilege; the required ADR comes
before code.
