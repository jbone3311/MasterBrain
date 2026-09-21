# ADR-037 — Repository documentation verification

Accepted 2026-09-21 for developer tooling only. No runtime, schema, permission,
provider, model, deployment or Factory-policy change.

## Context

The documentation pack explains the product and its current limits, but its check
only requires 20 documents and tests local file paths. A broken section link or
missing GitHub contribution template can pass. Repeated manual inspections do not
protect subsequent edits.

## Decision

Extend the existing offline `scripts/check_docs.py` gate to cover root guides,
all Markdown under `docs/` and `.github/`, and required contribution/release/operator
guides and issue/PR templates. Check repository-contained local destinations and
Markdown heading fragments, including same-document links, percent-encoded paths,
duplicate heading IDs and reference-style links. Ignore fenced/inline code examples.
Check this repository's explicit `blob/main` documentation URLs against the checkout
without fetching GitHub; leave other external URLs to deliberate research review.

Support the Markdown subset used by these documents, not every GitHub rendering
extension. Document that this does not prove factual freshness, external-link health,
complete Markdown syntax coverage, browser rendering or accessibility. Add synthetic
temporary-tree tests for the checker, including negative cases and path escape.
Keep dated research and old exact-commit test receipts intact.

Add a concise methods/reference guide and link it into owner and builder navigation.
Current capability claims must retain the separate MIME/PDF and synthetic/live
boundaries from ADR-035/036. The next runtime assignment remains the PDF owner UI.

## Verification and rollback

Run the checker, its regression tests and the existing repository validation suite.
CI already invokes this script; no new network access, credentials or service is
needed. A tooling regression is repaired or reverted as code, never worked around
by claiming documentation or product acceptance. No database rollback applies.
