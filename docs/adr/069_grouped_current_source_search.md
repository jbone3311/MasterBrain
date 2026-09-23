# ADR-069 — Grouped current-source and KnowledgeCore search

Status: implemented and hosted-verified in runtime revision `8da5b36`; mixed-source
fixture assertion corrected in `7939674`.

## Context

The existing unified endpoint can group retained DataCore history or active FileOS
evidence with reviewed KnowledgeCore assertions. ADR-068 provides current Email-family
layers separately. An LLM client currently needs multiple calls to get a complete
current-source view and could mistakenly compare lexical ranks produced by different
source representations.

## Decision

Add a separate `POST /v1/brain/current-search` endpoint. It groups active FileOS
evidence, current Email messages, current Email attachment text, current approved Email
documents and reviewed KnowledgeCore assertions. Every group has an independent 1–20
limit and rank ordering. The response states that ranks are comparable only within a
group and labels coverage explicitly:

- FileOS includes only sources with an activated immutable generation.
- Email includes only explicitly bridged evidence that passes ADR-068 current checks.
- Knowledge includes retained reviewed assertions matching the requested kinds.

The request and response stay compact and require both `brain.search` and
`knowledge.search`. Layer reads are independently authorized transactions rather than
an asserted cross-layer database snapshot, so the response declares
`independent_layer_reads` consistency. Existing unified, FileOS, Email and knowledge
routes remain unchanged.

## Safety and compatibility

Results expose bounded untrusted excerpts and opaque evidence/object identities only.
No source enumeration, filename expansion beyond existing safe locators, content read,
provider access, graph traversal, automatic synthesis or action authority is added.
Missing active/bridged source coverage yields an empty group, not a completeness claim.

## Acceptance and rollback

API tests must prove both scopes, closed limits/kinds, exact grouping, coverage labels
and no cross-group rank claim. Synthetic PostgreSQL must return FileOS, Email and
KnowledgeCore results together and prove a missing source group does not suppress the
others. Existing suites and populated restore must remain green. Rollback removes only
the new route/schema; all existing search contracts remain unchanged.
