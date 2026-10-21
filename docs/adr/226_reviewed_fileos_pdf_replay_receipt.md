# ADR-226 — Reviewed FileOS PDF text-layer replay receipt

Status: implemented and tested with fictional PostgreSQL and a simulated
restricted document pipe on an open PR. Hosted exact-head, real immutable-image
container and independent restore gates remain open. ADR-227 adds the narrow
operator command. No live root or financial claim is authorized.

## Context

ADR-225 can re-read one confined PDF and reproduce the exact text through the
pinned restricted processor. By itself that nonpublishing primitive does not
bind a current human source-tier review, grants, exclusion state or database
source version to the replay result.

## Decision

Add a worker-only store operation for one exact `stier_` review. It requires
`brain.document.publish`, a worker identity when one is bound, and an optional
configured source-ID restriction. The first tenant-fenced transaction checks
the review, current active FileOS version, source root binding, source-bound
unretained evidence, PDF media type, exact normalizer/image identity, full
normalized-text digest, quoted review basis, source grant and exclusion. It
then invokes ADR-225 against the confined current file. A second locked
transaction rechecks the entire basis and optional worker authorization before
inserting a digest-only immutable receipt under migration 0078. Repeated
identical replay is idempotent; a conflicting stored receipt fails closed.
The insert trigger independently checks the current SQL basis, and the table
has forced tenant and login-fence RLS plus update/delete/truncate guards.

The receipt records a **point-in-time worker-observed PDF text-layer
derivation**. It does not certify visual completeness, OCR, issuer identity,
the reviewer's source-tier judgment, currentness after the transaction or a
financial fact. It returns no PDF bytes, quote or path. It changes no source
file or Knowledge claim. FOS-Master remains unchanged.

## Acceptance and next gate

Fictional PostgreSQL tests must prove exact source/text/image/page binding,
idempotence, changed source and wrong scope/source refusal, authorization
revocation rollback, between-read source-version race, SQL trigger protection,
cross-tenant denial, no financial claim and unchanged source bytes. Run the
full disposable suite, static checks, hosted exact-head CI and independent
restore before merge. ADR-227 adds an exact tenant-bound operator command with
no-source-read check mode; next test the real immutable-image container and
remaining PDF/OCR and issuer-conflict coverage. No live cutover follows.
