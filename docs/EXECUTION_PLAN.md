# MasterBrain Incremental Execution Plan

Updated 2026-10-02. Checkpoints 1–5 below describe the original build sequence;
their bounded synthetic slices now exist on `main`, but their production-level exit
criteria are **not** all met. Do not assign them again as blank-slate work. The active
queue is [roadmap next verified sequence](ROADMAP.md#next-verified-sequence):
interactive cross-source acceptance; security/upgrade issues #7/#9 and
engineering-quality gate #34; assistant/hosting issues #88/#94; and bounded
FileOS donor shadow before any v2 current-state decision. PR #116's
human-only historical comparison API is merged and verified, but it does not
activate v2 or replace FOS-Master. The
[current function map](CURRENT_FUNCTIONS.md) separates implemented routes from
designs.

Every new checkpoint follows: implement → unit/fault/stress test → compare with the
pinned donor where applicable → update documentation/status → commit → push →
require green exact-head CI/restore before beginning the next checkpoint.

## Historical checkpoints and remaining exit gates

The bullets below retain target requirements. Completing an isolated function does
not close the whole checkpoint; use the roadmap and release criteria for current
priorities.

## Checkpoint 1 — Shared commands and contracts

- Add a dedicated `masterbrain` CLI without removing `email-brain` compatibility.
- Define stable source, source-item, evidence, digest and provenance contracts.
- Expose read-only hash, compare and duplicate-scan commands backed by DataCore.
- Add deterministic read-only FileOS snapshot manifests with safe relative locators.
- Expand FOS-Master live-donor parity and stress coverage.

Exit: deterministic repeated output, no source writes, root/symlink escape tests,
donor parity for adopted behavior, lint/type/unit/docs gates and green hosted CI.

## Checkpoint 2 — Shared persistence and lexical index

- Add additive PostgreSQL tables for sources, source items/versions, evidence metadata,
  provenance, normalized documents, chunks, jobs and change publication.
- Enforce tenant/source RLS and least-privilege grants.
- Import a snapshot manifest idempotently; preserve versions and detect drift.
- Publish deterministic chunks and PostgreSQL full-text index records.

Exit: replay/crash/concurrency/RLS/restore tests pass; no file content leaves authorized
storage; existing Email schema and behavior remain compatible.

## Checkpoint 3 — FileOS adapter and extraction

- Add bounded read-only root enrollment and incremental observations.
- Port/adapt text, CSV, HTML and metadata extraction first; then documents, archives,
  images and OCR through isolated workers.
- Account for every file/part and publish explicit unsupported/deferred/failure states.

Exit: format golden corpora, donor comparisons, malicious/fault corpus, restart and
performance gates pass in shadow mode.

## Checkpoint 4 — KnowledgeCore

- Add entities, aliases, relationships, claims, claim evidence, events, projects,
  commitments, corrections and bitemporal history.
- Migrate existing Email structured memory and FOS fact lessons into cited claims.
- Build known-answer evaluation and rebuild/freshness checks.

Exit: cross-source questions meet reviewed accuracy/citation thresholds and preserve
conflicts, uncertainty and history.

## Checkpoint 5 — Brain API

- Implement versioned search, expand, evidence and change-feed endpoints.
- Enforce progressive disclosure, scopes, pagination and byte/token budgets.
- Add provider-neutral client contract tests for Claude, Grok, ChatGPT and others.

Exit: authorization, revocation, prompt-injection, citation and compactness suites pass.

## Checkpoint 6 — Operational read-only product

- Add supervision, enrollment, metrics/alerts, backups/restores and bounded shadow
  operation for one Email account and one FileOS root.
- Compare FOS-Master and MasterBrain inventories, extraction, search and failures.

Exit: sustained read-only parity and owner acceptance. FOS-Master remains rollback.

## Checkpoint 7 — Reviewed effects

Migrate file/mail effect brokers last. Require typed proposals, re-hashing, legal-hold
checks, quarantine, caps, audit, preview/approval, idempotency and rollback. Retirement
or rename of FOS-Master is a separate explicit decision after sustained operation.
