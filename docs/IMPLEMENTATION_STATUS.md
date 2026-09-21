# Implementation status

Updated 2026-09-21. This file distinguishes shipped prototype behavior from the
ultimate product described in the PRD. A passing CI run does not make this production-ready.

| Capability | Current implementation | Remaining gate |
|---|---|---|
| Storage | PostgreSQL migrations; tenant RLS; composite ownership keys; runtime-role checks; verified synthetic logical dump/restore | Managed deployment, encryption/KMS, purge, offsite/PITR disaster-recovery drills |
| Ingestion | Atomic evidence/checkpoint; resumable Fastmail worker, fenced leases, certified inventory reconciliation, expired-history recovery, bounded raw quarantine and audited human retry | Enrollment/scheduler, hosted processing supervision, live acceptance and soak |
| Evidence | Default 1 MiB inline MIME; opt-in encrypted filesystem objects up to 16 MiB; restricted MIME recovery; durable approved processing API/UI/jobs with fenced atomic results | Hosted Blob/KMS, production identity/key recovery, controller hosting and retention/purge |
| Attachments | Per-part receipts/events, duplicate links, bounded plain/calendar text extraction, FTS, explicit deferred/failed outcomes; realistic synthetic MIME fixtures | Malware scanner, production PDF intake policy, Office/OCR/archive extraction; bulk historical document reprocessing and raw download policy |
| Approved PDF processing | Separate restricted worker; synthetic approval API/library and explicit operator CLI, durable fenced jobs, immutable results, opt-in FTS and page excerpts | Owner UI, hosted supervision, scanner/live policy and real-world quality; ordinary ingestion still defers PDFs |
| Retrieval | PostgreSQL FTS over subject/sender/body and extracted text attachments; opt-in latest-current PDF extraction text | Entity filters, chunk relevance excerpts, vector benchmarks and integration |
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

ADR-036 adds [explicit document execution](DOCUMENT_CONTROLLER.md), separate
purpose/policy configuration and worker scope, plus a loopback server channel flag.
It fixes invalid demo-owner credential generation by allowlisting human scopes.
Exact local/CI verification is recorded below and in the build receipt; do not
apply these counts to an untested later revision.

### Important attachment boundary

The MIME processing CLI/API/UI operate on approved held-message recovery, not arbitrary
PDF/Office parts in ready messages. Ready-body search and deferred-attachment
accounting can coexist. ADR-035 now adds a separate synthetic-only document-job
API/library and extraction publication; it does not expand MIME approvals or the
existing operator CLI. [Document contract](DOCUMENT_PROCESSING.md).

ADR-034 supplies the [restricted PDF worker](PDF_WORKER.md); ADR-035 supplies the
separate API/SQL/search workflow. UI controls remain absent. Exact-commit acceptance
is recorded in the build receipt, not inferred from this row. ADR-036 adds the
separate `process-documents` command; it does not expand `process-jobs` or its UI.

ADR-037 strengthens documentation inventory/local-section-link checks and adds a
methods guide. It changes no product capability or permission. Its tooling tests
and verification are recorded separately from runtime and live-acceptance claims.

### Verified runtime

Latest verified runtime/test revision: **73a8459**, [CI 35584256073](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35584256073).
1,632 Python tests (222 real PostgreSQL), 52 Node UI contracts, five MIME
and 15 PDF actual-container cases passed. The same revision's
[restore](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35584256115)
verified 26 tables, 142 rows, two tenants and four encrypted objects. See
[BUILD_RECEIPT.md](BUILD_RECEIPT.md) for exact scope, warnings and limitations.
These include the explicit document CLI from encrypted source to restricted PDF/
SQL/search/evidence, credential repair and known-answer mailbox generation/replay,
not document UI, scanning, sustained live feed, real model
accuracy or new browser/accessibility acceptance.

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
