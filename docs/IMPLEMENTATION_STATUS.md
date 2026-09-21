# Implementation status

Updated 2026-09-21. This file distinguishes shipped prototype behavior from the
ultimate product described in the PRD. A passing CI run does not make this production-ready.

| Capability | Current implementation | Remaining gate |
|---|---|---|
| Storage | PostgreSQL migrations; tenant RLS; composite ownership keys; runtime-role checks; verified synthetic logical dump/restore | Managed deployment, encryption/KMS, purge, offsite/PITR disaster-recovery drills |
| Ingestion | Atomic evidence/checkpoint; resumable Fastmail worker, fenced leases, certified inventory reconciliation, expired-history recovery, bounded raw quarantine and audited human retry | Enrollment/scheduler, hosted processing supervision, live acceptance and soak |
| Evidence | Default 1 MiB inline MIME; opt-in encrypted filesystem objects up to 16 MiB; restricted MIME recovery; durable approved processing API/UI/jobs with fenced atomic results | Hosted Blob/KMS, production identity/key recovery, controller hosting and retention/purge |
| Attachments | Per-part receipts/events, duplicate links, bounded plain/calendar text extraction, FTS, explicit deferred/failed outcomes; realistic synthetic MIME fixtures | Malware scanner, sandboxed PDF/Office/OCR/archive extraction; versioned historical reprocessing and raw download policy |
| Retrieval | PostgreSQL FTS over subject/sender/body and extracted text attachments | Entity filters, chunk relevance excerpts, vector benchmarks and integration |
| Access | Expiring hashed-token registry; tenant/actor/scopes; owner membership checks | OIDC/MFA, invitations, member/account grants, revocation UX, rate limiting |
| Feedback | Typed proposals; human-reviewed sender rule simulation/activation; immutable revisions and rollback; virtual search labels | Rich predicates/protected-sender configuration, temporal/entity application, drift evaluation |
| Providers | Fastmail durable worker; offline-tested Gmail/Graph read transports and injected-session IMAP contract | All live enrollment/acceptance; Gmail/Graph/IMAP durable database workers and notification ingress |
| Models | Opt-in loopback Ollama library; installed-digest checks; bounded fake-server/output tests; code-first candidate routing | Actual isolated runtime/quality evaluation, durable receipts/cache, remote disclosures/budgets |
| UI | Local search/evidence/proposals, rule preview/activation/rollback, account health, held-message retry, processing history/approval/cancellation; session/account/view race protection | Production login, bulk historical reprocessing, full browser/accessibility and live-data acceptance |
| MCP | Planned typed REST-backed surface | Official SDK adapter, OAuth, actual client compatibility matrix |
| Actions | No executable sending/deletion/mailbox-write path | Separate action ADR, preview/approval/outbox/reconciliation and disposable-account tests |
| Factory | Architecture/intake mapping and Product handoff | Registration, hooks, clean sibling checkout, bind PASS and independent Factory audit |
| Test data | Coherent seeded conversations/documents, independent PDF/Office reads, hash manifests, export and bounded paced/resumable SQL feed; mocked provider formats | More varied/held-out scenarios, scanned-text/password-protected fixtures, sustained soak and authorized live replay; see [test mailbox guide](TEST_MAILBOX_PLAN.md) |

The current source includes ADR-033's [known-answer test mailbox](TEST_MAILBOX_PLAN.md)
and ADR-032's [bounded operator processing command](PROCESSING_CONTROLLER.md),
plus ADR-031/migration 0011 processing history and owner controls. The command adds
private configuration/preflight, fresh worker authentication and graceful stop,
not credential enrollment or hosted supervision. Exact verification is recorded
separately in [BUILD_RECEIPT.md](BUILD_RECEIPT.md);
do not apply historical counts to a newer commit. Generic project/fact proposals
do not create entities. Virtual labels do not change provider folders. A configured
parser does not certify an online worker, and a completed job can have deferred attachments.

## Validation

### Important attachment boundary

The processing CLI/API/UI operate on approved held-message recovery, not arbitrary
PDF/Office parts in ready messages. Ready-body search and deferred-attachment
accounting can coexist. Source-bound attachment jobs and binary extraction still
need their own approved design and integrated tests; no new PDF capability is
claimed by this documentation refresh. [Next contract](BACKLOG.md#eb-006-next-source-bound-document-processing).

### Verified runtime

Latest verified runtime/test commit: **4286504**, [CI 35572975435](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35572975435).
1,392 Python tests (178 real PostgreSQL), 52 Node UI contracts and five additional
actual-container cases passed. Restore at the same runtime commit verified
24 tables, 119 rows, two tenants and four encrypted objects. See
[BUILD_RECEIPT.md](BUILD_RECEIPT.md) for exact scope, warnings and limitations.
These include bounded known-answer mailbox generation/replay, not sustained live
feed service, real model accuracy or new browser/accessibility acceptance.

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
