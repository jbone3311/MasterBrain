# ADR-162 — Bounded reviewed project dossier

Status: merged through PR #154 at `cf6c656` after exact-head CI,
strict-runtime and restore gates passed; merged-main checks passed too and
are tracked in the build receipt. Not a hosted or live-source acceptance claim.

## Context

KnowledgeCore can exact-read a reviewed project, search linked assertions, and
page occurrence-dated events or due-dated commitments separately. An owner or
authorized assistant still cannot orient around one project in a single,
compact read. Neither chronological window includes undated linked records.
The existing project assertion's state is a reviewer-authored claim, not a
computed or certified live state.

## Decision

- Add `GET /v1/knowledge/projects/{project_id}/dossier` and a matching
  provider-neutral read-client method under `knowledge.search`. Return the
  exact project assertion plus separately bounded linked event and commitment
  lists. Use independent 1–25 limits (default 10) and an optional aware
  recorded-time cutoff; `unsuperseded` is the default, `retained` is explicit.
  Order each list by `(recorded_at,id)` descending and include undated links.
  Return a truncation flag for each list, direct evidence IDs, and compact
  previews; full assertion/evidence expansion remains separately scoped. The
  project itself is the exact requested assertion, even if a later reviewed
  project version exists; visibility selection applies to the linked lists.
- Query both groups and the project inside one tenant-bound transaction.
  Enforce direct source grants on the project and every linked assertion before
  limiting. A commitment must also pass grants on its owner and counterparty;
  visible review-chain successors/corrections only may suppress a predecessor.
  Keep the existing transaction-time assistant grant/revocation check and
  forced RLS. Unknown, hidden, wrong-kind, or cutoff-invisible project IDs are
  indistinguishable as not found. Audit a fixed operation code, not titles,
  dates, or descriptions.
- This is a **dossier of reviewed assertions**, not a project-state reducer.
  It does not resolve contradictory branches, infer overdue status, check
  valid-time truth, or certify source freshness. The recorded cutoff limits
  rows and review-chain effects, but is not a durable cross-request MVCC
  snapshot if an earlier-recorded transaction commits late.
- Add partial `(tenant_id,project_id,recorded_at DESC,id DESC)` indexes for
  linked events and commitments in an append-only forward migration; neither
  assertion heap nor evidence is rewritten. The current transactional index
  build is acceptable only for synthetic alpha. A populated hosted upgrade
  requires an independent lock budget and online-index plan.

## Verification and rollback

Verify closed request bounds, route scope, missing/hidden project behavior,
source-grant filtering before limits, retained/unsuperseded chains, cutoff,
undated links, separate truncation flags, evidence links, order, tenant RLS,
client response validation, and populated no-rewrite migration. The local
test requires disposable PostgreSQL; exact-head CI, strict-runtime and
restore gates passed before merge. Rollback removes the read route
and client method; the additive indexes and immutable assertions may remain.
This grants no source action, automatic candidate pipeline, hosted identity,
or FOS-Master cutover.
