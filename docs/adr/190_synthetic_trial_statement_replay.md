# ADR-190 — Exercise private statement source replay in the fictional trial

Status: accepted for synthetic/disposable testing only. This is a test-harness
integration of ADR-189, not a new production worker, API or financial claim.

## Context

The browser trial already published a fictional FileOS statement and displayed
one unreviewed proposal row, but its startup path did not exercise the
source-byte replay receipt. Thus a successful owner trial could not detect a
broken connection between the proposal and its original fictional file.

## Decision

- After the existing fictional proposal reconciles, call the private ADR-189
  operation with that proposal ID and the same newly created, confined trial
  FileOS root. Startup fails closed if replay fails. Do not accept a caller-
  supplied root, real account, existing database or personal file tree.
- Keep the receipt private. The browser and public proposal API still report
  an unreviewed `proposed_extraction`; arithmetic reconciliation and byte
  replay do not authorize a verified holding or reviewed fact.
- The synthetic startup self-test checks the persisted receipt and its source
  digest. PostgreSQL acceptance checks receipt binding, proposed-only owner
  visibility and cross-tenant denial. No additional source privilege, schema,
  API route, provider token or FOS-Master mutation is introduced.

## Verification and rollback

Run the disposable browser-trial self-test and focused PostgreSQL acceptance,
then the standard repository gates. A startup failure leaves no persistent
trial database because the launcher destroys its exact temporary cluster.
Rollback removes only the trial-harness replay call and this acceptance check;
ADR-189's private receipt table remains for audit.
