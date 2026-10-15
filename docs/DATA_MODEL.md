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
- Migration 0049 adds forced-RLS `external_identity_sources`, keyed by the
  binding and an existing source in the same tenant. A grant insert/removal
  bumps the identity revision and writes an opaque audit event. The exact-key
  v2 resolver returns sorted source IDs; runtime/lookup logins cannot enumerate
  the grant table. Migration 0050/ADR-133 additionally admits source-filtered
  current coverage and change status for enrolled assistants, not hosted or
  all-route authorization.
- Migration 0051 admits `knowledge.read` and `knowledge.changes.read` in the
  administrator-owned OIDC scope constraint and every assistant/source-grant
  fence. The old exact-key resolver still refuses assistants carrying Brain or
  Knowledge reads; new binaries use the source-aware resolver. No historical
  identity or grant row is rewritten.

## Source and evidence

Migration 0058 adds `mail_accounts.read_scope_sha256` for an administrator-
pinned canonical Fastmail mailbox/date window on a previously unused account.
`sync_workers.read_scope_sha256` and `scope_claim_token` bind a fresh scoped
lease to that pin; the Email cursor must carry version 4 and the same digest.
Database triggers reject drift or unscoped worker takeover. The window itself
is not stored here. ADR-179 adds a synthetic-tested, private owner-reviewed
enrollment/disconnect command; no live enrollment is approved. ADR-184 includes
an exact excluded-mailbox policy in the pinned window fingerprint. Migration
0061 adds `excluded` to `message_sync_state.status`: an excluded provider ID
is retained only in the tenant-isolated sync/inventory ledger, with no new raw
object, message projection or DataCore document. An older `messages` row is
marked noncurrent in the same transaction; its immutable versions remain.
`excluded` is not a provider deletion or a retention purge.
Migration 0062 adds tenant/evidence lookup indexes on all three Email bridge
receipt families and a security-invoker predicate that maps a Brain evidence ID
to its current Email sync exclusion state under forced RLS. Read routes use it
without modifying immutable evidence, change rows or Knowledge assertions.

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

Migration `0064_private_statement_fileos_replay.sql` adds one append-only
`knowledge_statement_fileos_replays` row per proposal. Its tenant-composite
links and SQL basis guard bind the existing proposal/document/evidence/current
FileOS version, exact source/text digests, source size, text normalizer and
physical-root digest. Forced RLS, tenant-login fencing, immutable-row and
protected-TRUNCATE controls apply. The row is a private worker-observed replay
receipt, not a reviewed holding, cryptographic attestation against a compromised
runtime SQL login, or a general PDF/OCR/Email derivation record. The owner
statement preview does not consume it yet.

Migration `0063_private_knowledge_proposal_batches.sql` adds ADR-186's
`knowledge_proposal_batches`, ordered `knowledge_proposals`, per-proposal
`knowledge_proposal_evidence`, immutable `knowledge_proposal_decisions`, and
one `knowledge_proposal_review_receipts` row per completed batch. Canonical
JSON/digests and actor-scoped idempotency bind 1–50 source-stated proposals;
the per-evidence links and row/decision closure are SQL-checked. Forced RLS,
tenant-login fencing, runtime insert/select-only grants and protected TRUNCATE
apply. Only explicit approved rows enter the existing reviewed Knowledge
tables, in the same transaction as all decisions. These private rows are not
inferred claims or reviewed search material. ADR-202's additive
`0067_dossier_import_batch_binding.sql` adds a nullable immutable
`import_context_sha256` to the batch header; generic/historical batches keep
NULL and their original payload digest. A Markdown-imported project, event or
commitment batch binds the exact file and selected claim IDs/citations to its
typed payload digest. No raw Markdown or source path is stored in this column.
ADR-205's `0068_dossier_proposal_citation_binding.sql` adds two nullable,
tenant-FK-bound evidence IDs on each proposal: the selected row's quote basis
and (only for imported members) its displayed entity citation. New imports
recheck these IDs at private preview and human review as well as staging;
historical and generic batches retain NULL and their original contract.
The migration's insert guard also refuses a new import-context proposal if
its selected quote citation is absent or outside its direct evidence set, or
if an imported member lacks its separate entity citation. Generic batches
cannot smuggle imported citation columns. Historical ADR-202 rows are not
rewritten or retroactively rejected.

Migration `0069_private_project_fact_proposals.sql` adds a **separate**
ADR-206 fact batch, ordered proposal/evidence rows, explicit per-row decisions
and one atomic review receipt. The generic ADR-186 decision FK still points
only to `knowledge_receipts`; an approved fact decision instead binds the
reviewer's `knowledge_project_fact_receipts` row and resulting fact ID. The
batch binds an exact Markdown/selection context digest to canonical typed
payloads. SQL requires the selected quote evidence to match the payload and
its evidence array; deferred closure checks row/evidence/decision counts.
All five tables are forced-RLS, tenant-login-fenced, immutable and protected
from TRUNCATE. They are private unreviewed storage, not fact search or a
source-freshness certificate. No raw Markdown is stored.

Migration `0070_private_project_artifact_proposals.sql` adds a separate
ADR-207 private artifact-link batch, ordered proposals, explicit per-row
decisions and an atomic review receipt. Each proposal retains the exact
artifact evidence occurrence and independently cited basis occurrence, plus
canonical typed payload and import-context digest, not raw Markdown.
Approval binds a reviewed `knowledge_project_artifact_receipts` row and its
new link ID; rejection has no link. Forced RLS, tenant-login fencing,
tenant-composite keys, immutable/protected-truncate tables and deferred
whole-batch closure preserve the separate proof. These rows are not an
automatic current-file roster, inferred association or FileOS source effect.

Migration `0057_private_statement_proposals.sql` implements ADR-172's separate
append-only `knowledge_statement_proposals`, ordered
`knowledge_statement_rows`, and actor-scoped idempotency
`knowledge_statement_receipts`. Each proposal binds a current normalized
document, evidence, source version, active source, source-byte and extracted-text
digests, donor commit, transform version, status and coverage codes. Rows retain
exact decimal values and character offsets into the immutable document, not a
second copy of the text. Tenant-composite foreign keys, forced tenant RLS, the
tenant-login fence, direct-SQL basis/row/completion guards and runtime
SELECT/INSERT-only privileges protect this private ledger. It is deliberately
separate from reviewed `knowledge_claims`; no row is a verified holding or
current balance. `USD` and `reconciled` describe the donor recipe
assumption and within-tolerance arithmetic only.
ADR-173 adds no table: a human-only API reader rechecks current source grants,
version and hashes, then pages these unreviewed rows with bounded source quotes.
The stored model still has no reviewed investment assertion or automated
promotion path.

ADR-171 introduces an in-memory `StatementCandidate` and grouped `StatementRow`
for one fictional Streetbeat recipe. Rows carry exact `Decimal` quantity, price,
amount, cost basis and unrealized value where present; a source-kind/evidence
reference, donor commit and transform version, verified extracted-text SHA-256;
and precise character spans back
into that text. Separate status and content-free coverage codes distinguish a
within-tolerance row sum from mismatches, absent totals and incomplete parsing.
The source-byte evidence digest is *not* the extracted-text digest. Neither
the donor float rows are stored in KnowledgeCore or exposed by Brain API. ADR-172
stores only private proposals; its source/version/evidence binding is not human
review or publication. Reviewable provenance, current-grant rechecks and owner
approval remain required before publication.

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

Migration `0053_knowledge_unsuperseded_lookup.sql` adds tenant-scoped indexes
for the six same-kind `supersedes_id` links and correction targets. It changes
no assertion rows. Direct KnowledgeCore search may explicitly request the
source-grant-aware unsuperseded review-chain leaves (ADR-158); the default
continues to retrieve retained history. Multiple leaves and valid-time
intervals remain independent, so this is not a single current-truth row.
Migration `0054_knowledge_event_timeline.sql` adds tenant/time and
tenant/project/time lookup indexes for dated event reads. ADR-160 pages
immutable reviewed events under a recorded-at cutoff; no event or evidence
row is rewritten. Undated events and cross-kind timelines remain outside
that view, and source freshness is not implied.
Migration `0055_knowledge_commitment_due.sql` adds partial tenant/due and
tenant/project/due indexes without rewriting commitment or evidence rows.
ADR-161 pages reviewed commitments with non-null due time under the same
recorded-time cutoff pattern. `due_at` is a stated due time, not a computed
overdue status or a source-freshness assertion.
Migration `0056_knowledge_project_dossier.sql` adds partial tenant/project/
recorded-time indexes for linked events and commitments, including undated
ones; it rewrites no assertion or evidence row. ADR-162's exact project dossier
uses these indexes for independently bounded, recording-time-ordered links.
The project's stored state is still a reviewed assertion, not a derived current
state or contradiction resolution.
Migration `0059_reviewed_project_aliases.sql` adds immutable, tenant-fenced
project aliases with alias kind, evidence, quote, reviewer and normalized lookup
key. New project rows bind the complete alias set with a SHA-256 manifest;
deferred checks reject appended or unrelated-evidence aliases. Existing project
rows are not rewritten and keep exact-title fallback. A name may map to more
than one reviewed project candidate; neither uniqueness nor truth is inferred.
Migration `0060_reviewed_project_members.sql` adds immutable, tenant-fenced
person/organization-to-project `knowledge_project_members` role assertions.
Each has a bounded role slug, status, optional valid interval, direct evidence,
reviewer and same-kind supersession. The role is never an access grant. The
member kind is admitted to evidence, search and correction checks. Exact-project
dossiers include independently bounded members; source-scoped reads require
visibility of the member and both linked assertions. This is not a computed
current roster or a strict role registry, and historical rows are unchanged.

Migration `0065_reviewed_project_artifacts.sql` adds an append-only, tenant-
fenced reviewed association from one exact project to one exact DataCore
evidence occurrence. The separate basis evidence and quote explain the link;
the artifact may be an Email attachment whose parent message carries the
quote. Actor-scoped receipts make writes idempotent. The bounded read returns
current-authorized link history, source kind and evidence IDs, not source text,
paths, a computed current relation or a Markdown dossier. Same-hash Email
attachments remain distinct by occurrence evidence ID.

Migration `0066_reviewed_project_facts.sql` adds immutable, forced-RLS
`knowledge_project_facts` and actor-scoped receipts. Each fact has one exact
project subject, bounded predicate and typed value, a frozen 1–20-element
evidence-ID array, one quote-bearing evidence ID from that array, source-stated
derivation, review/status/confidence and observation/valid/recorded times.
The SQL insert guard rejects duplicate or missing evidence, stale/excluded
source versions, absent exact normalized-text quotes and supersession that
changes project, predicate or value type. A separate page index supports
pre-limit source-grant filtering; no old claim/project heap is rewritten.
This first fact kind is not included in generic Knowledge lexical search,
correction or change-feed contracts yet. Its read path is the exact-project
fact page/dossier only, with value previews and evidence IDs. It does not
store inferred basis links, unit/currency semantics or export-ready quotes.

The [Librarian interoperability review](LIBRARIAN_INTEROP.md) and
[ADR-169](adr/169_code_first_librarian_interop.md) define proposed additions.
ADR-202 now supplies a narrow project/event/commitment Markdown proposal route;
ADR-205 adds members, and ADR-206 adds a separate project-fact queue;
the remaining unimplemented additions are inferred-derivation/basis links,
typed monetary units and uncertain due
windows, expanded project-artifact dossier presentation and a compatible
fact-name registry.
New basis links must preserve transitive source grants. Existing Email attachment
occurrences remain distinct even when their content hashes match. Project
aliases, reviewed members, artifact links and source-stated project facts are
separate ADR-182/183/193/195 slices; the remaining proposed KnowledgeCore
additions have no migration.

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

Migration `0046_fileos_v2_document_publication.sql` adds immutable v2 document
attempts and one exact hashed-row outcome ledger per attempt. A deferred SQL
check balances all six terminal outcomes against the completed baseline's
prepared hashed rows, while a source-locked trigger refuses a superseded v1
or root. Extracted rows bind to normalized documents on prepared v2 evidence;
hashless and excluded rows gain no fabricated versions or documents. A ready
attempt has no changed/failed rows, and only one ready attempt is allowed per
completion. The tables do not activate v2 current reads or absence. See
[ADR-125](adr/125_fileos_v2_baseline_document_publication.md).

Migration `0047_fileos_v2_shared_index_generation.sql` extends the existing
DataCore generation parent with an exactly-one-of-v1-or-v2 basis. A v2 basis
binds the completed stage and one ready document attempt; its item and chunk
children reuse the existing immutable generation tables. Readiness validates
exact hashed attempt membership and published chunk identities against the
base `brain_chunks` ledger. The stage count map preserves nonindexed hashless
and excluded observations without inventing items or documents. SQL refuses
every v2 activation; v1 generations and current reads remain unchanged. See
[ADR-126](adr/126_fileos_v2_shared_index_generation.md).

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
