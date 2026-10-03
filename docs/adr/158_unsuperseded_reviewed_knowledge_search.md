# ADR-158 — Explicit unsuperseded reviewed KnowledgeCore search

Status: accepted and merged in PR #146 for synthetic/disposable read-only use;
exact-head CI, strict runtime and restore passed. No current-search switch or
live-source claim follows.

## Context

KnowledgeCore retains every reviewed assertion and correction. Its lexical
search currently returns all matching history, including a project, commitment
or claim later superseded or explicitly corrected. This is appropriate for
forensic retrieval but unsuitable as an unlabeled answer to “what is the latest
reviewed state?” The grouped Brain current-search and extractive Ask currently
reuse that retained KnowledgeCore search. The first implementation must not
silently resolve contradictory branches or turn reviewed assertions into fact.

## Decision

- Add an explicit `retained` (default) or `unsuperseded` visibility option to
  KnowledgeCore lexical search and its direct API request. Keep the default and
  every historical expansion/change feed unchanged. In `unsuperseded` mode,
  exclude correction records themselves and an assertion only if a later
  same-kind assertion names its ID as `supersedes_id`, or an explicit reviewed
  correction targets it and names a visible replacement. Apply this filter in
  SQL **before ranking and limit**, never on a truncated result page.
- A superseding assertion or correction/replacement can affect an assistant's
  result only when its own direct evidence links are nonempty and entirely
  within that assistant's current source grants. Keep transaction-time OIDC
  grant rechecks. This avoids making the presence of hidden-source assertions
  observable through disappearing older hits. Owners without source filtering
  see the full tenant projection. Direct evidence links on returned hits remain
  unchanged.
- Multiple unsuperseded branches remain multiple results: no last-write-wins,
  truth selection or automatic contradiction resolution. This mode is a
  *review-chain leaf* projection, not a valid-time or real-world-current
  guarantee. `valid_from`/`valid_to`, source freshness and conflicting claims
  are separate dimensions. Do not silently replace the retained compatibility
  search or grouped Brain reads in this tranche; evaluate the explicit mode
  first, then decide a separately verified current-search switch.
- Add supporting tenant-scoped indexes on successor and correction lookup
  columns in a forward migration. The ordinary transactional index build is
  acceptable for the synthetic alpha but needs a separately planned
  lock-budgeted/online path before upgrading a large hosted database. No
  existing assertion, evidence or search document is rewritten.

## Verification and rollback

Use disposable PostgreSQL to test two-step chains, explicit corrections without
`supersedes_id`, multiple branch leaves, correction visibility, source-grant
noninterference, post-filter ranking/limit, tenant isolation and legacy retained
behavior. Test the closed API request and invalid modes; run full CI, strict
runtime, restore and documentation gates. Roll back by reverting the code-only
optional mode; preserve the additive indexes and immutable history. Never
delete corrected assertions. FOS-Master and source effects are unaffected.
