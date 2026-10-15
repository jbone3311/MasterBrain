# ADR-197 — Fail-closed cited project dossier Markdown

Status: accepted for synthetic-only implementation. This is not a live-source,
hosted-assistant, inferred-fact, source-effect or FOS-Master cutover approval.

## Context

The exact-project JSON dossier already returns independently bounded reviewed
events, commitments, members, artifact links and source-stated project facts.
ADR-196 renders only the fact fragment. Older reviewed assertion tables store
quotes and direct evidence links, but their historical publication path did
not prove the quote appears in that evidence. Merely formatting those rows as
Markdown would fabricate citation confidence.

## Decision

1. Add a separate `GET /v1/knowledge/projects/{project_id}/dossier/markdown`
   read requiring both `knowledge.search` and `brain.content.read`. Source-
   enrolled assistants use the same tenant/source filters as human readers.
   Unknown or hidden projects return the same not-found result.
2. In one tenant-fenced transaction, take one recorded-time cutoff and select
   the exact project plus its source-visible reviewed events, commitments,
   project members, related artifact occurrences and source-stated facts.
   Apply the established transitive project/entity grant and visible-
   successor rules. Before output, require **every** direct evidence link for
   each displayed assertion to be current, active, granted and nonexcluded.
   At least one of that assertion's own current normalized documents must
   contain its stored full quote exactly; choose the lowest matching evidence
   ID as the deterministic citation. A member's displayed entity name also
   requires a separately verified entity quote and citation. Artifact links
   retain distinct artifact and quoted-basis evidence IDs; project facts use
   ADR-195's frozen basis and quote ID.
3. A request may include at most 25 visible rows in each section. If any
   section has more, or any selected row lacks a current exact citation,
   return a generic conflict with **no Markdown body**; never silently omit
   an unsupported reviewed assertion or describe the result as complete.
   A full response is complete only for the currently authorized reviewed
   rows at its cutoff, not for hidden sources, unreviewed proposals, source
   freshness, real-world truth or late commits before the cutoff.
4. Render fixed section headings and one escaped Markdown line per assertion.
   Every factual line carries its exact evidence ID and a short JSON-escaped
   quote prefix. Older project/event/commitment/member assertions are labelled
   `reviewed; derivation unspecified`, not `source_stated` or `inferred`.
   Facts retain their explicit source-stated label. Untrusted text cannot
   introduce HTML, links, headings or another citation. Cap the UTF-8 Markdown
   at 64 KiB and fail closed rather than truncate the dossier silently.
5. Return closed JSON metadata with section counts, cutoff, visibility,
   explicit coverage and `untrusted_content=true`. The provider-neutral
   client validates the response bound and shape. Audit only a fixed operation
   code, with no project ID, quote, value, source path or Markdown text.
   Do not persist an export artifact or authorize source changes.

## Acceptance and rollback

Use fictional Email and FileOS evidence only. Prove a whole small dossier
with exact citations across every section; refusal for invented, stale,
excluded, ungranted or missing quotes; hidden-source and successor behavior;
cross-tenant and assistant-source denial; independently oversized sections;
hostile Markdown text; deterministic output at a fixed cutoff; client/API
scope and malformed-response denial; fixed audit; and full local/hosted gates.
Rollback removes only this read route/client operation. Reviewed assertions,
immutable evidence and the ADR-196 fact fragment remain.
