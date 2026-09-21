# Roadmap

Updated 2026-09-21. This delivery order supersedes the initial phase numbering;
it does not grant new permissions. Dates depend on evidence and owner approvals,
not optimistic calendar promises. [Backlog IDs](BACKLOG.md) remain stable.

## Current position

The synthetic foundation is substantial: Fastmail worker/checkpoints, PostgreSQL
RLS/FTS, immutable evidence, attachment receipts, narrow reviewed virtual rules,
encrypted local objects, restricted MIME jobs and owner processing controls.
Real PostgreSQL, actual restricted-container and disposable restore tests run in
CI. No production phase is complete. Live enrollment, hosted identity/storage,
worker supervision, production binary-intake policy, operational acceptance and Factory bind remain.

## Next build packages

1. **Operator processing path:** [bounded approved-job command](PROCESSING_CONTROLLER.md),
   private configuration/preflight, fresh worker credentials and graceful stop are
   implemented. Hosted supervision, enrollment, service identities and health/alerts
   remain; the ingestion worker still needs its own operator workflow. The API
   never receives Docker authority.
2. **Known-answer mailbox:** coherent seeded scenarios, actual formats, versioned
   manifests, export and paced/restarted database replay are implemented (EB-023).
   Expand held-out variety, scanned-text/password-protected cases and sustained
   load measurement; existing format checks do not prove binary extraction quality.
3. **Binary intake:** ADR-035 now connects the restricted PDF worker to separate
   synthetic approval jobs, immutable results and opt-in FTS. Next add document
   owner UI and scanner/live policy, then broader Office/OCR intake. ADR-036 now
   supplies the separate bounded document command and loopback channel option.
   Quarantine-recovery permissions remain unchanged. See the
   [contract](DOCUMENT_PROCESSING.md) and [work package](BACKLOG.md#eb-006-next-source-bound-document-processing).
4. **Production foundation:** OIDC/grants, Azure adapters/private resources,
   secrets/key recovery, enrollment, rate limits, audit and restore (EB-007–009).
5. **Read-only acceptance:** owner-authorized disposable mailbox plus staging soak,
   security/accessibility review and documented rollback before real mail.

Some work can proceed independently. Provider conformance cannot be declared
complete from local capture alone, and production deployment cannot precede identity.

## Milestone 1 — Reproducible synthetic foundation

Scope: preserve source, normalize/account for every part, durable cursors,
search/evidence, owner review, forced RLS, replay and restore.

Current: implemented bounded slices; source/CI evidence is in [BUILD_RECEIPT.md](BUILD_RECEIPT.md).

Exit: locked tests reproducible; migration/grant negatives pass; crashed/replayed
events cannot skip evidence; account isolation and restored hashes/search hold.
No claim of live mail, model quality or hosted durability.

## Milestone 2 — Independent read-only pilot

Scope: one provider (Fastmail engineering default, owner choice pending), approved
enrollment/backfill, supervision, hosted Postgres/objects, recoverable keys,
OIDC/MFA, current-owner access, rate limits, audit export and operator alerts.
Selected document extraction either passes isolated acceptance or stays explicitly
deferred under an approved pilot coverage policy.

Exit: disposable-mailbox bootstrap/change/expiry/reconciliation tests; multi-day
bounded soak with restarts/outages; independent DB+object+key restore; private
networking/authorization review; approved retention and incident owner. All real
account use and paid resources require explicit approval.

## Milestone 3 — Useful understanding and organization

Scope: richer reviewed rules/protected classes, supported PDF/Office/OCR extraction,
evaluated local candidates, relational people/projects/threads/obligations, temporal
corrections and reversible merges. Keep lexical search and no-model operation.

Current: narrow virtual sender rules, a fake-tested optional local adapter and a
separate synthetic PDF approval/extraction/search backend. State projectors,
document UI controls and evaluated production interpretation remain open; explicit
synthetic operator execution is now available separately from MIME recovery.

Exit: held-out retrieval/extraction/classification results with sample sizes,
abstention and error costs; evidence links valid; stale facts supersede correctly;
rule rollback tested; no inference path can execute actions. A generated answer
key is necessary but not a real-world quality certificate.

## Milestone 4 — Assistant and authorized team access

Scope: REST-backed official MCP adapter, audience/scope-aware OAuth, explicit
member/account/project grants, invitations/revocation and tested client support.

Exit: Grok/ChatGPT/Claude compatibility recorded individually; no raw SQL/token
passthrough; authorization before retrieval/cache candidates; revoked access cannot
reappear through stale UI/caches; independent cross-tenant/resource tests pass.

## Milestone 5 — Controlled mailbox effects

Scope: previewed labels/folders/moves/flags/archive and provider drafts; separate
executor/credentials, expiring exact-intent approval, outbox, kill switch and
uncertain-outcome reconciliation. No automatic send/permanent deletion.

Exit: separately approved ADR and disposable write-account tests; duplicate and
out-of-order commands cannot bypass policy; ambiguous responses reconciled before
retry; compensation limits shown to owner; every effect audited. Never promise
universal exactly-once delivery or that sent mail can be unsent.

## Milestone 6 — Measured expansion

Scope: durable Gmail/Graph/IMAP workers and notification lifecycles; hybrid
FTS/vector retrieval if measured beneficial; approved remote inference with
disclosure/retention/budget rules; optional encrypted local read cache.

Exit: per-provider conformance; lexical-versus-hybrid comparison; permission-safe
candidate retrieval; model version/quality/disclosure receipts; offline edge
behavior and revocation tested. Do not add a graph database without measured need.

## Continuous release gates

The [worked product scenario](PRODUCT_WALKTHROUGH.md) is a useful acceptance
walkthrough, not proof of implementation. Update its status alongside the
[documentation maintenance checklist](DOCUMENTATION_STANDARD.md) when a milestone advances.

- Every behavior change: ADR where required, implementation/tests/docs together,
  migration compatibility, telemetry, rollback and exact-commit evidence.
- Every dependency: pinned versions, license/provenance/advisory review and an
  adapter escape hatch. SBOM/signature automation remains backlog work.
- Every release: distinguish local skips, real DB tests, actual containers,
  browser checks, live acceptance and soak. No promotion on test count alone.
- Every dataset: provenance, privacy/rights, bounded offline execution, known
  outcomes and separate development/test cases. [Test plan](TEST_MAILBOX_PLAN.md).
- Every hosted operation: independent product identities, budgets, alert ownership,
  retention/purge and tested recovery. Factory is not a runtime dependency.

See [PRD](PRD.md) for numeric quality/SLO targets and [open choices](OPEN_QUESTIONS.md)
for decisions that block live rollout but not safe synthetic implementation.
Use the [release acceptance record](RELEASE_ACCEPTANCE.md) to collect evidence for
each promotion; passing a component suite does not close a whole milestone.
