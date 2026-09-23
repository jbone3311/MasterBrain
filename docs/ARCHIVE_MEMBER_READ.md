# Hash-bound archive member read contract

Implemented in `c7d2d27`. Hosted CI 35789652225 and restore 35789652166 are green.

## Purpose

Read exactly one non-container archive member already recorded in the accepted
append-only inventory, so a later explicit extractor can consume verified bytes without
materializing an archive tree or granting arbitrary path access.

## Authority and selection

The parent first resolves one `brain_archive_members` row through forced RLS using an
exact inventory ID and safe member locator. The inventory must belong to the current
FileOS source version, and the selected row must not be an intermediate container. The
database returns only the source identity, inventory processor identity, member hash,
size, depth and parent locator; it returns no bytes.

An authorized local caller then reopens the source archive beneath its configured root
using the existing no-follow, same-file-before/after, hash/size revalidation pattern.
The request carries the exact source identity and bytes plus inventory ID, inventory
processor version, member locator, expected SHA-256 and expected size.

## Isolated worker

A separate fixed child command in the archive image accepts the closed request. It
reruns the accepted bounded inventory algorithm over the exact source bytes before
selection. Only complete/partial accepted inventories are eligible; bomb, duplicate,
unsupported or corrupt outcomes fail closed.

The worker follows the inventory's virtual nested locator rules entirely in memory and
returns only the selected raw member. The response repeats all source and target
identity, is base64/canonical-JSON bounded and remains `unscanned`. The parent treats
the response as untrusted and independently verifies length and SHA-256.

The first member-output cap is 8 MiB even though inventory permits a 64 MiB member.
Larger members remain explicitly deferred for a future streaming protocol; they are
not silently truncated. Empty members are allowed and still hash-bound.

## Non-goals

No directory extraction, arbitrary host path, glob, multi-member batch, container-byte
return, archive upload, persistence of member bytes, child source/evidence creation,
normalization, document extraction, search, API, scheduler or FileOS effect is added.

## Acceptance

1. closed request/result tests reject unknown fields, source/target substitution,
   duplicate JSON keys, noncanonical base64 and output overrun;
2. flat and nested ZIP/TAR members match their persisted hash/size and unrelated bytes
   never appear in the response;
3. containers, skipped members, stale inventories, historical source versions, wrong
   hash/size and over-8-MiB targets fail or defer before publication;
4. malicious traversal/link/encryption/bomb/duplicate/corrupt archives cannot produce
   member bytes;
5. parent timeout, crash, oversized-output, wrong-command and isolation inspection
   failures collapse to one content-free unavailable error;
6. a real immutable container invocation, live donor baseline, full PostgreSQL suite
   and populated restore remain green.

All six gates passed. The hosted suite ran 2,525 Python tests; the dedicated immutable
archive image passed both inventory checks and two real member-read checks. The pinned
FOS-Master archive suite remained 47/47 and the six-case live golden comparison passed.
The member result remains transient and `unscanned`; no evidence, document, chunk,
search row, public API, scheduler or FileOS effect was added.
