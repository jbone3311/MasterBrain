# ADR-127 — First-party read-only MasterBrain workspace

Status: accepted for synthetic/disposable implementation; no model answer or source effect.

## Context

The Brain API already exposes scoped current Email, FileOS, archive and reviewed
KnowledgeCore retrieval with bounded evidence expansion. The fictional browser
trial proves a narrow Email/FileOS search path, but it is not a normal owner
workspace. The Email capability's existing screen is provider-specific. The
product contract requires a first-party interface and external assistants to
share one Brain API, not parallel privileged backends.

## Decision

- Add a static, first-party `Ask MasterBrain` workspace served by the existing
  API process. It calls the existing `/v1/brain/current-search`, coverage and
  evidence routes through the same authorization path available to external
  clients. No new query or permission shortcut is introduced.
- This first slice is a conversation-shaped **read-only search**: each user
  question produces grouped current-source hits and explicit partial coverage.
  It does not interpret commands, generate prose answers, store conversation
  history, call a model, or claim that lexical hits answer the question.
  Knowledge assertions retain their own group and ranking; source groups are
  not collapsed into one global score.
- The owner enters a bearer credential into page memory. It is never placed in
  a URL, browser storage, or a cookie by this workspace. Requests stay same-
  origin, use `credentials: omit`, `cache: no-store`, and reject redirects. The
  page is only an unauthenticated static shell; all data routes independently
  enforce scopes. Evidence metadata and bounded content remain separately
  authorized, and a missing content grant must not leak text.
- Treat every query, result, locator, excerpt and error as untrusted text. Build
  DOM nodes with `textContent`, never source HTML. Clear visible content and
  invalidate in-flight responses when the credential changes or is cleared.
  Limit retained turns and rendered hits in browser memory. Show generic
  failures, no returned exception text, token, raw request or response dump.
- Do not add source effects, approval controls, model tools, direct database
  access or background provider calls. Future cited answer synthesis and
  reviewed actions require separate decisions, permissions and tests.

## Acceptance and rollback

Use fictional/disposable inputs only. Browser-contract tests must prove that
an unauthenticated shell makes no data request; invalid or changed credentials
cannot reveal a stale result; current Email, FileOS, archive and knowledge
groups render as text with independent counts; partial coverage is visible;
evidence expansion uses only the separately scoped API; hostile HTML remains
inert; no source-effect endpoint is called. API integration tests must verify
the static route, CSP and actual read-route authorization. Run the full
PostgreSQL suite, browser tests, docs gate, strict runtime and restore CI.

The workspace is not a hosted/live-source acceptance and cannot be called a
complete conversational assistant. Rollback removes its static routes/assets;
there is no schema, background job, source state or stored conversation to
reverse. Existing Brain API, Email screen and FOS-Master remain unchanged.
