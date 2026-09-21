# ADR-043: Explicit loopback TLS operator entry point

Status: accepted implementation direction, 2026-09-21.

Wire ADR-042 through `serve --browser-config`, mutually exclusive with API-only
OIDC and bootstrap registry mode. Require explicit owner-only TLS certificate/key
files and an HTTPS configured origin whose port matches the listener. Preserve
loopback binding, disabled proxy-header trust and disabled access logging. No
automatic issuer contact, certificate creation/trust installation or public ingress.

Preflight verifies current leaf validity, exact configured-host SAN, key strength
and certificate/key pairing. Initial policy accepts RSA 2048–4096/e65537 or P-256/
P-384 keys, rejects encrypted private keys (no interactive password prompt), and
uses a TLS-server context with TLS 1.2 minimum plus modern ECDHE ciphers. It does
not establish browser trust, chain revocation or hosted TLS acceptance.

`serve --check` is browser-only and checks private configuration/TLS without
database/issuer requests or starting a listener. Its content-free result must not
claim database readiness or working sign-in. No fallback after validation failure.
TLS flags are rejected outside browser mode rather than silently ignored.

Keep the operator command and owner UI separate deliveries. The next UI needs
explicit mode discovery, cookie/CSRF requests and stale-evidence fences across
expiry/logout/account changes; actual browser/TLS tests must prove those behaviors.
No SQL migration/grant, new dependency, mail effect or worker authority is introduced.

Tests use generated certificates and fake issuer configuration. Assert private
files, expiry/host/key mismatch, modes/ports, scrubbed failures and non-consuming
preflight. Rollback stops the loopback process (invalidating ephemeral sessions);
preserve identity mappings and never expose bootstrap as a public recovery mode.
TLS files are operator-controlled and loaded again by the server at startup;
replacement/renewal requires a controlled restart. Runtime source is the pinned
installed Uvicorn SSL-context implementation, not a claim of managed edge security.
