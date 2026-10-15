# ADR-201 — Current-evidence inspection of imported dossier Markdown

Status: accepted for synthetic-only, read-only implementation. No source
enrollment, Knowledge publication, proposal staging, or FileOS cutover follows
from this decision.

## Context

ADR-200 inventories the owner-selected ADR-197 Markdown format without trusting
its claimed IDs or citations. A file copied or edited outside MasterBrain may
retain plausible-looking evidence IDs after their source is revoked, excluded,
or superseded. A proposal-producing importer must not assume that a syntactically
valid Markdown citation is an authorized, current source span.

## Decision

1. Add a human-only `POST /v1/knowledge/dossier-markdown/inspect` operation
   requiring `knowledge.review` and `brain.content.read`. Its closed request
   accepts only a bounded Markdown string. It has no filesystem path, URL,
   provider or model parameter.
2. Extend the pure ADR-200 reader to recover each exported quote preview from
   the fixed Markdown grammar. Decode JSON/Markdown/HTML escapes only after
   checking canonical re-rendering. Reject missing, malformed or extra quote
   labels; never interpret JSON-string text as structural labels. Associate
   each preview with the adjacent claimed citation ID, including the separate
   entity and role citations on a member line.
3. In one tenant-fenced transaction, require **every** cited evidence ID to
   exist in the current version of an active, granted, nonexcluded source and
   require its own normalized document to contain that exact preview. A
   mismatch returns one generic refusal, with no partial inventory or
   per-citation existence oracle. Audit a fixed operation code without IDs,
   Markdown, quotes or paths. Return the bounded inventory only when all
   checks pass, with `citation_spans_checked=true`, `proposal_ready=false`,
   `staged=false`, and explicit `source_freshness=not_asserted`.
4. This verifies only that a **preview substring** is present in current
   authorized evidence at inspection time. It does not recover the full stored
   quote, observation time, complete assertion payload or original reviewer;
   does not certify real-world truth; and does not authorize a write. The later
   proposal-stage ADR must recheck full assertion bases inside its write
   transaction and require explicit missing metadata and human decisions.

## Verification and rollback

Use fictional Email/FileOS evidence and disposable PostgreSQL only. Test the
real ADR-197 exporter-to-inspector path, escaped hostile quote text, member
dual citations, stale/current/excluded/source-grant/cross-tenant denial,
assistant and scope denial, malformed/oversized Markdown, no partial response,
fixed audit and no proposal/reviewed writes. Run local and hosted full gates.
Rollback removes the inspection route/library only; existing export, proposal
and reviewed data remain unchanged.
