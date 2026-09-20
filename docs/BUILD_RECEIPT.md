# Build and validation receipt

Recorded 2026-09-19 Pacific. Product: `jbone3311/CW-EmailBrain`, verified **private**.

## Tested implementation

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
