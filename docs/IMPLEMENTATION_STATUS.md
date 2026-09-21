# Implementation status

Updated 2026-09-20. This file distinguishes shipped prototype behavior from the
ultimate product described in the PRD. A passing CI run does not make this production-ready.

| Capability | Current implementation | Remaining gate |
|---|---|---|
| Storage | PostgreSQL migrations; tenant RLS; composite ownership keys; runtime-role checks | Managed deployment, encryption/KMS, purge and restore drills |
| Ingestion | Atomic evidence/checkpoint; resumable Fastmail worker, fenced leases, certified inventory reconciliation, expired-history recovery, bounded raw quarantine | Enrollment/scheduler, large-message storage, live acceptance and soak |
| Evidence | Raw MIME up to 1 MiB; immutable normalized snapshots; version-stable citations | Encrypted object store and larger messages |
| Attachments | Per-part receipts/events, duplicate links, bounded text extraction, FTS, explicit deferred/failed outcomes | Malware scanner, sandboxed PDF/Office/OCR/archive extraction; raw download policy |
| Retrieval | PostgreSQL FTS over subject/sender/body and extracted text attachments | Entity filters, chunk relevance excerpts, vector benchmarks and integration |
| Access | Expiring hashed-token registry; tenant/actor/scopes; owner membership checks | OIDC/MFA, invitations, member/account grants, revocation UX, rate limiting |
| Feedback | Typed proposals, evidence links, idempotency conflict detection, human-only reviews | Rule activation/simulation/rollback and temporal projection application |
| Providers | Fastmail durable worker; offline-tested Gmail/Graph read transports and injected-session IMAP contract | All live enrollment/acceptance; Gmail/Graph/IMAP durable database workers and notification ingress |
| Models | Closed classification schema, source-excerpt validation, code/local/remote/human policy | Real local runtime, calibrated eval corpus, remote disclosures/budgets |
| UI | Local search/evidence/proposals, account health and paginated held-message metadata; session clearing; synthetic browser smoke | Production login, audited reprocessing, full accessibility and live-data acceptance |
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
