# ADR-052 — Grouped DataCore and KnowledgeCore search

Status: accepted for the additive prototype tranche on 2026-09-22.

## Decision

Add `POST /v1/brain/unified-search` as a compact, read-only composition of DataCore
lexical evidence retrieval and KnowledgeCore lexical assertion retrieval. The response
keeps the two ranked result sets in named layers and labels ranking as
`within_layer_only`; PostgreSQL full-text ranks from different indexes are not merged
into a misleading global order.

The request sets separate bounds of at most 25 results per layer and may restrict
knowledge object kinds. Every evidence result carries an evidence ID. Every knowledge
result carries all cited evidence IDs, allowing existing progressive evidence and
content endpoints to verify the assertion.

Both `brain.search` and `knowledge.search` scopes are required. Returned excerpts,
titles and locators remain untrusted content. The endpoint performs no synthesis,
model call, graph inference, source read or source effect.

## Verification and limits

Contract tests cover both-scope enforcement, strict request bounds, closed fields,
kind filtering and the grouped response. PostgreSQL integration publishes one FileOS
document and reviewed project assertions, then proves that a single request returns
both layers through tenant-isolated indexes.

This endpoint does not yet include the legacy Email index because Email evidence has
not been migrated to shared DataCore identities. It also does not claim cross-layer
score calibration, semantic ranking or answer synthesis. Rollback removes the route;
the underlying evidence and assertions remain unchanged.
