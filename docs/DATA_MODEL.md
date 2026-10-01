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
- Migration 0034 adds a dedicated, non-login `masterbrain_identity_admin` database
  role with a forced-RLS identity-binding management policy. It grants no runtime
  identity writes, table ownership or direct audit-event insertion; a named
  administrator login must be enrolled separately by a DBA.
- Migration 0035 removes the caller-settable identity-lookup policy and grants
  runtime only the exact, active-only resolver function, not table-wide SELECT.
  Other tenant-context RLS settings still need a separate compromised-SQL design.
- Migration 0037 adds DBA-owned `masterbrain_tenant_login_bindings`, one login to
  one tenant, and a restrictive policy on every existing forced-RLS tenant table.
  The opted-in login is fenced by `session_user` in addition to the older GUC
  policy; unregistered shared logins retain their existing behavior and risk.

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
Migration `0043_fileos_run_ledger_linear_validation.sql` makes the item-to-receipt
foreign key deferred so new items can precede their receipt in one transaction.
One deferred receipt trigger validates the final ledger; an immediate source-locked
item guard refuses late inserts after a receipt. No historical row is rewritten.
ADR-094 adds an application-level coverage precondition before those receipts:
blocking snapshot errors cannot become a completed inventory or absence evidence.
Migration `0031_fileos_policy_identity.sql` adds a nullable historical
`policy_sha256` to the immutable completion receipt. A NOT VALID check preserves
unknown legacy policies while requiring a valid digest on every new insert.
ADR-096 compares consecutive policy identities before absence inference; it does
not invent a digest for old receipts or rebaseline a source automatically.
ADR-097 adds a bounded, exact file/directory exclusion ledger to the immutable
snapshot manifest, not a new SQL table. The existing canonical manifest digest
binds this ledger to a completion receipt. A previously indexed locator covered by
the new ledger cannot produce an absence event; there is no schema migration.
Migration `0032_fileos_root_binding.sql` adds a nullable historical root digest
to FileOS sources and completion receipts. New FileOS sources and receipts require
one; a source trigger prevents changing a bound root or silently binding legacy
sources that already contain items or receipts. Unknown historical roots stay null.
ADR-098 requires intake and completion to agree on that digest. The populated
restore and migration regression passed on PR #22's runtime head; the change is
integrated on `main` via PR #28. Live cutover acceptance remains open.

Migration `0038_fileos_transition_review_packets.sql` adds a separate, immutable,
forced-RLS and tenant-login-fenced packet for one donor-policy candidate and
its exact completed-v1 comparison. Its completed-receipt foreign key and
canonical packet digest support private review and provenance, not v2 current
state. Search, freshness, absence and publication do not read it. See
[ADR-115](adr/115_fileos_transition_review_packet.md).

Migration `0039_fileos_v2_staged_inventory.sql` adds an immutable, forced-RLS
staging header and exact-count row ledger linked to a sealed transition packet
and its completed-v1 receipt. Hashed rows carry a candidate version and SHA;
deferred `no_hash`, `dataless` and `oversize` rows carry neither. Exclusion and
error rows remain explicit. These tables are not a completed v2 run and no
freshness, absence, index or search query consumes them. See
[ADR-117](adr/117_fileos_v2_staged_inventory.md).

Migration `0040_fileos_v2_transition_approvals.sql` adds one immutable,
forced-RLS owner-review receipt per staged FileOS v2 plan. Its composite
foreign key binds the stage, packet, source, prior run and packet/candidate
digests; its plan digest and acknowledged count maps bind the human decision.
The receipt is not a completed run, evidence version, absence event, active
index or source-effect authorization. See [ADR-118](adr/118_fileos_v2_transition_review_approval.md).

Migration `0041_fileos_v2_baseline_verification.sql` adds an immutable,
forced-RLS, tenant-login-fenced receipt bound by composite foreign keys to
one approved stage and its exact prior-v1, packet, candidate and plan identities.
It records a later observation and matching row digest after a fresh root scan.
This is historical verification, not a v2 completed run or current read
authority. See [ADR-119](adr/119_fileos_v2_baseline_verification.md).

Migration `0042_fileos_v2_prepared_evidence.sql` adds an immutable preparation
receipt and per-hashed-row mapping from donor candidate version to a
policy-scoped shared DataCore version/evidence. The mapping is necessary because
v1 version metadata includes mtime while the donor candidate does not; reusing
the same v1-style version ID would break later v1 imports. A deferred database
check requires exact hashed-row coverage and source-bound evidence. Hashless
staged rows have no mapping or fabricated evidence. This is not a completed v2
run or current search/freshness authority. See
[ADR-121](adr/121_fileos_v2_prepared_evidence.md).

Migration `0044_fileos_v2_baseline_authorizations.sql` adds one append-only
owner authorization per prepared stage/source. A composite foreign key binds
the exact preparation, review, stage, source, prior v1 run and digests; forced
RLS, tenant-login fencing, source locking, protected truncation and immutable
rows apply. No current pointer, v2 completion ledger, active index or absence
row references this receipt. See
[ADR-123](adr/123_fileos_v2_baseline_authorization.md).

Migration `0045_fileos_v2_baseline_completion.sql` adds one immutable private
completion receipt per owner-authorized FileOS v2 stage. Composite foreign
keys bind the exact authorization, preparation and staged row/count identities;
the staged rows and prepared mapping form its membership ledger without a
second row copy. A source-locked insert trigger rejects stale v1 baselines,
scan errors and mismatched counts. The receipt is forced-RLS and protected
against row mutation and truncation. It does not update current pointers,
v1 receipts, absence, active indexes or search. See
[ADR-124](adr/124_fileos_v2_baseline_completion.md).

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

Migration `0033_archive_ledger_parent_integrity.sql` completes the archive
inventory's deferred ledger check on both child insert paths: a new member or skip
must leave the sealed count and byte totals equal at commit. It also validates a
tenant-composite provenance-output document reference and exact inventory-parent
references for text, document and image archive receipts. It deliberately leaves
polymorphic provenance inputs unbound to any single evidence table. Existing ledger
drift or bad references stop migration for reviewed repair; no rows are rewritten.

Migration `0036_current_archive_image_search.sql` adds only a tenant-leading lookup
index on existing immutable image OCR receipts. Current-image retrieval rejoins
the receipt to sealed member, derivative and still-current archive parent; it does
not rewrite evidence, activate a generation or change receipt semantics.

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
