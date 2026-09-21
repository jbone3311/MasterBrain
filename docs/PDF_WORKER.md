# Source-bound PDF worker

Updated 2026-09-21. Explicit synthetic/local-worker library and dedicated container,
not automatic ingestion or a public upload endpoint. ADR-035 now connects this
reader to a separate [synthetic approval/result/search workflow](DOCUMENT_PROCESSING.md).
[ADR-034](adr/034_source_bound_pdf_worker.md) defines the accepted boundary.

## What it does

`DockerPdfProcessor.extract(raw_mime, part_path=..., part_sha256=...)` verifies an
exact local image, launches a fixed no-network profile and sends a closed request
through pipes. The request contains retained MIME, its SHA-256, an existing MIME
part path and the decoded attachment SHA-256. The child verifies both byte bindings
and selects only an existing deferred `application/pdf` receipt. It will not descend
into an attached email to invent an unreceipted document.

The parent does not parse PDFs. The child lazily imports exactly pypdf 6.19.0 after
limits and source validation. Text results identify physical one-based page numbers,
not PDF page labels. Parent validation rejects unknown fields, extra content on
failures, invalid Unicode, inconsistent pages/statuses and mismatched hashes.
`processor_version` includes `sandbox-pdf-v1` and the full image hash. This class has
no MIME `prepare`/`parser_version` interface and cannot be passed as a Recovery parser.

The pinned reader normally tries an empty password during initialization. A narrow
version-specific override refuses its encryption hook before that work; regression
tests verify encryption metadata/password verification is never invoked. Revalidate
this private-hook compatibility on every dependency upgrade; no automatic upgrade.

| Result | Meaning |
|---|---|
| `extracted / bounded_pdf_v1` | Bounded text from every page; not complete visual understanding |
| `partial / pages_without_text` | Some pages contain no extracted text; page positions preserved |
| `deferred / no_text` | No usable text layer; OCR is not enabled |
| `deferred / encrypted` | No password handling, including documents with an empty password |
| `deferred / unsupported_features` | Conservative feature screen detected catalog actions/names/forms/associated files or page annotations/actions |
| `deferred / *_limit` | Byte, page, decoded stream or text/output budget exceeded; no partial document text returned |
| `failed / invalid_pdf` | Fixed deterministic PDF-read rejection; no parser diagnostics exposed |
| `PdfUnavailable` | Source/contract mismatch, dependency mismatch, unexpected parser error, resource exhaustion or container/cleanup failure; no deterministic cache claim |

Every result is **unscanned**. The feature screen is deliberately conservative,
not a comprehensive active-content detector or malware scanner. Extracted text is
untrusted and never executes instructions. Images embedded beside text are not OCRed;
even an `extracted` result can omit visual information, layout or table semantics.

## Limits and isolation

Whole MIME ≤16 MiB; pipe request ≤24 MiB; selected PDF ≤4 MiB; ≤40 pages;
≤20,000 characters/page and ≤100,000 total; decoded page streams ≤2 MiB each and
≤8 MiB total; response ≤1 MiB. No partial text is retained after a limit deferral.
Source mismatch is not permission to process a different part.

Shared controller controls remain fixed: approved local image ID/no pull, local
Docker socket, no network/mounts, read-only root, UID 10001, dropped capabilities,
no-new-privileges, default seccomp, 512 MiB memory/swap ceiling, one CPU, 32 PIDs,
disabled container logs and scrubbed stderr. Linux child limits include 10 CPU
seconds, 512 MiB address space and zero file/core writes; wall time is 30 seconds.
Isolation is inspected before disclosure; only the exact owned container is removed.
Cleanup failure prevents a success response. Never give the API a Docker socket.

Content decompression/object traversal can allocate before a logical budget check.
OS/container bounds remain necessary; the parser is not a security boundary by
itself. See [upstream extraction limits](https://pypdf.readthedocs.io/en/stable/user/extract-text.html).

## Build and verify (synthetic only)

```sh
uv sync --locked --extra dev
uv run pytest -q tests/test_pdf_worker.py tests/test_pdf_processor.py tests/test_sandbox_runner.py
docker build -f Dockerfile.pdf -t email-brain-pdf-test .
docker image inspect email-brain-pdf-test --format '{{.Id}}'
```

Copy the verified full `sha256:...` image ID into `EMAIL_BRAIN_PDF_IMAGE_ID`, then:

```sh
uv run pytest -q tests/container_pdf_checks.py
```

Use a disposable trusted Docker test host. Do not pipe real mail through this
prototype. The `pdf-worker` extra is for the dedicated image, never the public API
image. CI still verifies that the default image contains no pypdf/Office/XML fixture
readers, then builds and tests the PDF image separately. Development in-process
parser tests receive only independently authored synthetic data.

## Integration boundary

The reader itself owns byte identity, not user authorization. ADR-035/migration
0012 adds a separate synthetic-only approval queue, immutable result cache and
revision selection, page citations and opt-in FTS. Existing ingestion receipts
still defer PDFs; only a successful explicitly approved result makes PDF-only text
available to document search. Source/body state is preserved. See
[document contract](DOCUMENT_PROCESSING.md) for scopes, routes and operational controls.
ADR-036 adds the [document CLI](DOCUMENT_CONTROLLER.md). UI, hosted supervision,
scanning and live acceptance remain open; do not
close EB-006 on parser or synthetic integration checks alone.

Schema inspection confirms current receipts are unique per message-evidence/part,
and current attachment search reads their original extracted text. Do not overwrite
those receipts to add a new PDF interpretation: define independent immutable
extraction versions and explicit citation/query selection. The old SQL scanner
value is `not_scanned`; the new worker contract uses `unscanned`. The integration
keeps both visible as their original independent records; neither is clearance.

## Operations and rollback

No supervisor is installed. Omit the worker image/caller to disable the capability;
the separate job channel now has migration/result state and its own cancellation
and forward-repair rules. Keep the default MIME image and
its recovery jobs separate. Routine reporting may include fixed status/reason and
counts only, never document text, request envelopes or parser diagnostics. No new
metrics backend or persistent telemetry is claimed.
