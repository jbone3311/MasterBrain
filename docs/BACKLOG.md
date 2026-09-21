# Implementation backlog

Ordered by dependency and risk, not calendar promises. The broad roadmap remains
the product sequence; these are buildable handoff tickets.

Reviewed 2026-09-21 through ADR-039; exact verified commits remain in the build receipt. A partly implemented
ticket stays open until its stated production/acceptance gates are met.

| ID | Work package | Acceptance / dependency |
|---|---|---|
| EB-001 | Factory registration and bind audit | Current descriptor/hooks/packs installed through Factory tooling; clean sibling checkout; bind PASS; proposals validated by Factory reader |
| EB-002 | Authenticated Fastmail transport, read-only worker and bounded operator CLI implemented | Fixed HTTPS/read methods, private preflight, ingest-only identity and guarded execution; enrollment/vault, hosted supervision and authorized disposable-account acceptance remain |
| EB-003 | Resumable backfill/reconciliation | Baseline Email state before listing; query-state-safe pagination; catches concurrent creates/deletes; durable leases; expired cursor reset; no partial-list deletions |
| EB-004 | Durable poison-message quarantine | Preserve source/error receipt before advancing past bad message; retry independently; accounting/alerts; no stalled account or silent skip |
| EB-005 | Encrypted object storage — local slice implemented | Local tenant-bound AES-GCM, 16 MiB preservation, transactional manifests and non-deleting inventory implemented; hosted IAM/KMS, key backup, authorized GC/purge and offsite acceptance remain |
| EB-006 | Sandboxed attachment extraction — synthetic PDF backend/operator/UI implemented | Restricted MIME recovery plus separate synthetic PDF approvals/results/FTS, explicit CLI and owner UI implemented; browser acceptance, scanner/live policy, Office/OCR/archives, hosted identity/supervision and production sandbox acceptance remain |
| EB-007 | Production identity/grants | OIDC/MFA, JWT issuer/audience/expiry, invite/revoke, account/project grants before candidate retrieval, permission-cache invalidation, negative role matrix |
| EB-008 | Hosted infrastructure and restore | Owner-approved region/budget; private Postgres/object storage, KMS/secrets, TLS ingress, CI artifacts by digest, actual restore of DB and bytes |
| EB-009 | Operations baseline | Rate limits, connection pool, job SLOs/counters, denial audit, immutable audit export, dashboards, alert ownership, budget caps |
| EB-010 | Rules storage/simulation/application | Safe DSL, immutable versions, sample preview, protected-class veto, explicit corrections outrank inferred patterns, shadow drift sample, rollback |
| EB-011 | Local model adapter/eval harness | Approved local model weights/license, schema constrained output, evidence verification, no cloud fallback, cache/versioning, gold-set calibration |
| EB-012 | People/projects/threads/obligations | Provenance, valid/recorded time, reversible merges, current-state reducers, obligations closed/reopened from evidence, grants |
| EB-013 | Narrow MCP adapter | Official pinned SDK, REST-backed scopes, OAuth/no token passthrough, injection fixtures, tested Grok/ChatGPT/Claude support matrix |
| EB-014 | Controlled actions and drafts | Separate credentials/worker; preview hash/version/expiry, human approval, outbox, reconcile uncertain effects, kill switch; no permanent delete/send by default |
| EB-015 | Gmail connector | History/PubSub auth, watch renewal, expired-history full sync, restricted-scope consent plan, attachments/moves conformance |
| EB-016 | Microsoft connector | Folder deltas, immutable IDs/moves, subscription lifecycle, authenticated notifications, consistency tests |
| EB-017 | iCloud connector | IMAPClient, PEEK/read-only SELECT, UIDVALIDITY, IDLE hint/reconcile, app-password rotation, no Seen flag side effects |
| EB-018 | Evaluated hybrid retrieval | Exact filters + FTS baseline; pgvector exact/RRF first; tenant grants before candidates; old/new model index versioning and recall tests |
| EB-019 | Remote escalation | Explicit disclosure policy/consent, redaction, per-task/tenant budgets, provider retention contract, evidence-based eval |
| EB-020 | Retention/export/purge | Legal/owner policy; raw/derived/vector/cache deletion; backup aging; append-only audit with content minimization; tested completion certificate |
| EB-021 | Review UI hardening | Auth/login, pagination, previews, full schema forms, keyboard/screen-reader tests, safe attachment download, no active email HTML |
| EB-022 | Supply chain release gates | SBOM/license/advisory scans, digest-pinned images/actions, artifact signatures, tested dependency upgrades and rollback |
| EB-023 | Believable known-answer test mailbox — bounded slice implemented | Coherent threads/revisions, actual formats, independent readers, manifest/export, paced SQL replay and crash/race tests; broader held-out layouts, OCR/password-protected fixtures, multi-day soak and authorized live delivery remain; see [guide](TEST_MAILBOX_PLAN.md) |

EB-021 now includes bounded processing history, explicit isolated approval/cancel,
manual status and stale-context safeguards. Production login, actual browser/
accessibility acceptance and broad review forms remain. EB-023 now has executable
known-answer generation/replay, not just sample-dataset research. Existing simple
seeding and isolated format fixtures remain supported. Milestone ordering is in
[ROADMAP.md](ROADMAP.md).

## What can proceed without owner answers

### EB-006 next: source-bound document processing

ADR-034 implements the [separate PDF worker contract/profile](PDF_WORKER.md).
ADR-035 now implements the [synthetic approval/API/SQL/search slice](DOCUMENT_PROCESSING.md)
of steps 1–4 below, with actual-container integration and restore tests. ADR-036
adds the [explicit document command](DOCUMENT_CONTROLLER.md); ADR-038 adds the
[owner review UI](DOCUMENT_REVIEW_SCREEN.md). Browser acceptance, scanner/live
policy, broader quality and hosted operations remain open. Do not
reimplement the reader or broaden the old MIME queue to make it callable.

Write and review an ADR before new behavior beyond the accepted contract. Existing `recovery_jobs`
approve a quarantine receipt, not arbitrary attachments in ready mail. Do not
fabricate quarantine rows, broaden the MIME result contract silently or remove
working message search to reuse that queue.

Deliver in independently verified slices:

The original acceptance checklist follows; it is not a fresh blank-slate assignment.
The explicit document UI now has session/account/view and same-request tests;
next complete browser, scanner/live and hosted acceptance. Keep those distinct from API/library proof.
The separate document controller/configuration tests are now implemented; do not
rebuild the command or reuse the MIME command for PDF work.

1. Define the attachment source/approval/result contract and decide whether a
   separate queue/schema is needed. Bind tenant/account, evidence version, part
   path/hash, processor/image, policy, requester and expiry. Document migration,
   grants, API/UI, counters and rollback before implementation.
2. Implement a dedicated bounded PDF worker profile. Keep binary readers out of
   API/ordinary MIME images; enforce no network, non-root execution, CPU/memory/time
   limits and closed parent-validated output. OCR/Office can remain deferred.
3. Wire eligible ready-message attachments through review -> durable job ->
   isolated processor -> fenced versioned evidence -> authorized FTS. Preserve
   working body search and historical citations on failure or cancellation.
4. Prove known-answer extraction plus encrypted, image-only, corrupt, oversized,
   complex and active-content cases. Define scanner policy separately; do not mark
   a document safe because text was extracted. Actual-container, real-SQL, tenant
   denial, restart, revocation, stale-source and restore tests are required.

The first integrated PDF backend exit is verified at the commits in the
[build receipt](BUILD_RECEIPT.md): a PDF-only marker initially absent from
search becomes searchable **only** after the authorized successful extraction;
other tenants never see it; failure has an explicit outcome and leaves body search
intact. This closes the bounded backend slice, not the full EB-006 production ticket.

### Other safe parallel work packages

EB-006/009 now include the [approved-processing operator command](PROCESSING_CONTROLLER.md):
private config, exact worker scope, non-claiming preflight, bounded polling, fixed
counts and graceful stop. This closes the recovery-library invocation gap, not
hosted supervision, Fastmail enrollment, service principals or alert delivery.

EB-010 now has a working narrow human-reviewed sender-rule loop, bounded simulation,
revisioned activation/rollback and virtual search labels. Rich policy/protected-class
configuration and autonomous application remain open. EB-011 now has an opt-in
Ollama adapter and fake-server evaluations; actual model quality and runtime isolation
remain unverified. EB-008 has a separate disposable logical restore workflow;
managed-cloud backup/PITR, encryption, region and owner approval remain open.

Worker progress update: EB-002 now includes orchestration plus synthetic HTTP-to-DB
coverage; EB-003 includes durable pagination, fresh-generation query restart,
fenced leases and certified full inventory reconciliation after history expiry.
EB-004 now retains bounded rejected MIME, immutable receipts and current quarantine
counts without stalling healthy mail. Migration 0008 adds explicit human retry of
current held evidence, immutable outcomes and parser-versioned search; bulk
historical reprocessing, automated alerts and live acceptance remain.
These tickets are not production-closed: enrollment, scheduling, live acceptance,
hosted object storage, hosted processing supervision and soak remain. Local encrypted
preservation is implemented; see [READ_WORKER.md](READ_WORKER.md).

Mock/provider transport tests, quarantine state machine, worker leases, synthetic
attachment sandbox fixtures, OIDC integration contract, SQL grants tests, temporal
reducers, policy simulations, and deployment templates. Real account consent,
paid resources, retention promises and remote disclosure await the parked choices.
