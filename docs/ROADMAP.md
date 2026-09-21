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

These are the remaining delivery packages, not a list of components to rebuild.

| Order | Package | Completion evidence |
|---|---|---|
| 1 | **Identity lifecycle (EB-007/021):** browser sign-in/session and enrollment/revocation controls over ADR-040's implemented API token/mapping foundation | New ADR; fake authorization server, callback/session/CSRF and revocation tests; browser acceptance; real issuer policy/enrollment only with approval |
| 2 | **Independent operation (EB-005/008/009):** hosted storage adapters, key recovery, supervision, enrollment administration, rate limits and alerts | Synthetic adapter contracts first; approved environment, DB/object/key restore, restart and alert-delivery proof before promotion |
| Alongside 1–2 | **Owner/document acceptance (EB-006/021/023):** browser/accessibility checks, broader held-out documents and an explicit scanner/live coverage policy | Actual browser and restricted-host evidence, per-format quality/deferral results; no implied Office/OCR support |
| 3 | **Read-only pilot:** one explicitly authorized disposable mailbox | Provider conformance, multi-day staging soak, security review, stop/rollback procedure and owner acceptance |

ADR-040 supplies the [access-token/SQL mapping foundation](IDENTITY_AUTH.md); do not
rebuild that slice. The next identity package starts with its own ADR; it does not create cloud accounts, app
registrations or public ingress. A token verifier alone is not browser login,
MFA, member invitations or authenticated MCP. Those boundaries must be explicit
in the implementation and acceptance record. See the
[Factory assignment](FACTORY_HANDOFF.md#suggested-next-issue).

Existing foundations to reuse: the [read command](READ_CONTROLLER.md),
[MIME recovery command](PROCESSING_CONTROLLER.md), [PDF command](DOCUMENT_CONTROLLER.md),
[document owner UI](DOCUMENT_REVIEW_SCREEN.md) and
[known-answer mailbox](TEST_MAILBOX_PLAN.md). These have bounded synthetic
implementations, not hosted supervision or live acceptance. The API never
receives Docker authority. Keep the three worker identities and their approvals separate.

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
separate synthetic PDF approval/extraction/search backend and owner controls. State
projectors and evaluated production interpretation remain open; explicit
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
