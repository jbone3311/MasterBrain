# ADR-224 — Tenant-bound operator command for one Email tier replay

Status: implemented and executed only with fictional inline and encrypted
Email on an open PR. Hosted exact-head and independent restore remain open;
no live mailbox is authorized.

## Context

ADR-223 added internal point-in-time retained-MIME replay for a current
human-reviewed direct-parser Email document. Operators needed a narrow way to
run exactly one review without giving the command a provider token, mailbox
write capability, arbitrary evidence selector or shared/owner database login.

## Decision

`masterbrain email replay-tier-text --config ... --review-id stier_... \
--tenant-bound-db --check` uses a closed version-1 private config containing
one account ID and a 0600 credential/token pair under a 0700 directory. The
worker token must have **exactly** `brain.document.publish` and
`email.evidence.read`. Both check and execution require a DBA-enrolled
database login bound to that worker's tenant. Check mode validates the exact
review-ID shape, config, credentials, active account and, if configured,
private encrypted-object root and key manifest; it never reads a selected
MIME object or review row and never writes a replay receipt.

Execution binds the selected review to the configured account. Inline
retained MIME needs no blob configuration; encrypted MIME requires a paired
private `blob_root` and `keys_file`. The command constructs a read-only-key
blob store only for execution, reauthenticates before replay, inside the
final locked transaction, and after execution. The result is the existing
digest-only ADR-223 receipt. Errors are fixed and scrubbed; credentials,
source content and blob paths are never returned. No provider connection,
mailbox mutation, automatic scan, public API write or financial claim is
introduced. FOS-Master is unchanged.

## Acceptance and next gate

Use fictional inline and encrypted MIME to prove check mode has no selected
source read or receipt, exact two-scope credentials, closed/private config,
shared/owner DSN refusal, account binding, actual tenant-bound execution,
unchanged retained bytes, final authorization rollback and CLI dispatch.
Run full local and hosted exact-head/restore gates before merge. A live pilot
requires separate owner approval and controls; this ADR does not grant it.

Next: attachment/PDF source-byte derivation, full format coverage, issuer and
conflicting-source-tier policy, then human-reviewed financial publication.
