# MasterBrain Roadmap

Roadmap entries are targets, not implementation claims. Gates are dependency-ordered.

## Next build packages

DC-004C now has an accepted isolated hash-only ZIP/TAR inventory worker and append-only
tenant-isolated manifest ledger. The immediate package is a separately approved,
persisted-hash-bound one-member read boundary. Images/OCR, automatic
KnowledgeCore projection, archive search publication and all source effects remain
later packages.

## Phase 0 — Identity and baseline (current)

- Establish MasterBrain product identity and layer ownership.
- Preserve EmailBrain as the Email capability and FOS-Master as untouched donor.
- Inventory Email implementation, FOS tools/tests/schema, and migration candidates.
- Pin donor provenance and create a synthetic parity framework.
- Extract the first read-only hash/dedupe tranche.

Exit: documentation is internally consistent; baseline commits are recorded; CI runs
DataCore unit tests and the live-donor parity command is reproducible.

## Phase 1 — DataCore read path

- Define source/evidence/provenance contracts and additive schema.
- Add read-only FileOS scanning in shadow mode.
- Consolidate file/attachment type detection, extraction, metadata, OCR policy,
  normalization, deterministic chunks and lexical indexing.
- Unify jobs, leases, receipts, freshness and reconciliation.

Exit: Email and synthetic FileOS items traverse one source-neutral DataCore path with
no evidence loss; golden and shadow parity meet documented tolerances.

## Phase 2 — KnowledgeCore

- Build evidence-backed entities, aliases, relationships, claims, contradictions,
  events/timeline, projects and commitments.
- Migrate narrow Email memory and FOS fact lessons into versioned projections.
- Add evaluation sets for identity resolution, temporal correction and retrieval.

Exit: representative cross-source questions are answered from deterministic retrieval
with correct citations, conflict handling, freshness and rebuild proof.

## Phase 3 — Brain API and clients

- Implement progressive search/expand/evidence/change-feed contracts.
- Add client-neutral authentication/scopes and adapters for Claude, Grok, ChatGPT and
  other approved clients.
- Enforce budgets, redaction, revocation and content-safe audit.

Exit: each client passes the same authorization, compactness, citation, revocation and
prompt-injection suites; no client has general storage/source authority.

## Phase 4 — Hosted read-only acceptance

- Complete browser identity lifecycle, managed storage/keys, supervision, alerts,
  backups/restores and incident runbooks.
- Enroll one disposable Email account and one bounded FileOS root, then expand only
  after acceptance.

Exit: all [release acceptance](RELEASE_ACCEPTANCE.md) read-only gates pass.

## Phase 5 — FileOS cutover

- Shadow FOS-Master in production-like operation; compare inventory, hashes, metadata,
  extraction, index, queries, errors and performance.
- Cut over a bounded cohort with rollback, then broaden gradually.

Exit: sustained accepted parity and owner sign-off. Only then consider folding or
renaming FOS-Master; deletion/retirement remains a separate decision.

## Phase 6 — Reviewed actions

- Add typed proposals, policy, preview/approval and narrowly scoped executors for
  selected mailbox/file actions.
- Migrate quarantine/move/dedupe brokers only after adversarial safety tests.

Exit: idempotency, audit, rollback, legal hold, batch caps and human control are proven.
Automatic sending and permanent deletion remain out of scope unless separately approved.
