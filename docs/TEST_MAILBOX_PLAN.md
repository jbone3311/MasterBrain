# Believable test mailbox and attachment plan

Updated 2026-09-21. **A bounded known-answer generator/exporter and paced synthetic
database feeder are now implemented.** No SMTP/capture server, always-on hosted feed,
public corpus import, testing subscription or live mail delivery. Broader format,
model-quality and soak requirements below remain open. [ADR-033](adr/033_known_answer_synthetic_mailbox.md)
records the boundary; [build receipts](BUILD_RECEIPT.md) record executed checks.

## Run the implemented mailbox

Export a new local packet, without a database or any provider account:

```sh
uv run email-brain export-test-mailbox --seed 42 --projects 3 --output-dir /private/tmp/email-brain-mailbox-42
```

Use a new absolute output folder outside Dropbox/the source checkout, with existing
non-symlink parents (`/tmp` is often a symlink on macOS; use `/private/tmp`). Existing
files/folders are refused, never overwritten. Fixed generated filenames contain no
mail-derived paths. Files are 0600 and the folder 0700. `manifest.json` is written
last; treat nonzero exit or an absent/invalid manifest as an incomplete packet.
Partial outputs are retained for inspection; choose another new directory to retry.

For a fresh initialized synthetic account, use this **instead of** `seed-demo` or
`seed-corpus`. Keep `demo.json` in its private 0700 state directory, mode 0600, and
supply only the runtime DSN through the trusted environment:

```sh
uv run email-brain seed-test-mailbox --state-dir /srv/email-brain-private/demo --seed 42 --projects 3 --max-events 10
uv run email-brain seed-test-mailbox --state-dir /srv/email-brain-private/demo --seed 42 --projects 3 --max-events 100 --interval-seconds 2
```

The first command advances at most ten scheduled events. The next resumes the
same manifest; a completed run is a no-op. `--interval-seconds` is a fixed optional
wall-clock delay between events (0–60), not a claim of production-realistic timing.
The manifest separately records varied logical arrivals and out-of-order source dates.
SIGINT/SIGTERM stop after in-flight work; SQL checkpoints survive interrupted output.
Conflicting feeders stop safely and can resume; they do not reset each other's cursor.

Bounds: seed 0–2147483647, 1–500 projects, at most 7,500 scheduled events, and
`--max-events` 1–7500 (default 100). Default three projects produce **36 source
messages and 45 scheduled events**. Each project has 12 source messages, one exact
duplicate delivery, one metadata update and one simulated provider tombstone:
14 unique provider events, ten ready messages, one quarantined and one deleted
current projection. Deletion is internal test input, never a mailbox command.

The manifest is tenant-neutral and hashes generator version, seed, source bytes,
attachment bytes, dates, IDs and expected outcomes. Ingestion binds it to the
existing private demo account/tenant and a manifest-hash cursor. A changed seed,
project count, byte format or unrelated cursor requires a new synthetic account.
Account ownership, active status and unenrolled synthetic binding are enforced,
including again inside every ingestion transaction. No arbitrary packet import.

Search markers from `manifest.json`, for example `rentproofs42p0000`, to find both
rent-roll CSV revisions. `pdfproofs42p0000` must currently return no hits: it exists
only in the deferred PDF. Both revisions remain source evidence; no automatic
project/entity/fact/reply-state implementation is implied.

## Current file and scenario coverage

Connected request/package/correction/receipt/confirmation conversations; original
and revised XLSX/CSV, text PDFs, minimal DOCX, a PNG floor-plan diagram and its
image-only PDF, same-UID ICS reschedule, forwarded EML, ZIP, a deliberately truncated
PDF, inert hostile instruction text and malformed Unicode MIME. PDF/Office/PNG/ZIP/
nested-message extraction remains deferred; text/CSV/calendar outcomes are checked.
The image-only PDF is a diagram, **not a scanned-text OCR-quality fixture**. Password-
protected files, JPEG, more varied business layouts and large soak sets remain gaps.

The generator uses deterministic standard-library format construction and fixed
MIME/ZIP/PDF metadata; independent dev-only readers validate generated formats:

| Reader | Resolved version / license | Fit and limits |
|---|---|---|
| [pypdf](https://pypi.org/project/pypdf/) | 6.19.0 / BSD-3-Clause | Strict PDF structure/text check; release September 16, 2026; not malware scanning or OCR |
| [openpyxl](https://pypi.org/project/openpyxl/) | 3.1.5 / MIT | Independent worksheet values with read-only/no-link retention; stable release June 28, 2024, not evidence of recent releases |
| [python-docx](https://pypi.org/project/python-docx/) | 1.2.0 / MIT | Independent paragraph read; release June 16, 2025; small maintainer base and limited fixture scope |

Versions observed September 21, 2026 and pinned with hashes in `uv.lock`; this is
not a fresh vulnerability audit. These readers validate our generated files,
not unsandboxed production intake. ADR-034 subsequently adds pypdf to a separate
optional [restricted PDF worker](PDF_WORKER.md); Office readers remain dev-only.
CI checks they and the added `lxml` dependency are absent from the runtime image.
No new core runtime dependencies. The separate PDF worker does not change this
generator's current ingestion/search expectations. See [PDF text limits](https://pypdf.readthedocs.io/en/stable/user/extract-text.html),
[read-only workbook API](https://openpyxl.readthedocs.io/en/stable/api/openpyxl.reader.excel.html),
and [DOCX stream support](https://python-docx.readthedocs.io/en/stable/user/documents.html).

## What exists now

- `seed-corpus` generates a resumable fictional inbox, bounded to 10,000 messages.
  It writes through the synthetic database pipeline, not SMTP or a real provider.
- `tests/attachment_samples.py` constructs deterministic MIME cases with actual
  harmless attachment bytes; format/provider tests verify structure and preservation.
- CI exercises a 256-message synthetic HTTP-to-Postgres import, incremental changes,
  malformed mail and history-expiry reconciliation. This is not a sustained load test.
- Plain/CSV and bounded calendar text can become searchable. PDF/Office/image/archive
  handling currently proves receipts/deferral, not successful binary extraction.

See [local development](LOCAL_DEVELOPMENT.md) for commands. Do not create a second
disconnected ingestion implementation just for the demo.

## Broader generator requirements (partly implemented above)

Generate a fictional world first: organizations, people, projects, invoices and
deadlines. Produce messages and their attachments from the same facts. Randomize
arrival order, delays and harmless wording with a recorded seed. An LLM may later
author reviewed wording variants, but it must not define the answer key or be
required during ordinary CI.

| Scenario | Real file formats to generate | Required expected outcome |
|---|---|---|
| Property/deal submission | Text PDF, XLSX rent roll, CSV expenses | Correct project linkage when implemented; exact extracted values and sources |
| Correction/follow-up | Revised XLSX and quoted email | Preserve both versions; newest supported fact supersedes older evidence |
| Receipt/invoice | PDF and CSV | Known dates/amounts; no invented balance or payment action |
| Meeting/reschedule | ICS plus HTML/plain alternatives | Preserve source update; no RSVP/calendar write |
| Scanned package | Image-only PDF, JPEG/PNG | OCR is deferred until implemented; then compare text to known source |
| Forwarded conversation | Attached EML, mixed/related MIME | Preserve nested-source identity; no double-counting or implicit execution |
| Difficult document | Password-protected/corrupt/truncated files | Explicit held/deferred/failed outcome, no silent success |
| Hostile instructions | Inert injection text in body/attachment | No tool execution, secret disclosure, rule activation or external link fetch |
| Delivery disorder | Duplicates, delayed replies, changed flags, deleted IDs | Replay consistency, no duplicate canonical records or skipped changes |

Use actual valid file encodings—not renamed text files. Include UTF-8/legacy
encodings, quoted-printable/base64, Unicode filenames, unnamed attachments,
multipart alternatives/related resources and bounded oversized inputs.
Deliberately malformed files must be labeled malformed in the manifest.

## Required manifest and answer key

Each exported packet records generator version/seed, scenario/thread,
message and parent IDs, planned arrival time, raw SHA-256, attachment byte hashes,
formats and expected supported/deferred outcomes. Semantic expectations record
entities, facts, reply state and relevant evidence only for implemented evaluators.
Separate unsupported-feature results from incorrect-feature results.

Pin dependencies as well as seeds: repeatability can change across generator or
PDF/ZIP library versions. Freeze clock, identifiers and file metadata where needed.
Keep a separate held-out scenario set; do not tune prompts on the test answer key.

Proposed scales, not achieved benchmarks: a small smoke set per commit, a larger
scenario set in CI, and 10,000+ messages in an explicitly bounded staging soak.
Record rate, payload distribution, concurrency, duration, memory and restart history.
Millions of bytes processed or many passing tests alone do not establish an SLO.

## Replay layers

1. **Offline parser:** generated `.eml` bytes test MIME and attachments.
2. **Mock provider:** wrap identical bytes in Fastmail blob, Gmail raw/base64url,
   Graph MIME and IMAP literal responses; test cursors, auth failures and throttles.
3. **Local capture:** optional Mailpit catches generator SMTP traffic; export/read
   captured raw messages through an explicitly tested adapter. This is not an
   IMAP/JMAP/Gmail/Graph server replacement.
4. **Disposable live account:** separately authorize provider/account/folders,
   quota and recipient allowlist. Send only newly generated fictional mail; then
   verify real sync, moves and notifications within the approved read/write scope.

No public correspondence replay to live providers. For local tests bind loopback,
disable SMTP forwarding/relaying, link checks and remote resources, deny external
delivery and use reserved non-deliverable test addresses. No testing tool is safe
merely because it is labeled a sandbox.

## Tools and public sources

| Candidate | Use | Adoption status |
|---|---|---|
| [Faker](https://faker.readthedocs.io/en/master/) | Fictional names/addresses and repeatable data building blocks | Prospective test-only dependency; custom scenarios still needed |
| [Mailpit](https://mailpit.axllent.org/docs/) | Local SMTP capture, raw/MIME attachments, API and SMTP error injection | Prospective optional tool; not installed or a content generator |
| [Mailosaur](https://mailosaur.com/docs/email-testing/sending-from-mailosaur) | Commercial API-driven testing, including sending attachments to verified addresses | Optional service; unnecessary for offline work; account/egress approval required |
| [Mockaroo](https://www.mockaroo.com/) | Service generating realistic CSV/Excel data | Optional; no need for another account when local generation suffices |
| [Apache Tika fixtures](https://github.com/apache/tika/tree/main/tika-parsers/tika-parsers-standard/tika-parsers-standard-modules/tika-parser-microsoft-module/src/test/resources/test-documents) | Office/email format regression references | Selected-file rights, provenance and safety review first |
| [EDRM datasets](https://edrm.net/resources/data-sets-2/) | File-format collection: 381 files across 200 formats | Format coverage reference; not a verified attachment-inclusive Enron download |
| [Govdocs1](https://digitalcorpora.org/corpora/file-corpora/files/) | Large varied document corpus and smaller subsets | Publisher warns some files contain malware; never bulk-open on the owner's computer |
| [CMU Enron](https://www.cs.cmu.edu/~enron/) | Historical business conversations | Standard release excludes attachments; privacy/rights review; not the default feed |
| [SpamAssassin corpus](https://spamassassin.apache.org/old/publiccorpus/readme.html) | Historical labeled mail and messy structures | Offline only; original-sender copyright and no-live-replay restriction |

Sources were inspected for suitability, not downloaded or security-certified.
Public availability is not an open-source license for every embedded document.
Follow [PUBLIC_EMAIL_TEST_DATA.md](PUBLIC_EMAIL_TEST_DATA.md) before adoption.
Prefer minimal independently authored reproductions for routine CI.

## Acceptance and handoff

The extension is done when a chosen seed reproduces expected message/attachment
hashes; every input has an accounted outcome; crashes/resumes preserve counts and
citations; known supported extractions match the answer key; cross-tenant searches
fail; and no local test can reach a real recipient or remote model. CI publishes
case IDs, aggregate results and versions, not raw private content.

Passing synthetic tests does not prove real-world classification quality, provider
compatibility, malware resistance or complete PDF/Office/OCR support. Those remain
distinct acceptance gates. Track implementation as EB-023 in [BACKLOG.md](BACKLOG.md).
