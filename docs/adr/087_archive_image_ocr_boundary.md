# ADR-087 — Isolate archive image OCR before any publication

Status: accepted design; runtime not implemented.

## Context

The pinned FileOS donor has useful, tested image behavior split across three tools.
The safest pixel/output caps and timeout are not present in the same path, and the
broader tools also expose EXIF/GPS, process-global decoder changes, filesystem naming,
SQLite, shell and external vision behavior. Archive-member bytes are untrusted and OCR
is substantially more resource-sensitive than the implemented text and PDF/Office
paths.

## Decision

Extract only the format validation, full decode, bounded OCR and minimal technical
metadata behavior into a dedicated immutable worker. Bind raw bytes to exact hash,
length and canonical format; accept six single-frame raster formats; cap input at
8 MiB, decoded size at 25 megapixels, OCR at 30 seconds and returned text at 5,000
code points/20,000 UTF-8 bytes. Keep Pillow's bomb guard enabled and add an independent
limit. Return no path, broad EXIF or pixels.

Treat OCR as untrusted derived evidence. Require a donor/known-answer/fault/container
corpus before persistence, and require separate persistence, private operator, search
and batch decisions afterward. The existing archive reader remains the only member
byte authority.

## Alternatives rejected

- Copy `doc_extract.py`: its OCR call is unbounded and broad EXIF/GPS reaches text.
- Copy `image_triage.py`: it mixes extraction with naming, observation, database and
  optional external vision effects.
- Copy `extract_metadata.py`: it mixes platform/database work and temporarily disables
  the process-global Pillow guard.
- Reuse the PDF/Office worker: a separate dependency and fault boundary keeps image
  codecs/Tesseract from expanding the document worker.
- Accept animation or HEIC immediately: frame and plugin behavior are not yet closed
  or parity-proven.
- Publish as part of extraction: worker success is not authorization to mutate the
  shared evidence store.

## Rollback

Because this checkpoint is documentation-only, rollback removes this ADR and its
inventory/contract. A later worker must remain removable without changing archive
inventory, member reading, document extraction or FOS-Master.
