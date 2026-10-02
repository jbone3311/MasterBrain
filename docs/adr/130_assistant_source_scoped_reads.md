# ADR-130 — Source-scoped assistant reads before answer assembly

Status: accepted for synthetic/disposable implementation; hosted revocation is not accepted.

## Context

The provider-neutral Brain client uses only `current-search`, evidence metadata
and bounded evidence content. Today those routes enforce tenant and operation
scopes, but an assistant with those scopes can see every indexed source in its
tenant. `TenantContext` carries no source grant. This is insufficient for an
owner who wants one assistant to see selected mailboxes or file roots, and it
must be fixed before a shared answer context or hosted assistant is certified.

## Decision

- Extend the **synthetic bootstrap credential** with an explicit, bounded set
  of source IDs for assistants holding Brain or Knowledge read scopes. Human and
  worker bootstrap identities retain their current tenant-wide behavior.
  Missing/empty assistant source enrollment fails closed; a source ID in a
  prompt or API request cannot add to it. This static credential is not a
  hosted grant or immediate-revocation mechanism. A source-scoped assistant
  credential cannot also hold legacy Email scopes, whose separate routes do
  not yet apply this source filter.
- Carry that allowlist in the trusted request context. Filter each current
  Email, FileOS and archive search in SQL **before** ranking and limiting.
  Filter reviewed KnowledgeCore hits before limiting, and exclude any assertion
  whose linked evidence includes a source outside the grant. An assertion with
  no linked evidence is not returned to a source-scoped assistant.
- Apply the same source check to evidence metadata and extracted-content reads.
  The three routes used by the reference client may be enabled for an enrolled
  assistant; other Brain/Knowledge routes remain denied to that client until
  their source-aware semantics are reviewed. Denial must not reveal whether
  an inaccessible evidence ID exists. A human owner continues to use the same
  routes without a new source restriction.
- Preserve independent-layer ranking, current-source fences, partial-coverage
  labeling and existing operation scopes. Do not interpret a grant as source
  ingestion, original-byte access or permission for source effects. Do not
  change FOS-Master.

## Acceptance and remaining work

Use two nonempty Email/FileOS sources in one synthetic tenant plus another
tenant. Show that a source-scoped assistant gets only allowed hits even when
the forbidden source ranks first, cannot expand forbidden evidence/content or
call an unreviewed alternate route, and cannot derive mixed-source knowledge.
Human behavior and the existing known-answer corpus remain unchanged. Test
invalid/missing grants, explicit empty grants, oversized grants, scope bypass,
and no source names in denials. Run full PostgreSQL, browser, deployment,
strict-runtime, restore and donor-parity gates.

This tranche does **not** solve hosted authorization. The OIDC binding currently
offers only narrow Email scopes and no Brain source grant. A later migration
must provide administrator-owned, dynamically revocable source enrollments and
rechecks across every read, cache, coverage route and worker path. Until then,
no named-assistant or hosted multi-source acceptance is claimed. Rollback
removes the synthetic allowlist and filters; retained evidence is unchanged.
