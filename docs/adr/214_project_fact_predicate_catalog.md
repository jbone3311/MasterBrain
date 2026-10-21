# ADR-214 — Controlled vocabulary for new reviewed project facts

Status: implemented for fictional local testing on an open PR; hosted exact-
head, independent restore and merged-main gates remain required. Issue #183
remains open for the broader registry, aliases and proposal workflow.

## Context

Project-fact predicates were syntactically bounded slugs but semantically
uncontrolled. A reviewer could publish `ask_price`, `asking_price` and
`loi.price` as unrelated names, or put text and currency values under one
name. A report grouped by slug would then imply consistency it did not have.
The existing historical facts are immutable; they must not be renamed or
automatically assigned a meaning.

## Decision

For **new reviewed project facts only**, a checked-in code catalog and
migration 0073 define versioned, immutable, active predicate rows. This first
catalog includes `deal.note` and raw-text `loan.proposed_amount`, plus
quote-backed currency-number `capital.amount`, `loi.price` and
`capital_call.amount`. Descriptions explicitly distinguish a source-stated
amount from a balance, completed sale or paid capital. The publication
boundary rejects unknown names, mismatched value types and mismatched or
missing measurement units **after** checking any exact idempotency receipt,
so an already-reviewed historical write can be replayed without minting a
new fact. A SQL insert trigger repeats the active latest-version/type/unit
check, stamps `predicate_registry_version`, and runs for direct database
inserts as well as API writes. A separate catalog-drift test compares every
checked-in code entry with SQL seed rows. Runtime roles may read this public
vocabulary but cannot edit it. Mutation and truncate guards protect the
catalog; a later version requires a reviewed forward migration and code update.

Migration 0073 adds a nullable registry-version column to the existing fact
table. Old rows retain NULL and their original predicate/value; no historical
fact is rewritten or certified. Existing read formats are unchanged. A new
fact under a previously used name must satisfy the current registered shape.
ADR-215 corrects the initial guard's latest-**active** lookup: the newest
revision, including a deprecated one, is authoritative, and a read-only API
allows clients to discover it without granting vocabulary edit authority.
An exact legacy idempotent replay remains available while its current source
basis is still authorized; the registry cannot authorize a new fact or bypass
the existing source check.

## Boundary and next gate

This is a first project-fact catalog, not the whole issue #183: generic
entity claims, event types and member roles remain free slugs. Deprecated
aliases and owner-approved vocabulary proposals are not implemented. Unknown
project-fact names may enter the existing **private fact proposal** queue,
where preview labels them `registry_status=unknown`; approval fails atomically
until a reviewed catalog migration defines them. This is not a dedicated
vocabulary proposal or automatic approval. Build that separate private
name-proposal/review path before accepting arbitrary Librarian imports. Do not
infer alias equivalence from similar
strings. The registry alone proves no source statement is true, no owner is
identified and no financial total is safe to compute.

## Acceptance and rollback

Use fictional model and disposable PostgreSQL tests to prove correct catalog
seed/code parity; recognized text and currency facts; unknown/type/unit
rejection at publication and direct-SQL boundaries; exact historical
idempotent replay, private unknown-name stage/preview and atomic approval
refusal; immutable catalog and
no-truncate protection; existing source-basis, RLS, proposal, restore and
cross-source preview behavior. Run full local and exact-head hosted gates.
Rollback disables new publications using the catalog while retaining existing
immutable rows and registry versions; it does not rewrite facts or weaken
provenance. FOS-Master remains untouched.
