# ADR-205 — Stage cited project-member rows as private proposals

Status: accepted for synthetic/disposable implementation only. No live source,
inferred role, automatic approval, permission grant, or FOS-Master cutover.

## Context

ADR-197's current Markdown dossier includes separately cited person/organization
identity and reviewed role assertions. ADR-202 stages selected project, event
and commitment rows into the ADR-186 private proposal queue, but refuses
member rows. The queue already understands the typed `MemberWrite` assertion;
the missing boundary is proving that the Markdown's displayed entity and both
citations still refer to one current, authorized local entity and a proposed
role over an existing local project. A role is knowledge, never access control.

## Decision

- Admit a selected `member` row through the existing human-only Markdown
  staging route. Require an explicitly supplied typed `MemberWrite` sidecar:
  complete direct evidence IDs, full role quote, observed time, confidence and
  matching local project/entity IDs. Reject supersession and valid-time fields
  absent from the exporter. The claimed member ID is only an import marker;
  approval creates a new local ID. The project and person/organization entity
  must already exist locally; a same-batch proposal cannot satisfy them.
- Reconstruct the selected export line using the local entity's immutable
  name/type/full source quote and its deterministic current citation. Compare
  the whole line, including both citation IDs and displayed role fields,
  exactly. A Markdown quote preview is never expanded into a full quote.
- In the same transaction as staging, and again on batch preview/review,
  verify the member's entire direct evidence set, its full quote in the
  specifically cited member evidence, and current/granted/nonexcluded full
  citation bases for the linked project and entity. Source revocation,
  exclusion, stale versions or an altered entity citation fail closed; one bad
  selected row rolls back the whole batch. Keep the ADR-202 import-context
  digest and per-row human decision contract unchanged.
- Facts and artifact links remain unsupported selected rows. Do not change
  the generic `KnowledgeAssertion` meaning, issue a source effect or treat a
  reviewed role as a permission assignment.

## Verification and rollback

Use only fictional Email/FileOS evidence and disposable PostgreSQL. Prove
private stage, idempotent replay, explicit approve/reject, exact line and two-
citation binding, missing/cross-tenant/hidden/stale entity or project denial,
revocation between inspection and stage, all-or-nothing rollback, and no
search/dossier exposure before review. Run full local and hosted CI, strict
runtime, restore, docs and browser gates. Rollback disables member selection
while preserving immutable proposal and decision history; FOS-Master remains
unchanged.
