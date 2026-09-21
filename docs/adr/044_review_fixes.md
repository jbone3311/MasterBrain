# ADR-044: Nonblocking cached keys and source-bound sender eligibility

Status: accepted bug-fix direction, 2026-09-21.

## Signing-key refresh

Keep a short cache-state critical section and one in-flight network refresh.
Unexpired known keys remain usable while a refresh is in progress. Cold/unknown/
expired-key requests may wait at most five seconds for that refresh, then fail
with the existing scrubbed unavailable outcome. Recheck expiry after waiting;
never return an expired key or extend its TTL after failure. Preserve the global
30-second refresh cooldown, atomic key-set replacement and five-minute cache TTL.
No token/issuer logging, new trust source or background thread is introduced.

## Sender rules

Normalize one complete, defect-free From header containing exactly one valid
mailbox. Multiple From headers, multiple addresses, groups, missing/invalid or
overlength addresses are not eligible for sender rules. Preserve original MIME;
ambiguous sender does not discard an otherwise valid body or its attachments.

Add a strict `sender_rule_eligible` boolean to normalized results and immutable
JSON snapshots. Bump ordinary parser provenance to `stdlib-mime-v5`; a new isolated
image is distinguished by its immutable image digest. The MIME parent accepts
legacy worker envelopes without this field only as ineligible, never guesses true.
New child output adds the field; deploy the updated parent before the new image.
Unknown extra fields and non-boolean flags still fail closed.

Search and rule simulation both require exact JSON boolean true in the current
snapshot before domain matching. Historical snapshots without provenance are
ineligible until separately authorized reprocessing publishes a new version.
Do not rewrite evidence, migrations or prior rule/simulation receipts. No automatic
bulk reprocessing is introduced. Keep the internal field out of existing public
evidence/search envelopes so browser/client contracts stay unchanged.

## Verification, operations and rollback

Test blocked refresh with valid concurrent cache hits, cold single-flight, failure,
expiry, rotation and bounded waiter timeout using generated keys/fake HTTP only.
Test raw MIME through normalization, isolated envelopes, SQL search and simulation,
including legacy snapshots and retained body/raw evidence. Existing fixed status/
duration telemetry remains; no header or token text enters logs.

No schema migration, grant, dependency, mailbox effect or cloud service is added.
Restart clears key cache. Stop workers/API before rollback; preserve versioned
evidence and deploy forward fixes. Do not restore the old ambiguous-sender behavior
or mark old snapshots eligible without source validation.
