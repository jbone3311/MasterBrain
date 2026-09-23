# ADR-050 — Progressive Brain API read slice

Status: accepted for the additive prototype tranche on 2026-09-22.

## Decision

MasterBrain exposes a source-neutral read-only API under `/v1/brain` while retaining
the existing Email capability endpoints unchanged. The first slice provides compact
lexical search, evidence metadata, separately scoped bounded extracted content and a
cursor-bounded change feed.

Scopes are split into `brain.search`, `brain.evidence.read`, `brain.content.read` and
`brain.changes.read`. Source import and document publication scopes remain worker-only.
Responses carry opaque evidence/document/chunk identities, source kind/locator,
verified SHA-256, observation/index times, truncation state and an explicit
`untrusted_content` marker. They never return absolute paths, source bytes, provider
credentials, storage keys, arbitrary SQL or unbounded text.

The legacy `/v1/search` remains Email-only for compatibility. A future unified search
can compose Email and DataCore results after shared Email evidence migration; this
slice does not mislabel two independent indexes as unified.

## Verification and rollback

Contract tests cover authentication, scope separation, validation, response bounds
and absence of effect/SQL routes. PostgreSQL tests cover real RLS-backed search,
evidence/content expansion, change cursors and cross-tenant denial. Rollback removes
or disables only the additive `/v1/brain` routes; indexed evidence remains intact.
