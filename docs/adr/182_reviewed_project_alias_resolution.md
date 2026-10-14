# ADR-182 — Reviewed project aliases and candidate-only resolution

Status: accepted for synthetic/disposable, additive KnowledgeCore use. This
does not authorize automatic deal merging, live-source acceptance or FileOS
cutover.

## Context

A deal can be named by a title, address, legal entity or mail folder. Before
this decision, KnowledgeCore stored aliases only for entities, so a project
could not carry its own reviewed alternate names. Treating a shared address as
a unique project key would also merge unrelated deals. Issue #175 asks for
project aliases with evidence and ambiguous candidate handling.

## Decision

- Extend the existing human-only `knowledge.review` project assertion with at
  most 20 typed aliases. Each alias has a kind, source quote and an evidence ID
  already in the same reviewed assertion. The canonical title is stored as a
  title-kind alias for new projects. Alias names use Unicode NFKC, casefolding,
  punctuation separation and whitespace collapse. This intentionally differs
  from the older entity-alias normalization; it is not entity resolution or a
  semantic equivalence claim. Duplicate normalized names within one project
  are invalid. The same name across projects is allowed.
- Add an immutable `knowledge_project_aliases` table and nullable manifest
  digest on `knowledge_projects` in migration 0059. New reviewed project writes
  bind their complete alias set to the project row. Deferred SQL checks require
  that the exact alias set matches the manifest and each alias cites a supporting
  project evidence link and the same reviewer. Direct SQL cannot append an
  unreviewed alias to an existing reviewed project, even with its own evidence.
  Existing project and evidence heaps are not backfilled or rewritten.
- `GET /v1/knowledge/projects/resolve?name=...` requires `knowledge.search`
  and returns at most 25 reviewed candidates with exact project and alias
  evidence IDs, an ambiguity flag and a truncation flag. It does not select,
  merge or redirect to one project. Both project evidence and alias evidence
  must pass current source grants before limit. Unknown names return an empty
  candidate list. Existing pre-migration projects retain exact case-insensitive
  title lookup without a history rewrite; punctuation-insensitive lookup for
  their old titles requires a later reviewed successor.
- The resolver deliberately labels its results `retained`: reviewed superseded
  versions may appear as separate candidates. That is not a current-project
  reducer. The provider-neutral `BrainReadClient.resolve_project_alias` checks
  identities, evidence IDs, normalized match, ordering, bounds and labels.
  Returned names are untrusted source-derived text. No alias is discovered by
  an LLM and no proposed or inferred alias is published automatically.

## Verification and rollback

Fictional PostgreSQL tests cover case/punctuation/Unicode matching, two-project
ambiguity, limit truncation, source grant and tenant denial, old-title fallback,
idempotent review writes, immutable rows and direct-SQL alias-set/evidence
refusal. API/client tests cover scope, closed bounds and malformed responses.
The populated forward migration, full repository, strict-runtime and restore
gates apply before merge. Rollback disables alias writes and lookup; retain
the append-only table and manifest columns for audit. FOS-Master is unchanged.
