# ADR-034 — Source-bound restricted PDF worker groundwork

Accepted for synthetic/local-worker and CI implementation, 2026-09-21. This is
the first EB-006 document-processing increment, not completed attachment intake.

## Decision and scope

Implement a separate fixed PDF worker profile and closed request/result contract.
The trusted caller supplies retained whole MIME, its requested attachment part
path and decoded-byte hash. The parent hashes the MIME; the restricted child checks
the MIME hash, verifies the selected part against existing attachment receipts and
checks its decoded hash before importing the PDF reader. No source filenames become
paths. No database, keys, provider credentials, URLs or passwords enter the child.

Use exactly pypdf 6.19.0 behind the dedicated worker-only extra/image, not in the default
API/MIME image. Reuse the already tested pipe/isolation/cleanup controller through
two fixed profiles, not arbitrary commands. Profile and exact image hash identify
the processor. PDF results must not satisfy the existing MIME Recovery protocol.

The child reads at most 24 MiB of JSON/base64 containing at most 16 MiB raw MIME.
The selected PDF is at most 4 MiB, at most 40 pages, at most 20,000 characters per
page and 100,000 total. Decoded page content streams are capped at 2 MiB each and
8 MiB total; limits cannot prevent all allocation during decompression, so Linux
512 MiB address-space/container memory, 10 CPU seconds, 30-second controller wall
time, no network/mounts, non-root, default seccomp and bounded output are mandatory.
Result JSON is at most 1 MiB. All values/hash/part/page/status/Unicode budgets are
revalidated in the parent. No truncated document is reported as complete.

Read strict PDF structure. Defer encrypted documents, detected unsupported document
features (catalog actions/names/forms/associated files and page annotations/actions),
page/stream/text/byte limits and documents without extracted text. Return per-page
text with an explicit partial outcome when some pages have no text. This is not
OCR or complete visual-content coverage. Malformed PDFs have a fixed failed outcome;
unexpected errors, dependency mismatch, resource exhaustion, source mismatch,
container failures and invalid output are scrubbed infrastructure errors, never
cached deterministic rejection. Scan status is always `unscanned`.

The feature screen is a conservative subset policy, not malware detection. Do not
resolve URLs, render pages, run JavaScript/macros, extract embedded files, read form
values or attempt passwords. Extracted text is still untrusted data.

## Deliberately not granted

No new HTTP/UI/MCP surface, SQL schema, account access, provider action, raw download,
scanner or automatic invocation. The worker is a library/pipe boundary for synthetic
tests. Existing ready-body search and deferred receipts remain unchanged.

Next ADR must bind durable human approval to tenant/account/evidence/part/hash,
processor, policy and expiry, then define a separate or properly generalized queue,
fenced result publication, independent extraction versions, authorized FTS/citations,
restore coverage and revocation/cancellation. Do not fabricate quarantine receipts.
A standalone worker does not close that integrated source-to-search requirement.

## Verification, telemetry and rollback

Test existing known-answer PDFs, page order/partial coverage, encrypted/image-only/
damaged files, feature deferral, every budget, substituted part/hash/MIME, duplicate
JSON keys, unknown fields/statuses, bad Unicode, unexpected parser failures and
fixed-profile isolation/cleanup. CI must exercise the real restricted PDF image,
while preserving all MIME/container regressions and default-image dependency checks.
Only fixed outcomes/counts are suitable for routine telemetry; no content, parser
exceptions or child logs. No persistent extraction cache or metrics collector added.

Disable/omit the PDF worker image to roll back; no migration or source mutation.
Retain existing default images. Recheck dependency advisories before promotion;
container tests do not certify absence of parser/kernel vulnerabilities.

Sources: [pypdf text extraction limitations](https://pypdf.readthedocs.io/en/stable/user/extract-text.html),
[strict reader and encryption API](https://pypdf.readthedocs.io/en/stable/modules/PdfReader.html),
[upstream security advisories](https://github.com/py-pdf/pypdf/security/advisories).
