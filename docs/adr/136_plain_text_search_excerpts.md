# ADR-136 — Plain-text search excerpts

Status: accepted for synthetic read paths. No source or permission change.

## Problem

PostgreSQL `ts_headline` inserts `<b>` and `</b>` around matched terms by
default. The first-party trial and `/brain` correctly render API excerpts with
`textContent` so untrusted source text cannot execute as HTML, but that makes
those formatting markers visible to a person. A live fictional browser trial
showed the raw markers in Email and FileOS cards. External clients receive the
same distracting strings.

## Decision

Ask `ts_headline` for empty start/stop selectors on DataCore and KnowledgeCore
read excerpts. Keep lexical matching, rank, limits, ordering, scopes, current
source checks and evidence drill-down unchanged. Excerpts remain untrusted,
bounded plain text and UI code must continue to use text nodes, never `innerHTML`.
The original evidence/content route, not a search excerpt, is the authority for
exact source text. No rich highlighting or model interpretation is introduced.

The fictional trial's evidence panel also verifies that metadata and bounded
content name the selected evidence ID, then shows the source text directly.
Provenance remains expandable. A mismatch fails closed with a generic message;
no raw response object is displayed as if it were source text.

## Verification and rollback

On the fictional cross-source PostgreSQL corpus, assert Email and FileOS
excerpts contain the query but no generated highlight tags, then exercise the
actual browser search and evidence controls. Test mismatched evidence responses
are refused and source-like HTML text stays inert in the browser. Run repository
checks and exact-head/merged-main CI and
restore. Rollback may restore the old read query, but must not replace text-node
rendering with HTML interpretation. No migration or FOS-Master change is needed.
