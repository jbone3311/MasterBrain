# Current archive-document search design

Status: checkpoint 4W accepted design; runtime not yet implemented.

## Purpose

Expose explicitly published archive-member PDF/DOCX/XLSX derivatives as a distinct,
bounded current-source search layer. Retained-history DataCore search remains
unchanged. The existing `archive_members` layer remains text/Markdown/HTML/CSV only;
document results use a separate rank, limit and coverage label.

## Currency and identity fence

One forced-RLS query may return a document chunk only when it proves all of these:

1. an immutable archive-document receipt names the exact inventory, member, parent
   source version/evidence, child source/item/version/evidence and normalized document;
2. the sealed inventory names the same parent source/item/version and still contains
   the exact member hash, observed size, media hint, depth and container classification;
3. the parent FileOS item still points to the inventory's source version;
4. the child item still points to the receipt's deterministic child version, whose
   hash, size and media type equal the sealed member;
5. receipt format, member suffix/media and container classification agree exactly:
   PDF is a non-container `application/pdf`; DOCX/XLSX are the accepted opaque OOXML
   containers; and
6. the returned evidence, document and chunks are the receipt's exact derivative.

The child pointer alone is insufficient. Replacing the parent archive removes the old
document from current search immediately without deleting evidence, receipts, chunks
or retained-history retrieval.

## Retrieval and API shape

Add `DataCoreStore.search_current_archive_documents`, requiring `brain.search`, using
the existing 500-character plain-text query, deterministic PostgreSQL lexical rank,
bounded headline and a strict 1–20 limit. Add a tenant-leading receipt lookup index;
do not rewrite document rows or an active FileOS generation.

Add `archive_document_limit` to the closed `/v1/brain/current-search` request and an
`archive_documents` response layer. Its coverage label is
`explicitly_published_current_archive_documents_only`. Ranks are meaningful only
inside this layer. Existing FileOS, archive-text, Email-family, KnowledgeCore and
retained-history semantics remain unchanged. Independent forced-RLS reads continue to
declare `independent_layer_reads`; no atomic cross-layer snapshot is claimed.

The response returns only the existing opaque child locator and normal compact search
fields. Full normalized content still requires the separate evidence/content scopes.

## Security and privacy

- read-only query and tenant-leading index; no worker, source read, archive byte access,
  receipt mutation, generation activation or source effect;
- no member enumeration, virtual member locator, sibling discovery or automatic
  publication/fan-out;
- no full document text, properties, raw bytes, paths, processor IDs or fault details;
- forced RLS plus exact receipt/parent/member/child joins fail closed on drift;
- the distinct layer prevents archive-document ranks from being presented as
  comparable with archive text, ordinary FileOS, Email or KnowledgeCore ranks.

## Acceptance

- exact current PDF, DOCX and XLSX derivatives match only in the new layer;
- same-term archive text/document and ordinary FileOS results remain separately ranked
  with stable opaque identities and independent limits;
- parent replacement removes the old document from current search while retained
  history and authorized direct evidence remain available;
- receipt replay cannot duplicate chunks; a current replacement appears only after
  explicit inventory, extraction and publication;
- child-only pointers, text receipts, mismatched parent/member/receipt identities,
  wrong suffix/media/container classification and foreign tenants return nothing;
- invalid query/limit/schema requests fail closed and audit names are exact;
- API coverage, layer, limits and content-free response shape are exact;
- full PostgreSQL/restore, real two-image chain, existing current-search, donor parity
  and archive text preview/batch gates remain green.

## Non-goals

No publication, preview, batch, scheduler, automatic archive fan-out, active-generation
mutation, rank merge, semantic search, atomic cross-layer snapshot, image/OCR support,
current-source coverage count, public mutation, source effect or FOS-Master cutover is
authorized.

