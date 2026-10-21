# Search and retrieval

Status: exploratory rationale, captured 2026-10-15; no new implementation or
dependency decision. See the [concepts guide](README.md) for authority and provenance.

## Idea and lesson

Finding relevant evidence is different from establishing truth. Combine exact identifiers, lexical retrieval and reviewed knowledge according to the existing retrieval contracts.

## Illustrative use

A request about “the insurance issue” might motivate a semantic-search benchmark, but an exact policy number still benefits from exact matching.

## Boundaries and next evidence

PostgreSQL is the data foundation; pgvector remains conditional on measured lexical misses. Do not promise embeddings, freeform answers or complete coverage from a concept example.

## Canonical follow-through

Read the [primary contract](../DATACORE_PERSISTENCE.md) and [related record](../BRAIN_API.md).
Check [current functions](../CURRENT_FUNCTIONS.md) and
[implementation status](../IMPLEMENTATION_STATUS.md) before claiming availability.
