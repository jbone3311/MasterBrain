# ADR-147 — Human-only API review of one historical FileOS v2 search

Status: accepted for synthetic/disposable read-only implementation. This
does not authorize v2 activation, later-run policy, FileOS effects or cutover.

## Context

ADR-128's private `FileOSV2SearchReviewer` already compares one ready,
historical v2 generation with the active v1 generation under the source lock.
It requires a human transition reviewer, search and evidence scopes, and an
exact latest-v1/root match. The comparison has no narrow first-party API
entrance, so an owner cannot inspect it through the same authenticated
boundary as other Brain reads. Exposing it as ordinary current search would
misrepresent historical evidence as live FileOS state.

## Decision

- Add `POST /v1/brain/sources/{source_id}/v2-search-preview` with a closed,
  bounded request naming one `generation_id`, lexical `query` and limit of
  1–50 per generation. Only a human with
  `brain.fileos.transition.review`, `brain.search` and
  `brain.evidence.read` may call it. An assistant is denied even if it carries
  those strings. No original-content or source-effect authority is implied.
- Reuse the existing reviewer unchanged. It enforces ready v2 membership,
  exact source/baseline/root binding, active-v1-only comparison, transaction
  locking and an opaque audit event. The API maps invalid inputs to a generic
  422, missing generation/source to 404 and stale basis to 409 without
  exposing database diagnostics.
- Return separately labelled, independently ranked `active_v1` and
  `candidate_v2` bounded hits, with the v2 group explicitly marked
  `historical_preview`. Include opaque generation IDs, source ID, a partial
  coverage warning and `untrusted_content`. The route never changes an
  activation, completion, evidence record, source file or donor checkout.
  Clients may request evidence/content only through their separately scoped
  existing routes. A comparison result is not a parity certificate.

## Acceptance and rollback

On fictional PostgreSQL data, verify direct library/API field parity, correct
source and generation binding, human/scope/assistant denial, invalid bounds,
stale-v1 refusal and no activation or source mutation. Keep the pinned donor
golden comparison separate. Run full CI, strict runtime and populated restore.
Rollback removes the additive API route while retaining historical v2
generations and their audit records; FOS-Master remains unchanged.
