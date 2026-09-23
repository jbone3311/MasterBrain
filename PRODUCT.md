# MasterBrain Product Contract

## Product identity

MasterBrain is the final product. EmailBrain is an internal Email source capability,
and FileOS is an internal file capability being migrated safely from FOS-Master.
Neither source owns shared ingestion, knowledge, or assistant-access concerns.

## Promise

MasterBrain turns authorized email and files into durable evidence and useful,
current knowledge. It lets people and assistants begin with a compact answer, expand
only the relevant objects, and reach the original evidence for verification.

## Layer ownership

- **Source adapters** own provider-specific discovery, cursors, fetches, and effect
  translation. Email and FileOS remain explicit adapters/capabilities.
- **DataCore** owns intake, hashing and dedupe signals, file/attachment extraction,
  OCR orchestration, normalization, metadata, provenance, chunking/indexing, and
  common database primitives.
- **KnowledgeCore** owns entities, relationships, facts/claims, events/timeline,
  projects, commitments, corrections, and unified retrieval.
- **Brain API** owns authorized progressive disclosure to Claude, Grok, ChatGPT, and
  other clients. It never exposes general SQL, arbitrary object access, or provider
  credentials.

## Outcomes

- Search and retrieve across all authorized sources with stable evidence citations.
- Preserve originals and every material transformation with verifiable provenance.
- Maintain current people, organizations, projects, commitments, events, and claims
  while retaining temporal history and contradictions.
- Reuse one deterministic intake/extraction/indexing substrate across Email and files.
- Keep common queries compact while allowing bounded drill-down to source evidence.
- Learn through typed, reviewed proposals rather than self-modifying behavior.
- Operate usefully when external models are unavailable.

## Non-negotiable invariants

- Raw evidence is immutable while retained; projections are versioned and rebuildable.
- Every tenant/user-owned record is scoped in application logic and enforced storage.
- Every source item has a stable identity, content digest, provenance chain, and
  explicit extraction/indexing status.
- Untrusted email, files, extracted text, OCR, and model output are data, never authority.
- Every write or external effect is idempotent, authorized, auditable, and recoverable.
- Cross-source duplicates are evidence links, not automatic deletion permission.
- Held-out test corpora are excluded from destructive dedupe.
- No automatic sending, permanent deletion, or broad file reorganization in the
  initial product.
- FOS-Master remains operational and unchanged until golden-corpus and production
  parity gates prove replacement.
- Migration preserves source repository, path, commit, license, and adaptation notes.

While retained, database evidence and receipts reject ordinary row mutation and
whole-table truncation. This is a runtime/accidental-administrator control, not a
claim that a malicious database owner cannot disable triggers; administrative audit,
separation of duties and restorable backups remain part of the preservation promise.

## Initial user and release

The initial user is an owner operating several personal/business mailboxes and file
domains, with later household/team access through explicit grants. The first
MasterBrain release provides read-only Email and FileOS ingestion, immutable evidence,
DataCore normalization/indexing, KnowledgeCore retrieval, Brain API evidence
drill-down, tenant isolation, audit, backup/restore, and operational monitoring.

## Success

The release can replay either source without duplication or omission; answer a
representative cross-source query set with correct evidence; survive worker crashes
and stale cursors; demonstrate isolation and least privilege; restore from backup;
and show FileOS output parity with the pinned FOS-Master baseline. Detailed gates are
in [release acceptance](docs/RELEASE_ACCEPTANCE.md).
