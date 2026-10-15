# ADR-215 — Authoritative predicate discovery and latest-revision retirement

Status: implemented for fictional local testing on an open PR; exact-head
hosted, independent restore and merged-main gates remain required.

## Context

ADR-214 introduced a versioned catalog, but its first SQL guard selected the
newest **active** row. If version 2 deprecated a name, version 1 would remain
active and could still accept a new fact. Code-only discovery could also
misstate what the database actually allows during an incomplete rollout.

## Decision

Migration 0074 replaces the insert guard so it selects the **latest revision
regardless of status**. A new fact is allowed only if that exact revision is
active and its value type/unit match. Older reviewed facts and exact
idempotent receipts are unchanged. Publication additionally compares the
checked-in code definition with the database's latest version, status and
shape after exact replay lookup and before insert. SQL remains the independent
last guard against direct writes or a mid-transaction catalog change.

`GET /v1/knowledge/fact-predicates` returns one bounded, name-sorted latest
revision per project-fact name from the database, including deprecated names.
It fails closed if the set or shape of active SQL revisions differs from the
running checked-in code catalog, rather than advertising a name that the
publication path would reject.
It requires `knowledge.search`; an assistant must also have its ordinary
source enrollment. The catalog contains no tenant or source content, but it
is still returned with `Cache-Control: no-store` and
`untrusted_content=true`. The response says it governs **new project-fact
writes only**, warns that historical unregistered rows may exist, and makes
no alias claim. A provider-neutral client validates every closed field,
shape, bound, order and duplicate before using it. A private fact-proposal
preview now combines code and latest SQL revision, reporting `active`,
`unknown`, `shape_mismatch`, `deprecated` or `version_mismatch`; none of these
statuses approves a proposed fact.

The code/SQL catalog remains reviewed-migration controlled. This route is
discovery, not an owner-editable registry, a source-freshness check, or
permission to aggregate financial values. It does not change FOS-Master.

## Acceptance and rollback

Fictional tests must prove a later deprecated SQL row blocks a direct new
insert even though an older active row exists; current human and enrolled
assistant API reads, missing-scope denial, no-store response, exact SQL
catalog authority, client rejection of forged/malformed envelopes, and
private proposal status. Run migration integrity, restore, full local and
hosted gates before merge. Rollback disables discovery and new catalog-based
publication without deleting reviewed facts or weakening the latest-revision
guard automatically.
