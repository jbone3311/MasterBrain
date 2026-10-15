# ADR-228 — Retained Email attachment PDF derivation proof

Status: synthetic-only pure DataCore primitive on an open PR. No review-bound
receipt, operator command, live mailbox or financial publication is enabled.

## Context

The existing Email PDF worker receives bounded retained MIME, identifies one
attachment by MIME part path and SHA-256, and extracts a text layer in an
isolated, image-pinned container. The approved extraction may be bridged into
the attachment occurrence's DataCore evidence and normalized document. That
bridge copies a completed result; it does not independently re-read the
retained MIME and reproduce the published text. ADR-223 covers the parent
message's direct-parser text, not attachments. ADR-225/226 cover FileOS PDFs,
not Email. Same-hash attachment occurrences must remain distinct.

## Decision

Add a nonpublishing deterministic proof for **one** explicit MIME part. The
trusted worker supplies the exact retained parent MIME bytes, expected parent
hash/size, MIME part path/hash, complete bridged text and text hash, the
published Email-PDF normalizer and an exact-image `DockerPdfProcessor`. The
function does not parse untrusted MIME in the parent: the isolated worker
selects and hashes the PDF part, returning a closed result. DataCore accepts
only the complete `extracted`/`bounded_pdf_v1` text-layer result with no empty
page, exact source identity, exact page-joined text and image/policy normalizer.
Partial, image-only, encrypted, changed, wrong-part, wrong-image or invented
text is unavailable. Return only digests, byte size, part identity, normalizer
and page count; suppress raw MIME, paths, credentials and processor diagnostics.

This proves one point-in-time transform if the trusted worker actually ran.
It is not a database-currentness check, immutable receipt, visual/OCR
completeness, sender authenticity, issuer proof, financial truth or a source
effect. No public API client gains MIME or Docker authority. The next tranche
must bind this proof to one currently authorized, nonexcluded reviewed
attachment and seal a tenant-fenced digest-only receipt with final locked
current/grant/worker checks. A tenant-bound private command and actual-image
CI run follow separately. FOS-Master is unchanged.

## Verification and rollback

Use fictional MIME/PDF fixtures to prove exact two-page text, same-hash
occurrence separation, changed MIME/part, wrong image/normalizer, partial and
image-only refusal, scrubbed failures, and no source/database effects. Keep
ordinary local tests independent of Docker. The explicit container suite now
includes a complete and partial replay through the built immutable image;
that gate remains pending until an exact-head hosted job actually runs. Rollback
is to stop invoking the pure function; it creates no schema, receipt or
source change. Preserve the prior Email bridge and FileOS replay behavior.
