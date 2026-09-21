# Testing and Evaluations

Updated 2026-09-21. [TEST_MAILBOX_PLAN.md](TEST_MAILBOX_PLAN.md) documents the
implemented bounded fictional generator, answer keys, export and database replay,
along with the remaining quality/soak gaps. [PUBLIC_EMAIL_TEST_DATA.md](PUBLIC_EMAIL_TEST_DATA.md)
governs outside samples. Runtime verification is tied to exact commits below and
in [BUILD_RECEIPT.md](BUILD_RECEIPT.md), not inferred from test-plan requirements.

Use the [worked product scenario](PRODUCT_WALKTHROUGH.md) as a cross-feature
acceptance checklist: import, body/attachment coverage, historical corrections,
search authorization, reviewed changes and eventual actions. Each step must keep
its current status until its own tests pass; a generated expected answer is not a
measured model answer. [Documentation rules](DOCUMENTATION_STANDARD.md) prevent
test plans, skipped checks and prior receipts from being presented as new results.

Processing history/owner controls add Python account/cursor/read-only tests and
27 independent Node cases, alongside 25 existing UI cases. ADR-038 adds the PDF
owner/search suite. Run all three suites:

```sh
node --test tests/web_session.test.cjs tests/web_processing.test.cjs tests/web_documents.test.cjs
```

The DOM harness covers same-key uncertain retries, double clicks, malformed
responses, cancellation/completion races, stale account/session responses and
history pagination. It is not browser/accessibility acceptance. The optional
[visual fixture](PROCESSING_REVIEW_SCREEN.md) simulates jobs in memory; SQL tests
and restore runs prove database durability separately. Exact verified counts and
commits belong in [BUILD_RECEIPT.md](BUILD_RECEIPT.md).

## Durable processing jobs

[ADR-030](adr/030_durable_recovery_jobs.md) adds API/worker/SQL tests for
human approval, scope separation, actor-bound idempotency, concurrent claims,
lease/approval deadlines, cancellation, membership revocation, provider changes,
bounded retries and crash recovery. Actual-container CI exercises a large encrypted
message through API approval, worker, atomic completion and searchable evidence.
Restore covers pending/cancelled/completed grants, unchanged expiry and tenant
isolation. No live provider, cloud host or real user message is used.

Isolated MIME adds strict parent-envelope, input/output/complexity/resource bounds,
Docker pre-disclosure isolation inspection, exact ownership cleanup and processor
version/race tests. The explicit post-image-build `tests/container_mime_checks.py`
suite runs actual Docker, then encrypted source -> isolated recovery -> real
PostgreSQL -> body/attachment search. Its results are counted separately from the
default Python suite; mocked isolation never substitutes for this check.
See [contract](ISOLATED_MIME_RECOVERY.md).

Encrypted evidence tests cover authenticated context, tampering, wrong keys,
rotation, concurrent publication, private paths, symlinks, ownership, crash/fsync
failure and bounded inventory. `tests/test_large_evidence.py` adds API error
scrubbing, direct staging limits and real PostgreSQL authorization/manifest/rollback
tests, mixed inline/external evidence, large-message holding and restarted Fastmail
worker progress. The restore drill requires restored SQL and ciphertext, rejecting
missing objects before verifying raw hashes. Local database skips are not proof;
CI supplies PostgreSQL. See [storage](LARGE_EVIDENCE_STORAGE.md) and the exact-commit
[receipt](BUILD_RECEIPT.md).

Held-message recovery adds human/scope/API denial, real PostgreSQL retry races,
newer-provider-event fences, atomic publication rollback, raw hash failure,
same-parser idempotency, parser-versioned search, immutable historical citations,
legacy metadata, RLS and populated-schema upgrade checks. The synthetic logical
restore also includes failed recovery attempts. See [recovery](QUARANTINE_RECOVERY.md).

See the [implemented coverage matrix and explicit gaps](TEST_COVERAGE_MATRIX.md).

## Current executable checks

[Read-controller tests](../tests/test_read_controller.py) cover private configuration,
exact scopes, explicit execution, zero-request preflight, fixed output, stop and
credential changes. [SQL integration](../tests/test_read_controller_postgres.py)
runs actual Fastmail transport logic against fake HTTPS responses and real SQL:
restart/search, paused/retry state, identity/source/lease changes during downloads,
encrypted large mail and CLI dispatch. This does not contact Fastmail or certify
hosted scheduling. Existing worker pressure tests remain required.

[PDF owner controls](DOCUMENT_REVIEW_SCREEN.md) add explicit selection/approval,
history/cancel, opt-in search and page-evidence Node contracts. Negative cases
cover exact identities, malformed envelopes, bounded pages, Unicode offsets,
same-key uncertainty, duplicate clicks and stale query/session/account/view/card
responses. Four SQL/API bridge cases feed actual serialized responses through the
DOM harness (extracted/partial/deferred/failed), using a known-answer reader.
These caught the original receipt's `not_scanned` versus PDF result's `unscanned`
contract mismatch; the corrected offline fixtures also reject invented clean/safe
scan states. Keep the SQL bridge when changing the UI's hand-authored fixtures.
Static-route/HTML checks retain same-origin/no-store and explicit opt-in controls.
Neither harness nor static HTML checks prove real browser/accessibility acceptance.

[Documentation checks](DOCUMENTATION_STANDARD.md#automated-check-scope) cover the
required pack/guides/templates and local paths/supported headings across root,
`docs/` and `.github/`. Synthetic checker regressions exercise missing files,
broken fragments, encoded paths, duplicate headings, code-example exclusion,
template navigation and repository escape. This is not external-source freshness
or rendered browser/accessibility proof.

[Document controller tests](DOCUMENT_CONTROLLER.md) exercise the separate CLI/config,
exact worker scope, synthetic account gate, nonclaiming preflight, private keys,
revocation/rotation, counters, cancellation and restart. Real PostgreSQL tests use
a known-answer reader; the explicit PDF container suite additionally runs fresh
CLI processes over encrypted source and the actual restricted image. The emitted
demo-owner registry has a regression test; server-option tests retain loopback binding.
These checks do not certify the separate document UI or a deployed supervisor;
the new UI-specific checks above cover its local contracts.

[Document jobs](DOCUMENT_PROCESSING.md) add real-SQL lifecycle/race/authorization,
API, immutable revision and current-versus-historical search tests. The PDF container
suite now also runs source -> approval -> restricted PDF -> SQL -> cited search.
Restore seeds completed/cancelled/pending document jobs and text/evidence revisions.
These do not certify a browser, malware scanner or live processing policy.

[PDF worker tests](PDF_WORKER.md) independently exercise the source-bound request
and strict parent response, known-answer PDF text, selected MIME paths/hashes,
encrypted/empty-password/damaged/image-only/mixed-page inputs and logical budgets.
Parent tests cover fixed-profile pre-disclosure isolation, ownership cleanup,
crashes, forged results and absence of eager PDF imports. The separate explicit
`tests/container_pdf_checks.py` runs the dedicated real image in CI; it is not
counted in the standard test suite. Reader-only cases do not prove integration;
the explicitly named SQL/search and operator-CLI cases exercise those connections.
Default-image exclusion and existing MIME/SQL/container tests remain required.

[Known-answer mailbox tests](TEST_MAILBOX_PLAN.md) now independently read generated
PDF/XLSX/DOCX, validate PNG/ZIP/MIME/calendar structure, check authored current-parser
outcomes and run the same sources through four mocked provider read contracts.
Actual SQL tests cover paced/restarted ingestion, commit-response loss, competing
feeders, account/enrollment/scope denial, malformed MIME quarantine, source hashes,
current search and absence of binary-only terms. Semantic targets remain unevaluated;
an image-only diagram is not an OCR benchmark. No private/public mail was downloaded.

[Controller tests](PROCESSING_CONTROLLER.md) add hostile private-file/configuration
cases, worker credential freshness, bounded polls, signal cleanup, result redaction
and actual SQL preflight/restart/revocation. The explicit container suite additionally
invokes the real CLI in new processes with encrypted source keys and an approved
local image. No hosted supervisor or multi-day soak is inferred from these tests.

[Calendar and format fixtures](CALENDAR_ATTACHMENTS.md) exercise actual MIME bytes,
harmless OOXML/image/calendar contents, and provider response encodings without
contacting providers. Deferred binary extraction is an expected limitation, not a
successful text extraction. [Public fixture adoption](PUBLIC_EMAIL_TEST_DATA.md)
is documented but no external corpus is part of current CI results.

New suites cover the complete reviewed-rule REST lifecycle, bounded previews,
competing activation/rollback, tenant/actor isolation and virtual-only effects.
The two Node suites above check the local UI contracts. Local-model tests
use fake responses exclusively; they test transport/schema/privacy boundaries, not
classification accuracy. The separate [restore workflow](RESTORE_DRILL.md) performs
an actual synthetic `pg_dump`/`pg_restore` with recovered content and RLS verification.

`uv run pytest -q` covers unit/API, JMAP/Fastmail mock transport, normalization,
hostile attachment/type/filename cases and, with a disposable DB, real Postgres
migrations, RLS, membership, composite ownership, raw-history protection, replay,
rollback, stale cursors, proposal conflicts and attachment FTS. Type/lint commands
are `uv run mypy src` and `uv run ruff check .`. CI requires the Postgres suite and
builds/smokes the developer container. Local skipped database tests are not passes.

The worker suite additionally tests synthetic HTTP → real DB → search, query-list
churn with deletions, process recreation, eight competing lease claimants, stale
worker fencing, crash-after-commit replay, malformed metadata/checkpoints, account
mismatch, auth/throttle/outage pauses, cursor expiry, metadata flag changes and
durable poison MIME quarantine. The larger corpus exercises full import, mixed
incremental updates/deletes, expired-history recovery and multi-page absence
reconciliation. Offline fuzzing uses 1,000 seeded bounded random byte inputs.
Retry bounds are checked over 15,015 combinations. These are
bounded fault/pressure tests, not a multi-day load/soak test or live-provider proof.

Targets below still need private-corpus and production-like testing. No live
provider, malware scanner, cloud restore or model-quality evaluation is implied by unit tests.

## Test layers

### First binary-extraction acceptance gate (ADR-035 synthetic slice)

Use a ready message from the existing known-answer packet whose PDF-only marker
is currently absent from search. Prove explicit source/part/parser approval,
isolated extraction, parent validation, atomic versioned publication and authorized
FTS. Its body must remain searchable when the document fails, is deferred or its
job is cancelled. Test foreign tenants, expired approval, revoked membership,
changed evidence, lost responses, restart and restore. Include image-only,
encrypted, malformed and resource-exhausting PDFs with explicit outcomes.

Keep scan status independent of text extraction. Independent readers verifying our
generated fixtures are not production extractor acceptance. Standalone sandbox
checks are necessary but do not prove the complete approved source-to-search path.
See [EB-006](BACKLOG.md#eb-006-next-source-bound-document-processing).

### Unit and property tests

MIME/date/address parsing, canonicalization, hashes, thread heuristics, rule AST, conflict ordering, authorization predicates, state transitions, rank fusion, redaction, and schema validation. Use generated MIME trees, Unicode, malformed headers, oversized parts, and property tests for idempotency.

### Connector contract tests

Recorded/synthetic provider fixtures cover pagination, empty pages, duplicate/out-of-order notifications, cursor expiry, full-resync recovery, deletes, moves, label/flag changes, rate limits, auth revocation, and crash boundaries. Live tests use disposable accounts/folders only.

For Gmail, explicitly test `historyId` HTTP 404 recovery described in the [sync guide](https://developers.google.com/workspace/gmail/api/guides/sync). For Graph, test opaque `nextLink`/`deltaLink`, folder scope, and `@removed` entries documented by [Microsoft](https://learn.microsoft.com/en-us/graph/api/message-delta?view=graph-rest-1.0).

### Database and tenancy tests

- Migrations up/down or forward-repair rehearsal on production-sized snapshots.
- RLS matrix for every role/table/operation, including missing tenant context and guessed IDs.
- Runtime role cannot own tables or bypass RLS; test all API scope/account boundaries.
  The prototype trusted server can set tenant context and read raw evidence for
  processing. RLS does not contain a server compromise with arbitrary SQL access;
  role splitting and a stronger service-principal boundary remain production gates.
- Backup restore, constraint checking, object/hash reconciliation, replica revocation.

### Action tests

State-machine model tests and fault injection before/after provider calls. Verify idempotency, approval hash/expiry, expected-version conflicts, kill switch, dry run, partial batch failure, compensation, and reconciliation. Permanent delete/send tests are disabled outside explicitly isolated fixtures.

## Retrieval evaluation

Create owner-authored questions with relevance judgments and required evidence. Include exact names, aliases, addresses, confirmation numbers, dollar amounts, dates, fuzzy concepts, thread context, negation, stale facts, and authorization boundaries.

Measure:

- Recall@k, MRR/nDCG, top-5 success, citation precision.
- Lexical vs vector vs hybrid ablations.
- Filter correctness, diversity, latency, index freshness.
- Answer faithfulness and unsupported-claim rate.

Never declare vectors successful without beating lexical/structured baselines on real tasks.

## Classification/extraction evaluation

Use synthetic mail plus consented, access-controlled, redacted real examples. Split by thread/sender/time to prevent leakage. Report per-class precision/recall/F1, confusion matrix, calibration/Brier score, abstention coverage, JSON validity, evidence-span accuracy, latency, hardware, tokens, and cost.

Set consequence-weighted gates:

- `Review Delete`: ≥99.5% precision target; no permanent auto-delete.
- `Needs Reply`: ≥95% precision target and explicit recall target after baseline.
- Facts/obligations: 100% valid evidence reference; measure semantic correctness separately.
- Model upgrades: non-inferiority on protected/high-impact slices.

## Security evaluations

- Cross-tenant ID guessing, pagination/cursor swapping, cache poisoning, signed-URL reuse.
- OAuth audience/scope/expiry/PKCE errors and token-passthrough attempts.
- Direct/indirect prompt injection in subject/body/HTML/signature/attachment/OCR and encoded text.
- Exfiltration URLs, tool-call injection, schema smuggling, oversized/nested payloads.
- Malicious MCP tool metadata and changed tool lists.
- SSRF, archive bombs, parser fuzzing, malware quarantine bypass.

OWASP recommends testing retrieved content, tool actions, monitoring, and kill switches as part of prompt-injection defense ([guidance](https://cheatsheetseries.owasp.org/cheatsheets/LLM_Prompt_Injection_Prevention_Cheat_Sheet.html)).

## Reliability and performance

- Soak sync and ingestion with millions of synthetic messages.
- Kill workers at each state transition; replay events repeatedly.
- Provider outage/throttle, queue backlog, database failover, model timeout, object-store errors.
- p50/p95/p99 API/search/ingest latency; memory/CPU/disk; connection/queue saturation.
- Recovery point/time measured in restore drills.

## Evaluation governance

Datasets have owners, consent/classification, retention, and access logs. Never commit real mail. Version dataset manifest, taxonomy, prompt, schema, model/runtime, chunker, embedding, and scorer. Store aggregate metrics and hashed case IDs; restrict raw failures. Promotion requires signed comparison and rollback plan.
