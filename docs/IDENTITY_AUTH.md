# API identity foundation

Implemented under [ADR-040](adr/040_access_token_identity.md), 2026-09-21.
This is a loopback **access-token resource server**, not a complete sign-in system
or permission to expose the application publicly. Verification belongs in the
[exact-commit receipt](BUILD_RECEIPT.md).

ADR-042 subsequently adds an optional [delegated browser session backend](BROWSER_AUTH.md)
over this verifier. CLI/UI and actual browser acceptance remain next. It requests
API scopes only and does not convert ID tokens into API credentials.

## What it does

```text
Bearer access token
  -> fixed profile/issuer/audience/client and signature checks
  -> existing administrator-managed identity binding
  -> current tenant owner and application scopes
  -> recheck binding/revision/expiry at each database transaction
  -> existing authorized search/evidence/proposal/review routes
```

An authentic token does not create a user, choose a tenant or grant roles. The
mapping key is issuer + subject + client ID, not email address or message sender.
Signed `roles`, `tenant_id`, display names and custom permissions are not local
authority. A configured token scope admits the request; the database mapping
supplies the application scopes. A human mapping may review; an assistant mapping
cannot. No mapping can grant read/MIME/PDF worker scopes.

## Explicit profiles

| Profile | Accepted boundary | Deliberate exclusions |
|---|---|---|
| `rfc9068` | RS256, access-token type, required issuer/audience/subject/client/token ID/issuance/expiry and configured `scope` | ID tokens, unsigned/symmetric tokens, automatic issuer trust |
| `entra-v2` | Fixed public-cloud tenant issuer, version 2.0, API application UUID, allowed client `azp`, delegated `scp`, matching `tid`; signing-key issuer restriction honored when present | Common/organizations issuer, Graph tokens, v1, app-only roles, national clouds, CAE/long-lived tokens |

Both profiles require a distinct API audience and client IDs, one audience
(string or one-element array), integer time claims, at most two-hour lifetime and
no clock-skew leeway. Keep host/database clocks synchronized. Tokens are never
stored or forwarded to the mail provider. Profile conformance is fake-issuer tested,
not a claim that a real tenant/app registration has been accepted.

Sources: [RFC 9068 access tokens](https://www.rfc-editor.org/rfc/rfc9068.html),
[Microsoft claim semantics](https://learn.microsoft.com/en-us/entra/identity-platform/access-token-claims-reference).
Our finite limits and server-owned mappings are application policy, not universal
requirements on every identity provider.

## Configuration and startup

First apply additive [migration 0013](../migrations/0013_external_identities.sql)
with the migration administrator and refresh `grant-runtime` for the existing
non-owner/non-BYPASSRLS runtime role. Existing bootstrap workers keep their own
credentials; do not merge human and worker registries.

Prepare the configuration in an owner-only `0700` directory, file `0600`, outside
the checkout/Dropbox. Existing private-file checks reject symlinks, hard links,
FIFOs, oversized files and unsafe ownership/modes. Example **fictional** shape:

```json
{
  "version": 1,
  "profile": "rfc9068",
  "issuer": "https://issuer.example.invalid",
  "discovery_url": "https://issuer.example.invalid/.well-known/openid-configuration",
  "jwks_url": "https://issuer.example.invalid/keys",
  "audience": "email-brain-api",
  "client_ids": ["owner-client"],
  "admission_scope": "email.access"
}
```

For Entra, also set `entra_tenant_id` to the fixed tenant UUID, issuer to
`https://login.microsoftonline.com/<tenant-uuid>/v2.0`, discovery to that issuer plus
`/.well-known/openid-configuration`, and audience/client IDs to distinct registered
API/client application UUIDs. Pin the approved Microsoft JWKS URL in configuration;
discovery cannot change it. Real registration/consent remains separately authorized work.

With the private runtime DSN set and `EMAIL_BRAIN_CREDENTIALS_FILE` **unset**:

```sh
uv run email-brain serve --oidc-config /private/operator-directory/issuer.json
```

The command binds only `127.0.0.1`; proxy-header trust and access logs remain off.
Specifying both identity modes is an error. There is no bootstrap fallback and no
issuer contact at startup. The first structurally valid request may fetch fixed
metadata/keys; configuration loading is not a successful issuer handshake.
Current UI credential entry remains memory-only manual testing, not browser login.

## Administrator-managed bindings

`external_identities` requires an existing tenant membership. An administrator
inserts an explicit UUID, `tenant_id`, `actor_id`, `issuer`, `subject`, `client_id`,
allowlisted `scopes` and `client_kind` (`human` or `assistant`). There is no public
enrollment/mapping endpoint or automatic matching. The administrator must establish
the subject/client through a trusted enrollment process, not copy an unverified token.

Allowed application scopes are `email.search`, `email.evidence.read`,
`email.proposal.create`, `email.proposal.read` and human-only `email.review`.
Bindings remain owner-only: member/reviewer/operator memberships are not yet served.
One verified triple maps to one tenant; workspace selection and granular sharing
need a later explicit design, not request-supplied tenant IDs.

Runtime can only SELECT bindings. RLS requires the verified identity context even
when a tenant context already exists. Binding IDs, tenant/actor and external identity
are immutable. Administrator updates to active/scopes/kind increment a revision;
disable/re-enable cannot revive an old saved context. Insert/update/delete emits an
append-only audit event with database role and local binding state, no subject or
token. This identifies the DB administrator role, not an invented end-user actor.

## Revocation and outages

- Disable a known binding (`active=false`) or narrow its scopes through an approved
  administrator operation. New authentication and database transactions recheck it;
  a saved context cannot outlive its revision, membership or token expiry.
- A transaction already admitted is not retroactively cancelled. Existing one-hour
  document/MIME approvals are separate durable consent: cancel their jobs or revoke
  owner membership using existing controls. Token expiry alone does not cancel them.
- Keys cache for five minutes. Refresh attempts are globally serialized and limited
  to one per 30 seconds; unknown key IDs are not accumulated. Publish overlapping
  rotation keys with distinct IDs. Replacing a key with the same ID may require
  cache expiry. Removing a key is not instant revocation of a valid cached key.
- If refresh fails, an already cached known key is usable only until its original
  expiry; failed refresh never extends that expiry. Expired keys cannot be used as
  an outage fallback. Restart clears the cache, not database permissions.
- Invalid/unknown/disabled credentials return generic 401; current authorization
  failure returns 403; issuer/key or mapping-store unavailability returns scrubbed
  503. Existing request/status/duration logs contain no token/subject/body details.
  Rate limits, dedicated auth alerts and immutable audit export remain hosted gates.

Multiple Authorization headers are rejected before authentication. Missing credentials
receive a plain Bearer challenge; invalid presented credentials receive `invalid_token`.

Metadata and JWKS fetches use HTTPS with certificate validation, no redirects or
environment proxies, fixed destinations, bounded streaming/time and response sizes
(128/256 KiB). Reject compressed responses, duplicate JSON keys, private-literal
URLs, token-selected URLs/keys and unsupported JOSE controls. RSA public signing
keys are limited to 2048–4096 bits. Elapsed-time checks run on incoming chunks,
without waiting for a caller-sized buffer to fill. Connect/read timeouts and these
checks are not a hard process-level deadline across DNS/TLS; hosted resolver/egress,
request-concurrency and supervision controls remain required.
Token size is at most 16 KiB. URL checks do not
prove DNS/egress isolation; configure and test that in the hosted environment.

## Testing, restore and rollback

[Offline tests](../tests/test_oidc.py) generate keys in memory and use fictional
HTTP responses. [SQL/API tests](../tests/test_oidc_postgres.py) exercise mapping,
RLS, scope/kind, wrong tenant, current revocation, administrator audit and denied
runtime changes. [Restore](RESTORE_DRILL.md) includes two populated bindings,
search/isolation and revision/revocation after restore. It exercises the SQL mapping
boundary, not a real issuer handshake or production key recovery.

Stop JWT-mode API before rollback. Preserve migration/bindings/audit; use forward
repair or a tested restore. Never expose bootstrap mode as an emergency public
bypass. Review outstanding processing approvals after any restore. No mailbox
compensation is needed: this increment adds no provider effect.

Remaining production identity work: browser authorization-code/PKCE/session design,
MFA/issuer policy, enrollment/admin and revocation UX, worker service identities,
rate limiting/alerts, team grants and independent review. Remote MCP OAuth and
Grok/ChatGPT/Claude compatibility remain separate, unimplemented integrations.
