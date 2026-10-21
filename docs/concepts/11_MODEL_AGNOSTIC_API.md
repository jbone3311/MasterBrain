# Model-agnostic access

Status: exploratory rationale, captured 2026-10-15; no new implementation or
dependency decision. See the [concepts guide](README.md) for authority and provenance.

## Idea and lesson

Keep knowledge and authorization in MasterBrain so different authorized clients can use the same evidence without owning its truth.

## Illustrative use

An assistant requests bounded results, then explicitly expands a citation. Client choice does not widen its source grants.

## Boundaries and next evidence

The MCP SDK is a protocol implementation candidate, not authorization or a certified client. Existing Brain API contracts govern; general SQL, arbitrary HTTP and provider credentials remain excluded.

## Canonical follow-through

Read the [primary contract](../BRAIN_API.md) and [related record](../EXTERNAL_CLIENT.md).
Check [current functions](../CURRENT_FUNCTIONS.md) and
[implementation status](../IMPLEMENTATION_STATUS.md) before claiming availability.
