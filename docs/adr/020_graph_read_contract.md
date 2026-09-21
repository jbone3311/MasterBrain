# ADR-020 — Bounded Microsoft Graph read contract

Accepted for an offline-tested library only, 2026-09-20. This does not enroll an
account, create a subscription, change the database, or activate a live worker.

Bind a client to one explicit Graph user. Read folder-scoped delta pages and MIME
using GET only, with immutable-ID preference on every request. Validate opaque
continuation URLs against the exact account/folder endpoint before following them;
never rebuild their query strings. A folder removal changes membership, not global
message existence. Fetch current evidence before projecting unordered changes.

Basic webhook notifications produce only deduplicated, server-bound sync hints
after subscription, tenant, expiration, resource and constant-time client-state
checks. Endpoint validation is a separate pending-registration handshake, not
notification authentication. Rich notifications and lifecycle processing are deferred.

Tests cover malicious cursors, credential redaction, no redirects, bounded response
parsing, pagination, duplicate changes, folder moves and forged notifications.
Rollback means stop using this additive library. No data migration or provider
compensation is needed. Durable per-folder checkpoints, identity enrollment,
folder discovery, subscription lifecycle, scheduling and real-account acceptance
must precede activation.

Sources: [Graph message delta](https://learn.microsoft.com/en-us/graph/api/message-delta?view=graph-rest-1.0),
[immutable IDs](https://learn.microsoft.com/en-us/graph/outlook-immutable-id),
[webhook delivery](https://learn.microsoft.com/en-us/graph/change-notifications-delivery-webhooks).
