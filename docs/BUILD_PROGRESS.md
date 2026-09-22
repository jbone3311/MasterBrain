# MasterBrain Build Progress

## Active checkpoint

**Checkpoint 1 — Shared commands and contracts.** Work occurs on
`codex/masterbrain-foundation` in PR #4.

## Completed gates

- Foundation identity/architecture documentation and ADR-047.
- DC-001 read-only hash/dedupe extraction from pinned FOS-Master.
- Initial live-donor hash/name/both parity corpus.
- Hosted CI and synthetic PostgreSQL restore green at foundation baseline.

## Current work

- Full repository regression, documentation, commit, push and hosted CI gate for the
  completed shared CLI/contracts/snapshot/stress implementation.

## Deferred by design

- Database schema/integration until Checkpoint 1 is green.
- File content extraction until read-only inventory contracts are stable.
- KnowledgeCore and Brain API runtime until shared persistence/indexing exists.
- All file/mail effects and any FOS-Master cutover/retirement.

## Rule for updates

After each checkpoint, record exact commits, tests, donor baseline, CI/restore runs,
known limits, rollback and the next active checkpoint. Do not mark a later checkpoint
active while an earlier gate has unexplained failures.
