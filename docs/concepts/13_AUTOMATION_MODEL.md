# Automation model

Status: exploratory rationale, captured 2026-10-15; no new implementation or
dependency decision. See the [concepts guide](README.md) for authority and provenance.

## Idea and lesson

Reliable automation needs explicit state, idempotency, retries, cancellation and audit. Reasoning proposes; policy and separately authorized executors govern effects.

## Illustrative use

A fictional delayed task should survive a restart without duplicating a reminder or source effect. A revoked grant must stop later execution.

## Boundaries and next evidence

Temporal and PydanticAI were named as candidates in the owner discussion, not adopted dependencies. First measure a gap in existing jobs and typed adapters; evaluate operational cost, security, licensing and migration before proposing adoption. Pydantic in the manifest is not PydanticAI.

## Canonical follow-through

Read the [primary contract](../ARCHITECTURE.md) and [related record](../OSS_EVALUATION.md).
Check [current functions](../CURRENT_FUNCTIONS.md) and
[implementation status](../IMPLEMENTATION_STATUS.md) before claiming availability.
