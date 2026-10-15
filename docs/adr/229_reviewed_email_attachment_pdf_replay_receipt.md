# ADR-229 — Reviewed Email attachment PDF text-layer replay receipt

Status: synthetic-only worker/store and protected schema on an open PR. Local
fictional PostgreSQL/full-suite tests passed; exact-head hosted, independent
restore and actual-image gates remain. There is no private operator command,
live mailbox or financial publication.

## Context

ADR-228 can reproduce one bounded Email PDF attachment's complete text from
retained parent MIME through the pinned isolated PDF processor, but it knows
nothing about current database state or a human source-tier review. ADR-223's
message receipt applies only to direct-parser Email message text; ADR-226's
PDF receipt applies only to a FileOS source. A same-hash attachment in two
messages represents two source occurrences and must not share one review or
receipt.

## Decision

Add an append-only, tenant-fenced receipt keyed by one current human source-
tier review of an Email attachment's bridged PDF document. It binds the
review, child evidence/version/source, legacy attachment and approved PDF
extraction, parent Email version/account/MIME hash and size, MIME part path
and hash/size, complete document-text hash, exact image/policy normalizer and
page count. The receipt carries no MIME, PDF, text, filename, path or provider
credential. Ordinary runtime and database-owner logins may not update/delete/
truncate rows; runtime insert is subject to a trigger that rechecks the same
current join and actor context. This is an accidental/compromised-runtime
barrier, not proof against a malicious database owner.

The narrow worker requires `brain.document.publish` and
`email.evidence.read`, source grants and an exact reviewed ID. It selects the
current active, nonexcluded attachment and current parent message/account;
requires the approved completed extraction and immutable Email bridges;
loads only the matching retained parent MIME through the existing authorized
inline or encrypted storage path; invokes ADR-228's isolated exact-part proof;
then, under source-item, parent-item, source and message row locks,
rechecks the entire basis and optional worker authorization before inserting.
Conflicts or revocation roll back the receipt. An exact retry returns the same
content-free result; divergent replay is refused.

The worker has no UPDATE privilege on the account or completed job tables, so
it does not take row locks there. It rechecks both in the final query and SQL
insert guard; a concurrent account/status transition after that check is not
claimed to be serialized by this receipt. Live-source use needs a separately
reviewed account/job transition fence.

This is a point-in-time text-layer derivation, not OCR/visual completeness,
attachment safety, sender/issuer authenticity, corroboration, a financial
fact, live-provider freshness or a FileOS cutover. No Brain API endpoint,
model or source effect gains this worker authority. FOS-Master is unchanged.

## Verification, rollout and rollback

Use fictional current bridged PDF/retained MIME to prove one receipt, exact
retry, distinct same-hash occurrences, changed parent/current child/part,
excluded/paused/revoked sources and wrong tenant. Test SQL RLS, immutable
guards, independent trigger rejection and final authorization rollback.
The current focused tests cover receipt/retry, changed parent, paused source,
retroactive exclusion, lost grant, wrong account/tenant, trigger/immutability
and authorization rollback; same-hash database occurrences still need their
own case. Run exact-head hosted PostgreSQL and populated
independent restore before merge. A later ADR must add a tenant-bound private
command with shared/owner login refusal and an actual immutable-image gate.
No live account is authorized. Roll back by stopping the worker; preserve the
append-only table and migrate forward rather than deleting receipts.
