# Source and Provenance Contract

Checkpoint 1 introduced dependency-light immutable contracts. Checkpoint 2 persists
them in additive tenant-isolated `brain_*` tables, and Checkpoint 3 begins publishing
bounded FileOS text through those contracts.

## Source

A source has a stable lowercase `source_id`, a kind (`email` or `fileos`) and a bounded
display name. A source identifies an authorized account or root, not a provider token
or absolute filesystem path.

## Source item and version

An item is the stable logical object; a version is one observed content state.

- `item_id` derives from source ID plus relative locator.
- `version_id` derives from item ID, SHA-256 and size.
- `locator` is relative and cannot contain an escape component.
- `observed_at` is timezone-aware and normalized to UTC.
- `content` is a lowercase SHA-256 digest; size and media type are explicit.
- Metadata is bounded scalar data and immutable after construction.

A file rename will initially produce a new item identity plus matching digest. Later
reconciliation may link the two observations as a move, but must not silently rewrite
history. Provider-native immutable IDs can use an adapter-specific stable locator.

## Evidence

Evidence references a source version and digest. Storage is explicit:

- `inline`: bounded retained bytes in an authorized record.
- `object`: retained encrypted object storage.
- `source_bound`: bytes remain at the source and are reverified before use.

Source-bound evidence cannot claim `retained=true`. A digest/reference does not prove
availability forever; freshness and revalidation remain separate.

## Provenance

A provenance record has one output, one or more inputs, transform name/version, code
revision, creation time and configuration digest. Identifiers are opaque hashes, not
embedded content. Every normalized document, extraction, chunk, index publication and
KnowledgeCore claim will require a provenance path back to evidence.

## Security and compatibility

Contracts reject naive timestamps, unsafe locators, non-SHA-256 evidence digests,
invalid identifiers, nested/unbounded metadata, NUL text and contradictory storage
state. They add no source permissions or external effects. Existing Email evidence
tables remain authoritative for the Email capability. The additive bridge maps only
explicit current Email versions into DataCore with an immutable legacy-to-shared
receipt; it does not redirect ingestion, search or original-byte access.
Attachment bridge receipts preserve each MIME occurrence separately and link child
source-bound evidence to the shared parent message evidence. They reuse only existing
receipt text and never claim that embedded part bytes were separately retained.
