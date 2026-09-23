# ADR-077 — Read one persisted archive member by hash

Status: accepted and implemented in `c7d2d27`; hosted CI/restore green.

## Context

ADR-075 inventories member identities without returning bytes, and ADR-076 persists
those identities without creating evidence. Downstream extraction needs bytes, but a
general unpack directory, arbitrary path request or all-member response would reopen
the path, output and fan-out risks those boundaries intentionally removed.

## Decision

Add a separate closed pipe contract and fixed child command that returns one persisted,
non-container member from one exact current source archive. Bind the request and
response to source version/locator/hash/size/media type, inventory ID and processor,
member virtual locator/hash/size/depth/parent. Rerun bounded inventory inside the child,
then locate the target under the identical virtual nested-path rules. Re-hash and size-
check the response again in the parent.

Cap the first response at 8 MiB. Larger members are explicitly deferred until a
separately reviewed streaming contract. The result remains unscanned and cannot be
persisted or searched by this ADR.

## Non-goals

No arbitrary paths, directory extraction, glob, batch, container-member return,
member persistence, evidence, normalization, OCR, indexing, API, scheduler, effects or
FileOS cutover are authorized.

## Acceptance and rollback

Unit/adversarial/fault tests, forced-RLS current-inventory resolution, source
revalidation and actual restricted-container invocation must pass. Rollback removes
the new command/contract/resolver; inventory and manifest persistence remain valid.
