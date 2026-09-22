# MasterBrain

MasterBrain is an evidence-first personal and organizational knowledge system. It
combines Email and FileOS source capabilities behind shared ingestion and knowledge
layers, then gives Claude, Grok, ChatGPT, and other authorized assistants compact,
progressive access with drill-down to original evidence.

**Status:** migration foundation and working synthetic-data prototype. The existing
Email capability has executable read-only ingestion, evidence storage, search,
review, recovery, and narrow structured-memory functions. The first FileOS donor
primitive—read-only hashing and duplicate discovery—now lives in DataCore with a
golden parity harness. MasterBrain is not yet a hosted product, and FOS-Master has
not been replaced, renamed, or modified.

The repository name and the internal `email_brain` package remain temporarily for
Git history and compatibility. They identify the original Email capability, not the
final product. New source-neutral code enters through `masterbrain.datacore`,
`masterbrain.knowledge`, and the Brain API boundaries.

## Product shape

```text
Email sources ─┐
               ├─> DataCore ─> KnowledgeCore ─> Brain API ─> authorized LLM clients
FileOS sources ┘       │              │                │
                      └──── immutable evidence <───────┘
```

- **Email capability:** provider change capture, MIME/attachment preservation,
  read-only sync, mailbox search, review, and future reviewed actions.
- **FileOS capability:** in-place file inventory, audited organization, extraction,
  dedupe, metadata, and file search, migrated from FOS-Master only after parity.
- **DataCore:** source-neutral intake, content hashing/dedupe, file and attachment
  extraction, OCR orchestration, normalization, metadata, provenance, chunking,
  indexing, and common database primitives.
- **KnowledgeCore:** evidence-backed entities, relationships, facts/claims, events,
  timelines, projects, commitments, corrections, and unified retrieval.
- **Brain API:** compact summaries first, explicit expansion second, original
  evidence last; every result carries source/provenance references and authorization.

## Current truth

| Capability | State |
|---|---|
| Email ingestion, evidence, PostgreSQL FTS, review/recovery | Working synthetic prototype |
| Typed reviewed travel/bill memory | Working narrow prototype |
| File hashing and read-only duplicate discovery in DataCore | Extracted; donor parity harness added |
| General file intake/extraction/OCR/chunking | Planned migration |
| Reviewed KnowledgeCore assertions and lexical retrieval | Working shared prototype |
| Progressive Brain API and grouped DataCore/KnowledgeCore search | Working shared prototype |
| Hosted identity, operations, live sources | Not accepted |
| FOS-Master cutover or retirement | Explicitly prohibited before parity |

Documentation is authoritative about status only where it distinguishes
**implemented**, **parity-proven**, **integrated**, and **accepted**. A design or
roadmap item is not an implementation claim.

## Documentation map

- [Product contract](PRODUCT.md)
- [Complete feature inventory](docs/MASTERBRAIN_FEATURE_INVENTORY.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Data model](docs/DATA_MODEL.md)
- [Brain API](docs/BRAIN_API.md)
- [Security and privacy](docs/SECURITY.md)
- [Deployment](docs/DEPLOYMENT.md)
- [Roadmap](docs/ROADMAP.md)
- [FOS-Master migration and parity plan](docs/FOS_MIGRATION.md)
- [FOS-Master common tool/test inventory](docs/FOS_TOOL_INVENTORY.md)
- [Incremental execution plan](docs/EXECUTION_PLAN.md)
- [Current build progress](docs/BUILD_PROGRESS.md)
- [Shared DataCore/FileOS commands](docs/DATACORE_COMMANDS.md)
- [Source and provenance contract](docs/SOURCE_PROVENANCE.md)
- [DataCore persistence and lexical retrieval](docs/DATACORE_PERSISTENCE.md)
- [FileOS read-only extraction](docs/FILEOS_EXTRACTION.md)
- [KnowledgeCore reviewed assertions](docs/KNOWLEDGECORE.md)
- [Acceptance criteria](docs/RELEASE_ACCEPTANCE.md)
- [Implementation status](docs/IMPLEMENTATION_STATUS.md)
- [Code map](docs/CODE_MAP.md)
- [Email capability documentation](docs/README.md)

## Migration rule

FOS-Master remains the battle-tested donor and operational reference. Migration is
incremental: inventory a candidate and its tests, preserve provenance, extract it
without intentional behavior change, compare both implementations on a golden
corpus, integrate behind DataCore, then prove operational parity. Only after those
gates may FileOS switch to shared DataCore; folding or renaming FOS-Master is a later,
separately approved decision.

The first tranches are intentionally read-only:

```sh
uv run python scripts/datacore_parity.py --fos-repo ../FOS-Master
uv run pytest -q tests/test_datacore_dedup.py tests/test_datacore_contracts.py \
  tests/test_fileos_snapshot.py tests/test_masterbrain_cli.py tests/test_datacore_stress.py
uv run masterbrain fileos snapshot /authorized/root --source-id files_primary
```

The parity harness compares hash, name, and combined duplicate scans, hashes and pair
comparisons against FOS-Master commit
`218d5caec2f20b9047fd3eb8e027dc671acf0c15`. No deletion or file movement code was
copied.

## Develop and verify

```sh
uv sync --locked --extra dev
uv run ruff check .
uv run mypy src
uv run pytest -q
node --test tests/web_session.test.cjs tests/web_processing.test.cjs tests/web_documents.test.cjs
node --test tests/web_reader.test.cjs tests/web_memory.test.cjs
uv run python scripts/deployment_gate.py
uv run python scripts/check_docs.py
uv run masterbrain --help
```

PostgreSQL tests require a disposable `email_brain_test*` database because the
Email capability retains its existing compatibility identifiers. CI supplies it;
local skips are not passes. Never commit real messages, files, credentials, dumps,
private embeddings, or content-bearing logs. Test fixtures must be synthetic.

Private proprietary product; dependency licenses remain separate.
