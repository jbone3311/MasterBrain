# ADR-026: Bounded calendar evidence and realistic synthetic format fixtures

Accepted 2026-09-20 for prototype implementation.

Add deterministic extraction of text/calendar .ics attachment evidence, using a
bounded, conservative RFC 5545 parser. Output is searchable text with explicit
source date/time/TZID/recurrence/cancellation fields; it is not an evaluated schedule,
invitation acceptance, reminder execution, authenticated organizer or obligation.
Never fetch URLs, interpret alarm actions, send RSVP, or change calendars. Unsupported,
malformed or oversized input has an explicit deferred/failed receipt, not silent
successful extraction. Raw MIME and attachment hashes remain unchanged.

No new dependency, permission, provider effect, API route or database schema.
Calendar MIME body alternatives without filenames/disposition also receive an
attachment receipt with a generated .ics name. This captures inline invitations
that are not conventional file attachments. Parser provenance advances to v4;
existing immutable snapshots are not silently regenerated.
Existing attachment receipts/FTS/evidence APIs expose bounded extracted text and
their parser reason/version. Keep parsed event details below the existing 20,000
character limit; cap components, properties, unfolded lines and nesting. Do not
claim timezone conversion, recurrence expansion, organizer authenticity or complete
iCalendar support. Non-event calendars stay deferred. Legacy binary attachments,
PDF/Office/OCR extraction and sandboxed archive processing remain open work.

Add deterministic synthetic .eml fixtures with valid benign attachment bytes and
known expected hashes/text outcomes, plus provider raw-response format tests. No
public correspondence is vendored, downloaded automatically or submitted to live
mail services. Public corpora are reference candidates only until provenance,
per-file rights/privacy review and an isolated opt-in evaluation path are approved.
Tests must separate attachment preservation/format recognition from actual text
extraction; deferred binary parts must not be mislabeled as successfully read.

Rollback: deploy prior code; previously stored versioned extraction receipts remain
retained. Do not rewrite source evidence or silently rerun old receipts. Existing
receipt versioning/reprocessing remains a separate worker milestone.

References: [iCalendar RFC 5545](https://www.rfc-editor.org/rfc/rfc5545.html),
[MailParser fixtures](https://github.com/nodemailer/mailparser/tree/master/test/fixtures),
[MimeKit test data](https://github.com/jstedfast/MimeKit/tree/master/UnitTests/TestData).
