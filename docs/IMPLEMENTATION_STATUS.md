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
- Source-bound, in-memory FileOS ZIP/TAR archive inventory contract and dedicated
  restricted worker image with donor-equivalent cumulative bounds, safe hash-only
  manifests and explicit bomb/duplicate non-publication; live donor, hostile/fault,
  hosted container and restore gates green. It has no persistence or search path.
- Append-only, forced-RLS archive hash-manifest persistence bound to current FileOS
  source and immutable processor versions, with sealed child ledgers and exact replay;
  hosted PostgreSQL/restore gates green. It stores no member bytes and publishes no
  evidence, documents, chunks or search entries.
- Hash-bound read of exactly one persisted non-container archive member through a
  separate fixed restricted-image command. Forced-RLS selection requires the current
  FileOS source version; the parent reopens it through no-follow descriptors, verifies
  file identity before/after, and independently verifies the returned member hash and
  size. Output is capped at 8 MiB, remains unscanned and is not persisted or searched;
  hosted PostgreSQL/container/restore gates are green.
- Explicit one-member text/Markdown/HTML/CSV normalization and append-only derived
  evidence publication with deterministic child source/version/evidence identities,
  parent archive plus inventory provenance, idempotent receipts and transaction-time
  current-parent/member revalidation. It stores no raw member bytes and remains absent
  from current-generation search; hosted PostgreSQL/restore gates are green.
- Private `masterbrain fileos archive-text` publication for one explicit persisted
  inventory/member pair, with immutable worker image binding, exact shared scopes,
  non-consuming check mode, repeated reauthentication, content-free output and exact
  replay. It grants no archive enumeration, batch, scheduling, public API, raw-byte
  return or source effect.
- Independently bounded current archive-member lexical search, fenced through the
  current parent archive plus sealed inventory/member and exact derivative identities.
  `/v1/brain/current-search` exposes it separately from immutable active FileOS
  generations with explicit partial coverage; stale parents disappear while retained
  history remains available. Hosted PostgreSQL/container/restore gates are green.
- Private `masterbrain fileos archive-text-plan` read-only preview for one current
  archive inventory. It returns only bounded eligible text-member metadata in sealed
  ordinal pages with already-published labels, constructs no worker, reads no source
  bytes and creates no derivative/key/batch authority. Hosted PostgreSQL/restore gates
  are green.
- Private `masterbrain fileos archive-text-batch` execution of one canonical,
  digest-bound plan containing 1–100 reviewed member locators and caller-supplied
  idempotency keys. It validates without target/worker/key effects, executes in exact
  order, stops on first refusal, reauthenticates sensitive boundaries and resumes only
  through unchanged-plan replay. Output contains indexes/counts rather than locators or
  content; hosted PostgreSQL/container/restore gates are green.
- Explicit one-member archive PDF/DOCX/XLSX extraction through two independently
  restricted immutable images, followed by append-only publication on deterministic
  child evidence. A separate receipt binds parent archive, inventory, member,
  document processor, revision and retry key; the publication transaction rechecks
  current parent/member identity and persists no raw member bytes. Private
  `masterbrain fileos archive-document` provides non-consuming preflight, repeated
  authorization, exact replay and content-free output. Hosted PostgreSQL, populated
  restore and real chained-image PDF/Office gates are green; these derivatives remain
  retained-history-only.
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
- Bounded `/v1/brain/current-coverage` status across registered FileOS and Email
  sources, including active-generation/completed-run comparison and current bridged
  Email family counts/timestamps; hosted PostgreSQL/restore gates green.
- Private, read-only `masterbrain email bridge-plan` command for a cursor-bounded page
  of current visible versions in one explicit account, with already-bridged labels and
  content-free output; hosted PostgreSQL/restore gates green.
- Private `masterbrain email bridge-batch` command for one owner-private, digest-bound
  list of 1–100 current message versions with fixed keys, account fencing, fail-stop
  execution and exact-plan retry; hosted PostgreSQL/restore gates green.
- Private, read-only `masterbrain email bridge-parts-plan` command with separate stable
  attachment and approved-document queues, current parent/dependency fencing and
  content-free output; hosted PostgreSQL/restore gates green.
- Private `masterbrain email bridge-parts-batch` command for one owner-private,
  digest-bound attachment or approved-document plan with fixed keys, batch account
  fencing, fail-stop execution and exact-plan replay; hosted PostgreSQL/restore gates
  green.
- Reviewed KnowledgeCore entities, aliases, relationships, claims, events, projects,
  commitments and corrections with evidence links, temporal history, lexical search,
  exact reads, change feed, forced RLS and append-only enforcement.
- Grouped dual-scope search across DataCore evidence and KnowledgeCore assertions,
  with independent limits/ranks and evidence IDs for progressive drill-down.

## Designed, not implemented

- Automatic Email backfill scheduling, atomic cross-layer snapshots and automated
  source coverage
  accounting and any redirect of legacy Email search.
- Scheduled/incremental FileOS scanning, source cursors, automatic rebuild, generation
  scheduling/global-search cutover and legacy image/OCR extraction. Archive-member
  document current-search activation, preview/batch expansion and automatic archive
  fan-out remain follow-on gates and are prohibited by the implemented command.
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
