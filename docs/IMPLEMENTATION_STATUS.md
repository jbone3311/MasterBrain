# Implementation status

Updated 2026-09-20. This file distinguishes shipped prototype behavior from the
ultimate product described in the PRD. A passing CI run does not make this production-ready.

| Capability | Current implementation | Remaining gate |
|---|---|---|
| Storage | PostgreSQL migrations; tenant RLS; composite ownership keys; runtime-role checks; verified synthetic logical dump/restore | Managed deployment, encryption/KMS, purge, offsite/PITR disaster-recovery drills |
| Ingestion | Atomic evidence/checkpoint; resumable Fastmail worker, fenced leases, certified inventory reconciliation, expired-history recovery, bounded raw quarantine | Enrollment/scheduler, large-message storage, live acceptance and soak |
| Evidence | Raw MIME up to 1 MiB; immutable normalized snapshots; version-stable citations | Encrypted object store and larger messages |
| Attachments | Per-part receipts/events, duplicate links, bounded plain/calendar text extraction, FTS, explicit deferred/failed outcomes; realistic synthetic MIME fixtures | Malware scanner, sandboxed PDF/Office/OCR/archive extraction; versioned historical reprocessing and raw download policy |
| Retrieval | PostgreSQL FTS over subject/sender/body and extracted text attachments | Entity filters, chunk relevance excerpts, vector benchmarks and integration |
| Access | Expiring hashed-token registry; tenant/actor/scopes; owner membership checks | OIDC/MFA, invitations, member/account grants, revocation UX, rate limiting |
| Feedback | Typed proposals; human-reviewed sender rule simulation/activation; immutable revisions and rollback; virtual search labels | Rich predicates/protected-sender configuration, temporal/entity application, drift evaluation |
| Providers | Fastmail durable worker; offline-tested Gmail/Graph read transports and injected-session IMAP contract | All live enrollment/acceptance; Gmail/Graph/IMAP durable database workers and notification ingress |
| Models | Opt-in loopback Ollama library; installed-digest checks; bounded fake-server/output tests; code-first candidate routing | Actual isolated runtime/quality evaluation, durable receipts/cache, remote disclosures/budgets |
| UI | Local search/evidence/proposals, rule preview/activation/rollback, account health and held-message metadata; session clearing; 15 Node contracts and prior synthetic browser smoke | Production login, audited reprocessing, full accessibility and live-data acceptance |
| MCP | Planned typed REST-backed surface | Official SDK adapter, OAuth, actual client compatibility matrix |
| Actions | No executable sending/deletion/mailbox-write path | Separate action ADR, preview/approval/outbox/reconciliation and disposable-account tests |
| Factory | Architecture/intake mapping and Product handoff | Registration, hooks, clean sibling checkout, bind PASS and independent Factory audit |

## Validation

Local unit/API/protocol/attachment tests, type checking and linting run with locked
dependencies. CI additionally runs real PostgreSQL integration tests against a
disposable database and non-owner runtime role. Check the repository's CI status
for the exact tested commit. No real mailbox, production restore, cloud deployment,
live model, or Factory bind has been tested by this bootstrap.

First verified database slice: [CI run 35479970496](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35479970496)
at commit `4515417`: **52 tests passed**, lint/type/repository gate passed. An earlier
run caught an ingestion-lock permission issue, fixed with an account-scoped advisory
transaction lock instead of granting account mutation privileges. Later additions
require their own newer CI run; this receipt covers the exact named commit.
