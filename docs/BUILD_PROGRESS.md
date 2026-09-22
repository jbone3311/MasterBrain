# MasterBrain Build Progress

## Active checkpoint

**Checkpoint 3 — FileOS adapter and extraction.** Work occurs on
`codex/masterbrain-foundation` in PR #4.

## Completed gates

- Foundation identity/architecture documentation and ADR-047.
- DC-001 read-only hash/dedupe extraction from pinned FOS-Master.
- Initial live-donor hash/name/both parity corpus.
- Hosted CI and synthetic PostgreSQL restore green at foundation baseline.
- Checkpoint 1 shared CLI, contracts, FileOS snapshots and 3,000-file donor parity
  completed in commit `73b58cb`; hosted CI and restore are green.
- Checkpoint 2 persistence/index completed in commits `20c5fb8` and `380761b`;
  hosted CI and populated logical restore are green.

## Current work

- First read-only FileOS extraction tranche: text, Markdown, HTML and CSV with
  source-version revalidation, explicit accounting and donor parity.
- End-to-end snapshot/import/extract/index/search and sibling-failure isolation.

## Deferred by design

- File content extraction until read-only inventory contracts are stable.
- KnowledgeCore and Brain API runtime until shared persistence/indexing exists.
- All file/mail effects and any FOS-Master cutover/retirement.

## Rule for updates

After each checkpoint, record exact commits, tests, donor baseline, CI/restore runs,
known limits, rollback and the next active checkpoint. Do not mark a later checkpoint
active while an earlier gate has unexplained failures.
