# FileOS v1 completion trigger-cost benchmark

This opt-in, synthetic-only audit supports [issue #71](https://github.com/jbone3311/MasterBrain/issues/71)
and ADR-122. It measures the 3,000-row v1 completion writer on a fresh
disposable PostgreSQL 17 database, then adds migration 0018's old deferred
per-item whole-ledger trigger to the **same current schema and writer** and
measures a second, otherwise equivalent source. The comparison isolates that
trigger's cost; it is not a full replay of historical pre-0043 binaries or a
production throughput guarantee. Today's immediate late-item guard remains
active in both runs, so the second run has more checks, not fewer.

Run `PYTHONPATH=src uv run python scripts/benchmark_fileos_v1_completion.py`
with `--admin-dsn` for an administrator DSN to a
**new empty** database whose name begins `email_brain_test_benchmark_`. The
script refuses other names, any existing public relation and more than 3,000
rows. It creates only fictional tiny files in an automatically removed
temporary directory, uses separate source IDs with identical row counts,
verifies both completed ledgers, removes the added trigger and ephemeral login,
and prints counts, elapsed times, ratio and checkpoint counts without paths,
content or credentials. Discard the entire test database after the run. The
dedicated [GitHub workflow](../.github/workflows/fileos-completion-benchmark.yml)
repeats it on `postgres:17`; it has no pass/fail latency threshold because a
shared runner is not a stable performance budget.

On 2026-10-02, local Homebrew PostgreSQL 17.11 on macOS completed the current
3,000-row writer in **0.577 s**, then the same writer with the legacy trigger
in **24.202 s** (41.97×). That first controlled run did not capture checkpoint
counters; a repeated run and the container result are recorded in the
[build receipt](BUILD_RECEIPT.md). These are one-machine observations, not an
SLA. A real FileOS cutover still needs donor parity, sustained read-only
shadowing, source-fault tests, rollback and owner acceptance.
