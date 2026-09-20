# Product Contract

## Product

CW-EmailBrain is the code-first intelligence and control layer over email. It converts provider changes into durable evidence and queryable operational state so assistants reason over compact, cited context instead of rereading mailboxes.

## Outcomes

- Search all authorized mail with stable evidence citations.
- Maintain current people, projects, thread state, obligations, decisions, and temporal facts.
- Organize mail through reviewed data-driven rules.
- Learn through typed proposals rather than self-modifying software.
- Keep most messages off remote models and preserve useful operation when models are unavailable.

## Non-negotiable invariants

- PostgreSQL is the multi-user source of truth; local SQLite is optional cache only.
- Every tenant-owned record is tenant-scoped in application logic and forced RLS.
- Raw evidence is immutable while retained under an explicit retention/purge policy; projections are versioned and rebuildable.
- Cursor advancement cannot skip an undurably processed change.
- Every write/effect is idempotent and auditable.
- Untrusted email/model content cannot authorize tools or mailbox effects.
- No automatic sending or permanent deletion in the initial product.
- Models return schema-validated proposals with evidence; deterministic policy decides what may happen.

## Initial customer

An owner operating several personal/business mailboxes who needs secure remote access and may later invite household/team members with explicit grants.

## Initial release

One provider, read-only incremental sync, raw evidence, normalization, PostgreSQL RLS, full-text retrieval, evidence API, audit, reconciliation, backups, and operational metrics.

## Success

The initial release can replay provider changes without duplication or omission, answer a representative query set with correct evidence, survive worker crashes and cursor expiry, demonstrate tenant isolation, and restore from backup. See [`docs/PRD.md`](docs/PRD.md) for full metrics.
