# ADR-145 — Bounded question-term retrieval for extractive answers

Status: accepted for synthetic/disposable read-only use. This does not add
semantic search, synthesis, a model, source effects or hosted acceptance.

## Context

ADR-144 made the local Ask path return verified source quotes, but its first
retrieval still sent the entire question to PostgreSQL's simple-dictionary
lexical search. That search requires all terms. Ordinary question boilerplate
such as “find the” or “what is” can therefore hide an otherwise matching
Email/FileOS document. This is a usability failure, not proof that a source is
missing.

## Decision

- For `POST /v1/brain/answers` only, derive a bounded lexical query from the
  original question by dropping a fixed list of question/filler words and
  retaining the remaining words in their original order. There is no synonym
  expansion, model rewrite, hidden source selection or permission change. If
  no substantive word remains, keep the original question so the existing
  bounded search contract and explicit no-evidence result still apply.
- Pass that same derived query to both the first current grouped search and
  ADR-134's final current-authority/evidence recheck. The selector still sees
  the original question and only the separately authorized, bounded passages.
  The server still verifies exact quotes and citations. The Search only route
  retains its existing literal query behavior.
- Document this as lexical question-word removal, not natural-language
  understanding. A question that requires synonyms, temporal reasoning,
  source-type interpretation or unstated context may still return no supported
  answer. Do not silently broaden it to retained or unauthorized sources.

## Acceptance and rollback

Fictional real-PostgreSQL Email/FileOS known answers must distinguish literal
full-question search from the answer route's derived query. Test client/API
parity, empty/boilerplate questions, fixed query bounds, original-question
selection, exact citations and source-grant recheck. No schema or donor change.
Rollback is an answer-route-only code rollback to passing the original question;
all evidence, source grants and the Search only API stay unchanged.
