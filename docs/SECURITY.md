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
