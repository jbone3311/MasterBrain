# ADR-060 — Explicit current FileOS search across active generations

Status: accepted for implementation; hosted verification pending.

## Decision

Brain API adds a separately named current FileOS search across every authorized source
that has an active immutable generation. For each source, only its newest append-only
activation participates. Sources with no activation contribute no results. Results
remain bounded, lexical, compact and evidence-linked.

The existing DataCore and unified search routes keep their compatibility behavior and
may include retained historical derivatives. They are not silently redirected. This
separation lets clients deliberately choose current FileOS state while historical
evidence remains accessible through existing evidence and compatibility paths.

The route requires `brain.search`, returns at most 50 results and audits the read.
Forced RLS remains the tenant boundary. Activation rollback immediately changes the
generation selected by subsequent current searches without deleting any generation.

## Acceptance and boundary

Tests compare deterministic identities with the existing index for current documents,
cover changed and zero-hit queries, prove rolled-back content disappears, exercise the
API and verify restored current search. This is not cross-layer synthesis, automatic
activation, semantic ranking, source reprocessing or a FileOS cutover.
