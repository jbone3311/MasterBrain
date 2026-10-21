# ADR-263 — Current working file visibility across Email and FOS Brain

Status: **proposed for a synthetic-only read tranche**. No API, UI, database
or search semantics are changed by this document. Donor review:
[October FOS delta](../FOS_DONOR_DELTA_2026_10.md).

## Context

The existing MasterBrain `/v1/brain/current-search` groups active FileOS,
current Email messages/attachments/documents, extracted members of archive
files and reviewed KnowledgeCore matches. The first-party workspace offers
All/Email/Files focus and separately authorized evidence drill-down. It does
not distinguish a working FileOS document from one moved under FOS-Master's
`<domain>/_Archive/` superseded-location convention. Its `archive_*` result
groups mean **content inside an archive file**, not superseded FOS versions.
An Email provider's Archive mailbox is a mailbox, not that FOS file state.

FOS-Master at `eb774fc` excludes `_Archive` file locations before result
limiting by default and offers explicit inclusion. It also retains an audited
archive move command. MasterBrain must preserve the useful read experience
without importing a file-effect command into a read-only API, hiding generic
FileOS folders by accident, or claiming complete indexing from a registration.

## Proposed contract

Keep one query box and one Brain API for optional EmailBrain and FOS Brain.
Default Search and Ask show **current Email plus current working FileOS
evidence**, with reviewed knowledge kept separately labelled. An explicit
`working_and_superseded` FileOS visibility choice reveals authorized
superseded-location evidence; it does not change Email mailbox visibility,
grant access to a source, perform an archive move, or turn retained history
into current evidence. The control is visible only when a searched FileOS
source declares a versioned FOS archive policy. For a generic or unclassified
FileOS source, retain current behavior and report `visibility_policy_unknown`
instead of silently excluding a folder by name.

Bind the FOS archive convention to the **source's reviewed root and policy
version**, not an unqualified SQL substring. Classify the exact `_Archive`
directory segment beneath that source's FOS domain root; near-misses such as
`_Archived`, `Archive`, or `_Archive.md` remain working paths. Filter at the
database query before ranking and `LIMIT`, under the same tenant/source grant
as the result. Apply the parent file's policy consistently to its derived
document, compressed-archive member, document and OCR hits. Preserve immutable
original evidence and historical access through existing separately scoped
routes. A move changes observed source location only after a fresh, complete
source run; no path spelling alone proves that one file is a prior version of
another.

Expose a compact coverage envelope per source kind: `not_registered`,
`not_available`, `registered_no_current_index`, `indexed_current`,
`stale_or_incomplete`, or `not_searched`, without enumerating ungranted sources.
Show the index observation time, selected file-visibility policy and whether
limits truncated results. A zero-hit search must not read as "nothing exists"
when indexing is absent, stale or incomplete. The first-party view should
provide All/Email/Files focus, an opt-in superseded-file switch, source-kind
and current/superseded labels, path or mail provenance, date/freshness, a
bounded excerpt, and an explicit Open evidence control. Technical layers
may remain grouped initially; do not blend incomparable FTS scores into a
single global rank before a held-out cross-source evaluation.

No model is needed to search. Ask may select and quote only evidence eligible
under the same visibility, grant and currentness policy as Search. A model
cannot use a quoted path or prompt text to widen the visibility choice or
authorize a source effect. File rename/move/archive remains a separately
designed proposal, human approval and confined executor with undo evidence.

## Implementation sequence and acceptance

1. Freeze a fictional cross-source corpus and exact new donor search hashes:
   current and archived FileOS paths, near-misses, nested archive-file
   derivatives, Email in an Archive mailbox, same bytes in Email and FileOS,
   stale/no-generation sources, source grants and result-limit crowding.
   Compare the donor's FTS and body-text behavior without copying its JSON
   fallback inconsistency or post-limit extension filter.
2. Add a pure, versioned source-relative visibility classifier plus a
   source-policy binding and coverage status. Keep existing queries unchanged
   until classification is exercised on the entire synthetic corpus.
3. Apply the policy before rank/limit to **all** current FileOS-derived search
   layers; add a closed visibility request and response coverage contract to
   Search and Ask. Prove no Email change, no ungranted leakage, no retained
   history bypass, no false `complete` claim and unchanged default for
   unclassified generic file sources.
4. Add the first-party switch and clear stale/in-flight responses on changes;
   show readiness, truncation and evidence drill-down. Prove the same exact
   request/coverage shape in the external client. Only after held-out query
   evaluation consider cross-layer reranking or optional semantic retrieval.
5. Keep the donor's archive move and mass-phantom repoint behavior as separate
   action and inventory-safety tranches. Neither is smuggled into read-only
   search. Require fresh donor pin, synthetic parity, hosted exact-head gates,
   backup/rollback and owner-approved shadow before any source cutover.

Successful Search must find a current fictional investment memo in Files and
its related Email attachment without duplicate-byte deletion or fabricated
financial conclusions; default results omit the known superseded FOS-location
memo, opt-in includes it, and each hit opens separately authorized evidence.
When FileOS is unavailable, Email still works and coverage says why Files
were not searched. The reverse also holds. This is a target acceptance test,
not a claim of current implementation or live data access.
