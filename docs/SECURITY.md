# Security

## New local prototype boundaries

[Isolated MIME recovery](ISOLATED_MIME_RECOVERY.md) runs explicitly on a trusted
controller with an image-bound parser, no network/mounts, disabled logs and enforced
resource/output limits. Default API retry cannot select or launch it. Docker daemon
access must never be given to the API or parser. This extracts bounded source text,
not binary documents; cloud queue authorization and sandbox operational acceptance
remain gates. Infrastructure failures cannot be cached as successful/rejected mail.

[Encrypted large evidence](LARGE_EVIDENCE_STORAGE.md) adds an opt-in tenant/account
bound AES-GCM filesystem backend, immutable SQL manifests and verified reads.
Only raw external objects are encrypted here; normalized database text and legacy
inline bytes still need managed database encryption. Missing/corrupt storage fails
closed, without checkpoint advancement or destructive cleanup. Cloud IAM/KMS and
key-loss recovery remain gates.

[Held-message recovery](QUARANTINE_RECOVERY.md) requires a human owner with review
and evidence scopes at the library boundary. Hash verification precedes parsing;
account locking and latest-event checks prevent stale recovery from resurrecting
deleted/replaced mail. Fixed attempt outcomes are immutable and tenant-isolated.
Raw bytes, cursors and provider events are unchanged; parser exceptions are scrubbed.
This supersedes earlier statements that all independent reprocessing is deferred;
bulk reprocessing, automatic retry, binary execution and production access remain gated.

Calendar extraction is quoted untrusted source text, never an RSVP or scheduler.
It validates bounded syntax and MIME/body method agreement, with no alarm/URL
execution or organizer authentication. Binary calendar data is unsupported and
malware scan status remains unchanged. See [calendar boundary](CALENDAR_ATTACHMENTS.md).

Rule activation requires human owner identity plus review/search scopes, an
actor-bound simulation receipt, unexpired database time and matching rules revision.
Rollback is append-only; virtual Review Delete labels never hide or delete messages.
Sender domains are untrusted header metadata, not authenticated identity.
All direct request text fields reject NUL and unencodable Unicode before SQL.
See [reviewed rules](REVIEWED_RULES.md).

The opt-in [Ollama adapter](LOCAL_MODEL_RUNTIME.md) requires operator-attested local
daemon isolation and checks installed model metadata/digest before email disclosure.
These checks cannot substitute for daemon egress controls or eliminate a privileged
local replacement race. No model path is enabled by default and no model output
executes actions. [Restore testing](RESTORE_DRILL.md) uses a fresh disposable cluster,
private temporary archive, content-free results and exact owned-container cleanup.

## Implemented quarantine and reconciliation boundary

Bounded malformed MIME is stored byte-for-byte behind the same tenant RLS as raw
evidence, not rendered, executed or exposed by the status API. Receipts contain a
fixed reason rather than parser exception text. NUL bytes are removed only from
normalized text fields; original bytes and their hash remain unchanged. This is
not malware scanning or an isolated binary extractor. Default raw storage remains
1 MiB; opt-in encrypted Fastmail ingestion preserves up to 16 MiB and holds mail
above the parser budget. Beyond the configured download/storage limit still pauses.
Only a certified complete provider inventory can hide absent current projections;
partial or duplicate-ID inventories cannot authorize absence. No provider deletion
or evidence erasure is involved. Demo corpus loading refuses enrolled accounts.

## Current release boundary

The v0.1 service is loopback-only, synthetic-data-first, owner-only per tenant.
Bootstrap tokens are hashed, expiring, scope-bound, and revocation is via the private
registry plus restart; they are not production OAuth/OIDC. The schema is tenant-isolated
but team/account-grant sharing is not implemented. Binary attachments remain deferred,
not malware-scanned. No send/delete/action/model network path is enabled. OIDC,
rate limiting, grant-aware sharing, denial audit, external immutable audit export,
full retention/purge, cloud encryption and restore proof are production blockers.

RLS is defense in depth against missing query filters, not protection against a fully
compromised server with arbitrary SQL execution and shared runtime credentials.
The trusted server sets transaction-local tenant context only after token resolution.
Separate per-tenant service credentials may be required by a stronger threat model.

## Security objectives

Protect message confidentiality, tenant isolation, provider credentials, mailbox integrity, and the trustworthiness of derived state. Assume every email, attachment, link, web result, and model response may be adversarial.

## Threat model

| Threat | Primary controls |
|---|---|
| Cross-tenant data access | Tenant IDs, API checks, PostgreSQL RLS, negative tests, scoped caches |
| Stolen provider token | OAuth/app password vault, narrow scopes, envelope encryption, rotation/revocation |
| Prompt injection in mail | Data/instruction separation, reader without tools, schema allowlists, action policy |
| Assistant overreach | Per-tool scopes, bounded result sets, approval tokens, no token passthrough |
| Malicious/buggy rule | Simulation, review tiers, immutable versions, protected classes, rollback |
| Duplicate/destructive action | Idempotency, outbox state machine, confirmation, reconciliation |
| Database/operator compromise | Private networking, KMS, least privilege, audit export, backups, break-glass alerts |
| Backup leakage | Client/provider encryption, separate key access, retention, restore audit |
| Supply-chain compromise | Pinned dependencies, SBOM, signature/provenance checks, staged upgrades |

## Identity and authorization

- Use an OIDC identity provider with MFA/passkeys; short-lived access tokens; server-side sessions where appropriate.
- Resolve `tenant_id`, `user_id`, roles, grants, and purpose at ingress. Never accept tenant identity from an unverified request body.
- Enforce authorization in service code and PostgreSQL RLS. Enable and `FORCE ROW LEVEL SECURITY` on tenant tables; runtime roles must not own tables and must not have `BYPASSRLS`. PostgreSQL RLS defaults to deny when enabled without a policy ([documentation](https://www.postgresql.org/docs/17/ddl-rowsecurity.html)).
- Separate roles: migration owner, runtime API, read connector, action executor, audit reader, and backup operator.
- Use object keys prefixed and authorized by tenant; signed URLs are short-lived and single-purpose.

## Network and remote access

- Database and internal services have no public ingress.
- Put API ingress behind a managed WAF/reverse proxy and OIDC; optionally require a device-aware private overlay for owner/operator access. Tailscale Grants are deny-by-default and can combine network and application permissions ([docs](https://tailscale.com/docs/features/access-control/grants)). A Cloudflare Access or equivalent Zero Trust deployment is an acceptable alternative.
- Require TLS in transit, certificate verification, egress allowlists for provider/model endpoints, and separate subnets/security groups for actions and inference.
- Never expose Ollama/llama.cpp or a local MCP server to the LAN/Internet without authentication and policy enforcement.

## Secrets and cryptography

- Store OAuth refresh tokens and iCloud app-specific passwords in a managed secret vault, encrypted with KMS envelope keys; keep only secret references in PostgreSQL.
- Prefer per-environment KMS keys and consider per-tenant data-encryption keys for high-sensitivity deployments.
- Managed database/storage encryption is mandatory; encrypted backups and key rotation are tested.
- Redact secrets, auth headers, body text, and attachment contents from logs. Hash identifiers only when correlation is necessary.

## Prompt-injection defense

OWASP recommends separating instructions from data, least privilege, output validation, monitoring, and—at higher risk—a quarantined reader/privileged actor split ([cheat sheet](https://cheatsheetseries.owasp.org/cheatsheets/LLM_Prompt_Injection_Prevention_Cheat_Sheet.html)). Apply it as architecture:

1. Parse and label message content as `UNTRUSTED_EMAIL_DATA`; never interpolate it into system/tool instructions.
2. The inference reader has no provider write token, shell, arbitrary URL fetch, secret access, or broad database tool.
3. Permit only versioned JSON Schemas; reject extra fields, URLs/tool calls, oversize output, and unknown enums.
4. The policy engine evaluates proposed actions from original user intent + structured facts, not raw email instructions.
5. High-impact actions require a fresh human approval bound to exact preview/hash/expiry.
6. Sanitize rendered HTML/Markdown, proxy or disable remote images, and scan attachments before parsing.
7. Maintain injection/red-team fixtures and alert on suspicious phrases, encoding, exfiltration patterns, and policy denial spikes.

## MCP/API security

The current MCP authorization guidance requires token audience validation and forbids token passthrough ([MCP security considerations](https://github.com/modelcontextprotocol/modelcontextprotocol/blob/main/docs/specification/2026-07-28/basic/authorization/security-considerations.mdx)). Therefore:

- Remote MCP uses OAuth with PKCE/resource indicators, audience-bound tokens, exact redirect URIs, short lifetimes, and per-tool scopes.
- The MCP gateway translates identity into a tenant-scoped service context; it never forwards a client bearer token to providers.
- Tool descriptions and server packages are pinned/approved; tool-list changes are treated as security-sensitive.
- Search and evidence tools are read-only by default. Mutation tools are separate and approval-aware.

## Audit and privacy

Append-only audit events record who/what/when/tenant/request, policy version, proposal/action hashes, approval, provider result, and correlation ID. Store minimal content in audit; evidence is referenced by ID. Export audit events to an access-restricted immutable sink.

Support consented account connection, data export, retention settings, account disconnect, tenant deletion, and deletion propagation into replicas/backups according to documented retention. Legal/privacy obligations depend on deployment jurisdiction and require counsel before broad team deployment.

## Backup and incident readiness

- Managed PITR plus daily encrypted logical/object manifests; quarterly restore drills.
- Separate backup credentials and deletion protection; document key-loss consequences.
- Emergency controls: disable all mailbox writes, disable remote inference, revoke one account, revoke one assistant client, put service read-only, rotate credentials.
- See [OPERATIONS_RUNBOOK.md](OPERATIONS_RUNBOOK.md) for playbooks.
