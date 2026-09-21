# Deployment

This is the production target, not a deployed environment. See
[HOSTING_DECISION.md](HOSTING_DECISION.md) for the consolidated Azure planning target
and AWS/other alternatives, and
[LOCAL_DEVELOPMENT.md](LOCAL_DEVELOPMENT.md) for the executable synthetic prototype.
No cloud infrastructure, real email connection or paid resource has been provisioned.

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
   |-- action executor (provider-write egress, no model access)
   |-- managed queue/cache
          |
   managed PostgreSQL + pgvector (private endpoint, PITR)
   encrypted object storage (raw MIME/attachments, versioning)
   KMS + secrets manager
   immutable log/metrics destination
```

This can run on AWS, GCP, Azure, or a reputable managed Postgres platform. Select region, data-processing terms, backup/restore support, extension support, private networking, audit logs, and exit/export capabilities—not marketing convenience alone.

## Access from anywhere

Users access only HTTPS API/MCP, authenticated through OIDC. Operators and owner-only administration should additionally use a device-aware Zero Trust/private overlay. A Tailscale deployment can apply deny-by-default Grants ([documentation](https://tailscale.com/docs/features/access-control/grants)); equivalent Cloudflare Access/private service connectivity is acceptable. Do not publish PostgreSQL, SSH, Ollama, worker dashboards, or raw object storage.

## Database

- Managed PostgreSQL 17+ (or supported current version), `pgvector`, Multi-AZ where budget permits.
- Private endpoint, TLS required, connection pooler, automated PITR, deletion protection, maintenance window.
- Separate migration owner and runtime roles; RLS on tenant tables; runtime does not own tables or bypass RLS.
- Start with exact vector search. Add HNSW only after production-sized tests; `pgvector` documents the recall/build-memory tradeoff ([project](https://github.com/pgvector/pgvector)).
- Nightly logical schema/data export is supplementary; PITR is primary. Verify restoration, not just backup status.

## Object storage

Versioned, encrypted buckets with public access blocked, tenant-derived prefixes, malware-scan/quarantine states, lifecycle policies, and access logs. Store raw MIME and large attachments; keep hashes/metadata in PostgreSQL. Signed download URLs are short-lived and issued only after authorization.

## Local processing and replicas

Two supported modes:

1. **Hosted inference:** local-model runtime inside the private deployment. Simplest operations, still avoids third-party model disclosure.
2. **Trusted edge inference:** an always-on owner device pulls encrypted, tenant-scoped jobs over mutually authenticated outbound connections and returns schema-validated results. No inbound home port. Jobs and results are signed/replay-protected.

An encrypted SQLite replica may provide offline search on an authorized device. It contains the minimum tenant/user subset, has a revocable device key, expires stale data, and syncs through a change feed. It never accepts shared authoritative writes.

## Environments

- `dev`: synthetic mail only; local containers allowed.
- `staging`: synthetic/reversible provider test accounts; production-like auth/RLS/networking.
- `prod`: separate cloud account/project, KMS keys, database, OAuth apps, buckets, and model credentials.

No production data copies to development. Sanitized fixtures require an explicit irreversible process and review.

## Delivery

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

Start small: 2 API instances, independently scaled worker pools, managed Postgres with enough RAM for hot FTS/indexes, and one local inference worker sized after benchmarks. Autoscale queue-bound stateless workers; cap model concurrency and provider rate. Measure before partitioning.

## Configuration

Environment contains secret references and non-sensitive boot config only. Taxonomy, rule versions, model routing, folder mappings, retention, and approval policy are versioned database/config artifacts with audit and staged rollout.
