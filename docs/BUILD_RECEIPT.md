# Build and validation receipt

Updated 2026-09-20 Pacific. Product: `jbone3311/CW-EmailBrain`, verified **private**.

## Image-bound isolated large-MIME recovery

Code/test commit **bc7ea12**, initial implementation **b860d2e**.
[CI 35564748494](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35564748494)
and [restore 35564748495](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35564748495)
passed on 2026-09-20 Pacific (September 21 UTC).

- **1,153 standard Python tests passed**, including **115 PostgreSQL cases**, no
  CI skips. **Three additional actual-container tests passed**, one exercising
  encrypted objects -> restricted MIME worker -> real PostgreSQL recovery -> body
  and text-attachment search. **25 Node UI tests passed**. Repeated gate runs and
  the restore safety subset are not double-counted.
- Local: **1,038 passed, 115 explicit PostgreSQL skips**. No local Docker acceptance
  is claimed. Ruff, strict typing across 32 source modules, locked dependency sync,
  all 16 pack documents/local links, image build and CLI smoke passed. The restore
  script separately passed strict typing. Full Git-history secret scan was clean
  through bc7ea12.
- Restore regression: **23 tables, 95 rows, two tenants, four encrypted objects**,
  matching hashes and tenant authorization; database-only/missing-object recovery
  refused. Elapsed **15.16 seconds** includes disposable container startup and is
  not a production RTO. Owned test container/archive/object trees were cleaned up.

The increment adds **119 MIME/contract tests**, **54 controller/pipe tests**, **15
recovery-boundary tests** (10 real database), and the three explicit post-build
container cases. Independent review found an injected-adapter contract gap:
inconsistent tuples could have become cached MIME rejections. The final code
validates types, hashes, fields, collection/Unicode/serialization budgets and
outcome consistency before publication or caching; four SQL tests prove malformed
adapter results leave mail held with no attempt. Processor changes and newer provider
events during parsing also prevent publication. No blocking review finding remains.

Actual Docker acceptance verifies fixed local image identity, checked isolation
before raw-byte disclosure, no network/host mounts, read-only filesystem, dropped
capabilities, unprivileged UID, resource limits, disabled logs, bounded pipes and
exact-owned cleanup. The synthetic attachment-heavy message becomes searchable;
its large PDF stays deferred, not falsely extracted. Empty MIME is a deterministic
rejection. This is not a kernel escape audit or real-mail scale/soak certificate.

The feature is an **explicit trusted operator/worker library**, not a public API
Docker endpoint. Default UI/HTTP retry still uses the 1 MiB parser; the isolated
processor can handle retained MIME up to 16 MiB and uses full image hash provenance.
No new SQL migration, provider writes, raw download, model call, real mailbox,
cloud resource or Factory mutation. Hosted authenticated jobs, scanning and
PDF/Office/OCR/archive extraction, OIDC/grants, Azure storage/KMS, retention/purge
and live acceptance remain gates. Two upstream test deprecations and CI action/
runner notices remain tracked supply-chain work. See
[isolated recovery](ISOLATED_MIME_RECOVERY.md), [ADR-029](adr/029_isolated_large_mime_recovery.md)
and [implementation status](IMPLEMENTATION_STATUS.md).

## Encrypted large-email preservation and two-part restore

Implementation commit **cefce1d**, follow-up pressure tests **0e50870**.
[CI 35563585338](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35563585338)
passed at 0e50870; the unchanged runtime/restore implementation passed
[restore 35563364090](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35563364090)
at cefce1d. Verified 2026-09-20 Pacific (September 21 UTC).

- **965 Python tests passed**, including **105 real PostgreSQL cases**, no CI skips;
  **25 Node UI tests passed**. The repeated repository-gate suite is not counted
  twice. Local results: 860 passed, 105 explicit PostgreSQL skips.
- Locked dependencies, Ruff, strict typing across 30 source modules, all 16 pack
  documents/local links, container build and CLI smoke passed. The restore script
  also passed independent strict typing with `MYPYPATH=src`.
- Actual PostgreSQL 17 restore verified **23 tables, 95 rows, two tenants and four
  encrypted external objects**, alongside legacy inline evidence. All table and
  decrypted raw hashes matched; search/evidence/recovery/rules and tenant RLS passed.
  Database-only and empty-object restoration were explicitly refused. Elapsed
  **12.43 seconds** includes container startup, not a production RTO. The drill
  cleaned up its exact owned container, temporary archive and ciphertext trees.
- Full Git-history secret scan was clean through 0e50870. The private worktree
  directory scan also passed before the implementation commit.

Added 72 encrypted-backend tests, 30 Fastmail/worker tests and 24 storage API/unit/
database cases. Coverage includes authenticated tenant/account context, wrong keys,
tampering, symlinks/ownership, concurrent publication, crash/fsync failures, fixed
size budgets, transactional rollback/orphans, SQL manifest forgery, revoked authority
during staging, persisted old-key reads after rotation, missing-key refusal without
cursor movement, and large-message progress through a restarted durable worker.
Independent integration review found no blocking issue; simultaneous mixed
inline/external writer stress remains a useful additional scenario.

Migration **0009** requires coordinated API/worker/backup-reader upgrade. The
encrypted filesystem backend is explicit opt-in; it preserves complete raw messages
up to **16 MiB**, but the parser still caps at **1 MiB**. Larger retained messages
remain visibly held as `mime_too_large`, not parsed/indexed/extracted. Existing
inline evidence is unchanged. No automatic object deletion or raw-download API.

No real mailbox, model, cloud/KMS service, binary extractor or Factory runtime was
activated. Hosted storage/key recovery, production identity/grants, larger isolated
parsing/extraction, retention/purge and live acceptance remain gates. Two upstream
test-client deprecations and action-runtime/runner notices remain tracked supply-chain
work. See [storage contract](LARGE_EVIDENCE_STORAGE.md),
[ADR-028](adr/028_encrypted_large_evidence.md) and [status](IMPLEMENTATION_STATUS.md).

## Audited human recovery of held messages

Code/test commit: `063ac14` (implementation `af76838`, follow-up assertions/UI).
[CI 35561947038](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35561947038)
and [restore 35561947019](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35561947019)
both passed on 2026-09-20 Pacific.

- **839 Python tests passed**, including **86 real PostgreSQL cases**, no CI skips;
  **25 Node UI contracts passed**. The repository-gate repetition is not counted
  twice. Local validation: 753 passes, 86 explicit PostgreSQL skips.
- Locked dependency sync, lint, strict typing across 29 source modules, all pack
  documents/local links, container build and CLI smoke passed. The restore script
  separately passed strict typing with `MYPYPATH=src`.
- Actual PostgreSQL 17 dump/restore verified **23 tables, 82 rows, two synthetic
  tenants**, equal content hashes, tenant authorization, search/evidence and
  recovery-attempt persistence. Elapsed **23.74 seconds** includes disposable
  container startup, not a production recovery-time promise. Owned test resources
  and private temporary archive were cleaned up by the drill.
- Full Git-history secret scan found no leaks through `063ac14`.

Twenty new real-database cases and two API/library cases cover explicit human
authorization, simultaneous retries, competing owner audit, newer provider events,
membership/account revocation, hash corruption, parser crashes, atomic rollback,
old citations, legacy metadata, populated migration and active worker compatibility.
Same-parser output drift now fails closed; it cannot change searchable text while
reusing a historical citation. Ten new UI tests cover explicit clicks, exact parser
binding, cached outcomes, generic errors and session/account/refresh races.

The first CI pass found an old security-test assertion expecting all reprocessing
to be unavailable (838 passed, one failed). That assertion was updated for the
new human-only retry contract without removing its raw-access, paging or isolation
checks. Independent review also caught missing audit on a concurrent cached retry;
it was fixed and both actors/requests are tested. The final UI explicitly displays
the parser version being approved. Two agents implemented/reviewed this increment.

Migration **0008** requires coordinated API/worker upgrade and refuses legacy
parser-provenance mismatches. No raw bytes, provider events, sync cursors or worker
leases are changed by recovery. No real mailbox, model, binary extractor, cloud
resource or Factory runtime was activated. Two upstream test-client deprecations
remain; CI also warns about old action Node runtimes and an upcoming runner-image
change. Dependency/action modernization belongs to the supply-chain backlog.
See [recovery contract](QUARANTINE_RECOVERY.md), [ADR-027](adr/027_quarantine_recovery.md)
and [remaining gates](IMPLEMENTATION_STATUS.md).

## Calendar extraction and realistic attachment formats

Code/test commit: `e3695d8`.
[CI 35560344173](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35560344173)
and [restore 35560344225](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35560344225)
both passed on 2026-09-20 Pacific.

- **817 Python tests passed**, including 66 real PostgreSQL cases, no CI skips.
  **15 Node interface tests** also passed. The repeated repository-gate suite is
  not counted twice. Locally: 751 passes and 66 explicit database skips.
- Lint, strict typing across 28 source modules, docs/link checks, developer image
  build and CLI smoke passed. Restore script also passed separate strict typing.
- Actual synthetic PostgreSQL restore passed for **22 tables, 77 rows, two tenants**
  with equal content hashes, recovered calendar attachment search/evidence, rules
  and tenant authorization. Elapsed 20.52 seconds includes container startup and
  is not a production recovery-time claim. Owned test container/archive cleaned up.
- Full Git-history secret scan found no leaks through the code commit.

Nine deterministic attachment-bearing MIME cases include minimal DOCX/XLSX packages,
PNG files, CSV, folded Unicode calendar invitation/cancellation, nested email and
a mixed bundle. Thirty-one format/payload/hash tests and 36 mocked-provider wrapper
tests independently check expected bytes and receipt outcomes. OOXML structure is
checked, not full Office rendering. Binary extraction is still deferred/skipped,
not counted as successfully read. No public correspondence was imported.

Calendar source extraction has 73 focused parser tests and 11 independent security
cases, plus named/unnamed MIME handling, charset/transfer-encoding failures and two
real database integration tests. Review fixed case-insensitive binary-value refusal;
integration rejects mismatched MIME/body METHOD and malformed transfer encodings.
The existing restore fixture assertion was updated to require the added calendar
attachment and its extracted content, retaining its binary-deferred checks.

This adds searchable calendar evidence, **not** meeting acceptance, RSVP, timezone
conversion, recurrence expansion, URL/alarm execution or obligation changes. Parser
provenance is v4 for new snapshots; old evidence is not silently reprocessed. Four
agents total implemented/reviewed the slice. No real mailbox, calendar, model daemon,
paid cloud resource or Factory runtime was activated. Two upstream test-client
deprecation warnings remain. See [calendar scope](CALENDAR_ATTACHMENTS.md),
[public sample adoption gates](PUBLIC_EMAIL_TEST_DATA.md) and
[remaining product gates](IMPLEMENTATION_STATUS.md).

## Prior reviewed rules, local-model adapter and actual restore proof

Code/test commit: `d5f8f47`.
[CI 35556627769](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35556627769)
and [restore 35556627775](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35556627775)
both completed successfully on 2026-09-20 Pacific.

- **658 Python tests passed**, including 64 real PostgreSQL cases, with no CI skips.
  **15 additional Node interface tests passed**. The repository gate repeats the
  Python suite; this is not counted as another 658 distinct tests.
- Lint, strict typing across 27 source modules, all 16 pack documents/local links,
  developer container build and CLI smoke passed.
- Actual PostgreSQL 17 custom dump/restore verified **22 tables, 73 rows and two
  synthetic tenants**: hashes, evidence, attachment/search results, quarantine,
  approved proposals, active rules and row-level authorization survived recovery.
  Elapsed 23.82 seconds includes disposable container startup and is not production RTO.
- Local checks: 594 Python passes, 64 explicitly skipped database tests; 15 Node
  passes. Full Git-history secret scan found no leaks through `d5f8f47`.
- Four agents total implemented and independently reviewed the changes. Review
  caught/fixed ambient PostgreSQL address redirection in the disposable drill and
  a stale Review Delete selection surviving owner-screen disconnect.

The working feedback loop is propose → approve → bounded sample → explicit human
activation → virtual search labels → append-only revision rollback. Tests cover
the REST lifecycle, concurrent receipts, expiry, foreign tenant/actor, malformed
text, 50-message sample bounds and unchanged provider/evidence state. Review alone
still applies nothing; project/fact/feature/correction application remains deferred.

The opt-in local Ollama library has 90 fake-response tests plus independent runtime
checks. It is not automatically wired into ingestion/API, no daemon was contacted,
and no model accuracy claim is made. No model downloaded, real email accessed,
mailbox changed, paid cloud resource deployed or Factory runtime modified.

The restore drill removed its exact owned disposable container and temporary
synthetic archive. It is logical recovery proof, not managed-cloud PITR, encryption,
offsite backup or regional disaster-recovery validation. Production OIDC, account
enrollment, encrypted large objects, binary extraction, additional durable provider
workers, actual model/MCP integration, controlled actions and Factory bind remain
release gates. Two upstream test-client deprecation warnings remain non-failing.

## Prior parallel implementation and pressure-test pass

Code/test commit: `3b7d972` (integrated implementation `c9e1829`).
[GitHub Actions run 35555204407](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35555204407)
completed successfully:

- **485 Python tests passed**, including 52 real PostgreSQL integration cases;
  no CI database skips. Six additional Node UI-contract tests passed.
- Strict typing passed across 24 source modules; lint, document/link gates,
  developer container build and CLI smoke passed.
- Locally: 433 Python tests passed; 52 database cases explicitly skipped; six
  Node tests passed. Full Git-history secret scan found no leaks through this commit.
- Four agents total worked on implementation and independent adversarial review.
  Changes were integrated and checked together, not counted as isolated successes.

Shipped in this increment: certified inventory reconciliation and expired-history
recovery; exact-byte bounded MIME quarantine; resumable fictional-inbox seeding;
owner import-health and paginated held-message metadata; Gmail/Graph read-only
libraries and an injected-session IMAP contract. Only Fastmail currently has durable
database worker orchestration. New provider libraries are not enrolled live connectors.

The fake-mailbox lifecycle imports 256 varied messages, applies seven changed IDs,
then recovers twenty unseen deletions after expired history. Parser checks include
1,000 seeded bounded random byte inputs. These are not a multi-day soak or measured
production throughput benchmark. [Coverage and gaps](TEST_COVERAGE_MATRIX.md).

Independent review found and verified fixes for decoder-produced NUL/surrogate
strings reaching SQL, inconsistent demo-account guards including a preflight race,
Gmail quota 403 misclassification, Graph non-ASCII Retry-After values and empty-body
deadline bypass. Integration review also corrected real provider/library contract
assumptions: Gmail minimal responses need not contain timestamps/history/thread,
and IMAPClient may consume the inner UID into its response dictionary key.

A temporary loopback UI with a mocked Store was checked in the actual browser:
connect, fictional search, evidence inspection, held-message status, and session
clearing all worked. The temporary server and tab were closed. This was not a live
database/browser integration run or full accessibility acceptance; CI separately
exercises real PostgreSQL and the HTTP API.

Remaining warnings are upstream test-client deprecations and GitHub runner/action
upgrade notices. Production OIDC, cloud infrastructure, restore drills, larger
encrypted objects, binary extraction, durable additional-provider workers, actual
model inference/MCP, action execution and Factory binding remain release gates.
No real mailbox, model, paid cloud service or Factory runtime was activated.

Prior recovery-only pass: `9173e26`,
[CI 35553409905](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35553409905),
180 passing Python tests. The receipt above supersedes its test totals.

## Read-worker refinement pass

Code commit: `01eb47d`.
[GitHub Actions run 35501983332](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35501983332)
completed successfully:

- **119 tests passed**, including 29 real PostgreSQL integration cases; none skipped in CI.
- Strict typing passed across 20 source modules; lint and all document/link gates passed.
- Developer Docker image build and CLI smoke test passed.
- Full Git-history secret scan found no leaks through this code commit.
- Locally: 90 passed, 29 database tests explicitly skipped (no local Postgres).

Added durable listing/change checkpoints, leased single-account orchestration,
stale-worker/account-binding fencing, restart after query churn, retry deadlines,
failure pauses and content-free run receipts. Tests include eight simultaneous
lease contenders, process recreation, crash-after-commit replay, deleted messages
during listing, wrong-account tokens, provider failures, expired cursors and MIME
rollback. Retry bounds cover 15,015 combinations. This is bounded fault/pressure
testing, **not** a long-running soak, production load test or live-provider trial.

The first CI attempt caught PostgreSQL infinity timestamps that Python could not
decode in status rows; a forward migration replaced those sentinels. Review also
prevented an unsafe cursor-expiry reset: that path now explicitly pauses pending
the inventory-diff reconciler. [Worker limits and recovery](READ_WORKER.md).

Remaining warnings: two upstream Python test-client deprecations and CI action/
runner upgrade notices. They do not fail this run; dependency/runtime upgrades
remain in the supply-chain backlog. No additional mailbox/cloud privileges were added.

## Earlier foundation verification

Code commit: `3612ac5`.
[GitHub Actions run 35480784089](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35480784089)
completed successfully:

- **69 tests passed**, including 16 real PostgreSQL integration cases; none skipped in CI.
- Lint passed; strict typing passed across 18 source modules.
- Repository quality gate and all 16 document-pack/local-link checks passed.
- Developer Docker image built and its CLI smoke test passed.
- Local full-history secret scan found no leaks through the tested implementation commit.

The tests exercise actual PostgreSQL 17 using a non-owner runtime role, real HTTP
API-to-database flow, tenant isolation, transaction-local context reset, composite
ownership, concurrent replay, checkpoint rollback, proposal/evidence/review flow,
correlated audit, historical evidence and attachment search/accounting. Provider
network tests use mocked HTTP only. Two upstream test-client deprecation warnings
remain; they are not skipped/failed checks and should be resolved during dependency maintenance.

## What was not done

No real mailbox access, sending, deletion, folder modification, model inference,
paid cloud provisioning, production restore, malware scanning or Factory bind.
No Factory/other Product files were modified. Five portable improvement requests
are staged in this Product's `_FACTORY_CANDIDATES.jsonl`, not adopted upstream.

The working build remains in the Codex project workspace. Factory's actual source
checkout was located at `~/CW-Systems/CW-Factory`; its Dropbox counterpart
is the content surface. Canonical Email Brain local placement is parked in Q08,
so no existing source/content folders have been moved or reorganized. Runtime
databases and credentials must remain outside Dropbox regardless of source placement.

## Reproduce

See [LOCAL_DEVELOPMENT.md](LOCAL_DEVELOPMENT.md). The ZIP is a source-only Git
archive: no `.git`, local venv, caches, credentials, database or real mail. It
contains the docs, implementation, synthetic tests, migrations and dependency lock.
CI evidence above names the exact code commit; subsequent documentation-only
receipt changes do not imply a separate live deployment.
