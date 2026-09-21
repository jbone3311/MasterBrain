# Implementation backlog

Ordered by dependency and risk, not calendar promises. The broad roadmap remains
the product sequence; these are buildable handoff tickets.

| ID | Work package | Acceptance / dependency |
|---|---|---|
| EB-001 | Factory registration and bind audit | Current descriptor/hooks/packs installed through Factory tooling; clean sibling checkout; bind PASS; proposals validated by Factory reader |
| EB-002 | Authenticated Fastmail transport and read-only worker | TLS/host allowlist, bounded responses/downloads, token vault, no mutating methods; mock HTTP conformance then authorized disposable account |
| EB-003 | Resumable backfill/reconciliation | Baseline Email state before listing; query-state-safe pagination; catches concurrent creates/deletes; durable leases; expired cursor reset; no partial-list deletions |
| EB-004 | Durable poison-message quarantine | Preserve source/error receipt before advancing past bad message; retry independently; accounting/alerts; no stalled account or silent skip |
| EB-005 | Encrypted object storage — local slice implemented | Local tenant-bound AES-GCM, 16 MiB preservation, transactional manifests and non-deleting inventory implemented; hosted IAM/KMS, key backup, authorized GC/purge and larger isolated parsing remain |
| EB-006 | Sandboxed attachment extraction | Factory-reviewed package contract; scanner; PDF/Office/OCR/archives; no egress, bounded CPU/time/memory/disk/depth; per-child receipts and timeouts |
| EB-007 | Production identity/grants | OIDC/MFA, JWT issuer/audience/expiry, invite/revoke, account/project grants before candidate retrieval, permission-cache invalidation, negative role matrix |
| EB-008 | Hosted infrastructure and restore | Owner-approved region/budget; private Postgres/S3, KMS/secrets, TLS ingress, CI artifacts by digest, actual restore of DB and bytes |
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

## What can proceed without owner answers

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
large-message object storage and soak remain. See [READ_WORKER.md](READ_WORKER.md).

Mock/provider transport tests, quarantine state machine, worker leases, synthetic
attachment sandbox fixtures, OIDC integration contract, SQL grants tests, temporal
reducers, policy simulations, and deployment templates. Real account consent,
paid resources, retention promises and remote disclosure await the parked choices.
