# MasterBrain Deployment

## Target topology

Deploy source connectors, API, DataCore workers, KnowledgeCore workers, and effect
executors as separate least-privilege services. Use private PostgreSQL, private object
storage, managed identity/secrets, an internal queue, monitored backups, and explicit
network egress. FileOS roots may remain in place and be reached through a narrowly
scoped scanner/agent rather than copied wholesale.

Azure remains the current hosting direction for the Email prototype, with separate
MasterBrain resources and permissions. This is not a requirement to use Microsoft
mail or SharePoint. A hosting change requires an ADR, equivalent privacy/security
controls, and restore/rollback proof.

## Environments

- **Development:** synthetic fixtures, loopback services, disposable database, no
  real source credentials.
- **Parity:** pinned FOS-Master checkout plus synthetic golden corpus; read-only.
- **Staging:** production-shaped identities/network/storage with disposable or
  explicitly authorized test sources.
- **Production:** approved sources only, private endpoints, managed keys, alerting,
  backups, retention/legal hold, and operator runbooks.

Environment identities, databases, buckets, indexes and keys are separate. Never
place live databases, secrets, object stores, model caches, or content-bearing logs in
Git or synchronized source folders.

## Service privileges

Connectors can read only their configured source/account/root and publish intake.
Extraction workers can read bounded evidence and publish derivatives, not source
effects. Knowledge workers read DataCore publications and write projections. Brain API
has scoped retrieval, not provider/filesystem credentials. Effect executors are
separate, disabled initially, and restricted to approved commands.

PDF, DOCX and XLSX use the dedicated `Dockerfile.documents` worker image. The ordinary
API image intentionally excludes document-reader dependencies. The document worker is
invoked through the existing networkless, read-only, capability-free sandbox with CPU,
memory, process and output limits; it receives one bounded request on stdin and returns
one schema-validated result. Production must preserve or strengthen that boundary.

## Release and rollback

Build immutable artifacts with dependency locks, SBOM/provenance, schema compatibility
checks, migrations with rollback/forward recovery, and staged health gates. Deploy
additively, backfill from immutable evidence, compare counts/digests/query answers,
then direct bounded traffic. Rollback fences new jobs, restores the previous service,
preserves newly captured evidence, and reconciles cursors/outboxes.

FileOS cutover follows [the migration plan](FOS_MIGRATION.md): golden parity, read-only
shadow, bounded cohort, observation, and explicit owner acceptance. FOS-Master stays
available throughout rollback and is not renamed or retired by deployment automation.

## Operations

Monitor source lag, intake failures, extraction outcomes, quarantine, index freshness,
knowledge lag, authorization denials, unusual evidence reads, effect proposals,
storage/key health, backup age and restore tests. Alerts contain no source content.
Capacity limits cover item size, archive depth, OCR pages, chunk count, query budget,
concurrency and retry storms.

Before promoting a document-worker image, run the malicious-container corpus and a
PostgreSQL publication check. Image identity, dependency lock, sandbox inspection,
corpus result and database result belong in the release receipt.

The prototype FileOS publisher is an explicit one-shot operator process, not an API
route or daemon. Mount its configuration/credential/token/manifest read-only, inject
the least-privileged runtime DSN at process launch, run `--check`, then invoke once
with a recorded UUID. Do not place Docker authority in the Brain API service. A future
scheduler must add fenced leases and durable whole-run completion receipts first.

The current `compose.yaml` remains a local Email-capability PostgreSQL setup, not a
production MasterBrain deployment.
