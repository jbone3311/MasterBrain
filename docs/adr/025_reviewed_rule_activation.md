# ADR-025: Reviewed, versioned, virtual-only sender rules

Status: accepted for local prototype implementation, 2026-09-20.

Approval of a proposal remains distinct from activation. A human owner with
`email.review` and `email.search` must simulate an approved rule, then explicitly
activate its receipt. Assistants cannot do either. Only the existing exact sender
domain/category/canonical-mailbox rule lane is executable; all other proposal
types remain proposals. Domains do not imply authenticated sender identity.

Migration 0007 adds two append-only, FORCE-RLS tables: bounded simulation receipts
and immutable tenant ruleset revisions. Revision zero means no rules. No mutable
head or UPDATE/DELETE grants are needed: greatest revision is active. Tenant
advisory locks serialize activation and rollback; a receipt binds tenant, human
actor, proposal version/hash, base revision and a database-clock 15-minute expiry.
Repeated activation of the same receipt returns its historical committed revision
without reactivating it. Stale competing receipts fail with 409. Rollback appends a
new revision copying a prior snapshot (zero clears rules), using an expected current
revision; history and provider evidence remain untouched.

One rule per exact domain, at most 100 active domains. Simulation inspects at most
50 live, nonquarantined messages ordered by ID, records IDs and before/after effects,
and explicitly reports bounded-sample coverage, never whole-mailbox precision.
Mail can change after simulation; activation acknowledges a sampled configuration
preview, not a transaction over those messages. No automatic mailbox actions result.
Search derives labels from one active snapshot at read time, with revision and rule
provenance, so rollback requires no destructive message rewrite or backfill.

Review Delete is only a virtual review suggestion, never deletion, hiding, or an
eligibility decision for a future executor. This narrow API cannot configure
protected-sender exceptions or arbitrary engine predicates; those need another
reviewed schema/workflow before any mailbox automation. Existing pure engine
protected-keep veto remains tested. Header sender matching is spoofable, so labels
must not confer authorization or suppress mail.

Audit events cover simulation, activation, replay and rollback. Runtime SQL remains
trusted backend code; RLS protects tenant filtering errors, not arbitrary SQL after
backend compromise. Existing bootstrap credentials still forbid hosted exposure.

References: [PostgreSQL row security](https://www.postgresql.org/docs/current/ddl-rowsecurity.html),
[transaction advisory locks](https://www.postgresql.org/docs/current/explicit-locking.html#ADVISORY-LOCKS),
[rules policy](../RULES_AND_FEEDBACK.md).
