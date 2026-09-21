# ADR-042: Server-side browser authorization sessions

Status: accepted implementation direction, 2026-09-21. Completion requires the
backend, operator entry point, owner UI and separate browser acceptance evidence.

## Decision

Add an explicitly configured confidential-client authorization-code flow with
S256 PKCE and one-use browser-bound state. Exchange the code only at a fixed HTTPS
token endpoint. Verify the resulting **API access token** using ADR-040, require
the configured browser client and an existing human owner mapping, then discard
the token. Never auto-enroll identities or accept callback-supplied tokens/tenants.

This is delegated API authorization, not an OpenID Connect ID-token login/profile
implementation. Request only configured API scopes; do not request `openid`,
profile, email or offline access. Reject unexpected ID/refresh tokens. No nonce
claim is consumed because no ID token is accepted. An eventual OIDC/MFA policy or
silent refresh requires its own explicit design and tests, not a renamed token.

The fixed issuer, client, endpoints and redirect are operator-owned. Entra uses
tenant-specific public-cloud authorization/token endpoints. Other supported issuers
use the configured issuer origin. An optional returned `iss` must match. Only one
issuer exists per process; no callback can choose a provider, endpoint or redirect.
Confidential-client secret-post is the initial fixed exchange method; private-file
loading/redaction is required. Certificate/federated client authentication remains
an operator deployment decision, not an invented existing integration.

## Session and request boundary

Opaque 256-bit cookies identify hashed server-side records. Cookies use `Secure`,
`HttpOnly`, `Path=/`, no Domain and the `__Host-` prefix. The pending-flow cookie is
SameSite=Lax for the top-level code callback; the authenticated cookie is Strict.
Never store tokens, claims or evidence in cookies or browser persistence.

Anonymous session discovery establishes a short-lived login-CSRF capability.
Login and logout require exact configured Origin plus a matching CSRF header.
Every cookie-authenticated unsafe method, including POST search, needs the same
checks. Duplicate cookies/authorization headers and mixed cookie/bearer credentials
fail closed. Existing standalone bearer mode is not weakened or silently selected.
Host is checked against the configured browser origin; callback URLs are never
built from forwarded headers. TLS termination/trusted ingress remains a release gate.

Pending flows expire after five minutes and are consumed before any exchange,
including a failed exchange. Sessions have at most one-hour absolute life and
15-minute idle life, additionally capped by access-token expiry. Current database
binding revision/scopes/kind/owner are checked for every authenticated request;
each Store transaction retains ADR-040's check. Logout removes the session, but
cannot cancel a request already admitted or existing durable processing consent.

Use bounded, locked process-memory storage initially: 128 pending flows and 1,024
sessions, no eviction of valid sessions to admit new ones. Restart signs everyone
out and loses pending callbacks. This is an explicit **single-process** deployment
contract, not distributed/HA session storage. Current data authority remains
PostgreSQL. No SQL table, grant, mail effect, model call or account is added.

## Delivery and verification

Implement the flow/session backend and REST boundary, then explicit private CLI
configuration and the owner UI; do not claim a usable browser workflow while the
latter are absent. Test fixed targets, PKCE/state binding, callback replay/races,
exchange limits/redaction, human/current mapping, idle/absolute/token expiry,
logout, capacity, duplicate/mixed credentials, Origin/CSRF and SQL revocation.
Use fictional issuers and generated keys only. Actual browser/TLS/cookie behavior
and authorized issuer acceptance require separate evidence.

No migration is needed. Rollback disables the browser mode and clears process
sessions; preserve mappings and audit. Log existing fixed route/status/duration
only, never code/state/cookies/secrets or exchange exceptions. Rate limiting,
admin enrollment, MFA, hosted availability and identity audit export remain gates.

Sources: [OAuth security BCP](https://www.rfc-editor.org/rfc/rfc9700.html),
[PKCE](https://www.rfc-editor.org/rfc/rfc7636.html),
[OWASP sessions](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html),
[Entra authorization-code flow](https://learn.microsoft.com/en-us/entra/identity-platform/v2-oauth2-auth-code-flow).
The finite limits and single-process policy above are application decisions.
