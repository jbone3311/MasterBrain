# Browser authorization session backend

Implemented backend under [ADR-042](adr/042_browser_authorization_sessions.md).
**Not yet an owner-ready browser sign-in feature:** owner UI integration and actual
browser acceptance remain next. [ADR-043](adr/043_browser_operator_tls.md) wires
explicit `serve --browser-config` with private TLS files; unflagged `serve`
remains bootstrap mode. No implicit upgrade or fallback occurs.

## Flow and trust

1. `GET /auth/session` creates a bounded anonymous flow cookie and returns a CSRF
   value, or reports a valid existing session. Never cache this response.
2. `POST /auth/login` requires that flow cookie, exact configured `Origin` and
   `X-CSRF-Token`. It returns the fixed authorization endpoint URL with one-use
   state, S256 PKCE, client, API scopes and exact callback URI.
3. The browser navigates to that URL. The identity provider returns an authorization
   code to `GET /auth/callback`; this is not a token supplied by the browser.
4. The backend claims the flow once, exchanges the code at the fixed HTTPS token
   endpoint, verifies the API token with ADR-040 and resolves an existing human
   owner mapping. Unknown/assistant identities cannot create browser sessions.
5. Successful callback sets a new opaque session cookie, clears the flow cookie and
   redirects only to `/`. The API token is discarded, not stored in the session.
6. Subsequent cookie requests recheck current SQL authority. Unsafe methods need
   Origin and CSRF, including POST search. `POST /auth/logout` removes the session
   and cancels its supplied pending flow; admitted requests/processing grants are
   not retroactively cancelled.

This is confidential-client **delegated API authorization**, not ID-token/OIDC
profile login. No `openid`, profile, email or offline scope is requested; unexpected
ID/refresh tokens are rejected. MFA/identity-provider policy is not inferred from
an access token. Those policies still require explicit issuer acceptance.

## Configuration and construction

`BrowserConfig` is closed, immutable configuration loaded through existing
owner-only private-file checks. Fields are `version: 1`, `identity` (the complete
[ADR-040 configuration](IDENTITY_AUTH.md)), `public_origin`,
`authorization_endpoint`, `token_endpoint`, `client_id`, `client_secret`, `scopes`.
The secret uses a redacted value type; never print configuration validation details
or put the file in Git/Dropbox. CLI failures suppress configuration and secret details.

Browser origin is exact HTTPS without a path/query/fragment, userinfo or explicit
default port. Explicit HTTPS loopback origins with a non-default port are supported
for local operator setup. Issuer endpoints remain public HTTPS on the
configured issuer origin; Entra endpoints are fixed to its configured tenant.
Callback is always `<public_origin>/auth/callback`, not derived from request or
forwarded headers. The browser client must be accepted by the API verifier.

Developer construction (not an operator launch command):

```python
config = BrowserConfig.from_file(private_config_path)
auth = OIDCAuthenticator(store, AccessTokenVerifier(config.identity))
browser = BrowserAuth(config, auth)
app = create_app(store, auth, browser_auth=browser)
```

## Private operator startup

Provide the configuration above and a certificate/key in an owner-only directory
outside Git/Dropbox. All three files must be regular, owner-only files, not symbolic
or hard links. Set `EMAIL_BRAIN_DSN` to the restricted runtime-role database connection;
unset `EMAIL_BRAIN_CREDENTIALS_FILE`. Never paste a DSN or secret into a command log.

```bash
email-brain serve --browser-config /private/emailbrain/browser.json \
  --tls-cert /private/emailbrain/certificate.pem \
  --tls-key /private/emailbrain/private-key.pem --port 8765 --check
```

These paths are placeholders, not supplied files. The exact configured origin can
be `https://localhost:8765`; the certificate must contain that exact host in its
SAN and its key must match. For an IP origin, require the corresponding IP SAN.
Wildcards and legacy Common Name alone are not accepted. Validity dates, RSA
2048–4096/e65537 or P-256/P-384 key strength, server EKU when present, and OpenSSL
certificate/key loading are checked. Encrypted private keys are rejected without
prompting. TLS uses a server context with minimum TLS 1.2 and modern ECDHE ciphers.
This preflight does **not** certify browser trust, issuer policy or chain revocation.

`--check` outputs only mode/status and explicit `database_checked: false` and
`network_contact: false`; it starts no server, performs no SQL or issuer request
and does not enroll a user. The DSN environment variable is required but not tested.
Remove `--check` to start the single API process on **127.0.0.1 only**. Proxy-header
trust and access logs remain disabled. Do not add forwarding/public ingress or
extra workers to this command. Configure browser trust separately for synthetic
acceptance; never bypass certificate validation to obtain a passing result.

`--browser-config` conflicts with `--oidc-config` and any nonempty bootstrap
registry environment value. Both TLS paths are mandatory. TLS flags and `--check`
outside browser mode fail rather than being ignored. Certificate renewal requires
a controlled restart; the server reloads those operator-controlled files at startup.
Restart invalidates all in-memory sessions. Stop the process to roll back; preserve
SQL mappings and never expose bootstrap credentials as a public recovery mode.

The application refuses mismatched authenticator/Store objects. No registration,
tenant creation, SQL grant or migration is introduced. Confidential client
authentication currently uses secret-post, with no redirects/environment proxies
and a bounded response reader. Certificate/federated client authentication is not
implemented. Token audience/client/signature authority remains ADR-040's job.

## Cookies, limits and lifecycle

- Both cookies are Secure, HttpOnly, host-only, Path=/ and `__Host-` prefixed.
  Pending flow uses SameSite=Lax for the callback; session uses Strict.
- Cookie values are random 256-bit handles; only their hashes index server records.
  Session records contain the verified principal and CSRF value, not raw tokens.
- Up to 128 pending flows, five-minute expiry. Claim once before exchange; failed
  exchange requires starting again. Replaced/cancelled reservations cannot publish
  a late session. Refreshing anonymous discovery replaces a started flow.
- Up to 1,024 sessions. Fifteen-minute idle life and at most one-hour total life,
  also capped by API/response expiry. Wall and monotonic deadlines prevent idle
  renewal or a backward wall-clock adjustment from extending total lifetime.
- Process memory is locked and bounded. Restart signs everyone out. **One API
  process only** until a distributed-session contract exists; do not add workers
  or sticky sessions and claim HA. These ephemeral sessions are not restored from DB.
- Changes to binding revision/scopes/kind, membership or expiry deny the saved
  session. An outage returns 503 without extending idle expiry; it does not become
  bootstrap fallback. Reauthentication rotates the session and revokes its predecessor.
- Signing-key removal alone does not revalidate an already-created session.
  For emergency session revocation, disable the mapped identity or stop/restart
  the single process; do not assume the verifier's five-minute key cache is the
  session lifetime. Session expiry and database authority remain independent checks.

Duplicate/mixed credentials, wrong Host/Origin, absent or invalid CSRF, malformed
callbacks and foreign identity fail closed. Authentication denials are generic
401 `browser_session_denied`; request-boundary denials are generic 403;
infrastructure/capacity failure is 503 `authentication_unavailable`.
Cookie attributes in HTTP tests are not proof of a real browser enforcing them.
Fetch metadata denies cross-site/same-site requests outside the bound callback;
cross-site discovery cannot clear or replace session cookies. Missing metadata
does not bypass Origin/CSRF; browser compatibility still needs real-browser proof.

## Verification and operations

[Offline flow tests](../tests/test_browser_auth.py) use generated RSA keys and
fictional issuer responses. [Real SQL tests](../tests/test_browser_postgres.py)
exercise both profiles, search/evidence isolation, current revocation/revision,
expiry, logout and unknown-subject refusal. Exact results belong in the
[build receipt](BUILD_RECEIPT.md). The key reader additionally checks elapsed time
after EOF and byte caps before accumulation; token exchange uses the same bounds.
[Operator tests](../tests/test_browser_operator.py) cover private configuration,
certificate/key preflight and real TLS 1.2/1.3 handshakes over in-memory buffers.
They do not install browser trust or test a public listener.

Only fixed route/status/duration are logged, never callback query strings, tokens,
cookies, secrets or provider diagnostics. Capacity exhaustion denies new flows
without evicting valid sessions; rate limits and dedicated auth alerts remain
necessary before public ingress. Stopping the process clears sessions/flows;
disable injection to roll back, preserving SQL identity mappings and audit.

Remaining: owner UI/no-token-persistence wiring,
browser/accessibility acceptance, real registration and MFA policy, enrollment,
service identities, hosted session availability/rate limits/audit export. No real
issuer, email account, cloud service or public listener was enabled.
