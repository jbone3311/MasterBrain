# One-member archive image/OCR composition

Status: checkpoint 5A design; runtime not implemented.

## Purpose

Compose two already bounded capabilities for one explicitly selected current archive
member: the hash-bound archive reader releases exactly that member, then the isolated
image worker fully decodes and OCRs it. This is a read-only orchestration primitive,
not publication, discovery or a command.

## Exact handoff

The caller supplies an existing forced-RLS `ArchiveMemberTargetRecord` and authorized
FileOS root. Before either worker, the parent requires a `.jpg`, `.jpeg`, `.png`,
`.tif`, `.tiff`, `.bmp`, `.gif` or `.webp` suffix and the existing 8 MiB member cap.
The current archive inventory records these legacy image media hints as
`application/octet-stream`; 5A does not rewrite old manifests or infer authority from
that broad hint.

The sequence is:

1. reopen and revalidate the exact current parent archive through the existing
   no-follow source boundary;
2. invoke the immutable archive-member image with the persisted parent/member hash,
   size, locator and inventory processor identity;
3. accept only a still-`unscanned`, exact-hash/size one-member result;
4. derive the canonical image format only from the already validated suffix and pass
   raw bytes, exact member SHA-256, suffix and format to the separate image worker;
5. validate the entire image response again in the parent and bind the immutable image
   processor version; and
6. discard member bytes after returning a bounded in-memory extraction result.

The image worker independently requires suffix/format/signature agreement, so a
renamed or format-masquerading member fails even if its archive manifest was accepted.
Neither worker receives database credentials. The archive worker knows the parent and
selected member but cannot OCR; the image worker sees only selected bytes and has no
archive, path, sibling, inventory, tenant or database knowledge.

## Result

The parent result keeps the deterministic archive-child version and locator already
defined by the archive-member contract. A text result is `extracted`; valid empty OCR
is `empty`; bounded resource/policy outcomes are `deferred`; corrupt or unavailable
boundaries are `failed`. Metadata is limited to image processor version, canonical
format, image reason, width, height, mode, single-frame count and truncation flag.

OCR text remains untrusted derived evidence and is not evidence merely because this
composition succeeds. No EXIF, GPS, path, raw bytes, rendered pixels, exception,
worker/container detail or sibling content enters the result.

## Acceptance

- flat and nested static fixtures cross both workers for each suffix alias and return
  exact bounded text/metadata without sibling content;
- blank OCR returns an explicit empty result rather than failure or fabricated text;
- unsupported suffix, oversized member and container member refuse before either
  worker;
- format masquerade, corrupt body, over-pixel header, animation, archive hash/size
  substitution and changed parent refuse closed;
- either worker crash, timeout, malformed response, processor-version fault or output
  substitution returns only a bounded failure classification;
- real immutable archive and image containers prove a known text image, blank image,
  nested member and animation refusal while source bytes/timestamp remain unchanged;
- no sibling is read, no raw member/image byte is persisted, and no DataCore/search/
  KnowledgeCore row or source effect occurs; and
- all prior donor parity, PostgreSQL, restore and restricted-container gates stay green.

## Non-goals

No database selector beyond the existing generic exact-member primitive, publication,
receipt, provenance row, current search, private command, preview, plan, batch,
scheduler, archive-wide recursion, automatic fan-out, standalone image crawl, scanned
PDF, EXIF, external vision, scanner verdict, source effect or FOS-Master cutover is
authorized. Each is a later separately reviewed checkpoint.
