# ADR-146 — Show reviewed KnowledgeCore matches beside extractive Ask quotes

Status: accepted for synthetic/disposable read-only implementation. This is
not claim synthesis, automatic fact resolution or hosted acceptance.

## Context

Current grouped search returns source-scoped reviewed KnowledgeCore hits, but
the first-party Ask path uses only DataCore passages. An owner or enrolled
assistant asking about a reviewed project, claim or commitment can therefore
receive “no supported answer” even when a matching, evidence-linked assertion
is available through the same authorized search. Treating an assertion as an
exact source quote would erase the distinction between reviewed interpretation
and underlying evidence.

## Decision

- Add a separate `reviewed_knowledge` array to the extractive answer response,
  at most four compact hits in the grouped search order. Each hit has a bounded
  kind, opaque ID, title and excerpt, up to five direct evidence IDs and the
  total direct-link count. These are reviewed assertion *matches*, not
  model-authored answers or exact source quotations. A linked evidence button
  still requires the separately authorized evidence route.
- Use the existing KnowledgeCore search result, which filters enrolled
  assistants by **every** directly linked evidence source before rank/limit
  (ADR-143). Validate the shape and bounds before disclosure. The final
  current grouped search must still contain each selected assertion with the
  same full evidence-link set and displayed text; otherwise fail closed as
  stale. Search scopes, current DataCore quote checks and source grants remain
  unchanged. No additional database read or direct assertion expansion occurs.
- Keep `quoted_evidence` only for verified source quotes. When there is no
  source quote but a reviewed match exists, use `no_supported_answer` with a
  neutral explanation and show the separate reviewed matches. Empty evidence
  and empty knowledge retain the existing no-evidence response. Results remain
  explicitly partial and untrusted text; reviewed assertions do not become
  current source facts by appearing in Ask.

## Acceptance and rollback

Test source-only, knowledge-only and combined results; source-grant denial
including mixed Email/FileOS assertions; revocation or projection drift
between initial and final searches; malformed/oversized hits and evidence-link
bounds; browser text-only rendering, credential-clear behavior and external
client/API parity. Use fictional PostgreSQL evidence, full tests, container,
strict-runtime and restore gates. Rollback omits the additive array and
restores the prior UI while preserving all KnowledgeCore records. There are no
schema, FileOS donor or source-effect changes.
