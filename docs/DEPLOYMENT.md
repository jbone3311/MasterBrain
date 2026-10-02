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
Synthetic bootstrap assistant source allowlists are not a hosted access system:
administrator-owned OIDC source enrollment, revocation and derived-cache
invalidation remain release gates (ADR-130 and issue #88).

PDF, DOCX and XLSX use the dedicated `Dockerfile.documents` worker image. The ordinary
API image intentionally excludes document-reader dependencies. The document worker is
invoked through the existing networkless, read-only, capability-free sandbox with CPU,
memory, process and output limits; it receives one bounded request on stdin and returns
one schema-validated result. Production must preserve or strengthen that boundary.

## Release and rollback

Schema migrations use a dedicated administrative credential whose effective role
has `BYPASSRLS` or superuser visibility as well as the needed DDL permissions. The
migrator rejects any other role before creating its ledger or changing schema;
runtime and worker credentials must never inherit this privilege. Migration
0034 also needs `CREATEROLE` to create the cluster-global, non-login identity-admin
group if it does not already exist. A DBA may pre-provision that group with the
attributes in [ADR-105](adr/105_identity_admin_enrollment.md) and no members;
review membership before applying 0034 or granting a named administrator login.
Apply 0035 and rerun `grant-runtime` before starting the new API binary: it removes
direct runtime identity-table SELECT and grants the exact resolver instead. An old
API binary fails closed after 0035; rollback must restore compatible code and
grants under an operator-reviewed plan, not re-enable the lookup GUC policy.
Older 0006/0008 receipts made under a non-bypass table owner do not prove that their
cross-tenant reads ran. Before applying 0029, audit missing sync-state keys and
parser mismatches with the actual migration identity. A mismatch stops the rollout
for reviewed evidence repair. See the [migration-integrity contract](MIGRATION_INTEGRITY.md).
Apply 0030 only after 0029 has completed. Verify the public-schema protected-table
inventory and enabled statement triggers under that same migrator, then exercise
direct and FK-cascaded truncation refusal in staging. See the
[protected-record contract](EVIDENCE_TRUNCATE_GUARDS.md). Neither guard replaces
privileged-administrator monitoring or restorable backups.
Migration 0036 adds a transactionally built archive-image receipt index. It is
verified on disposable synthetic data only; a populated live table requires a
reviewed lock budget or online-index migration path before rollout (issue #9).
Migration 0037 adds restrictive policies to every existing forced-RLS tenant
table. Apply only after a reviewed DDL lock budget and inventory check. Its
tenant-specific login is opt-in through a superuser provisioning helper; never
serve multiple tenants with one scoped DSN. The current shared runtime login is
still vulnerable under arbitrary SQL, so issue #7 remains open. See the
[staging/rollback contract](TENANT_LOGIN_FENCE.md).
ADR-109 adds an opt-in `serve --tenant-db-config` path using an exact-lookup-only
login plus distinct DBA-bound tenant logins. The private owner-only route file
contains explicit DSNs and is never passed to a client; the service refuses a
missing route, a wrong binding and a shared/unbound runtime DSN before tenant
queries. This synthetic path does not rotate/revoke credentials, route the
separate worker commands, or establish hosted safety. Keep the old single-DSN
mode local-only; do not deploy it as multi-tenant service access.

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
scheduler must add fenced leases, source cursors and reconciliation first.

Migration `0017_fileos_run_receipts.sql` and refreshed runtime grants must be applied
before using completion/freshness. A rollout may continue older one-shot publication
without the new controller revision, but must not advertise source freshness until
the receipt table, constraints, RLS and restore verification are active.

Migration `0018_fileos_inventory_reconciliation.sql` must precede the matching
controller revision because completion now writes the exact item ledger atomically.
Do not mix the new controller with an older schema. Rollback stops the new controller
and inventory read route; it does not remove immutable receipt or absence history.

The current `compose.yaml` remains a local Email-capability PostgreSQL setup, not a
production MasterBrain deployment.

The first-party `/brain` workspace is served as static assets by the prototype
API. It requires the same authorized read scopes as external API clients and
has no model or effect executor. Serving this shell is not a hosted product
rollout: production still requires identity, private tenant routing, enrollment,
TLS, retention, revocation, telemetry, backup/restore and owner acceptance.
