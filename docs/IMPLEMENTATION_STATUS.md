# Implementation status

Updated 2026-09-21. This file distinguishes shipped prototype behavior from the
ultimate product described in the PRD. A passing CI run does not make this production-ready.

| Capability | Current implementation | Remaining gate |
|---|---|---|
| Storage | PostgreSQL migrations; tenant RLS; composite ownership keys; runtime-role checks; verified synthetic logical dump/restore | Managed deployment, encryption/KMS, purge, offsite/PITR disaster-recovery drills |
| Ingestion | Atomic evidence/checkpoint; resumable Fastmail worker and bounded private-configured read CLI; fenced leases, certified inventory reconciliation, expired-history recovery, bounded raw quarantine and audited human retry | Enrollment/resume administration, hosted supervision/alerts, live acceptance and soak |
| Evidence | Default 1 MiB inline MIME; opt-in encrypted filesystem objects up to 16 MiB; restricted MIME recovery; durable approved processing API/UI/jobs with fenced atomic results | Hosted Blob/KMS, production identity/key recovery, controller hosting and retention/purge |
| Read original email | Human-only complete selected body for MIME up to 1 MiB, inert HTML-to-text, headers, explicit verified original/leaf-part downloads | Larger bodies remain stored projections on screen; full large-message reader and nested-part export require restricted processing; no formatted HTML |
| Attachments | Per-part receipts/events, duplicate links, bounded plain/calendar text extraction, FTS, explicit deferred/failed outcomes; explicit unscanned human downloads for small-source leaf parts | Malware scanner, production PDF intake policy, Office/OCR/archive extraction; bulk historical document reprocessing and large/nested separate exports |
| Approved PDF processing | Separate restricted worker; synthetic API/library/operator and owner approval/history/cancel UI, durable fenced jobs, immutable results, opt-in FTS and cited pages | Browser acceptance, hosted supervision, scanner/live policy and real-world quality; ordinary ingestion still defers PDFs |
| Retrieval | PostgreSQL FTS over subject/sender/body and extracted text attachments; opt-in latest-current PDF extraction text | Entity filters, chunk relevance excerpts, vector benchmarks and integration |
| Access | Explicit bootstrap or RFC/Entra access-token verification; administrator-owned SQL mappings, revision/expiry/scope/owner rechecks and binding audit | Browser sign-in/session lifecycle, MFA/issuer enrollment, invitations, member/account grants, revocation UX, rate limiting |
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

ADR-045 adds the [owner reader](MESSAGE_READER.md) and [fictional user test](USER_TESTING.md).
The latter is a usability fixture, not database/live-mail acceptance. The verified
runtime below predates this addition until its own exact-commit receipt is recorded.

ADR-044 corrects cache-refresh contention and sender ambiguity. Current search and
rule previews require source-derived sender eligibility; historical snapshots
without it remain readable but do not match rules. Ordinary parser is v5; no
automatic reprocessing or schema change. Exact verification is in the build receipt.

ADR-042 now supplies the optional [browser authorization/session backend](BROWSER_AUTH.md),
including fake code exchange, current mapping, cookie/Origin/CSRF, expiry and
cancellation/replay fences. ADR-043 adds explicit `serve --browser-config` with
private TLS files and a non-consuming configuration check. Unflagged `serve` and
the owner UI are unchanged. UI integration and actual browser acceptance remain
next; no production sign-in or hosted availability is claimed.

### Latest verified runtime

**98a334c** passed [CI 35624876529](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35624876529):
2,156 Python tests including 306 real SQL cases, 84 Node contracts, five actual
MIME-container and 15 actual PDF-container cases. The same revision passed
[restore 35624876390](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35624876390):
27 tables, 147 rows, two tenants, four encrypted objects and two identity bindings,
including revoked-context denial. Exact scope, local skips and limitations are in
the [build receipt](BUILD_RECEIPT.md). Receipt-only edits are not a new runtime test.

### Increment boundaries

ADR-041 closes buffered response deadline gaps in Fastmail, Gmail, Graph and the
local Ollama adapter. Sixteen controlled-clock transport cases include slow-drip
and delayed-empty regression tests, fragmentation, byte caps and stream closure.
This changes neither connector availability nor live-service acceptance.

ADR-040 adds the [configured API identity foundation](IDENTITY_AUTH.md), migration
0013 and PyJWT 2.14.0. Generated-key/fake-issuer tests exercise token/profile/cache
boundaries; real SQL/API cases cover mapping/RLS/revocation and the restore fixture
now includes populated identity bindings. Exact pass/fail evidence belongs in the
build receipt, not this implementation description. No browser login, live issuer,
MFA enforcement, team grants or public ingress is implied.

ADR-039 adds the [bounded read controller](READ_CONTROLLER.md), exact ingest-worker
identity, explicit execution flag and non-consuming preflight. Current tests use
fake HTTPS plus SQL for restart, revocation, lease/source binding, retries/pauses
and encrypted evidence. Exact observed results belong in the build receipt; no
live/provider/hosted acceptance follows from the new CLI.

ADR-038 adds the [owner PDF screen](DOCUMENT_REVIEW_SCREEN.md), generation-fenced
search/evidence rendering and opt-in document search. Node contracts and a real
SQL/API-response-to-DOM bridge test this slice; neither is browser/accessibility
acceptance. No new schema, dependency or mailbox/worker scope.

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
separate API/SQL/search workflow. ADR-038 now adds separate owner controls. Exact-commit acceptance
is recorded in the build receipt, not inferred from this row. ADR-036 adds the
separate `process-documents` command; it does not expand `process-jobs` or its UI.

ADR-037 strengthens documentation inventory/local-section-link checks and adds a
methods guide. It changes no product capability or permission. Its tooling tests
and verification are recorded separately from runtime and live-acceptance claims.

### Previously verified read-operator runtime

Read-controller implementation **0b4f0d3** passed
[CI 35590968421](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35590968421):
**1,772 Python tests (249 real PostgreSQL), 84 Node contracts, five MIME and 15 PDF
actual-container cases**. New operator cases use fake HTTPS responses with real
SQL, including restart, revoked credentials/ownership, changed bindings/leases,
pause/retry and encrypted source readback. No real provider or identity enrollment.

[Restore 35590968376](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35590968376)
at the same runtime verified 26 tables, 142 rows, two tenants, four encrypted
objects, matching hashes and RLS. Local tests explicitly skipped 249 SQL cases;
the CI run supplies their proof. Later receipt-only changes do not alter this
runtime. Full scope and remaining gates are in [BUILD_RECEIPT.md](BUILD_RECEIPT.md).

### Prior verified owner PDF runtime

Owner PDF implementation **8d8af93**, corrected at **f73c235**, passed
[CI 35589125895](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35589125895):
**1,668 Python tests (226 real PostgreSQL), 84 Node contracts, five MIME and 15 PDF
actual-container cases**. The four SQL/API-to-DOM cases initially exposed a
scan-status contract mismatch; the corrected implementation and fixtures now pass.
No schema, permission or immutable-receipt change was needed.

[Restore 35589125878](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35589125878)
at f73c235 verified 26 tables, 142 rows, two tenants and four encrypted objects,
matching hashes and RLS. The limited browser smoke covered initial controls and
session reset only, not end-to-end PDF/browser accessibility acceptance. Exact
scope, local skips and remaining gates are in [BUILD_RECEIPT.md](BUILD_RECEIPT.md).
Later receipt-only documentation is not a newly CI-verified runtime revision.

### Prior verified runtime (before the owner PDF screen)

Application runtime **73a8459** and its documentation/tooling follow-up
**874c288** passed [CI 35585839904](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35585839904):
1,660 Python tests (222 real PostgreSQL), 52 Node UI contracts, five MIME
and 15 PDF actual-container cases. The added 28 cases test documentation tooling,
not new product features. Runtime revision 73a8459's separate
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
