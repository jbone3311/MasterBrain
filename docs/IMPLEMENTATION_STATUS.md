# MasterBrain Implementation Status

Updated 2026-09-21. **Implemented** means executable in this repository; it does not
mean hosted, live-source accepted, or production ready.

## Implemented

- Existing `email_brain` capability: Fastmail/JMAP read worker, raw/evidence storage,
  MIME/attachment accounting, PostgreSQL FTS, owner search/read, reviewed rules,
  recovery/quarantine, synthetic mailbox, PDF approval path, and narrow reviewed
  travel/bill memory. Existing detailed guides define exact limits.
- Offline-tested Gmail/Graph libraries and an injected-session IMAP contract.
- MasterBrain package boundary with DataCore read-only file hash, filter, duplicate
  grouping, name grouping and file comparison extracted from FOS-Master.
- Synthetic DataCore unit corpus and live-donor parity harness pinned to FOS-Master
  commit `218d5caec2f20b9047fd3eb8e027dc671acf0c15`.

## Designed, not implemented

- General source/evidence/provenance schema and unified DataCore pipeline.
- FileOS scanner integration, generalized extraction/OCR/chunking/indexing.
- KnowledgeCore entities, relationships, claims, events, projects and commitments.
- Unified Brain API and external LLM client integrations.
- Hosted operation and production identity/source enrollment.
- Any FileOS write, move, quarantine, dedupe deletion, cutover, fold or retirement.

## Verification boundaries

Most Email tests use synthetic data; PostgreSQL suites require an explicitly disposable
database and local skips do not count. The parity script requires a clean checkout of
the pinned FOS-Master commit. It compares normalized observable scan results and does
not yet cover donor CLI text, configuration discovery, logging, performance, or file
effects. See [migration](FOS_MIGRATION.md) for the next gates.
