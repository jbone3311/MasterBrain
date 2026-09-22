# ADR-047 — MasterBrain identity, shared cores, and safe FileOS migration

Accepted 2026-09-21 for the migration foundation. This decision does not authorize a
live source, FileOS cutover, file effect, FOS-Master rename/retirement, or cloud spend.

## Decision

Rename the final product concept to MasterBrain while retaining EmailBrain as an
internal Email capability and compatibility package. Introduce source-neutral
boundaries: DataCore for intake/evidence/extraction/indexing and database primitives;
KnowledgeCore for evidence-backed knowledge; Brain API for progressive client access.

Treat FOS-Master as an unchanged, battle-tested donor. Migrate in bounded tranches
with pinned provenance, synthetic golden corpora, live-donor comparison, read-only
shadowing, rollback and explicit acceptance. Effects migrate last.

The first tranche copies the dependency-free, read-only hash/dedupe behavior from
`_SYSTEM/tools/dedup_tool.py` at FOS-Master commit
`218d5caec2f20b9047fd3eb8e027dc671acf0c15` into
`masterbrain.datacore.dedup`. It preserves result/default semantics for hashing,
filtering, duplicate/name grouping and pair comparison. It intentionally omits donor
CLI, config discovery, logging and every move/delete path.

## Consequences and verification

Historical Email identifiers remain in imports, migrations and compatibility command
to avoid a destructive big-bang rename. New shared code uses the MasterBrain package.
A live-donor harness compares hash/name/both scans over a synthetic corpus; unit tests
pin core outputs. Any intentional donor divergence requires a later ADR.

Rollback removes the new package/alias/docs and leaves the Email capability and
FOS-Master untouched. No data migration or external compensation is required.
