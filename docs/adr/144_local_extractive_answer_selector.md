# ADR-144 — Local deterministic quote selection for the default Ask path

Status: accepted for synthetic/disposable read-only use. It does not approve
remote inference, free-form synthesis, hosted deployment or live-source use.

## Context

ADR-134 established a bounded, citation-checked answer interface, but the
default service has no selector. Consequently the first-party Ask control
usually falls back to grouped search. The owner needs a usable first-party
question path while model/provider selection and private-data transfer remain
unapproved.

## Decision

- Supply a stateless, local, deterministic `AnswerSelector` as the default for
  the API factory. It has no network, storage, tools, credentials or source
  effects. It selects at most four exact excerpts from the already authorized
  passages, ranking sentences by overlap with substantive question terms. No
  overlap returns `no_supported_answer`; it does not invent a response.
- Keep ADR-134's server-owned authorization, content bound, exact-substring
  verification, citation construction and final current-source recheck.
  Explicit `answer_selector=None` disables selection and returns the fixed
  503, retaining the grouped-search fallback and an immediate rollback switch.
  An explicitly supplied adapter still replaces the local selector; sending
  content off-host requires a separate approval and configuration review.
- Label the result as **verified source quotes**, not an AI answer or semantic
  conclusion. Passage text remains untrusted; it is displayed as text, never
  interpreted as instructions. Search-only credentials retain the separate
  Search only control. No schema, FileOS donor or source-effect change occurs.

## Acceptance and rollback

Use fictional Email/FileOS evidence to check exact offsets, deterministic
ordering, bounded quotes, no-overlap refusal, prompt-injection text isolation,
same API/client/first-party route, access denial and grant-revocation recheck.
Run local PostgreSQL, browser, documentation, deployment, strict-runtime and
populated-restore gates before merge. Roll back by passing `None` in service
configuration; source records and grants do not change. The local selector
does not establish answer completeness or the owner's live browser acceptance.
