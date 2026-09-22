# ADR-080 — Keep current archive derivatives in an independently ranked layer

Status: accepted design; implementation pending.

## Context

Archive-member text is published after a FileOS index generation may already be
active. Inserting it into that immutable generation would falsify the generation's
sealed plan and counts. Searching the generic child current pointer would also be
unsafe because only the parent archive's current pointer establishes source currency.

## Decision

Add a separate current archive-member search joined through the append-only derivative
receipt, sealed inventory/member ledger and parent FileOS source item. Require the
parent archive version to remain current and verify the child version against the
member hash, size and media type. Expose the results as their own bounded layer in
`/v1/brain/current-search`, with no cross-layer rank comparison.

Preserve generic retained-history search and active FileOS generation contents. Return
only the existing opaque child locator and require the existing evidence/content scopes
for drill-down.

## Alternatives rejected

- Mutate the active generation: violates immutability, completion binding and rollback.
- Rebuild automatically after each member: grants scheduling/fan-out authority and can
  thrash large archives.
- Trust the derivative child pointer alone: leaves stale content visible after the
  parent archive changes.
- Merge results into the FileOS rank: suggests comparability between independently
  built corpora and obscures partial archive coverage.

## Rollback

Remove the new read method, request field and response layer. Append-only derivative
receipts and retained-history retrieval remain intact; no source, generation or
FOS-Master state changes.

