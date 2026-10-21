# ADR-223 — Worker-observed retained Email byte/text replay

Status: implemented and exercised with fictional inline and encrypted MIME
on an open PR. ADR-224 adds a restricted operator command; hosted exact-head
and independent restore gates remain open. No live mailbox is authorized.

## Context

ADR-217's human source-tier review pins a current DataCore document and its
source hash, but is not a byte attestation. ADR-218/219 added point-in-time
replay for current FileOS **text**. Email's bridge uses retained original MIME
and a normalized `Subject`/`From`/body projection, but until now no later
worker could re-read the MIME and prove that a reviewed document still derives
from those bytes. ADR-222 repaired encrypted-source size so both Email storage
modes can enter this gate.

## Decision

For one exact `stier_` review, an internal worker operation requires both
`brain.document.publish` and `email.evidence.read`, and a worker identity when
one is bound. It checks the current active Email source, unexcluded retained
evidence, current nondeleted/nonquarantined legacy message, active account,
exact bridge receipt, source/version/document hashes and source grant. It
supports only direct `stdlib-mime-v5` messages of at most 1 MiB using the
`email-message-v1` bridge projection; other parser and part/document forms
fail closed rather than being approximated.

The worker loads the currently retained original bytes through the existing
authorized raw-object path, which authenticates encrypted blobs. It rehashes
the MIME, re-runs the pinned parser, refuses truncated body text, and compares
the entire normalized bridge text and its digest. A second locked transaction
rechecks the full basis and optional authorization before inserting one
immutable digest-only receipt under migration 0077. Replays are idempotent;
conflicting receipts fail. No body, MIME, token or path is returned. A
database trigger rejects a receipt whose current reviewed/bridged source
basis is inconsistent; it is not itself proof that bytes were read.

This proves only a **point-in-time worker-observed text derivation**. It does
not prove the sender or issuer is authentic, that MIME/attachments were fully
interpreted, that the source remains current after the transaction, or that
any financial fact is true. It makes no mailbox, file or Knowledge claim
change. FOS-Master remains unchanged.

## Acceptance and next gate

With fictional data, prove inline and encrypted replays, exact byte/text
hashes, source grants and scope denial, stale message/version denial,
encrypted-ciphertext tamper refusal, a version change after byte read,
authorization revocation before receipt insertion, idempotence, and protected
table behavior. Run the full disposable-PostgreSQL suite, strict runtime,
restore and hosted exact-head gates before merge.

ADR-224 adds the restricted tenant-bound operator command with a no-byte-read
check mode and final credential recheck. Attachment/PDF source-byte derivation,
source-tier conflict policy and financial publication remain separate gates.
