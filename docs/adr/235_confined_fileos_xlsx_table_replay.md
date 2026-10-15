# ADR-235 — Confined current FileOS XLSX table replay

Status: implemented as a nonpublishing, synthetic-only proof on an open PR.

## Decision

Reacquire one exact current FileOS `.xlsx` through DataCore's existing
descriptor-relative, no-follow read boundary. Require the configured root
binding, source version, size and SHA-256, and a published
`sandbox-fileos-document-v1` text body digest. Run ADR-234's separate bounded
table worker from the **same immutable image** as that published document;
its normalizer/image suffix must match. Re-render table values into the
existing indexed text layout and refuse any digest mismatch. Recheck the root
binding after processing. Do not move, rename or change source bytes.

Return only source/text SHA-256s, table processor version, bounded counts and
a canonical row-layout SHA-256. The layout digest includes sheet names,
visibility, physical row numbers and positional values but excludes XLSX ZIP
packaging and source identity; those are returned as separate bindings. On
fictional workbooks, inserting a blank row preserves the indexed text digest
but changes the layout digest. Changing only package metadata changes the
source digest while leaving the layout digest stable. This is a point-in-time
worker observation, not an independent cryptographic proof that a compromised
worker parsed coordinates honestly.

## Gate and limitations

Tests cover ordinary and formula-bearing workbooks, changed bytes and digests,
wrong root/image, symlink refusal, duplicate layout under different package
metadata, and no source effects. The explicit document-container suite now
includes an actual-image re-read; it is collected but not run locally because
Docker is unavailable. No database review/currentness transaction, durable
receipt, source grant, Brain API read, table index, financial approval, live
root or FileOS cutover is enabled. Next bind this proof to one current human
source-tier review under a final source lock and tenant-fenced digest receipt,
then expose an exact private operator command. FOS-Master remains unchanged.
