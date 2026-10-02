# ADR-134 — Grounded extractive answers over current Brain evidence

Status: accepted for synthetic/disposable read-only implementation. Free-form
answer synthesis, hosted inference and named-assistant acceptance remain open.

## Context

The first-party `/brain` workspace and the provider-neutral client can search
and open evidence, but neither returns a question-shaped answer. Letting a
model freely summarize private Email/FileOS text would add an unverified claim
surface and a new prompt-injection route. The same Brain API must serve the
owner and approved external assistants without giving either source effects,
database access or a privileged retrieval path.

## Decision

- Add `POST /v1/brain/answers` as a separately scoped, read-only operation.
  It requires current search, reviewed Knowledge search, evidence metadata and
  bounded extracted-content grants. An assistant must have explicit source
  enrollment. The route uses the same grouped current-search implementation
  as the owner workspace; retained-history search is never silently substituted.
- A configured, provider-neutral `AnswerSelector` receives at most eight
  bounded, source-labelled passages (at most 1,200 characters each) and the
  bounded question. It has no tools, credentials, URLs or effect methods.
  No selector is configured by default; the route then returns a fixed 503
  rather than sending content to an unapproved remote model. A separately
  reviewed local/hosted adapter and operator configuration are later work.
- The selector may return at most four `(evidence_id, exact_quote)` choices.
  The server accepts a quote only when it is a nonempty exact substring of
  the same authorized, current extracted document, at most 400 characters.
  The server computes its offset and SHA-256 citation, not the selector.
  Unsupported selections cause a fixed failure, never a partly trusted
  answer. The API constructs the response from verified quotes; it does not
  publish model-authored free-form claims or interpret source instructions.
- Read current-search results again before responding. A changed source grant
  or a selected hit that is no longer current fails closed. Results explicitly
  state partial source coverage and that reviewed KnowledgeCore assertions
  are not yet synthesized in this extractive slice. The browser and external
  client call the same route; history stays in browser memory only.
- No database, migration, source-effect or FOS-Master change is authorized by
  this ADR. An answer is a view of evidence, not durable evidence itself.

## Threats and acceptance

Test source-grant denial and revocation between search, selection and final
recheck; stale evidence; model-invented IDs, quotes and instructions; duplicate
and oversized selections; model failure; missing content grants; wrong tenant;
bounded input/output; Email/FileOS known answers; browser text-only rendering;
and client/API parity. Log only fixed failure codes and opaque request IDs.
Do not log questions, passages, model responses or credentials. Local and CI
PostgreSQL, browser, strict-runtime, populated-restore and documentation gates
must pass before merge.

Rollback is forward: disable the selector and route while preserving all
evidence and source grants. A deployment with no selector continues to offer
the existing read-only search workspace. This first slice is not a claim of
semantic entailment, complete retrieval, hosted inference, a real named
assistant or source-write safety. Those remain [issue #92](https://github.com/jbone3311/MasterBrain/issues/92)
and [issue #88](https://github.com/jbone3311/MasterBrain/issues/88).
