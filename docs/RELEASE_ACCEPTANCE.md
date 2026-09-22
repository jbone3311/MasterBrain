# MasterBrain Release Acceptance

No documentation, unit test, or donor extraction alone makes MasterBrain production
ready. Evidence for every gate records artifact version, environment, corpus/source,
operator, date, result, exceptions and rollback receipt.

## Product and source gates

- Email and FileOS are presented as capabilities under MasterBrain, not competing
  product identities.
- Each authorized source can initial-sync, resume, replay, reconcile, pause and revoke
  without omission or unintended duplication.
- FileOS operator preflight is non-mutating; exact retries converge, credential
  revocation fails closed, and output/logs do not disclose paths, content or secrets.
- Unsupported/partial/quarantined items are counted and inspectable.
- FOS-Master stays available and unchanged until FileOS cutover is separately accepted.

## DataCore gates

- Stable source/version/evidence IDs and SHA-256 are reproducible.
- Original evidence is immutable/verified; all derivatives have complete provenance.
- Extraction/OCR limits, format outcomes and malicious corpus tests pass.
- Document workers prove network isolation, read-only root, dropped capabilities,
  process/resource/output limits, dependency separation and closed-result validation.
- Chunk/index rebuild produces equivalent identities and query results.
- Rebuild preview is run-bound, paginated and side-effect free. Generation execution
  is completion/plan/code/chunker-bound, idempotent, transactionally closed and
  immutable; activation is separately authorized and prior-generation reactivation
  proves rollback before any global search cutover.
- Generation check mode is non-consuming; build and rollback credentials have exact
  operation scopes, revocation fences activation, and output contains no paths,
  content, credentials or database diagnostics.
- Source freshness advances only on an immutable receipt whose terminal counts cover
  the exact intake manifest; crash prefixes and conflicts never report complete.
- Inventory membership balances exactly against its completion receipt; absence is
  inferred only between complete monotonic observations and never deletes evidence.
- Dedupe never implies deletion; held-out/cross-domain protections pass.
- Every migrated FOS tranche has zero unexplained golden differences and documented
  shadow tolerances.

## KnowledgeCore gates

- Entity resolution, claims, relationships, timeline, projects and commitments meet
  agreed precision/recall or reviewed known-answer thresholds.
- Every surfaced claim has supporting/contradicting evidence and precise locators.
- Corrections/supersession preserve history; conflicting claims remain visible.
- Source, DataCore and KnowledgeCore freshness are independently reported.

## Brain API gates

- Search/answer/expand/evidence pagination and byte/token budgets are enforced.
- Citations resolve to hash-verified evidence; revocation invalidates all derived access.
- Claude, Grok, ChatGPT and reference clients pass one provider-neutral contract suite.
- Prompt injection cannot expand scopes, select credentials, invoke arbitrary tools, or
  turn a proposal into an effect.
- Cross-tenant/source isolation and enumeration tests pass.

## Privacy, security and operations gates

- Threat model, least-privilege identities, RLS, network isolation, key rotation,
  dependency/container scans and parser sandbox review are accepted.
- Retention, export, purge and legal hold cover originals, derivatives, indexes,
  summaries, caches, logs and backups.
- Telemetry/content leakage tests pass; remote-model disclosure/consent is verified.
- Backup/restore, disaster recovery, worker crash, cursor expiry, queue replay,
  rate-limit and dependency outage drills meet RPO/RTO targets.
- Dashboards and alerts expose lag/failure without content.

## FileOS cutover gates

- Pinned donor provenance and inventory are complete.
- Golden, fault-injection, scale and read-only shadow comparisons pass.
- Safe-effect broker equivalence is proven separately if effects are in scope.
- Bounded cohort cutover and rollback are rehearsed.
- Owner accepts results and explicitly authorizes broader switch.
- FOS-Master rename/retirement is not bundled with initial cutover.

## Initial read-only release decision

Release requires all applicable gates above, no unresolved critical/high security or
data-loss defect, complete operator/user documentation, and a signed exception record
for any deferred non-critical item. Local test skips are not passes.
