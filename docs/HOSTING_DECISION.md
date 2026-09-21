# Hosting recommendation

Updated 2026-09-20 for Jim's preference to avoid multiple hosting accounts.
**Preferred planning target: the same Azure account used for RealEstateOS, if Azure
is its selected host.** This supersedes the earlier AWS-first recommendation below.
It does not mean adopting Microsoft mail, SharePoint, or Microsoft-only software.
Actual account ownership, subscription, region and budget still need confirmation;
no paid deployment or cloud configuration has been performed.

## Consolidated Azure shape

- Container Apps for the API and separately scoped read workers; it supports API
  endpoints and scheduled/background jobs. The current loopback CLI/developer image
  must not be exposed publicly as-is. Production ingress and OIDC are release gates.
  ([Container Apps](https://learn.microsoft.com/en-us/azure/container-apps/overview))
- Managed PostgreSQL with private connectivity, public access disabled, verified
  TLS, backups and separate migration/runtime roles. Keep forced application RLS;
  cloud identity does not replace tenant authorization.
  ([PostgreSQL security](https://learn.microsoft.com/en-us/azure/postgresql/security/security-overview))
- Private Blob storage for larger raw mail/attachments; least-privilege managed
  identities and Key Vault for remaining provider secrets. Database and object
  recovery require separate, coordinated restore tests.
  ([Blob recommendations](https://learn.microsoft.com/en-us/azure/storage/blobs/security-recommendations),
  [Container Apps identities](https://learn.microsoft.com/en-us/azure/container-apps/managed-identity))
- Same hosting billing home, separate product resource groups/identities/database
  boundaries. Email Brain must run independently of Factory and RealEstateOS.
  Avoid adding AWS Bedrock or a separate database vendor to the initial Azure design.
  Local models remain optional; remote inference requires its own consent, cost,
  availability and retention review. No GPU or remote inference is provisioned.

This is our design recommendation, not a claim of zero extra setup or a fixed
monthly price. Existing mailbox authorization remains necessary. Verify the whole
region-specific bill and any actual partner credits; do not assume $50/month or
free production use. If the established hosting home is AWS instead, the alternative
below remains viable without creating Azure merely for Email Brain.

## Earlier AWS alternative

For multiple products in one security/operations environment, AWS offers private
networking, database backups, workload identities, KMS, secrets, objects and logs.
RDS encryption covers the database and associated encrypted backups/snapshots;
key access and recovery must be planned.
([RDS encryption](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/Overview.Encryption.html))

Having another AWS bill is **not** a subscription making these resources free.
Database compute, app workers, storage/backups, logs, model compute, traffic,
NAT/endpoints and load balancers have separate cost drivers. Estimate the entire
stack in the chosen region; do not assume free-tier eligibility.
([RDS pricing](https://aws.amazon.com/rds/postgresql/pricing/))

## Alternatives

| Option | Why choose it | Main check/tradeoff |
|---|---|---|
| AWS RDS + S3 + ECS/Fargate | Unified private infrastructure and isolated worker identities | More setup and baseline network/compute costs |
| Supabase Postgres/Auth/Storage | Faster setup with integrated auth/storage | Verify plan-level PITR/network controls; custom non-bypass DB role; object bytes need separate backup |
| Neon + API host + object store | Portable Postgres, usage-based compute, development branching | Separate auth/blob/app services; verify IP/private connectivity and restore retention |
| Self-hosted VPS | Direct control and low entry compute cost | You own OS/DB patching, HA and recovery; not preferred for unattended private mail |

Sources: [Supabase responsibility](https://supabase.com/docs/guides/deployment/shared-responsibility-model),
[backup scope](https://supabase.com/docs/guides/platform/backups),
[pricing](https://supabase.com/pricing), [Neon security](https://neon.com/security),
[Neon usage pricing](https://neon.com/blog/new-usage-based-pricing).
Verify exact plan/security features before approval; encryption does not fix an
overly broad application role. Supabase database backups do not include stored
object bytes. Model charges are separate from hosting on every option.

## AWS deployment shape

1. Private RDS Postgres endpoint, TLS, encryption, PITR, deletion protection and
   separate migration/runtime roles. A shared early RDS instance can host separate
   product databases only after accepting shared maintenance/failure impact.
2. Private S3 raw/attachment storage: block all public access, SSE-KMS, scoped IAM,
   versioning, lifecycle, manifests and independent recovery. Do not enable fixed
   Object Lock retention before deciding purge requirements.
   ([S3 security](https://docs.aws.amazon.com/AmazonS3/latest/userguide/security-best-practices.html))
3. Separate container roles for API, provider readers and extraction. The binary
   extraction worker has no Internet route/provider credentials, bounded memory,
   CPU, time and scratch space, and a scanner gate.
   ([Fargate security](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/security-fargate.html))
4. HTTPS/OIDC/MFA for users; private Zero Trust operator access. Never expose DB,
   raw buckets or Ollama. Assistant clients that cannot join a VPN need a narrowly
   scoped OAuth HTTPS/MCP ingress and client-specific compatibility testing.
5. Managed KMS/secrets, scrubbed logs, budget alerts, and restore drills for both
   DB and objects. Start without a hosted GPU: a private outbound-only local-model
   worker can pause while offline; no silent remote-model fallback.

## Where data lives

| Data | Authoritative home | Local/Dropbox treatment |
|---|---|---|
| Code/migrations/docs | Private GitHub | Working source checkout or intentional mirror |
| Messages/entities/rules/obligations/grants/audit | Managed Postgres | Never a live DB in Dropbox |
| MIME/attachments/extracted artifacts | Encrypted private object store | Explicit exports only |
| Secrets/keys | Secret manager/KMS | Private OS-backed bootstrap storage only |
| Inference cache/optional replica | Device-private encrypted storage | Outside Dropbox; disposable and scoped |
| Factory feedback | Product proposal files in Git | Factory pulls/reviews; runtime stays independent |

Pending owner decisions: budget ceiling, region/data residency, existing AWS
operations, first account/backfill, retention and sharing model. No paid cloud
resources or billing commitments were created during this build.
