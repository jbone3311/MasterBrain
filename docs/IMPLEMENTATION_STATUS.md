# MasterBrain Implementation Status

Updated 2026-09-22. **Implemented** means executable in this repository; it does not
mean hosted, live-source accepted, or production ready.

## Implemented

- Existing `email_brain` capability: Fastmail/JMAP read worker, raw/evidence storage,
  MIME/attachment accounting, PostgreSQL FTS, owner search/read, reviewed rules,
  recovery/quarantine, synthetic mailbox, PDF approval path, and narrow reviewed
  travel/bill memory. Existing detailed guides define exact limits.
- Offline-tested Gmail/Graph libraries and an injected-session IMAP contract.
- MasterBrain package boundary with DataCore read-only file hash, filter, duplicate
  grouping, name grouping and file comparison extracted from FOS-Master.
- Dedicated `masterbrain` CLI for shared hash/compare/duplicate commands and
  deterministic read-only FileOS snapshots; source files are never changed.
- Immutable source/item/version/evidence/provenance contracts with stable opaque IDs,
  safe relative locators, bounded metadata and explicit source-bound evidence.
- Synthetic DataCore unit corpus and live-donor parity harness pinned to FOS-Master
  commit `218d5caec2f20b9047fd3eb8e027dc671acf0c15`.
- Additive shared DataCore persistence, FileOS text/Markdown/HTML/CSV extraction,
  lexical index and progressive evidence/content/change Brain API.
- Source-bound FileOS PDF/DOCX/XLSX extraction contract and dedicated restricted
  worker image with archive/active-content bounds; hosted container and restore gates green.
- Explicit private-config FileOS snapshot publication command with exact worker scopes,
  idempotent replay and repeated authorization; hosted PostgreSQL/restore gates green.
- Append-only FileOS whole-run receipt and Brain API latest-complete freshness endpoint;
  hosted PostgreSQL and populated-restore gates green.
- Exact completed-run item ledger, stale-completion refusal, immutable absence events
  and bounded inventory counts; hosted PostgreSQL and populated-restore gates green.
- Paginated, run-bound deterministic FileOS rebuild preview with no source or index
  effects; hosted PostgreSQL and populated-restore gates green.
- Immutable, latest-completion-bound FileOS lexical generations with database-checked
  readiness, append-only activation/reactivation rollback and active-only API search;
  hosted PostgreSQL and populated-restore gates green.
- Explicit private generation build/activation and activation-only rollback command
  with exact scopes, check mode and reauthentication; hosted PostgreSQL/restore green.
- Explicit cross-source current FileOS search over newest activations while historical
  compatibility search remains unchanged; hosted PostgreSQL/restore green.
- Explicit current-FileOS evidence mode for grouped KnowledgeCore retrieval with
  retained-history default and separate ranks; hosted PostgreSQL/restore green.
- Additive current-Email evidence bridge into shared DataCore source/version/evidence/
  document/chunk identities with opaque locators, exact replay, immutable provenance,
  forced RLS and account-race fencing; hosted PostgreSQL/restore green. Existing Email
  ingestion and search remain authoritative.
- Private `masterbrain email bridge` command for one explicit evidence UUID with exact
  shared worker scopes, non-consuming check mode, safe replay, reauthentication and
  content-free output; hosted PostgreSQL/restore green.
- Explicit `/v1/brain/email-search` read over bridged Email evidence that remains
  current and visible in both shared and legacy state; retained history and legacy
  Email search remain unchanged; hosted PostgreSQL/restore green.
- Additive Email attachment-occurrence bridge with distinct child evidence/parts,
  duplicate occurrence preservation, bounded legacy-text publication and explicit
  zero-document outcomes. Existing Email attachment/document behavior is unchanged;
  hosted PostgreSQL/restore gates green.
- Additive approved Email PDF derivative bridge from one immutable completed legacy
  extraction onto its existing attachment evidence, with exact approval/result/
  processor provenance and no byte access; hosted PostgreSQL/restore gates green.
- Private `masterbrain email bridge-attachment` and `bridge-document` commands using
  the existing closed configuration, exact shared worker scopes, non-consuming checks,
  reauthentication and content-free output; hosted PostgreSQL/restore gates green.
- Explicit `/v1/brain/email-family-search` read with independently bounded/ranked
  message, attachment-text and approved-document layers, each fenced by current legacy
  parent and shared pointers. Existing reads remain unchanged; hosted PostgreSQL/
  restore gates green.
- Explicit `/v1/brain/current-search` grouped read across active FileOS, current Email
  family and reviewed KnowledgeCore results with independent bounds/ranks, partial-
  coverage labels and declared independent-layer consistency; hosted PostgreSQL/
  restore gates green.
- Reviewed KnowledgeCore entities, aliases, relationships, claims, events, projects,
  commitments and corrections with evidence links, temporal history, lexical search,
  exact reads, change feed, forced RLS and append-only enforcement.
- Grouped dual-scope search across DataCore evidence and KnowledgeCore assertions,
  with independent limits/ranks and evidence IDs for progressive drill-down.

## Designed, not implemented

- Email bridge batch/backfill, atomic cross-layer snapshots, automated source coverage
  accounting and any redirect of legacy Email search.
- Scheduled/incremental FileOS scanning, source cursors, automatic rebuild, generation
  scheduling/global-search cutover and legacy Office/archive/image/OCR extraction.
- Automatic KnowledgeCore extraction, known-answer quality evaluation, graph traversal,
  semantic ranking and Email/FOS knowledge migration.
- Unified cross-source synthesis and external LLM client integrations.
- Hosted operation and production identity/source enrollment.
- Any FileOS write, move, quarantine, dedupe deletion, cutover, fold or retirement.

## Verification boundaries

Most Email tests use synthetic data; PostgreSQL suites require an explicitly disposable
database and local skips do not count. The parity script requires a clean checkout of
the pinned FOS-Master commit. It compares normalized observable scan results and does
  now covers fixture and scale hash/name/both scans, pair comparisons and hashes. It
  does not cover donor CLI text, configuration discovery, logging or file effects.
  See [migration](FOS_MIGRATION.md) for the next gates.
