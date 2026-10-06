# ADR-163 — Owner workspace project drill-down

Status: merged through PR #156; exact-head gates passed. Merged-main restore
passed, while full CI and the final strict gate were blocked before execution
by hosted-runner acquisition ([issue #158](https://github.com/jbone3311/MasterBrain/issues/158)).
No hosted or live-source acceptance is implied.

## Context

ADR-162 merged a bounded, source-aware KnowledgeCore project dossier and a
provider-neutral client method. The first-party `/brain` workspace still shows
reviewed project matches only as titles, excerpts and evidence buttons. The
owner cannot open a project's related reviewed events and commitments there,
even though an authorized external client can use the same Brain API route.

## Decision

- Add an explicit **Open reviewed project** control only to a validated
  project-identity match under the All-sources reviewed-knowledge layer of
  Search only or Ask. Do not fetch the dossier automatically or infer a
  project from free text. Call the existing read-only
  `GET /v1/knowledge/projects/{id}/dossier` route with fixed independent
  five-item event and commitment limits; never add a privileged UI endpoint.
- Validate the bounded response before rendering any of it: exact requested
  project identity, reviewed coverage labels, limit/truncation fields,
  linked project IDs, allowed states and types, aware timestamps and direct
  evidence identities. Render all returned titles, previews, IDs and errors
  as inert text. Label the exact project state as a reviewed assertion, not
  live truth; label independent list truncation and unknown source freshness.
  Each displayed assertion may expose its existing, separately authorized
  evidence drill-down control.
- Reuse the current in-memory bearer credential and no-store/no-cookie request
  boundary. An explicit token edit, source-focus change, session clear or
  cleared conversation invalidates and aborts an in-flight dossier fetch;
  a stale response cannot restore old content. Scope denial, hidden project,
  invalid response and transport errors display generic messages without
  leaking source text or credentials. No effect or proposal route is called.

## Verification and rollback

Browser tests must cover no automatic request, exact route and fixed bounds,
valid compact rendering with evidence buttons, hostile text inertness,
malformed/mismatched data refusal, source denial, stale response clearing,
focus change and read-only network methods. Existing API/PostgreSQL dossier
tests remain the server authority; this UI does not replace them. Run full
Python and browser gates, documentation validation, strict runtime and restore
on the exact branch before merge. Rollback removes only the UI control and
renderer; the ADR-162 API and immutable knowledge stay intact. This grants no
model-written answer, project-state reducer, hosted assistant or FileOS action.
