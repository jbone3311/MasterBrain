# ADR-078 — Model an archive member as derived evidence before text publication

Status: accepted and implemented in `97aeab1`; hosted CI/restore green.

## Context

ADR-077 can return one exact member, but `brain_evidence` is uniquely bound to one
source version. Attaching several member documents to the archive's source version
would collapse distinct hashes and make evidence drill-down ambiguous. Treating a
member as an ordinary top-level FileOS observation would falsely claim it exists under
the configured root.

## Decision

Create a deterministic derived source item/version/evidence for one explicitly read
member and seal the relationship in an append-only archive-member derivative receipt.
The receipt links the accepted inventory and member locator to the parent archive
source version and child identities. Generic child locators are opaque; the receipt
retains the exact virtual locator under RLS.

Only the existing bounded text/Markdown/HTML/CSV normalizer is eligible first. Recheck
the current archive parent and every member identity in the publication transaction.
Do not retain raw member bytes. Record both parent archive evidence and inventory as
provenance inputs. Retained-history search may include the explicit derivative;
current-source search requires a later receipt-to-current-parent join.

## Alternatives rejected

- Multiple documents on the archive evidence: loses per-member evidence identity.
- A materialized extraction directory: introduces path, cleanup and mutation risk.
- Automatic publication of every manifest member: creates unreviewed fan-out and
  partial-failure semantics.
- Marking child currency independently: can expose stale derivatives after the archive
  source changes.

## Rollback

The migration is additive and append-only. Rollback disables the publisher/read layer;
existing archive inventories and one-member reads remain valid. No FileOS source bytes
or FOS-Master state are changed.
