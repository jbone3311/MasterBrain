# Deployment

Updated 2026-09-21. [GAME_PLAN.md](GAME_PLAN.md) explains the delivery stages.

[ADR-039's read command](READ_CONTROLLER.md) now provides explicit private-configured
bounded Fastmail operation and non-consuming preflight. It adds no hosted resources,
service installer, enrollment or new SQL grants. Keep its provider token separate
from API/MIME/PDF credentials. Production supervision and live acceptance remain.
Migration 0012 and updated runtime grants are required for the separate
[document channel](DOCUMENT_PROCESSING.md). Configure its exact processor only
after the restricted worker is available; API configuration grants no Docker access.
ADR-036 adds the separate [document CLI](DOCUMENT_CONTROLLER.md) and loopback
`serve --document-processor-version` option. ADR-038 adds the
[owner PDF screen](DOCUMENT_REVIEW_SCREEN.md); deploy compatible `app.js`,
`document_review.js`, HTML/CSS and the fixed asset route together. It changes no
schema or worker permissions. Hosted deployment and browser acceptance remain pending.
Migration 0011 adds the owner history index; ship compatible API/assets together
and account for index-build locking. Hiding controls does not cancel existing
approvals. The production topology below is planned, not provisioned.

The optional [isolated MIME controller](ISOLATED_MIME_RECOVERY.md) is a separate
trusted-worker privilege. Do not add the Docker socket to the API image/deployment.
The [operator CLI](PROCESSING_CONTROLLER.md) now supports explicit private
configuration and bounded execution on that trusted host; credential enrollment
and service installation remain operator/deployment work, not automatic startup.
The [durable job channel](RECOVERY_JOBS.md) adds explicit bootstrap approvals and
requires migration 0010 plus updated runtime grants, API and controller code.
Hosted scheduling, production identity and isolation verification remain gates;
the checked local/CI Docker controls are not an Azure deployment template.

The opt-in [encrypted local object backend](LARGE_EVIDENCE_STORAGE.md) is an
executable storage contract, not Azure Blob deployment. Migration 0009 requires
upgrading API, workers and backup/recovery readers together. Keep object roots
outside Git/Dropbox and supply tenant keys separately; neither is discovered by
the CLI. Hosted IAM/KMS, offsite backups and production ingress remain gates.

This is the production target, not a deployed environment. See
[HOSTING_DECISION.md](HOSTING_DECISION.md) for the consolidated Azure planning target
and AWS/other alternatives, and
[LOCAL_DEVELOPMENT.md](LOCAL_DEVELOPMENT.md) for the executable synthetic prototype.
No cloud infrastructure, real email connection or paid resource has been provisioned.

The current default image deliberately excludes the PDF/Office fixture readers.
Do not install development extras in a production API image to enable document
intake. ADR-034 adds [Dockerfile.pdf](../Dockerfile.pdf), a dedicated opt-in synthetic
worker image/profile; ADR-035 adds a separate synthetic approval/result/search path.
The local Docker isolation checks are not proof that
an arbitrary managed container service provides equivalent isolation.

## Recommended production topology

```text
Internet/provider webhooks
          |
 managed edge: TLS + WAF + OIDC + rate limits
          |
 private application network
   |-- API/MCP gateway
   |-- query/control workers
   |-- connector workers (egress to mail providers)
   |-- inference quarantine (local model, no action credentials)
   |-- future action executor (separately approved; absent in read-only pilot)
   |-- optional managed queue/cache (only if measured need)
          |
   managed PostgreSQL / FTS (private endpoint, PITR; vectors optional later)
   encrypted object storage (raw MIME/attachments, versioning)
   KMS + secrets manager
   immutable log/metrics destination
```

This can run on AWS, GCP, Azure, or a reputable managed Postgres platform. Select region, data-processing terms, backup/restore support, extension support, private networking, audit logs, and exit/export capabilities—not marketing convenience alone.

## Access from anywhere

Users access only HTTPS API/MCP, authenticated through OIDC. Operators and owner-only administration should additionally use a device-aware Zero Trust/private overlay. A Tailscale deployment can apply deny-by-default Grants ([documentation](https://tailscale.com/docs/features/access-control/grants)); equivalent Cloudflare Access/private service connectivity is acceptable. Do not publish PostgreSQL, SSH, Ollama, worker dashboards, or raw object storage.

## Database

- Managed PostgreSQL on a supported, provider-available version verified with our
  migrations/extensions. PostgreSQL 17 is the current CI baseline, not a newest-version
  recommendation. Choose the provider's high-availability configuration for the
  accepted availability target and budget; it is not already provisioned.
- Private endpoint, TLS required, connection pooler, automated PITR, deletion protection, maintenance window.
- Separate migration owner and runtime roles; RLS on tenant tables; runtime does not own tables or bypass RLS.
- Start with FTS. If measured retrieval gaps justify `pgvector`, benchmark exact
  search before approximate indexes such as HNSW. Keep permission filters and recall
  tests in every comparison ([pgvector](https://github.com/pgvector/pgvector)).
- Nightly logical schema/data export is supplementary; PITR is primary. Verify restoration, not just backup status.

## Object storage

Versioned, encrypted buckets with public access blocked, tenant-derived prefixes, malware-scan/quarantine states, lifecycle policies, and access logs. Store raw MIME and large attachments; keep hashes/metadata in PostgreSQL. Signed download URLs are short-lived and issued only after authorization.

## Local processing and replicas

Two planned modes (neither is a deployed service):

1. **Hosted inference:** local-model runtime inside the private deployment. Simplest operations, still avoids third-party model disclosure.
2. **Trusted edge inference:** an always-on owner device pulls encrypted, tenant-scoped jobs over mutually authenticated outbound connections and returns schema-validated results. No inbound home port. Jobs and results are signed/replay-protected.

An encrypted SQLite replica may provide offline search on an authorized device. It contains the minimum tenant/user subset, has a revocable device key, expires stale data, and syncs through a change feed. It never accepts shared authoritative writes.

## Environments

- `dev`: synthetic mail only; local containers allowed.
- `staging`: synthetic/reversible provider test accounts; production-like auth/RLS/networking.
- `prod`: isolated resources/identities, keys, database, OAuth apps and storage.
  A separate Azure subscription is an optional stronger boundary, not a requirement
  to sign up with another vendor. Sharing billing never implies shared data access.

No production data copies to development. Committed/CI fixtures stay synthetic.
Any external-data exception requires the explicit [adoption gate](PUBLIC_EMAIL_TEST_DATA.md).

## Delivery

The following are production delivery requirements, not a list of completed CI
features. See [status](IMPLEMENTATION_STATUS.md) and [receipts](BUILD_RECEIPT.md)
for checks actually implemented and run. In particular, infrastructure-as-code,
SBOM/signature automation, cloud rollout and production acceptance remain gates.

- Infrastructure as code; immutable container images by digest; minimal non-root images.
- Migrations are backward-compatible: expand → deploy → backfill → contract.
- CI produces tests, dependency/license report, SBOM, vulnerability scan, migration plan, and image signature/attestation.
- Canary workers/API; shadow model/search versions; fast application rollback. Database rollback uses forward repair unless a tested reversible migration exists.

## Backups and disaster recovery

- RPO target ≤15 minutes; RTO ≤4 hours after v1 stabilization.
- PostgreSQL continuous/PITR and daily snapshot; object versioning plus inventory manifest; configuration/rule exports.
- Cross-account or cross-region protected copy for production where threat model/budget warrants.
- Quarterly full restore into an isolated environment, verify hashes/counts/search, rotate temporary secrets, and record measured RPO/RTO.

## Minimum sizing

For a production availability objective, evaluate two API replicas plus separately
scaled workers and Postgres sized for the measured corpus/indexes. A single-instance
synthetic pilot is not a high-availability commitment. Do not buy a GPU or provision
a model worker before quality/capacity benchmarks. Cap concurrency and provider
rate, price the whole region-specific topology, and measure before partitioning.

## Configuration

Environment contains secret references and non-sensitive boot config only. Taxonomy, rule versions, model routing, folder mappings, retention, and approval policy are versioned database/config artifacts with audit and staged rollout.
