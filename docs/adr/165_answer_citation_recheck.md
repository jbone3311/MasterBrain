# ADR-165 — Recheck selected answer evidence before disclosure

Status: accepted for the read-only answer service. This is a hardening increment, not generated-chat,
hosted-access or source-effect acceptance.

## Problem

The extractive answer service checks current search visibility after a selector
chooses quotes, but a search hit can retain the same evidence and document IDs
while its separately fetched body or source metadata changes. Search membership
alone does not prove that the quoted bytes remain authorized and current.

## Decision

After the final scoped search recheck, reopen only cited evidence (at most four
items) using the caller's existing read grants and the same bounded content
read. Require its document, source ID, source kind, body digest and selected
passage prefix to match the values supplied to the selector. A missing or
changed item returns the existing scrubbed `answer_stale` response; a revoked
read grant continues to fail closed. No selector receives a new tool, database
credential or effect authority, and no source text is logged.

This narrows a selection-time race but cannot provide a durable snapshot after
the response leaves the server. Hosted freshness and owner chat acceptance
remain separate gates.

## Verification

Service and API regressions cover changed body/digest, inconsistent body with
an unchanged digest, changed source metadata, revoked content access and a
scrubbed HTTP 409. Run the full test, type, lint, documentation and hosted
database/container gates on the exact PR head before merge.
