# Reviewed rules: working prototype workflow

In the local owner screen, propose an exact sender-domain rule, approve it in the
queue, preview the bounded sample, then separately activate its receipt. Search
again to see current category and virtual review labels. “Restore revision” appends
a new version of the earlier labels. Neither activation nor rollback changes the
provider mailbox, evidence bytes, search visibility, or message deletion state.

This is the first working feedback loop, not general autonomous learning. Project,
fact, feature and correction proposals are still recorded/reviewed only. The local
model library is not automatically connected to rules or ingestion.

## Implemented REST contract

All paths require a current owner membership and server-bound tenant identity.

| Request | Scope and behavior |
|---|---|
| `GET /v1/rules` | `email.search`; active revision and at most 100 exact-domain rules |
| `POST /v1/proposals/{uuid}/simulation` with `expected_version` | Human + `email.review` + `email.search`; approved rule only, exact proposal version |
| `POST /v1/rules/activations` with `simulation_id` | Same human actor/scopes; fresh receipt and unchanged base revision |
| `POST /v1/rules/rollback` with `expected_revision`, `target_revision` | Same human scopes; current revision must match; target earlier, zero means empty |

Simulation returns `id`, `proposal_version`, `base_revision`, `expires_at`, and
`sample` (message IDs and before/after effects). Coverage is always `bounded_sample`:
at most 50 currently live, nonquarantined messages ordered by ID. It is not a random
accuracy evaluation or guarantee about the entire mailbox. Incoming mail may change
after preview. Receipts expire after 15 database-clock minutes.

Activation returns the new revision and `replayed: false`. Retrying the same receipt
returns its original committed revision and `replayed: true`, even after a later
rollback; that replay never makes the historical revision active again. Read
`GET /v1/rules` for current state. Competing/stale/expired operations return 409;
foreign or other-owner receipts return 404. Rollback retries with an obsolete
expected revision return 409; inspect current state before another decision.

Search results include `classification` with `rules_revision`, `effects`,
`matched_rule_versions` and `virtual_only: true`. These are read-time derived labels,
not evidence facts or an executor authorization. Search results already on screen
are snapshots; refresh after any rule change. Domain matches are exact and do not
include subdomains; one active rule per domain, with explicit replacement via a new
proposal. Header domains can be spoofed and must never grant access or hide mail.

[ADR-044](adr/044_review_fixes.md) requires source-derived sender eligibility in
the current immutable snapshot. Exactly one defect-free From header with one
valid mailbox is eligible; duplicate headers, multiple authors, groups, missing,
malformed or overlength senders are not. Ambiguous sender becomes empty in the
normalized projection, but original MIME, valid body and attachments remain intact.
Search (including attachment/PDF hits) and simulation use the same exact-boolean
gate. This checks syntax/ambiguity, **not sender authenticity**.

Historical snapshots without the flag no longer receive sender-rule effects.
They remain searchable/readable; separately authorized reprocessing must publish
a new version before they can match. No automatic bulk backfill or evidence edit
is performed. Old simulation receipts remain historical samples, not proof that
current results will match. Rule schemas and mailbox permissions are unchanged.

## Database / deployment / rollback

Apply new migration `0007_reviewed_rules.sql` using the administrator migration path,
then re-run runtime grants to add SELECT/INSERT on `rule_simulations` and
`rule_revisions`. Neither table permits runtime UPDATE/DELETE; immutable triggers,
FORCE RLS and composite tenant keys preserve history. Tenant advisory locks serialize
changes. Revision zero is implicit, highest revision is current. No model, provider
network call, broad SQL, scheduled job or cloud resource is added.

Operational rollback: restore a previous virtual rule revision. Application rollback
to the prior binary can leave additive tables in place; do not drop evidence/history
or rewrite a migration checksum. Production retention for these receipts, high-volume
simulation limits, protected-sender configuration, richer predicates and denial-audit
export remain future work. Before mailbox automation, protected keep rules and full
action previews must be implemented; Review Delete here is merely a suggestion.

Tests: `tests/test_rule_control.py`, `tests/test_rule_control_security.py`,
`tests/web_session.test.cjs`; real database tests run in CI, not mocked SQL.
See [ADR-025](adr/025_reviewed_rule_activation.md),
[security policy](SECURITY.md), [rules target](RULES_AND_FEEDBACK.md).
