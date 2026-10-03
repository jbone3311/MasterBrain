# ADR-149 — Keep legacy Email API routes outside assistant access

Status: accepted for synthetic/disposable authorization hardening. This does
not certify a hosted issuer, named assistant or derived-cache revocation.

## Context

Enrolled assistants have source-filtered Brain and Knowledge reads. The older
Email compatibility routes use `email.*` operation scopes but do not apply the
new source enrollment before search limits, status, evidence expansion or
other reads. A bootstrap Email-only assistant credential, or an older OIDC
assistant binding with Email scopes, can therefore reach a route without the
Brain API's source boundary. For the final product, assistants use the Brain
API; the legacy Email API is a human/operator compatibility surface, not a
second LLM entrance.

## Decision

- Refuse every `email.*` API dependency for an assistant principal before any
  route body or database read. Human and worker behavior is unchanged. The
  Brain/Knowledge routes retain their existing source-grant checks.
- Refuse new bootstrap assistant credentials carrying any `email.*` scope.
  Keep the specific human-review and worker-processing validation ahead of
  this broader refusal so those existing error contracts remain clear.
- Refuse OIDC assistant contexts carrying `email.*` scopes at each Store
  transaction, including a saved context created before this change. The
  existing authentication flow returns an invalid credential rather than
  resolving such a binding into an API principal. No historical identity row
  is rewritten and no new database privilege is granted.
- Administrators who want an assistant to read Email must enroll that
  assistant for explicit sources and Brain read scopes. Do not grant it a
  legacy Email scope as a shortcut. A stored legacy assistant binding may
  remain administratively visible but is unusable until reviewed migration.

## Acceptance and rollback

Test bootstrap refusal, a forged assistant principal's denial at legacy
search/evidence routes before Store calls, a real OIDC Email-only assistant's
authentication and saved-transaction denial, and unaffected human, worker and
source-scoped Brain assistant behavior. Use fictional data and disposable
PostgreSQL; run exact-head and merged-main CI, strict runtime and restore.
Rollback must not reopen unfenced assistant Email routes: first implement and
verify equivalent source filtering on every compatibility read, or revoke the
affected assistant bindings. Issue #88 stays open for hosted enrollment,
named-assistant conformance and cache/revocation acceptance.
