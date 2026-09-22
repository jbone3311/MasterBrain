# Tools discussion: extraction, indexing and realistic testing

Reviewed 2026-09-21. **Research and proposed trials, not dependency approval or
implementation.** No package, model, service, account or fixture was installed by
this change. This discussion complements [OSS evaluation](OSS_EVALUATION.md)
and preserves the older [health snapshot](OSS_HEALTH.md).

## Recommendation for Jim and Factory

Evaluate KItinerary for travel first. Compare Docling and Apache Tika on attachment
formats that our existing bounded readers cannot handle well. Add OCR only when
scanned-document tests justify it. Consider Mailpit for a local synthetic mail lab.
Keep PostgreSQL authoritative; add pgvector only after measuring search gaps.
Use MimeKit as an independent parsing reference before considering another runtime.

These are complementary roles, not seven packages we must install. None requires
a hosted vendor account for its self-hosted use; operation, hardware and maintenance
still have costs. Community maintenance is not a contractual support guarantee.

## Ranked shortlist

| Package | What it would contribute | Preliminary license observation | Proposed disposition |
|---|---|---|---|
| [KItinerary](https://github.com/KDE/kitinerary) | Typed travel details from reservation emails, tickets and calendar documents | Mixed component licenses; GitHub reports NOASSERTION, so inspect pinned files/dependencies | First isolated extraction trial; reuse engine intact behind our adapter |
| [Docling](https://github.com/docling-project/docling) | Layout-aware documents, tables, OCR and structured output | Main package MIT; models and transitive dependencies need separate review | Compare on difficult PDFs and Office attachments; optional worker, not default intake |
| [Apache Tika](https://tika.apache.org/) | Broad file identification, metadata and text extraction | Apache-2.0; transitive components still need review | Compare as broad-format fallback; do not deploy alongside Docling without a demonstrated need |
| [OCRmyPDF](https://github.com/ocrmypdf/OCRmyPDF) | Searchable text layer for scanned PDFs | MPL-2.0 core; other components have different terms | Conditional OCR worker, only if simpler/document-stack OCR is inadequate |
| [MimeKit](https://github.com/jstedfast/MimeKit) | Independent MIME, encoding, nested-message and TNEF parsing reference | MIT | Differential test candidate; do not replace Python email parsing without evidence |
| [Mailpit](https://github.com/axllent/mailpit) | Local SMTP capture, attachment inspection and testing API | MIT | Development-only trial with fictional mail and no forwarding |
| [pgvector](https://github.com/pgvector/pgvector) | Semantic retrieval inside our existing PostgreSQL boundary | PostgreSQL License; API classifier reports NOASSERTION | Conditional retrieval benchmark; retain exact text/structured search |

License labels are screening observations, not legal clearance. NOASSERTION means
the GitHub classifier did not identify a standard license; it does not establish
that a project has no license. Inspect release artifacts, notices and all bundled
components before adoption or distribution.

## Maintenance evidence, not popularity-based approval

Public GitHub REST repository metadata was read on 2026-09-21. All seven repositories
reported `archived: false`. The table records `pushed_at`, which is not necessarily
a substantive default-branch code change or release. Watchers are notification
subscribers, not users; stars are interest, not quality. No commit-window counts,
maintainer response-time study or full security audit were performed in this pass.

| Repository / metadata source | Stars | Watchers | Last push, UTC |
|---|---:|---:|---|
| [KDE/kitinerary](https://api.github.com/repos/KDE/kitinerary) | 45 | 2 | 2026-09-16 04:54:45 |
| [docling-project/docling](https://api.github.com/repos/docling-project/docling) | 67,560 | 227 | 2026-09-21 15:53:55 |
| [apache/tika](https://api.github.com/repos/apache/tika) | 4,071 | 89 | 2026-09-21 14:09:46 |
| [ocrmypdf/OCRmyPDF](https://api.github.com/repos/ocrmypdf/OCRmyPDF) | 34,835 | 193 | 2026-09-16 23:20:07 |
| [jstedfast/MimeKit](https://api.github.com/repos/jstedfast/MimeKit) | 2,002 | 89 | 2026-09-21 15:40:07 |
| [axllent/mailpit](https://api.github.com/repos/axllent/mailpit) | 10,411 | 26 | 2026-09-20 05:27:22 |
| [pgvector/pgvector](https://api.github.com/repos/pgvector/pgvector) | 23,120 | 143 | 2026-09-10 13:49:14 |

These sources are live endpoints; this table is the dated observation, not a live
counter. KDE develops on its own infrastructure, so its GitHub mirror's audience
does not describe its entire community.

## KItinerary: reuse the engine, not the whole application

The engine documents use by KDE Itinerary, KMail and Nextcloud Mail, and exposes
a command-line interface returning structured reservation data. That is a useful
boundary for our Python service. Its extraction/post-processing is documented as
offline. [Engine architecture](https://github.com/KDE/kitinerary)

The September 10, 2026 application release lists extractor improvements for Air
Canada, Booking.com and Lufthansa; KDE separately publishes the signed KItinerary
26.08.1 source package. This is stronger evidence of relevant maintenance than
stars alone. [Release notes](https://apps.kde.org/itinerary/),
[source release](https://kde.org/info/releases-26.08.1/)

Trial shape: source-bound email/attachment -> isolated extractor -> bounded typed
candidate -> our evidence/review boundary. Email Brain retains ownership of
identity matching, conflicts, history, permissions and publication. Keep the
upstream engine intact so fixes remain adoptable; do not fork scattered parsers
without a maintenance owner. The inspected CI configuration includes a legacy
standalone build environment; independently review artifact dependencies rather
than assuming a downloaded binary is cleared.
[CI configuration](https://github.com/KDE/kitinerary/blob/master/.gitlab-ci.yml)

Test exact airline/hotel variants, forwarded bookings, multiple travelers,
cancellations and time zones. The upstream list explicitly has coverage gaps.
[Provider list](https://community.kde.org/KDE_PIM/KItinerary/Supported_Providers)

## Docling versus Tika: fidelity versus broad coverage

Docling offers structured layout/table extraction and local execution. It originated
at IBM Research and is hosted by LF AI & Data. That gives it institutional/community
signals, not a guarantee about any individual output. Its recent activity makes it
worth evaluating for financial statements and complex attachments. Do not assume
MIT on the main package covers downloaded model weights or every optional backend.
[Project organization](https://github.com/docling-project),
[capabilities](https://github.com/docling-project/docling)

Tika is an Apache Software Foundation project covering text/metadata extraction
from over a thousand formats. Its August 21, 2026 release is 4.0.0; 3.3.2 remains a
supported maintenance line. Version 4 changes packaging and requires Java 17.
Choose a supported version after compatibility/security review, not just the
largest version number. Disable remote-model and URL-fetching paths in any trial.
[Tika news](https://tika.apache.org/), [downloads](https://tika.apache.org/download)

Run both against the same fictional invoices, tables, multi-column PDFs, Word and
Excel fixtures. Score reading order, table cells, page/location provenance, decimal
and date fidelity, memory, latency and failure reporting. Select one initially;
retain the existing pypdf worker for straightforward supported PDFs unless evidence
justifies replacing it. A spreadsheet parser must not execute macros, refresh
external links, or silently treat missing cached formula results as zero.

## OCRmyPDF: conditional help for scans

OCRmyPDF creates searchable derivatives of scanned documents. Its release page
shows v17.12.1 on September 16 and detailed fixes to the surrounding PDF pipeline.
That is useful evidence of ongoing maintenance, not proof all malformed PDFs are
safe. Preserve the original bytes; OCR output is derived evidence and can misread
amounts or account identifiers. [Repository](https://github.com/ocrmypdf/OCRmyPDF),
[release notes](https://github.com/ocrmypdf/OCRmyPDF/releases)

Review the selected release's OCR engine, PDF renderer, optional codecs and model
licenses as a complete bundle. Compare with Docling's OCR first; avoid two expensive
OCR paths for the same page without measured benefit. No OCR output is a virus scan.

## MimeKit and Mailpit: confidence in the email plumbing

MimeKit supplies a separate .NET MIME implementation with tests and a security
policy. It is useful for differential checks of our synthetic encoded headers,
nested messages and unusual attachments. Parser disagreement should produce an
investigation, not an automatic assumption that either parser is correct. Adding
.NET to production solely for routine MIME parsing is not justified yet.
[MimeKit](https://github.com/jstedfast/MimeKit)

Mailpit captures SMTP messages and exposes a UI/API, including MIME attachments.
It could make generated scenarios easier to inspect. Bind explicitly to loopback
or an isolated test network; its documented defaults listen on all interfaces.
Disable relaying, forwarding, link checks and remote image fetching. It is not a
Gmail History, Graph delta, JMAP or IMAP simulator and cannot replace connector
contract tests. [Mailpit capabilities/defaults](https://github.com/axllent/mailpit)

Use our [known-answer generator](TEST_MAILBOX_PLAN.md); do not download real-mail
corpora or copy upstream fixtures without the [rights/privacy gate](PUBLIC_EMAIL_TEST_DATA.md).

## Search and other tools already considered

pgvector remains the preferred prospective vector extension, not a new database.
Benchmark tenant/account-filtered recall as well as latency: its documentation
notes that approximate-index filtering can return too few results and describes
iterative scans. Authorization must still be enforced independently of ranking.
[pgvector documentation](https://github.com/pgvector/pgvector)

Keep IMAPClient/imap-tools, Talon, notmuch, Ollama/llama.cpp, sqlite-vec and Graphiti
in the existing [evaluation](OSS_EVALUATION.md). This pass does not refresh their
older measurements. Graphiti remains a temporal-memory design reference before
a graph-database pilot; whole email-agent/RAG frameworks are not default additions.
Stalwart's Rust mail-parser is a possible later MIME comparison candidate, but its
release/license/maintenance review was not completed here, so it is not approved.

## Cross-cutting design discussion to retain

The [current memory slice](STRUCTURED_MEMORY.md) records mailbox-check time and
reviewed-record changes. Future processing coverage must separately identify
pending, failed and unsupported source versions; mailbox sync does not mean all
mail has been interpreted. Assistants need a durable change cursor, not timestamps
alone, and evidence invalidation must be visible without silently cancelling a trip.
Time-based reminders are another planned event source even when no mail arrives.

Try embedded reservation markup before LLM extraction. Parse it as bounded inert
data, with no script execution or remote context resolution; markup does not prove
the booking is genuine or live. [Google reservation markup](https://developers.google.com/workspace/gmail/markup/reference/flight-reservation)

Keep field-level evidence, conflicting sources, effective versus observed dates,
exact search, semantic retrieval and structured queries distinct. These are design
requirements under discussion, not capabilities supplied automatically by a package.

## Trial acceptance and open questions

Before implementing an integration, Factory must write the applicable ADR and:

1. Identify the exact capability gap and baseline; pin a release/artifact digest.
2. Inspect maintainer concentration, recent substantive changes, issues, advisories,
   licenses/NOTICE, complete dependency inventory and model provenance. Record
   what could not be verified; repository counters are not clearance.
3. Define an isolated no-network worker with no provider/database credentials,
   bounded bytes/pages/nesting/time/memory/output and explicit failure outcomes.
4. Evaluate held-out synthetic known-answer cases, including malformed documents,
   ambiguity, contradictions, duplicate evidence and attempted prompt injection.
5. Agree field-specific quality thresholds before scoring; report abstentions,
   missed facts and false facts separately from schema-valid output.
6. Version extracted evidence by source hash and extractor/model configuration;
   preserve originals and make reprocessing, cancellation and rollback explicit.
7. Assign upgrade/security ownership and document replacement/export paths.

Questions to settle through those trials, not by installing everything:

- Which representative travel templates are covered without a model?
- Does Docling add enough table fidelity to justify its resource footprint?
- Does Tika cover important formats that the smaller readers cannot?
- Is separate OCRmyPDF worthwhile once document-stack OCR is measured?
- Can the same versioned worker contract be reused by Factory without making
  Email Brain depend on Factory being online?
- What is the acceptable review burden, and which fields must never auto-publish?

Publication of this discussion does not change roadmap priority, approved security
boundaries, dependency locks, runtime behavior or deployment. Adoption requires a
separate implementation decision and verified tests.
