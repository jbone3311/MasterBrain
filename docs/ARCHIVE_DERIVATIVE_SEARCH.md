# Current archive-derivative search design

Status: implemented in `6c7b043`. The runtime passed 2,556 hosted Python tests and all
restricted worker gates in [CI 35796920249](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35796920249),
plus the populated [restore 35796920235](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35796920235).

## Purpose

Expose explicitly published archive-member text as a distinct current-source search
layer without rewriting an activated FileOS generation or treating archive publication
as automatic extraction. Retained-history DataCore search remains unchanged.

## Currency fence

A result is current only when one forced-RLS query proves all of the following:

1. the derivative receipt names the same inventory, parent source version, source,
   child item/version/evidence and normalized document being returned;
2. the inventory names that same parent source/item/version and the selected member
   still exists in its sealed member ledger as a non-container;
3. the parent FileOS source item's `current_version_id` is the inventory's archive
   source version;
4. the child source item still points at the deterministic derivative version, and
   that version's hash, size and media type agree with the sealed member;
5. the returned document, evidence and chunks are the receipt's exact derivative.

The child current pointer alone never proves currency. When a later FileOS snapshot
makes the parent archive historical, the old derivative stops appearing immediately;
no receipt, evidence, document or history is deleted.

## Retrieval and API shape

Add a bounded `DataCoreStore.search_current_archive_members` read requiring
`brain.search`. It uses the same 500-character plain-text query contract, deterministic
PostgreSQL lexical ranking and headline bounds as other DataCore layers, with a 1–20
limit. It returns the opaque child locator, never the virtual archive member locator.

Add `archive_member_limit` to the closed `/v1/brain/current-search` request and an
`archive_members` response layer. Ranks are meaningful only inside that layer. The
coverage label is `explicitly_published_current_archive_members_only` and global
`complete` remains false. FileOS active-generation, Email-family, KnowledgeCore and
retained-history results keep their existing semantics and limits.

Each current-search layer remains an independent forced-RLS read, so the response
continues to declare `independent_layer_reads`; it does not claim an atomic cross-layer
snapshot.

## Security and privacy

- no new mutation, worker, scheduler, source read or archive byte access;
- no member enumeration, sibling discovery, automatic fan-out or publication;
- no path, virtual locator, raw byte or normalized full-text field in ordinary search;
- existing evidence/content scopes still gate drill-down after a search hit;
- generic validation and forced RLS preserve tenant isolation;
- current-source transitions hide stale derivatives without destructive cleanup.

## Acceptance

- flat and nested published members match only in the new independently limited layer;
- the same text in a normal FileOS document and archive member keeps separate ranks and
  stable opaque identities;
- parent source replacement removes the old derivative from current search while it
  remains available through retained-history search and direct authorized evidence;
- a newly inventoried/published replacement appears without changing an older index
  generation;
- child-only pointers, mismatched inventory/member/receipt identities, containers and
  foreign tenants cannot produce a result;
- empty, NUL, overlong, non-integer and out-of-range requests fail closed;
- API response schema, coverage label, audit event, limits and content-free locators
  are exact;
- PostgreSQL, restore, archive container, donor parity and existing FileOS/Email/
  KnowledgeCore retrieval suites remain green.

## Non-goals

No active-generation mutation, generation rebuild, rank merging, semantic search,
coverage claim for unpublished siblings, archive batch, non-text extraction, OCR,
public mutation, source effect or FOS-Master cutover is authorized.

## Implemented result

Migration `0025` adds only the tenant-leading lookup index. The forced-RLS query uses
an `EXISTS` fence so multiple exact-replay receipts cannot duplicate a chunk. It joins
the receipt to the sealed inventory/member, current parent item, parent evidence,
current child item, child version/evidence/document and chunk; hash, size and media
type must agree. `/v1/brain/current-search` exposes the separately limited
`archive_members` layer and the declared partial-coverage label. Parent replacement
hides the derivative there while retained-history search continues to return it.
