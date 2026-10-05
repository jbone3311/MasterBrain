# ADR-161 — Bounded reviewed commitments due

Status: accepted and merged through PR #152 with exact-head and merged-main
CI, strict-runtime and restore passed. Hosted and live-source acceptance
remain separate.

## Context

KnowledgeCore stores reviewed commitments with an optional due time, state,
project, owner and counterparty. Lexical search and exact expansion expose
them, but cannot answer a bounded due-window question in chronological order.
The event occurrence timeline (ADR-160) deliberately excludes commitments.

## Decision

- Add `GET /v1/knowledge/commitments-due` under `knowledge.search` and a
  matching provider-neutral read-client method. Require an aware `[start,end)`
  window no wider than 366 days. Return 1–50 commitments per page ordered by
  `(due_at,id)`, with optional exact project and state filters. Undated
  commitments stay in search/history. Each compact row carries an opaque ID,
  state, due time, optional related IDs, a maximum 300-character untrusted
  description preview, a truncation flag and direct evidence IDs; full text
  and source quote require existing exact expansion.
- Reuse ADR-160's first-page database recorded-time cutoff and keyset paging.
  Later pages must supply both cutoff and opaque commitment-ID cursor. Apply
  the cutoff to returned rows and to visible successors, corrections and
  replacements. Resolve the cursor under the same window, filters, visibility
  and current source grants; a hidden or mismatched anchor is not found.
  `unsuperseded` is the default, `retained` is explicit. The cutoff is **not**
  a durable MVCC snapshot: an earlier-recorded transaction that commits late
  may enter a later page.
- For source-enrolled assistants, every direct evidence link of the commitment
  and each referenced project, owner and counterparty entity must be visible
  before ranking/limit. A successor or correction can suppress an older row
  only when its own direct evidence and all of its related references are
  visible. The database's forced RLS and transaction-time grant check remain
  authoritative. This is a reviewed assertion view, not a promise that the
  state is currently true or the underlying sources are fresh.
- Add partial tenant/due and tenant/project/due indexes in a forward migration.
  Do not rewrite assertion or evidence rows. The transactional index build is
  suitable only for the current synthetic alpha; hosted large-table upgrades
  need an independent lock budget and online plan.

## Verification and rollback

Test date boundaries, same-time paging, null due dates, state/project filters,
retained and unsuperseded review chains, correction cutoff, hidden direct and
related-object sources, revoked/invalid cursors, tenant isolation, evidence
drill-down, request/response validation and a populated no-rewrite migration.
Audit only a fixed operation code, never description, dates or related IDs.
Stop exposing the route/client on rollback; preserve the additive indexes and
immutable history. This change grants no source effect, automatic candidate
extraction, hosted assistant acceptance or FOS-Master cutover.
