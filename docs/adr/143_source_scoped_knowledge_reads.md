# ADR-143 — Source-scoped KnowledgeCore reads for enrolled assistants

Status: accepted for synthetic implementation, 2026-10-02.

## Context

KnowledgeCore search already excludes an assertion whose directly linked
evidence includes an ungranted source, but direct Knowledge routes deny all
assistants. Assertion expansion and the Knowledge change feed have no such
source filter. Unified Brain search composes the already filtered DataCore and
Knowledge search paths but is likewise denied. OIDC binding constraints do not
yet admit `knowledge.read` or `knowledge.changes.read`. Opening only the API
dependency would leak cross-source assertions or yield unusable credentials.

## Decision

- An assertion is readable by an enrolled assistant only when it has at least
  one direct evidence link and **every** directly linked evidence version belongs
  to a source in that assistant's current grant set. A mixed-source assertion
  is hidden in full, not partially redacted. This is the same policy already
  used by Knowledge search and current grouped search. Opaque references to
  other assertions are not recursively expanded or interpreted as grants.
- Apply that predicate inside PostgreSQL to assertion expansion and to both
  anchor validation and page selection in the Knowledge change feed, before
  ordering and `LIMIT`. A hidden or unknown assertion/cursor returns not found.
- Admit enrolled assistants on direct Knowledge search, assertion expansion,
  Knowledge changes and unified Brain search. Unified search keeps its
  independent evidence/knowledge limits and visibility mode; retained DataCore
  search is source-filtered under ADR-142.
- Forward migration 0051 adds the two Knowledge read scopes to administrator-
  bound OIDC identities and to every assistant/source-grant eligibility fence.
  The legacy exact-key resolver continues to refuse Brain/Knowledge assistants
  because old binaries cannot represent source grants. Application token
  resolution and transaction-time revision/source validation use the same
  scope set. Grant removal invalidates saved contexts before another read.

Human owner reads and reviewed publication are unchanged. This grants no
source effect, original-byte access, model tool, inferred authority from source
text or FOS-Master cutover. The policy labels assertions by their **direct
evidence**; it is not a semantic guarantee that a human-written assertion
contains no information learned elsewhere. Hosted trust requires enrollment,
review and acceptance beyond this synthetic read-path test.

## Verification and rollback

Use fictional same-tenant FileOS and Email evidence plus a separate tenant;
publish file-only, email-only and mixed-source assertions. Test search,
expansion, unified search, hidden/unknown change cursors, `LIMIT 1` starvation,
transaction-time OIDC grant revocation and the old-resolver refusal. Exercise
new and populated-database migrations, full suite, restore, strict-runtime and
container gates. Roll back application exposure if necessary; migration 0051 is
additive/forward-only and retains historical knowledge and grant records.
Issue #88 stays open for legacy Email routes, hosted issuer acceptance and
derived-cache revocation.
