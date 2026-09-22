# MasterBrain Security and Privacy

MasterBrain processes highly sensitive email and files. Its threat model includes
malicious source content, compromised client/model output, parser exploits, confused
deputy actions, cross-tenant access, credential theft, poisoned indexes, data
exfiltration, destructive file/mail effects, and leakage through logs/backups.

## Trust boundaries

- Email, files, archives, metadata, OCR, extracted text, links, and model output are
  untrusted data. They cannot grant permission or select credentials/tools.
- Source adapters, extraction workers, DataCore, KnowledgeCore, Brain API, and effect
  executors use separate identities and least-privilege scopes.
- Brain API clients receive typed operations only—never general SQL, arbitrary HTTP,
  provider tokens, storage credentials, unrestricted paths, or raw object keys.

## Privacy principles

- Collect only authorized sources and retain only what an explicit policy requires.
- Prefer deterministic/local processing; remote inference is optional, minimized,
  redacted where practical, disclosed, logged, and revocable.
- Do not use user content to train a model without a separate explicit opt-in.
- Separate metadata/search permission from extracted content and original evidence.
- Support export, retention, purge, and legal hold with auditable receipts.
- Telemetry excludes content by default; logs use opaque IDs, states, counts, timings,
  and bounded sanitized errors.

## Required controls

- Strong human/service identity, short-lived credentials, explicit enrollment and
  current authorization checks.
- Tenant/source isolation in application code and forced database RLS.
- Encryption in transit and at rest; managed key rotation and recovery procedures.
- Network isolation for databases/object storage; no public administrative endpoints.
- Sandboxed parsers with type/size/time/memory/depth limits, malware policy, and
  quarantine. Unsupported/partial content remains visible.
- Hash verification before and after sensitive reads/effects where applicable.
- Append-only audit and transactional receipts for access, policy and effects.
- Backups encrypted separately and restore-tested; retention applies to derivatives,
  indexes, caches, exports, and backups.

## FileOS document parser controls

PDF, DOCX and XLSX are accepted only when suffix and declared media type agree. The
adapter reopens and hashes the source immediately before processing. A dedicated image
with pinned reader dependencies runs with no network, read-only root, dropped Linux
capabilities, bounded CPU/memory/processes/output and no source mount. Returned data is
validated against a closed contract and rebound to the expected source version,
locator, digest, size and media type before publication.

The worker rejects encrypted PDFs, PDF actions/attachments/forms/annotations beyond
the supported subset, encrypted or macro-enabled Office packages, unsafe or duplicate
ZIP paths, excessive members/expansion/compression ratios, DTD/entity declarations and
external Office relationships. Page, sheet, row, column, cell, stream and extracted
text limits are enforced. Rejected or incomplete documents remain accounted as
unsupported, deferred or failed; they do not silently publish partial text. See
[FileOS document extraction](FILEOS_DOCUMENT_EXTRACTION.md).

The FileOS publication command accepts secrets only from owner-private files and a
runtime environment DSN. Its credential is an expiring worker identity with exactly
the two DataCore write scopes. Check mode performs no intake or extraction; execution
revalidates the local identity around each item. PostgreSQL independently rejects
privileged/owning roles and rechecks owner membership under forced RLS. Results omit
paths, filenames, content, credentials and diagnostics.

FileOS completion receipts are append-only, forced-RLS records bound to the intake
actor/request/manifest digest. Closed outcome counts must cover every item and match
published documents. Freshness reads expose only the latest complete run and never a
partial prefix, root or locator.

Completed FileOS inventories are independently balanced in PostgreSQL against their
receipt counts. Per-source serialization and monotonic observation time prevent stale
completion from replacing newer state. Absence is inferred only between two completed
ledgers; it retains evidence and does not authorize hiding, deletion or any file effect.

Rebuild preview is bounded to 50 current-ledger items and returns opaque identities,
dispositions and counts without paths or text. It uses the source completion lock and
run-bound cursor to prevent mixed-run plans. Both source and DataCore effects are false.

Index generation is separately authorized and transactionally bound to the latest
completed run. Its immutable identity includes the exact item plan, code revision and
chunker version. PostgreSQL refuses incomplete readiness, post-ready append, mutation
and cross-tenant access. Activation uses a distinct scope and idempotency receipt;
rollback reactivates a prior ready generation without deleting evidence or derivatives.

The index operator reads credentials only from owner-private files and the DSN only
from the runtime environment. Build-and-activate requires exactly the publish and
activation scopes; rollback requires exactly activation. It reauthenticates between
build and activation and after completion, returns no paths/content/secrets, and has
no source, Docker or scheduling authority.

The Email bridge operator uses the same private-file and safe-runtime checks with
exactly the shared ingest and document-publication scopes. It accepts one explicit
legacy message, attachment or approved-extraction UUID, reauthenticates around the
transaction and returns only opaque identities/counts/status. It has no Email ingest,
document approval, provider, original-content, mailbox-write, scan, scheduler or batch
authority. The bridge transactions share the Email account advisory lock so a current
version cannot become historical during publication.
Current bridged-Email search independently rejoins the receipt to the legacy current
message on every query and excludes deleted/quarantined state. It returns bounded
untrusted excerpts and opaque identities only; it does not expose raw MIME or grant
Email/source authority.

The attachment bridge requires a current visible bridged parent, shares its account
lock and never reads MIME bytes. Each occurrence remains distinct even when its digest
matches another attachment. Only already-bounded legacy extracted text is published;
all other statuses remain explicit evidence/accounting with no document or chunk.
Embedded bytes are source-bound to the retained parent MIME, not mislabeled as a
separately retained object.

The approved-PDF derivative bridge additionally requires an immutable extraction with
a completed approval job and the existing current attachment bridge. It publishes
only bounded legacy page text, records the exact result digest and processor/policy,
and never opens attachment bytes or grants document-approval authority.

## Dedupe and file safety

Duplicate detection is read-only in DataCore. A matching hash does not authorize
deletion. Cross-domain/cross-source matches require review. Held-out `TEST - */`
corpora remain excluded from destructive dedupe. Future file effects must re-hash
keeper and candidate at execution, quarantine instead of unlink where possible,
respect legal hold, cap batches, log intent before action, reconcile the index, and
support rollback.

## LLM and prompt-injection controls

Retrieved content is delimited and labelled with provenance. Models return closed,
schema-validated proposals. Deterministic policy, current identity and explicit
approval decide effects. Models cannot choose a tool outside the caller's grant or
expand their own evidence scope. Cached summaries/embeddings are purged or made
inaccessible when source access is revoked.

## Incident posture

Fail closed on authorization/provenance ambiguity and fail loud on incomplete work.
Support credential revocation, worker fencing, source pause, evidence quarantine,
audit preservation, blast-radius analysis, rebuild from immutable evidence, and
documented notification/recovery. Live-source use requires security review and the
[release gates](RELEASE_ACCEPTANCE.md).
