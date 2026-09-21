# Calendar attachments and format-faithful synthetic tests

## Working behavior

Newly ingested `text/calendar` MIME parts are indexed as bounded source evidence.
This includes named `.ics` attachments and calendar body alternatives without a
filename/disposition. The latter receive a generated `calendar-{part}.ics` receipt.
The original message and attachment hashes remain retained; calendar extraction
does not rewrite the message or contact an organizer/provider.

Calendar text passes through the existing attachment receipt → PostgreSQL FTS →
cited evidence API. Successful receipts say `bounded_calendar_v1`; overall MIME
snapshot provenance advances to `stdlib-mime-v4`. Unsupported charsets/structures
are deferred; malformed calendars fail extraction explicitly. Such a failure does
not discard the message or block healthy messages in its page. An invalid later
attachment version replaces current search results, while earlier evidence remains
available by its original citation.

## Interpretation and safety

This is source-text extraction, **not a calendar application or complete RFC/iTIP
validator**. Dates, time zone identifiers, recurrence rules, cancellation METHOD,
organizer and attendee addresses are quoted untrusted source values. No time zone
conversion, recurrence expansion, meeting acceptance, RSVP, URL download, alarm,
invitation-authentication or obligation change happens. A matching sender or valid
calendar syntax does not authenticate the organizer. `scanner_status` stays
`not_scanned`; extracted text is not a clean-malware certificate.

The parser unfolds bytes before UTF-8 decoding (including folds inside multibyte
characters), preserves escaped text in quoted output, checks calendar/event
structure and selected required fields/date syntax, and rejects conflicting MIME
and body METHOD values. It preserves supported timezone and alarm components as
inert source. Unknown/non-event components and inline binary encodings remain
unsupported. The complete iCalendar specification is broader than this subset.

Bounds: 256 KiB input, 4,096 physical lines, 4,096 bytes per physical line,
16,384 bytes per unfolded line, 128 components, depth four, 1,024 properties,
16 parameters per property, 32 events and 20,000 output characters. Exceeding a
bound never returns silently truncated successful extraction. Uniform LF is an
accepted compatibility input; bare CR/mixed line endings are rejected.

## Fixtures and independent verification

`tests/attachment_samples.py` constructs nine deterministic, harmless MIME cases in
memory. They include minimal Word/Excel OOXML packages, PNG attachments/inline images,
UTF-8 CSV, folded Unicode calendar invitations/cancellations, a nested email and a
mixed bundle. ZIP metadata and MIME boundaries are fixed. Expected receipt outcomes
are authored separately from application parsing. OOXML tests check package/XML
structure, not full Office rendering or application acceptance.

Tests verify decoded attachment bytes/hashes and exercise identical whole-message
bytes through Gmail base64url JSON, Graph MIME `$value`, Fastmail JMAP blob download
and an IMAP literal/session fake. This is not live-provider conformance, authenticated
notification testing or a durable Gmail/Graph/IMAP worker. Real PostgreSQL tests
verify storage/receipts/search/replay/history using the non-owner runtime role.

Word, Excel, PNG and nested email fixtures are preserved but remain deferred/skipped
as appropriate. Do not count their presence as text/OCR extraction success. The
legacy nested-email receipt hashes its serialized MIME part; the complete unchanged
outer raw message is the byte-preserving source, and fixtures test that distinction.

No public correspondence was imported. See [public sample research and adoption
gates](PUBLIC_EMAIL_TEST_DATA.md) for provenance/licensing/privacy requirements.

## Deployment and rollback

No migration, new dependency, permission or network path is required. Existing
stored v3 evidence/receipts are not silently re-extracted; a versioned reprocessing
worker is still needed for historical calendars. Stop the new binary and redeploy
the prior one to disable extraction for future input, retaining immutable evidence.
Hosted identity, larger encrypted raw storage, binary sandbox extraction, PDF/OCR,
calendar semantics and production operations remain separate gates.

References: [RFC 5545 content lines](https://www.rfc-editor.org/rfc/rfc5545.html#section-3.1),
[ADR-026](adr/026_calendar_attachments_and_format_fixtures.md),
[Factory intake alignment](FACTORY_INTAKE_REVIEW.md).
