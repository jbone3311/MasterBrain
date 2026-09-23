# ADR-088 — Compose one archive member with isolated image OCR

Status: accepted design; runtime not implemented.

## Context

The exact one-member archive reader and isolated image/OCR worker are independently
proven. Letting the archive worker decode images would merge hostile codec authority;
letting the image worker receive the parent archive would expose siblings. Automatic
inventory traversal would add selection and retry policy before a one-item primitive
exists.

## Decision

For one explicit current non-container member, run the existing hash-bound archive
reader and pass only its independently revalidated in-memory bytes to the separate
image worker. Bind exact member hash, size and suffix-derived format across the
handoff; validate the closed image result again; expose only a bounded extraction
result and discard bytes. Keep the tranche entirely outside persistence and commands.

Preserve legacy archive media hints rather than rewriting sealed manifests. Treat the
image worker's signature check as the exact format authority. Empty OCR remains a
successful empty derivation; OCR text remains untrusted.

## Alternatives rejected

- Add Pillow/Tesseract to the archive image: merges two parsers and fault budgets.
- Send the parent archive to the image image: exposes unrelated members.
- Select by broad `application/octet-stream`: suffix and signature must both bind.
- Persist immediately: extraction success is not mutation authorization.
- Reuse document receipts: image metadata, engine and empty outcomes need an explicit
  later persistence model.
- Batch or recurse: prove sibling exclusion and failure behavior for one item first.

## Rollback

Remove only the composition module and chained tests. Archive inventories/member reads,
the standalone image worker, PDF/Office composition and FOS-Master remain unchanged.
