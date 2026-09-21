# ADR-040 — Verified API access tokens with durable local authority

Status: accepted for bounded implementation, 2026-09-21. Not live enrollment,
browser sign-in, production deployment or an authorization to contact a real issuer.

## Decision

Add an explicit loopback API authentication mode, selected by a private operator
configuration file. Keep bootstrap mode separate; never fall back from rejected
JWTs to bootstrap credentials. Use PyJWT 2.14.0 with existing cryptography/httpx,
fixed RS256 verification and actual RSA public keys, not custom signature code.

Two separately configured access-token profiles are supported:

- `rfc9068`: access-token `typ`, required registered claims and configured admission
  scope. The verifier checks issuer, audience, subject/client and issuance/expiry. See
  [RFC 9068](https://www.rfc-editor.org/rfc/rfc9068.html).
- `entra-v2`: fixed tenant-specific public-cloud issuer, API application audience,
  `JWT` type, version 2.0, configured tenant, allowed `azp` and delegated `scp`.
  Honor issuer restrictions on signing keys. No common/organizations issuer,
  Graph-resource tokens, v1, app-only permissions or automatic tenant trust. See
  [Microsoft claims](https://learn.microsoft.com/en-us/entra/identity-platform/access-token-claims-reference)
  and [validation](https://learn.microsoft.com/en-us/entra/identity-platform/access-tokens).

Require a distinct API audience and client IDs, one audience, integer timestamps,
at most two-hour lifetime and synchronized clocks (no expiry leeway). This bounded
profile rejects long-lived/CAE tokens. Token types and claims never imply that MFA
or interactive consent was performed; those remain issuer/enrollment policy gates.

Fix discovery and JWKS URLs in configuration. Metadata must match both configured
issuer and key URL. Reject redirects, proxies, insecure/private-literal URLs,
compressed/oversized responses and token-selected URLs/keys. Bound token/JSON/key
sizes, reject duplicate JSON keys and unsupported critical headers. Accept RSA
2048–4096-bit public signing keys only. Cache keys for five minutes, serialize
refresh and limit refresh attempts to one per 30 seconds. No expired-cache fallback
after failure and no unbounded unknown-key cache. Private DNS/egress isolation
remains a hosted gate, not something URL syntax validation proves.

PyJWT's [algorithm policy](https://pyjwt.readthedocs.io/en/stable/api.html) requires
fixed allowed algorithms. Its [2026 advisory](https://github.com/jpadilla/pyjwt/security/advisories/GHSA-jq35-7prp-9v3f)
was fixed in 2.13.0; the selected version is later, and the application additionally
checks header/JWK algorithm consistency and passes an RSA public key to decode.

## Server-owned authority and migration 0013

`external_identities` binds `(issuer, subject, client_id)` uniquely to an existing
tenant membership, client kind and explicit API scopes. Only administrators may
insert/update/delete bindings; runtime has SELECT only. No signup, invitation or
mapping-mutation endpoint. No email-address matching, inferred membership or worker
scopes. Review remains human-only; all data paths still require owner membership.

Force RLS on identity rows using transaction-local **verified** issuer/subject/client
context, because tenant is unknown before mapping. Other tables retain tenant RLS.
No new SECURITY DEFINER function or runtime ownership. This defends against missing
query filters, not arbitrary SQL execution by a compromised application.

Keep binding identity immutable; administrator changes to active/scopes/kind advance
a monotonic revision. An invoker-rights trigger records administrator binding insert/update/delete
in existing append-only audit events using the database role, binding ID/revision
and active/scopes/kind, never token/subject contents; no human actor is invented.
Authenticated contexts carry binding ID/revision and expiry, never the token.
Every Store transaction rechecks that binding, its scope/
kind, expiry and current membership. Revocation fences new transactions, not an
already-running transaction. Token/identity revocation does not cancel existing
one-hour processing approvals: cancel those jobs or revoke owner membership using
their existing controls. This distinction must be visible in operations docs.

## API, operations and failure behavior

Invalid/unknown/disabled credentials yield a generic 401; current authorization
loss yields 403; bounded issuer/key or mapping-store unavailability yields scrubbed
503. Existing request IDs/status telemetry provides content-free outcomes; never log
tokens, subjects, metadata payloads or exception strings. No token persistence.

`serve --oidc-config` remains 127.0.0.1-only. Reject simultaneous bootstrap registry
configuration. Worker commands retain separate private exact-scope credentials.
This is a resource-server boundary, not authorization-code/PKCE login, cookies,
refresh tokens, MFA enforcement, team grants, MCP OAuth or issuer provisioning.

## Verification, upgrade and rollback

Test generated in-memory keys/fake issuer, malformed/confused tokens, rotation,
cache/outage bounds, concurrency and no credential disclosure. Exercise actual
API plus SQL mapping, foreign tenants, least privilege, identity changes, scope/
membership revocation and stale contexts. Upgrade a populated earlier schema and
include two-tenant identity mappings in the disposable restore drill.

Apply additive 0013 with administrator credentials and refresh runtime SELECT
grants before starting the new mode. Existing bootstrap workers keep working.
Stop JWT-mode API to roll back; preserve bindings and audit history, retain the
migration, and use forward repair or tested restore. Do not expose bootstrap mode
as a hosted emergency bypass. No destructive downgrade or mailbox compensation.
