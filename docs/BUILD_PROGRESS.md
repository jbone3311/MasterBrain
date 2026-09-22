# MasterBrain Build Progress

## Active checkpoint

**Checkpoint 2 — Shared persistence and lexical index.** Work occurs on
`codex/masterbrain-foundation` in PR #4.

## Completed gates

- Foundation identity/architecture documentation and ADR-047.
- DC-001 read-only hash/dedupe extraction from pinned FOS-Master.
- Initial live-donor hash/name/both parity corpus.
- Hosted CI and synthetic PostgreSQL restore green at foundation baseline.
- Checkpoint 1 shared CLI, contracts, FileOS snapshots and 3,000-file donor parity
  completed in commit `73b58cb`; hosted CI and restore are green.

## Current work

- Additive DataCore schema, bounded/idempotent FileOS manifest import, immutable
  evidence/provenance, deterministic chunks, lexical retrieval and job primitives.
- PostgreSQL replay, drift, concurrency, rollback, RLS, immutability and restore gates.

## Deferred by design

- File content extraction until read-only inventory contracts are stable.
- KnowledgeCore and Brain API runtime until shared persistence/indexing exists.
- All file/mail effects and any FOS-Master cutover/retirement.

## Rule for updates

After each checkpoint, record exact commits, tests, donor baseline, CI/restore runs,
known limits, rollback and the next active checkpoint. Do not mark a later checkpoint
active while an earlier gate has unexplained failures.
