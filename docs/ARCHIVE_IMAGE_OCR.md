# Archive image/OCR donor inventory and closed contract

Status: checkpoint 4Z isolated worker implemented through `512185b`; archive-member
composition, persistence and search are not authorized by this document.

## Pinned evidence

The inspected donor is `jbone3311/FOS-Master` at
`218d5caec2f20b9047fd3eb8e027dc671acf0c15`. Its relevant files are:

```text
746932e5ce033a9b8f8bd7155a88dfbb6d1c57a9916aea2230e6afbe1a3ab269  _SYSTEM/tools/doc_extract.py
b3fbc5ab7bf8ce06072865b5f1c0c3cd57ab968c0490e6996f95ed37c657cfb0  _SYSTEM/tools/image_triage.py
553503e599e91636e8e004b45e348559a3e43fc848b0dd1310454641db22be63  _SYSTEM/tools/extract_metadata.py
823ce03a8d7e2b8c42845ae1685db0ed92391461428b989034b9d83140421a41  _SYSTEM/tests/test_doc_extract.py
83cff8f74b5736d7efb1fd130f968b6295f12a906d2281f1037781c7a4119335  _SYSTEM/tests/test_image_triage.py
```

On 2026-09-22, the two focused donor modules passed 149 tests against the pinned,
clean checkout using system Python, Pillow, pytesseract and Tesseract 5.5.1. The
MasterBrain project environment could not collect `doc_extract.py` because it does
not contain the donor's optional PyMuPDF dependency; that environment mismatch is
not counted as a donor failure. Running the donor tests changed no donor file.

## Behavior found

`doc_extract.py` recognizes JPEG, PNG, HEIC/HEIF, TIFF, BMP, GIF and WebP before
its configured extension allowlist. It opens the path with Pillow, returns dimensions,
format, mode and broad EXIF, and optionally runs Tesseract. OCR is limited to images
at or below 25,000,000 pixels and appended text is truncated to 5,000 characters.
The OCR call has no timeout. HEIC/HEIF requires process-global Pillow plugin
registration. GPS and other EXIF can enter indexed text.

`image_triage.py` adds independent header and full-decode checks, hashes raw bytes,
and gives pytesseract a configurable 90-second timeout. Its bomb limit is
178,956,970 pixels, substantially larger than the document extractor's OCR limit.
It also performs filename-based naming, boilerplate observation, optional command or
Anthropic vision, SQLite writes and filesystem-oriented triage. Its HEIC extensions
are listed but no HEIF opener is registered. Animated GIF is accepted using Pillow's
implicit frame behavior rather than an explicit frame contract.

`extract_metadata.py` combines image/PDF OCR, SQLite and platform commands. It
temporarily disables Pillow's process-global decompression guard while decoding
images. A `try/finally` now restores the value, but disabling the guard is unsuitable
for a shared untrusted-input service.

These tools remain behavioral references. None is copied wholesale.

## First runtime boundary

The first implementation will be a separate immutable, non-networked image worker.
Its parent supplies raw bytes and a closed request; it receives no source path,
database credential, tenant credential, archive inventory or sibling member. For an
archive member, the existing hash-bound reader remains the only byte source and its
8 MiB member limit remains in force.

The request binds:

- protocol version;
- declared `jpeg`, `png`, `tiff`, `bmp`, `gif` or `webp` format;
- exact lowercase SHA-256 and byte length of the supplied bytes;
- OCR enabled as a literal true value; and
- fixed worker limits/version, not caller-selected command or model options.

The suffix, declared format, detected Pillow format and supported file signature must
agree. `.jpg` and `.jpeg` map to `jpeg`; `.tif` and `.tiff` map to `tiff`. HEIC/HEIF,
ICO, SVG, PDF and every other encoding are refused in this tranche. Any image with
more than one frame, animation, zero dimensions, truncated payload, inconsistent
header/body or failed full decode is refused. Supporting multi-frame or HEIC content
requires its own dependency, resource and evidence decision.

The worker must enforce all of these limits before OCR:

| Resource | First-tranche limit |
|---|---:|
| Encoded bytes | 8 MiB |
| Width × height | 25,000,000 pixels |
| Frames | exactly 1 |
| OCR wall time | 20 seconds inside a 30-second parent/container deadline |
| Returned OCR text | first 5,000 Unicode code points and at most 20,000 UTF-8 bytes |
| Whole response | 64 KiB |

The worker forces a full decode before Tesseract. Pillow's own guard stays enabled;
the independent 25-megapixel check does not rely on global state. Tesseract language,
page-segmentation defaults, executable version and language data must be fixed in the
immutable image and reported as non-secret runtime provenance. The worker has a
read-only root filesystem, a 32 MiB in-memory writable scratch area, no network, no inherited
secrets, dropped capabilities, non-root identity, memory/CPU/PID limits and no shell.
The parent validates the closed response again and treats timeout, process exit,
malformed/oversized output or hash/format disagreement as refusal.

## Result and provenance

A successful closed result contains only protocol/runtime version, input hash and
length, detected canonical format, width, height, mode, one-frame count, OCR engine
identity, bounded OCR text, truncation flag and warnings from a fixed enum. Empty OCR
text is a valid derived result, not proof that the image contains no writing.

No filename, path, arbitrary EXIF, GPS, thumbnail, raw bytes, rendered pixels,
exception text, command output or credential crosses the worker boundary. OCR is
untrusted derived evidence. Publication must give it a separate immutable evidence
identity linked to the exact archive member, exact current archive inventory and
parent source version. It must never overwrite source evidence or become an assertion
without KnowledgeCore review and evidence links.

## Parity and security corpus

Before publication, the runtime gate must include:

1. known PNG/JPEG/TIFF/BMP/static-GIF/static-WebP fixtures with legible and blank
   content, compared with the donor's normalized dimensions/format/mode and first
   5,000 OCR characters under the same Tesseract runtime;
2. repeated execution proving stable contract output and no source-byte/timestamp
   changes;
3. suffix/format/signature mismatch, zero byte, random bytes, valid-header truncated
   body and corrupt checksum cases;
4. 25-megapixel boundary and over-boundary header-only bomb cases without pixel
   allocation;
5. animated/multi-frame GIF, TIFF and WebP refusal;
6. forced OCR timeout, worker crash, malformed JSON, oversized output, wrong hash and
   hostile OCR text cases;
7. container checks for non-root/no-network/read-only/no-secrets/resource limits; and
8. archive selection, stale parent/member, tenant isolation, revocation, replay and
   source-preservation tests through real PostgreSQL.

Exact OCR equality is only meaningful when the Tesseract executable and language
data match. Across runtime versions, compare the bounded normalized contract and use
reviewed known-answer token thresholds; never silently call drift parity.

The implemented live harness is `scripts/image_ocr_parity.py`. Against the pinned,
clean donor it passed 12 text/blank cases across all six admitted formats, 120
additional generated text-image comparisons and one deliberate safer animated-GIF
refusal. It compares both paths under the same local OCR engine while the real
container gate separately proves the immutable Tesseract 5.5.0 runtime. Source files
and the donor checkout remain unchanged.

## Explicit exclusions

This design grants no standalone filesystem crawl, directory batch, automatic
archive fan-out, EXIF indexing, GPS retention, filename-derived naming, boilerplate
registry, SQLite access, shell/command backend, external vision/LLM call, scanned-PDF
OCR, database publication, search activation, scheduler or FOS-Master cutover. Each
later effect needs a separately gated contract and rollback.
