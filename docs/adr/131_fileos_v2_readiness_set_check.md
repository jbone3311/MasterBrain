# ADR-131 — Indexed FileOS v2 readiness closure

Status: accepted for synthetic/disposable performance correction; v2 activation remains forbidden.

## Context

ADR-126 requires PostgreSQL to prove that every v2 generation chunk exactly
matches its retained base chunk. Migration 0047 uses a wide left anti-join
against all tenant `brain_chunks`, followed by a base-chunk count. Under a
populated disposable PostgreSQL 17 database, the 3,000-hashed-row readiness
test has intermittently exceeded the existing five-second statement limit;
an isolated run passes. The server log identifies the anti-join inside
`enforce_index_generation_ready()`, with forced tenant RLS in the plan.
The [tracked finding](https://github.com/jbone3311/MasterBrain/issues/84)
is not evidence of wrong membership, but a readiness gate that is not reliably
usable at its accepted stress size.

## Decision

- Keep every v1/v2 count, item-membership, source-lock, immutable receipt and
  activation refusal unchanged. Do not raise the statement timeout.
- Replace only the wide v2 anti-join with one primary-key lookup per generation
  chunk, fenced by a lateral subquery so PostgreSQL cannot replan it as a
  population-sensitive join under forced tenant RLS. Compare ID, document,
  ordinal, offsets, text and SHA-256 without a digest-only shortcut. The
  existing base-chunk count also uses one indexed document probe per item.
  That count plus the generation-chunk count prove that zero unmatched rows
  means exact membership in both directions.
- Ship the replacement as a forward-only migration. Do not edit applied 0047,
  rewrite historical receipts, change current FileOS reads or touch FOS-Master.

## Acceptance and rollback

Run the 3,000-row v2 preparation/readiness case repeatedly after a populated
full suite, including a fresh database. Preserve direct-SQL wrong-text,
missing/extra-chunk and nonactivation regressions; run full PostgreSQL,
browser, strict runtime, populated restore and pinned donor parity. Record
wall time and query-plan evidence without logging source content. If the
bounded check still times out, leave the issue open and do not merge a claim
of resolved readiness. Rollback stops new v2 generation builds and uses
forward repair or a tested restore; prior ready receipts remain immutable.

An initial `EXCEPT ALL` candidate passed the isolated 3,000-row test but
timed out in the same readiness statement during a populated full-suite run.
The first indexed revision moved the timeout to the unchanged, wide base-count
join; neither candidate was committed. Under the runtime role, indexed lateral
lookup and per-document counting measured 25 and 28 ms respectively on a
committed 3,000-chunk synthetic generation. Fresh and populated end-to-end
results still control acceptance.
