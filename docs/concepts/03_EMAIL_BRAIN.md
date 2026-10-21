# Email brain

Status: exploratory rationale, captured 2026-10-15; no new implementation or
dependency decision. See the [concepts guide](README.md) for authority and provenance.

## Idea and lesson

Email is one optional source capability within MasterBrain. Source adapters own provider-specific intake; shared processing belongs in DataCore.

## Illustrative use

A fictional email and its attached term sheet can contribute separate evidence to the same project without making Email the system-wide knowledge store.

## Boundaries and next evidence

Read-only intake is separate from moving, archiving, drafting or sending. Current source permissions and live acceptance remain governed by the security and status records.

## Canonical follow-through

Read the [primary contract](../EMAIL_PROVIDER_CONNECTORS.md) and [related record](../SECURITY.md).
Check [current functions](../CURRENT_FUNCTIONS.md) and
[implementation status](../IMPLEMENTATION_STATUS.md) before claiming availability.
