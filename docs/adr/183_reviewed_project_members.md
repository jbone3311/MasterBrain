# ADR-183 — Reviewed project members and roles

Status: Accepted for implementation (2026-10-14). Issue: [#176](https://github.com/jbone3311/MasterBrain/issues/176).

## Decision

Add an immutable `member` KnowledgeCore assertion linking one reviewed project
assertion and one reviewed person/organization entity assertion. A member records a
bounded role slug, `asserted`/`disputed`/`retracted` status, observed and optional
valid-time interval, confidence, source quote, one to twenty direct evidence IDs,
reviewer, and optional same-kind supersession. Existing reviewed publication,
idempotency, correction, search and change mechanics apply. A role describes a
source-backed claim; it never grants API, project or source permissions.

Initial role vocabulary is advisory (`broker`, `counsel`, `operator`, `investor`,
`lender`, `other`) with the existing bounded predicate syntax. Unknown syntactically
valid slugs remain possible until the separate compatible registry decision is
implemented. Claiming strict registry rejection now would contradict that gap.

The exact-project dossier adds an independently bounded `members` list. It returns
reviewed assertion IDs, linked entity ID/name/type, role, status, valid interval,
recording time and direct evidence IDs. It is ordered by recording time, including
disputes and retractions; it is not a current roster or permission list. The
existing retained/unsuperseded choice controls review-chain visibility, not
real-world truth. Generic search, exact get, grouped search and change feeds must
filter a member *before* limiting or exposing a cursor unless the caller can see
all direct evidence of the member and of both linked project and entity. A hidden
successor/correction must not suppress a visible predecessor.

## Boundaries and verification

Migration 0060 is forward-only, tenant-composite, forced-RLS, tenant-login-fenced,
immutable and protected from truncate. It extends the existing closed kind checks;
no historical assertions are rewritten. Publication remains human-reviewed only.
No inference, role registry, project-state reducer, live source access or source
effects are authorized. Fictional synthetic tests cover two roles, supersession,
dispute/retraction history, cross-tenant FKs, RLS, source-grant loss, bounded paging,
correction, direct SQL mutation denial, client shape and restore. The FileOS donor
and live Fastmail account remain untouched.
