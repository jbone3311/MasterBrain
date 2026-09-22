# Archive member text derivative contract

Implemented in `97aeab1`. Hosted CI 35792838710 and restore 35792838718 are green.

## Purpose

Turn one explicitly selected, hash-bound archive member into a normal DataCore text
derivative while preserving the archive, inventory and member as separate identities.
This is not automatic unpacking: one authorized request names one accepted inventory
and one member locator.

## Identity and provenance

The archive source version remains the parent evidence. A selected member becomes a
derived FileOS source item/version/evidence with opaque stable IDs computed from the
inventory ID, inventory processor version, virtual locator, member SHA-256 and size.
The child locator exposed through generic source reads is opaque; the exact virtual
member locator remains in the tenant-isolated derivative receipt.

The normalized document points to the child evidence, not the archive evidence. Its
provenance names both the parent archive evidence and accepted inventory, plus the
member-read contract, inventory processor, normalizer, code revision and configuration
hash. This avoids pretending the member was independently present beneath the FileOS
root and makes drill-down return to the exact archive and member identity.

## Execution fence

1. Resolve one non-container member using the forced-RLS/current-version selector.
2. Reopen and revalidate the source archive, then run the isolated hash-bound member
   read from ADR-077.
3. Accept only a `read`, still-`unscanned` result at or below the existing 1 MiB text
   normalization limit and only the already supported text/Markdown/HTML/CSV suffixes.
4. Normalize outside the archive worker using the existing deterministic text rules.
5. In one database transaction, reacquire the inventory/member and current-parent
   locks, compare every source/member identity again, and append the child source,
   evidence, document, chunks, provenance and sealed receipt.

The transaction is idempotent by actor/key and deterministic derivative identity.
Concurrent exact attempts converge; key reuse, processor drift, changed normalized
text or a now-historical parent fails closed.

## Search and currency

The first persistence tranche may enter retained-history DataCore search because it is
an explicit accepted derivative. It must not enter active-generation or current-source
search until those queries join the derivative receipt back to an inventory whose
archive source version is still current. A later current-search tranche adds that join
and independent coverage counts; it must not infer currency merely from the child
item's own current pointer.

## Non-goals

No automatic fan-out, batch, recursive publication, archive upload, raw-member
retention, Office/PDF/OCR extraction, semantic ranking, public API, scheduler, FileOS
write/effect or FOS-Master cutover is authorized. Unsupported, oversized, binary, NUL,
empty or failed members record no child evidence in the first tranche.

## Acceptance

- deterministic child identities and exact replay/concurrency tests;
- forced-RLS selection and transaction-time parent/member revalidation;
- supported flat/nested ZIP/TAR text fixtures with exact normalized output;
- stale parent, substituted target, binary, NUL, empty and over-limit refusals;
- no automatic siblings, no raw-byte retention and no current-search visibility;
- full PostgreSQL, populated restore, pinned donor and hostile archive gates remain
  green.

The first persistence tranche passed all listed gates. Migration `0024` adds the
forced-RLS append-only receipt. The runtime publishes deterministic child source,
evidence, document, chunks and two-input provenance only after transaction-time parent
and member revalidation. Exact replay and concurrent identities converge; drift and
idempotency-key reuse fail closed. The derivative appears only in retained-history
search, not current-generation search. No raw member bytes are stored.

The separately gated [current archive-derivative search](ARCHIVE_DERIVATIVE_SEARCH.md)
is now implemented, but remains a distinct layer rather than changing this
publication contract or any active generation.
