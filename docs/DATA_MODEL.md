# MasterBrain Data Model

This document combines implemented source-neutral tables with the remaining target
model. Migrations `0015` through `0021` implement the first DataCore,
KnowledgeCore and FileOS completion/freshness slices; names not identified as
implemented remain logical targets.

## Identity and access

- **tenant**, **principal**, **membership**, **grant**, **external_identity**
- Grants scope source accounts/roots and operations: metadata, search, extracted
  content, original evidence, administration, proposal, approval, execution.
- Every tenant-owned row includes `tenant_id`; access is enforced in application logic
  and storage policy.

## Source and evidence

- **source**: kind (`email`, `fileos`, future), provider, account/root, configuration.
- **source_item**: stable logical item ID and source-native ID/path; current observation.
- **source_version**: immutable observed version, source cursor/revision, timestamps.
- **evidence**: immutable bytes or immutable provider-bound reference, media type,
  size, SHA-256, encryption/key version, retention/legal-hold state.
- **part**: MIME part, attachment, archive member, document page, image, or embedded
  object with parent/ordering and its own digest/status.
- **provenance_edge**: input evidence/derivative, output derivative, transform name and
  version, code revision, worker, configuration digest, observed/created times.

An Email message and a filesystem file are source items. An attachment is both a part
of the message evidence and a candidate document source version; the relation is
explicit, not inferred from filename.

## DataCore derivatives

- **extraction_job/result**: policy, worker, lease/fence, attempts, outcome and errors.
- **normalized_document**: canonical title, authors/participants, times, body/sections,
  source-specific fields, language, safety flags, parser version.
- **metadata_assertion**: field/value, origin (`source`, `embedded`, `extracted`,
  `human`), confidence, valid/observed time, evidence locator.
- **chunk**: deterministic chunk ID/version, normalized-document version, order,
  character/page/part locator, text digest and bounded text.
- **index_record**: chunk/document, index kind/model/version, publication/freshness.
- **duplicate_group/member**: algorithm/digest, members and scope. Membership never
  implies permission to remove a source item.

## KnowledgeCore

Migration `0016_knowledgecore.sql` implements append-only tenant-scoped tables for
all objects below, evidence links, lexical search documents, change events and
idempotency receipts. The first service requires human-reviewed writes and existing
DataCore evidence. Participant sets, milestones, graph traversal and automated
extraction remain targets.

- **entity** and **entity_alias**: people, organizations, places, accounts, artifacts.
- **relationship**: typed endpoints, direction, validity interval and evidence.
- **claim**: subject, predicate, typed value/object, assertion status, confidence,
  extractor/reviewer, observed and valid intervals.
- **claim_evidence**: supporting/contradicting evidence plus precise locator.
- **event**: type, participants, event interval, location/project and evidence.
- **project**: identity, state, members, milestones, decisions and source coverage.
- **commitment**: description, owner, counterparty, due interval, state and evidence.
- **supersession/correction**: links versions without erasing prior assertions.

Knowledge uses bitemporal thinking: when something was true (`valid_time`) is distinct
from when MasterBrain learned it (`observed_time`). Missing or conflicting evidence is
represented explicitly.

## Operational primitives

Migration `0017_fileos_run_receipts.sql` implements an append-only, forced-RLS
completion receipt. It binds exact intake/manifest identity to terminal outcome counts
and extractor provenance. Only a completed receipt advances the current FileOS
freshness view; intake and partial document prefixes do not.

Migration `0018_fileos_inventory_reconciliation.sql` binds every completed receipt to
an exact immutable item/outcome ledger. Consecutive complete ledgers produce immutable
absence events without deleting evidence or treating partial work as a full inventory.

Migration `0019_datacore_index_generations.sql` adds immutable, completion-bound index
generations, exact item/chunk membership, a database-validated readiness receipt and
append-only activations. The active FileOS read path follows the latest activation;
rollback appends an activation of an older ready generation rather than rewriting it.

Migration `0020_email_datacore_bridge.sql` adds an append-only mapping receipt from
one legacy Email message-version UUID to shared source, item, version, evidence and
normalized-document identities. The original MIME remains in `raw_objects`; the
receipt and shared derivatives are forced-RLS and immutable.

Migration `0021_email_attachment_bridge.sql` adds shared `brain_parts` plus an
append-only mapping from each legacy Email attachment occurrence to a distinct child
source item/version/evidence. Same-hash occurrences remain distinct. Bounded legacy
text may produce a normalized document; other outcomes retain explicit zero-document
accounting. Attachment evidence is source-bound to the retained parent MIME rather
than falsely claiming separately retained bytes.

Migration `0022_email_document_extraction_bridge.sql` adds an append-only receipt
from one immutable, completed approved-PDF extraction to a second normalized document
on its existing attachment evidence. It records the completed approval job, processor,
policy, extraction revision, result digest, shared identities and bridge provenance;
it does not read or copy source bytes.

- **job**, **lease**, **checkpoint**, **inbox**, **outbox**, **idempotency_record**
- **audit_event**, **policy_decision**, **change_feed**, **retention_action**
- **schema_version**, **extractor_version**, **model_version**, **restore_receipt**

## Invariants

Evidence and versions are immutable; corrected projections point to replacements.
Content digests use an explicit algorithm. Stable IDs do not depend on mutable paths.
All derivatives trace to evidence and transform versions. Original content and safe
previews are separate. Cursor advancement and publication are transactional.
Cross-tenant references are forbidden. Cascade behavior must never erase retained
evidence or audit history accidentally.
Migration 0030 adds statement-level refusal of direct and cascaded `TRUNCATE` for
protected evidence/receipt rows, stateful approval jobs and audited identity
bindings. This guard supplements row triggers and forced RLS; an administrative
table owner can still disable it, so backup/audit controls remain essential.
