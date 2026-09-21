# ADR-033: coherent known-answer synthetic mailbox

Accepted for offline/synthetic development, 2026-09-21.

## Decision

Extend synthetic tooling with versioned, seeded fictional conversations and
documents authored from the same facts. Preserve actual MIME encodings, reply
headers, source dates, attachment hashes and expected outcomes in a manifest.
Generate valid text/image PDFs, minimal DOCX/XLSX, CSV, PNG, ICS, attached EML and
ZIP; deliberately damaged files are explicitly labeled. No downloaded/private
correspondence or model-generated answer key.

Export a new, exclusive local folder of `.eml` and a manifest written last. Never
overwrite an existing output, read arbitrary attachment input or accept recipients.
Use fixed synthetic file names, bounded corpus size and reserved `.invalid` addresses.
The packet is evidence for tests, not a live-mail replay service.

Add bounded, optionally paced ingestion through existing `Store.ingest_page`,
`synthetic_only=True`, on an existing unenrolled synthetic account. Every scheduled
event commits with its cursor. Include duplicate delivery, metadata updates,
out-of-order source dates, a provider tombstone and malformed MIME. These simulate
provider changes inside the database; they perform no provider action. Stop signals
stop new events; restart resumes the same version/seed/configuration only. Reject
an unrelated cursor or account enrollment, including changes during a run.

Manifests distinguish current parser/search expectations from future semantic
targets (project/fact/reply state). Deferred PDF/Office/image/archive handling is
not success or an extraction-quality score. Current evaluators compare known source
text, hashes, receipts and replay state without deriving the oracle from the parser.

## Dependencies and boundary

Generate a small deterministic subset of formats with stdlib code and explicit
fixed metadata. Add pypdf, openpyxl and python-docx as pinned **development-only
independent readers** for known generated PDF/OOXML tests. They are not imported by
the service, parser or generator. Their presence in CI grants no permission to open
untrusted binary mail in the API. Source/license references and exact resolved
versions belong in the test-mailbox documentation/lockfile.

## Verification and rollback

Tests cover reproducible bytes, changed seeds, format structure/readability,
conversation/correction consistency, declared current versus deferred outcomes,
bounded/no-network generation, safe output creation, SQL account ownership,
concurrent/restarted feeds, commit ambiguity, enrollment races, quarantine and
unchanged evidence under replay. Existing provider wrappers test the same MIME
bytes. Export completion does not certify a production mailbox, malware resistance,
semantic/model quality, OCR or live provider acceptance.

No migration or new runtime permission. Rollback stops invocations and preserves
synthetic evidence/cursors; choose a new synthetic account for another generator
version. Never reset a production cursor or delete retained evidence to make tests pass.
Continuous hosting, capture-server SMTP, live replay and multi-day soak remain gated.
