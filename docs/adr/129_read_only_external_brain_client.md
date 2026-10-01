# ADR-129 — Provider-neutral read-only Brain API client

Status: accepted for synthetic/disposable implementation; no hosted or named-assistant certification.

## Context

The first-party `/brain` workspace calls the scoped current-search and evidence
routes, while a separately authorized external assistant currently has only the
raw REST contract. A small reference client makes the same sequence testable
without creating an alternate retrieval backend or granting a model direct
database, provider or filesystem access. A client library is not itself a
deployed integration with Claude, Grok or ChatGPT.

## Decision

- Add a provider-neutral Python read client with exactly three methods: grouped
  current search, evidence metadata, and bounded extracted-content expansion.
  Reuse the server's closed request models and route paths. No write/proposal,
  historical-search, arbitrary URL, SQL, source connector or raw-byte method.
- The operator fixes one API origin and supplies a bearer credential; questions
  and source content cannot choose the origin, path or headers. Require HTTPS,
  except an explicit loopback-only option for disposable local testing. Ignore
  ambient proxy configuration; do not follow redirects or cache responses.
  Set finite connect/read/overall timeouts and cap decompressed JSON responses.
- Validate the minimum response contract and requested identity before returning
  data. Keep server authorization authoritative: search does not imply evidence
  metadata or extracted-text access. Return fixed-code errors without raw bodies,
  source text, tokens or transport exception messages.
- Treat results as untrusted evidence candidates. The client does not synthesize
  an answer, store a transcript, retry effects, or claim complete source
  coverage. It is suitable as the transport behind a later narrow assistant
  adapter only after that adapter's identity, prompt-injection, citation,
  revocation and hosted acceptance gates pass.

## Acceptance and rollback

Use fictional data. Contract tests cover origin/credential validation, fixed
read-only paths, request bounds, redirects, timeouts, oversized/malformed JSON,
denied scopes, ID mismatches, no token/body leakage, and close behavior. A real
PostgreSQL/FastAPI conformance test compares the client with a direct Brain API
call on the same known-answer corpus, including separately scoped evidence and
cross-tenant denial. Run full suite, strict runtime, restore and donor parity.

Rollback removes this client and its tests/docs. No database migration or source
state is involved. FOS-Master remains unchanged.
