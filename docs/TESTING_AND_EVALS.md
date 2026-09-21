# Testing and Evaluations

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

[Calendar and format fixtures](CALENDAR_ATTACHMENTS.md) exercise actual MIME bytes,
harmless OOXML/image/calendar contents, and provider response encodings without
contacting providers. Deferred binary extraction is an expected limitation, not a
successful text extraction. [Public fixture adoption](PUBLIC_EMAIL_TEST_DATA.md)
is documented but no external corpus is part of current CI results.

New suites cover the complete reviewed-rule REST lifecycle, bounded previews,
competing activation/rollback, tenant/actor isolation and virtual-only effects.
`node --test tests/web_session.test.cjs` checks 15 UI contracts. Local-model tests
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
provider, malware sandbox, cloud restore or model evaluation is implied by unit tests.

## Test layers

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
