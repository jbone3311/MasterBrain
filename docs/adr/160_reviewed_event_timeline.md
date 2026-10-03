# ADR-160 — Bounded reviewed-event timeline

Status: accepted for a synthetic/disposable read-only candidate, pending PR
verification. No live-source or hosted acceptance follows.

## Context

KnowledgeCore stores reviewed, evidence-linked events with optional occurrence
times, but only lexical search, exact expansion and the change feed expose
them. The change feed orders database recording, not event occurrence. The
MasterBrain product needs a chronological, project-filterable read that can
answer “what happened when?” without giving an assistant a broad database
query or treating an undated assertion as a dated event.

## Decision

- Add `GET /v1/knowledge/timeline` under the existing `knowledge.search`
  scope and source-aware assistant enrollment. Require an explicit aware-UTC
  `start` and `end` interval, `[start,end)`, no wider than 366 days, and
  bound pages to 1–50 rows. Include only reviewed events with `starts_at`;
  undated events remain reachable through exact/search/history reads. Return
  event kind/ID, type, title, start/end, optional project ID and direct
  evidence IDs, all marked untrusted. Do not expose the source quote or
  private locators in the compact page.
- Default to ADR-158's source-grant-aware `unsuperseded` review-chain leaves;
  allow explicit `retained` history. A hidden correction or successor cannot
  suppress a visible event. For source-filtered assistants, an event linked to
  a project is returned only if the referenced project is also directly
  source-authorized; otherwise omit it before limit and cursor selection.
  Tenant RLS and transaction-time OIDC grant rechecks remain authoritative.
- Order by `(starts_at,id)` ascending. On the first page, return a database
  transaction-time `recorded_cutoff_at`; later pages must pass that timestamp
  with the opaque event-ID `after` cursor. Rows recorded after the cutoff are
  excluded. Apply that cutoff to visible successors, corrections and their
  replacements as well, so a later review cannot retroactively suppress an
  earlier page's eligible event. Resolve the anchor under the same tenant, interval, project,
  visibility and source filters; a hidden/invalid anchor is indistinguishable
  from an unknown one. This is a recorded-time cutoff, **not a durable MVCC
  snapshot**: a transaction that inserted before the cutoff but commits after
  the first page may enter a later page. A truly frozen cross-request view
  needs a separately designed materialized cursor or commit-order proof.
  Neither mechanism asserts source freshness.
- Add tenant/time and tenant/project/time indexes in a forward migration.
  The ordinary transactional index build is only accepted for synthetic
  alpha; a lock-budgeted/online path is required before large hosted upgrades.
  No event or evidence is rewritten.

## Verification and rollback

Use disposable PostgreSQL for interval edges, same-time tie paging, a late
backdated insert, undated exclusion, project filtering, tenant isolation,
source-hidden events/projects, revocation/hidden cursors, late supersession and
correction visibility across a cutoff, retained history and evidence drill-down. Check invalid
windows/cursors/scopes, documentation, full CI, runtime and restore. Record
only opaque operation codes in audit; do not log title, dates, source quote or
project IDs. Roll back the route/service while preserving additive indexes and
immutable history. FOS-Master and all source effects remain unchanged.
