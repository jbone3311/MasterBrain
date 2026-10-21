# ADR-265 — Byte-order reads, true XLSX extent and correctable retired facts

Status: **accepted; implemented on the PR #245 branch**. Synthetic-only. No
live source, mailbox, FOS-Master or current-read behavior changes.

## Context

An independent four-part review of PR #245 found three defects, each with one
defensible fix. The first hosted run of the full PostgreSQL suite after the
Actions billing gate cleared also failed on the first one.

1. **Collation.** Historical later-FileOS reads sorted expected rows in Python
   (code-point order) and stored rows with `ORDER BY locator` (database
   collation), then compared them by position. Local test clusters used `C`;
   hosted CI uses `en_US.utf8`, where `~$draft.docx`, `_` and mixed case sort
   differently. Every stored attempt and preparation with such names became
   permanently "requires review" — fail-closed, but unusable. The predicate
   catalog had the same order dependence in its response.
2. **XLSX extent.** openpyxl read-only iteration stops at the sheet's declared
   `<dimension>`. A writer that understates it hid cells, including formulas,
   from extraction still reported `extracted` — contrary to ADR-240's
   "formula-dependent or incomplete leaves no result". FOS-Master's
   `doc_extract.py` at the pinned donor commit has the same read-only
   behavior; this is an intentional, recorded difference from the donor.
3. **Retired predicates.** ADR-214/215 gated every project-fact insert on the
   latest active registry revision. Because a correction must keep its prior's
   predicate (0066) and facts have no other correction path, a reviewed fact
   under a deprecated or never-registered predicate could no longer be
   retracted or corrected, contrary to SECURITY.md.

## Decision

1. Positional comparisons of locators read from SQL use `COLLATE "C"`, which
   equals Python's code-point order for UTF-8 text (prior art: migration 0059).
   The catalog response orders by `name COLLATE "C"`. Stored digests were
   already computed in Python order, so no data migration is needed.
2. Both XLSX readers reset the declared dimension, measure the real extent,
   recheck the row/column bounds and iterate from A1. A truthful dimension that
   starts at A1 reads identically. A sheet whose used range starts later now
   reports correct physical row numbers and leading blank columns; a document
   indexed by the older code for such a sheet will not match a new table
   projection and fails closed rather than binding to the wrong cells.
3. The registry gates new fact chains. A successor (`supersedes_id` set) that
   keeps its prior's exact project, predicate, type and unit — and inherits the
   prior's recorded registry version — is admitted even when the predicate is
   deprecated or unregistered. Migration 0094 enforces this in SQL; the Python
   publish path skips the registry check only for such successors.

4. The first-party XLSX review view shows each Unicode format character
   (category Cf, plus U+2028/U+2029) as a visible `⟨U+XXXX⟩` marker with a
   per-page warning, so bidi overrides and zero-width characters cannot make
   the reviewed text look different from what is published. The browser still
   verifies the digest over the exact raw text; the server contract is
   unchanged.

## Verification

Each fix has a regression test that fails on the unfixed code: a mixed-case
hashed locator in the later-FileOS lifecycle (`Later_add.txt`), an XLSX with an
understated dimension and a hidden formula, and a retraction under a retired
predicate (registry row inserted in a rolled-back transaction). Results are in
`docs/BUILD_RECEIPT.md`.

## Not decided here

Separation of human duties across XLSX approval/review/publication,
revocation of an unexpired approval, and whether an idempotent publish replay
should return its receipt after the approval or review expires remain open
review findings for separate ADRs.
