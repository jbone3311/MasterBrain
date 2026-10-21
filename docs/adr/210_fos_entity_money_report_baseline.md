# ADR-210 — Isolated FOS entity and numeric-fact report comparison

Status: accepted for synthetic, nonpublishing comparison only. Extends
[ADR-209](209_fos_report_baseline.md); it neither activates a Brain API report
nor grants an assistant authority to present extracted amounts as investments.

## Donor authority and behavior

Use unchanged FOS-Master commit `218d5caec2f20b9047fd3eb8e027dc671acf0c15`,
`_SYSTEM/tools/reporting.py`, SHA-256
`e52ee7672121a609171a827eab086080dcea159ef987e21f0793e32528521cc9`.
The remaining three donor reports are `top_entities`, `entity_crossdomain`
and `dollars_by_domain`. The donor groups entity rows by canonical name **and
type**, not entity ID; counts each mention including duplicates; excludes
NULL domains from distinct spread; and filters `top_entities` before grouping.
Its `STRING_AGG(DISTINCT domain)` does not specify internal domain order, so
comparisons normalize only that presentation list. Equal-ranked report rows
likewise have no donor tie-order contract. The numeric report sums **all**
non-NULL `money` facts by domain, regardless of currency, ownership, overlap,
date, source trust or whether the fact is an asset, debt or transaction. It
cannot be interpreted as a portfolio, company investment total or balance.

## Comparison and limits

Add pure, bounded row aggregators alongside ADR-209's coverage and timeline
comparisons. No database, network, source grant, currentness or effect is
available to this module. Keep explicit fictional goldens for type separation,
duplicate mentions, NULL domains, filtered and empty output, negative values,
numeric rounding, and 10,000-row input bounds. The donor DuckDB `ROUND` uses
half-away behavior; Python's built-in ties-to-even gave a different average
on the first direct replay and was corrected before this decision was
accepted. Reject non-finite amounts as a deliberate fail-closed divergence
outside the valid numeric corpus. Execute the exact-hash pinned donor functions locally against
fictional SQLite through DuckDB's SQLite extension; compare 1,000-row repeats.
Hosted checks without the private donor checkout or DuckDB dependency run
goldens but must not be described as direct donor parity. Omit only the donor
wall-clock `generated_at`; normalize unordered domain lists and equal-rank
row order in comparison.

## Next gates and rollback

Before any product report, define an authorized, current-source projection
from DataCore and KnowledgeCore with evidence IDs, visibility fencing,
currency/unit normalization, deduplication, contradictory claim handling,
reviewed versus proposed facts, and a known-answer fictional company dossier.
Then test denial, revocation, stale versions, pagination and stress through
Brain API, with hosted full and restore gates. No generic donor `grand_total`
may be reused as financial truth. Rollback removes these pure functions and
tests only; no stored data, donor file or public route changes.
