# ADR-209 — First isolated FOS intelligence-report parity baseline

Status: accepted for synthetic, nonpublishing comparison only. This does not
enable a financial report, certified coverage, portfolio total, live source,
assistant claim or FOS-Master cutover.

## Donor and risk

The read-only donor authority is FOS-Master commit
`218d5caec2f20b9047fd3eb8e027dc671acf0c15`, path
`_SYSTEM/tools/reporting.py`, SHA-256
`e52ee7672121a609171a827eab086080dcea159ef987e21f0793e32528521cc9`.
`report_data_collector.py` collects fleet/file/database metrics, not the five
intelligence reports. The donor's `reporting.py` queries a SQLite index and
returns `dollars_by_domain`, `top_entities`, `coverage`, `entity_crossdomain`
and `timeline`. Its money report sums all numeric money facts by domain; that
is **not** an investment balance and must not be presented as one. Its
`coverage_pct` includes extracted, failed and skipped documents as completed,
while `overall_pct` counts only successful extraction. Neither is a source-
freshness certificate.

## First comparison slice

Extract only the deterministic row-aggregation behavior of `coverage` and
`timeline` into a pure, bounded comparison module. Keep the donor's status
codes, NULL/empty handling, domain filter truthiness, year-prefix grouping,
row counts and distinct percentage denominators. Omit the wall-clock
`generated_at` field from parity comparisons. Do not connect the candidate to
Brain API, KnowledgeCore, FileOS current search or a live database.

Use fictional SQLite rows to run the exact pinned donor functions locally
through a narrow AST loader, comparing their data output to the candidate.
Keep explicit expected goldens so CI without the private donor checkout still
checks the adopted behavior. Include empty, filtered, failed/skipped/pending,
malformed date and large-repeat cases. A missing donor checkout may skip only
the direct donor replay; it cannot turn hosted goldens into a parity claim.

## Next gates and rollback

The later [ADR-210](210_fos_entity_money_report_baseline.md) compares the
remaining three row shapes, including entity grouping, cross-domain spread,
duplicate mentions, unsupported money totals and report ordering. Source
grants and time/currentness remain product gates. Then design a
MasterBrain-native report over authorized evidence and reviewed assertions;
the donor schema is not a runtime contract. Rollback removes this isolated
candidate and tests; no persisted data or donor files change.
