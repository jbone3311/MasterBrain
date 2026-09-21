# Open-Source Evaluation

## Dedicated PDF worker adoption (2026-09-21)

ADR-034 adds **exactly pypdf 6.19.0**, BSD-3-Clause, to an opt-in `pdf-worker`
extra/image, behind a closed source-bound adapter. No default API/MIME dependency
or automatic intake is added. This extends the fixture-only usage below; Office
readers remain dev-only. Independent structure/text fit and a small pure-Python
surface favor this bounded first reader, not a claim of universal PDF/OCR quality.

Reviewed upstream advisories for
[appearance streams](https://github.com/py-pdf/pypdf/security/advisories/GHSA-php9-fj8v-98fj),
[alphabetical page labels](https://github.com/py-pdf/pypdf/security/advisories/GHSA-w23x-9jrw-r45c),
[embedded-file enumeration](https://github.com/py-pdf/pypdf/security/advisories/GHSA-v247-6f48-mgcj)
and [malformed Flate streams](https://github.com/py-pdf/pypdf/security/advisories/GHSA-jw7q-gvrg-4vj3).
Their documented fixes are in 6.19.0 or earlier. We do not invoke the first three
features; decompression/text parsing still requires hard resource isolation. This
is a selected-advisory review, not exhaustive vulnerability clearance. Keep release
scanning, maintainer/replacement review and real-world extraction evaluation open.
See the [worker limits and integration gaps](PDF_WORKER.md).

## Added development-only format validators (2026-09-21)

The [known-answer mailbox](TEST_MAILBOX_PLAN.md) uses pypdf 6.19.0 (BSD-3-Clause),
openpyxl 3.1.5 and python-docx 1.2.0 (both MIT) as independent readers of our own
generated fixtures. Reuse directly for bounded development tests, not as an
unsandboxed production intake stack. Runtime generation remains standard-library
code and the default deployment image excludes these readers and their added XML
dependency. The later dedicated PDF worker exception is described above.

[pypdf's release history](https://pypi.org/project/pypdf/) shows recent September
2026 releases. [openpyxl](https://pypi.org/project/openpyxl/) last released the chosen
stable version in June 2024; [python-docx](https://pypi.org/project/python-docx/) in
June 2025. Their established format fit justifies narrowly scoped independent
fixture checks; release age and small maintainer teams remain limitations, not
evidence of active weekly updates or production security approval. The lockfile
pins artifacts; live vulnerability scanning and full release provenance remain
separate supply-chain gates. These observations do not refresh historical star/
watcher/commit counts below.

Documentation aligned 2026-09-21. Dispositions below are architecture choices,
not installation receipts. Current dependencies are [pyproject.toml](../pyproject.toml)
and [uv.lock](../uv.lock); pgvector, MCP SDK, IMAPClient and parser frameworks are
not installed merely because direct reuse is recommended. Star/activity figures
remain the dated [snapshot](OSS_HEALTH.md), not live counters.

## Test-data/tool shortlist

Use [TEST_MAILBOX_PLAN.md](TEST_MAILBOX_PLAN.md) for the implemented standard-library
scenario generator and independent dev-only readers. Faker, optional local Mailpit
and Tika/EDRM/Govdocs format references remain prospective. Commercial services
are explicitly distinguished from OSS. No new dependency or external fixture is
adopted by this documentation-only refresh. Each future adoption needs the checklist below;
correspondence/embedded attachment rights need the [per-file gate](PUBLIC_EMAIL_TEST_DATA.md).

## Implemented authenticated encryption dependency

The optional raw-object backend directly reuses the maintained
[`cryptography` AESGCM implementation](https://cryptography.io/en/latest/hazmat/primitives/aead/)
instead of implementing cryptographic primitives. Version 50.0.1 is locked for this
increment (installed metadata: Apache-2.0 OR BSD-3-Clause; upstream
[licenses](https://github.com/pyca/cryptography/blob/main/LICENSE));
authenticated-context, wrong-key, tampering, rotation and publication
tests wrap its use. This library supplies encryption, not cloud KMS, IAM, key
backup or an independently certified deployment. See [storage](LARGE_EVIDENCE_STORAGE.md).

## Method

See [measured repository activity](OSS_HEALTH.md) and the retained JSON snapshot
for exact stars, forks, watchers, 90-day commit counts and dates. These are
prospective dependency selections, not a claim every package is installed.

Projects are assessed on demonstrated maintenance/release activity, tests/documentation, community/adoption, license, security posture, architectural fit, and replacement cost. “Reuse” means a pinned production dependency behind an adapter. “Pilot” means optional and removable. “Reference” means borrow concepts/tests only. Repository activity and licenses must be reverified before adoption.

## Recommended disposition

| Project | Maturity / maintenance / community | License | Fit and disposition |
|---|---|---|---|
| PostgreSQL | Very mature, large ecosystem, managed everywhere | PostgreSQL | **Reuse directly** as multi-user authority, RLS, transactions, FTS |
| [pgvector](https://github.com/pgvector/pgvector) | Active, widely deployed; exact/HNSW/IVFFlat, WAL/PITR benefits | PostgreSQL-style | **Reuse directly** behind repository interface |
| [notmuch](https://notmuchmail.org/) | Long-lived, fast Maildir/MH indexing on Xapian | GPLv3+ | **Reference/pilot only**; excellent search/tagging patterns, but file-centric and copyleft/core mismatch for hosted multi-tenant service |
| [mail-memex](https://github.com/queelius/mail-memex) | Alpha; tiny community; clear SQLite/FTS5/MCP design | License grant not verified; GitHub reports none | **Reference only** for architecture ideas; do not copy code until an actual license is established |
| [Mailgun Talon](https://github.com/mailgun/talon) | Established quote/signature parser and dataset; visible modernization work remains open | Apache-2.0 | **Pilot behind adapter**; benchmark on real multilingual/HTML mail and maintain fallback/replacement |
| Python `email` stdlib | Mature, maintained with Python | PSF | **Reuse directly** for MIME baseline; retain raw bytes and fuzz parsers |
| [IMAPClient](https://github.com/mjs/imapclient) | Mature, production-oriented, UID-first; active September 2026 | BSD (verify distribution license) | **Preferred prospective dependency** for iCloud/generic IMAP protocol layer |
| [imap-tools](https://github.com/ikvk/imap_tools) | Active, ergonomic, no external dependencies, broad operations/IDLE | Apache-2.0 | **Evaluate as alternative**; useful for operations, but avoid dual IMAP stacks in production |
| [sqlite-vec](https://github.com/asg017/sqlite-vec) | Portable and promising; comparatively young/small maintainer surface | MIT/Apache-2.0 | **Optional edge-cache pilot**, never hosted authority; pin, benchmark, keep lexical fallback |
| SQLite FTS5 | Mature SQLite feature | Public domain SQLite | **Reuse** in optional local replica; PostgreSQL FTS in hosted core |
| [Ollama](https://github.com/ollama/ollama) | Popular local runtime, simple packaging/API, structured output support | MIT | **Reuse behind inference adapter** for operator-friendly local deployment |
| [llama.cpp](https://github.com/ggml-org/llama.cpp) | Highly active, broad hardware/runtime adoption | MIT | **Reuse/alternative backend** when tighter control/performance matters; pin build/model formats |
| [Graphiti](https://github.com/getzep/graphiti) | Active temporal-context project with provenance/hybrid ideas; adds graph DB/LLM complexity | Apache-2.0 (verify release) | **Reference and later pilot**; borrow bitemporal/provenance model first, keep relational v1 |
| [MCP specification/SDKs](https://github.com/modelcontextprotocol/modelcontextprotocol) | Rapidly evolving standard with official specs/SDKs | Apache-2.0 (verify component) | **Reuse official SDK**, pin protocol version, front with auth/policy gateway |

## Stronger default alternatives

### Hosted retrieval

Use PostgreSQL built-in full-text search first. If measured retrieval gaps justify
vectors, prefer adding `pgvector` behind the same authorization/data boundary over
introducing a separate vector database. It supports exact and approximate search
([documentation](https://github.com/pgvector/pgvector), rechecked 2026-09-21).
The prospective reuse decision above is conditional, not a requirement to install
it for the read-only pilot. A dedicated search engine needs separate measured
recall/latency/operations justification; a SQLite cache is not hosted authority.

### IMAP

Prefer IMAPClient’s thin UID-centric abstraction for connector correctness. `imap-tools` is a credible higher-level alternative; select one after an iCloud conformance spike. Provider-native APIs remain preferable for Gmail, Microsoft 365, and Fastmail.

### Quote/signature removal

Talon is useful, but do not make cleaned text destructive or singular. Keep raw content, implement deterministic HTML/block-quote handling, and benchmark Talon against modern real mail. A parser ensemble or maintained internal adapter can replace it without re-ingestion.

### Temporal/entity memory

Borrow Graphiti’s episodes/provenance/validity concepts. Do not adopt a graph database or autonomous graph extraction until relational entity/fact queries demonstrate a real limitation. Graphiti describes temporal facts, source episodes, and hybrid graph/keyword/semantic retrieval ([README](https://github.com/getzep/graphiti)).

## Hybrid RAG and MCP references

- Use structured SQL/exact entity lookup + FTS + vectors + rank fusion, not vector-only RAG.
- Keep message storage separate from chunks and derived summaries.
- Expose narrow tools, not `execute_sql` or arbitrary provider calls.
- Follow MCP audience validation and prohibition on token passthrough ([security spec](https://github.com/modelcontextprotocol/modelcontextprotocol/blob/main/docs/specification/2026-07-28/basic/authorization/security-considerations.mdx)).
- `mail-memex` demonstrates FTS5, stable record URIs, deduplicated import, and MCP access, but its own README calls it alpha and shows a very small adopter base—use it as a design sample, not a dependency.

## Rejected-for-now categories

- Elasticsearch/OpenSearch, Qdrant, Weaviate, Pinecone: extra data plane and authorization/backup burden before need is proven.
- Neo4j or another graph database: premature for v1 relational temporal facts.
- Full agent/RAG frameworks: obscure security/data flow and enlarge upgrade surface; use small explicit adapters.
- Generic email-agent repos that auto-send or embed credentials: pattern reference at most.
- Hosted “memory” SaaS: wrong trust boundary for raw private mail unless separately approved.

## Dependency acceptance checklist

Before merge: verify license/NOTICE, current release/commits, maintainer bus factor, security policy/advisories, transitive dependencies, supported platforms, tests, deterministic behavior, data-egress behavior, SBOM/provenance, upgrade/rollback plan, and a contract-test escape hatch. Pin by lockfile/digest and schedule review.

## Additional current alternatives and cautions

- [Inbox Zero](https://github.com/elie222/inbox-zero) is an actively maintained
  product with useful feedback/reply-tracking UX. Its [license](https://github.com/elie222/inbox-zero/blob/main/LICENSE)
  contains additional commercial/organizational restrictions alongside AGPL text.
  Treat it as source-available reference material, not a permissive dependency.
- [Mail-0/Zero](https://github.com/Mail-0/Zero) has substantial stars and MIT metadata,
  but its default branch has no commits in the measured 90-day window and its last
  commit is August 2025. Do not make it our maintained backend foundation.
- [ThunderAI](https://github.com/micz/ThunderAI) offers local-email-client workflow
  ideas, not a substitute for provider-independent synchronization and tenant storage.
- `imap-tools` fetching can mark mail Seen by default; an ingestion adapter must
  explicitly use read-only/PEEK behavior and test it. This is a connector correctness
  issue even though the package itself is legitimate.
- Runtime licenses do not grant model-weight rights. Review each local model's
  license separately. No production model has been selected from benchmarks alone.
- Factory's PDF toolkit optionally imports PyMuPDF; review its AGPL/commercial
  terms before enabling it. Prefer a separately evaluated permissively licensed
  extraction backend if our distribution model cannot meet its conditions.
