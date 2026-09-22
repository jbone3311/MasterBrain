# ADR-061 — Current-aware grouped FileOS and KnowledgeCore retrieval

Status: accepted and verified for the additive prototype tranche on 2026-09-22.
Revision `8bada56` passed hosted
[CI 35731669724](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35731669724)
and [restore 35731669604](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35731669604).

## Decision

The existing grouped `/v1/brain/unified-search` request gains an explicit
`evidence_visibility` choice. `retained` is the compatibility default and preserves
the existing DataCore evidence search. `current_fileos` uses only the newest activated
generation of each authorized FileOS source. KnowledgeCore retrieval, its kind filter
and its independent bound are unchanged.

The response identifies the selected evidence visibility. Evidence and knowledge stay
in separate layers with `within_layer_only` ranking; scores are never merged. Both
`brain.search` and `knowledge.search` remain required. Returned content is untrusted,
and the operation performs no model call, synthesis, activation or source effect.

## Acceptance and boundary

Contract tests must prove the default is backward compatible, the explicit current
mode selects the current-generation store method, unknown modes fail closed and both
scopes remain mandatory. PostgreSQL integration must bind reviewed knowledge to
evidence in an activated completed FileOS generation and return both layers.

This does not migrate the legacy Email index, recalibrate scores, infer new knowledge,
hide retained evidence, or redirect any other search route.
