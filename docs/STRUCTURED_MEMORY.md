# Structured memory: trips, reservations, bills and changes

ADR-046 implements a first **reviewed memory** slice, not automatic understanding
of all email. Migration 0014 is required. No live mailbox/model/bank/airline is
contacted. [Implementation](../src/email_brain/memory.py),
[schemas](../src/email_brain/memory_schema.py),
[extractor](../src/email_brain/memory_extract.py).

## Working experience

Open `/memory` on the database-backed service. The owner can load records and
coverage, request a candidate from a current evidence ID, review/edit its fields,
and explicitly save it. The current field editor is JSON and requires an account
ID/token: **developer preview**, not finished nontechnical UX or browser sign-in.
The existing loopback fictional reader preview has no database/memory backend.

The following record types are implemented:

- Trip: title, status, optional start/end dates.
- Flight reservation: airline, confirmation, travelers, up to eight segments;
  each segment can carry flight number, airports and timezone-aware departure/arrival.
- Hotel reservation: hotel, confirmation, location, check-in/out dates, optional
  IANA time zone. Unknown local check-in time is not invented.
- Bill: vendor, invoice number, due date, nonnegative decimal-string amount and
  uppercase three-letter currency together. Currency syntax is checked; no exchange
  rate, ISO registry validation, payment verification or accounting interpretation.

Fields not supplied stay null/unknown. A bill marked paid means the owner reviewed
that claim, not that a bank verified settlement. A flight's confirmed status is
not live airline status. Flight/hotel records can explicitly link to a trip in
the same account; cross-account grouping and automatic duplicate/alias matching
are not implemented. Confirmation numbers alone are never global identity keys.

## Candidate extraction and publication

The first deterministic parser supports one short, wholly labelled body, for example:

```text
Record type: flight
Title: Fictional autumn trip
Status: confirmed
Airline: Example Air
Confirmation: DEMO42
Traveler: Fictional Owner
Flight: EX123
From airport: SFO
To airport: JFK
Departure: 2026-10-12T08:00:00-07:00
Arrival: 2026-10-12T16:30:00-04:00
```

Hotel labels: `Hotel`, `Confirmation`, `Location`, `Check in`, `Check out`, `Time zone`.
Bill labels: `Vendor`, `Invoice`, `Due date`, `Amount`, `Currency`.
Trip labels: `Start date`, `End date`. All use `Record type`, `Title`, optional `Status`.
Dates use ISO date strings; flight timestamps need explicit UTC offsets.
Unknown/duplicate labels, invalid values, unstructured prose, quoted conversation,
truncated projections and bodies over 2,000 characters abstain. This deliberately
does **not** claim compatibility with real airline templates. No model is invoked.

Owners may manually author typed records from other normalized emails. Publication
requires a verbatim supporting quote from a current evidence version, exact boolean
review acknowledgement and human review/evidence scopes. The quote proves source
association, not that every edited field follows logically: provenance says
`owner_reviewed_email_claim`. Future inference needs field-level evidence and evals.
One revision cites one email; independent multi-source field provenance is pending.

Updates are full snapshots, not implicit patches. The owner supplies the expected
current revision; stale updates conflict. Record kind/account are immutable. A new
email correcting an old booking is explicitly associated by the owner. Cancellations
append a version rather than deleting the trip. Provider deletion never silently
cancels a booking; retained state exposes `source_current: false` when its cited
version is no longer current. Do not render these fields as HTML or instructions.

## What changed, and is it fresh?

The account summary reports travel/bills bucket revisions and last recorded change,
last successful `caught_up` sync observation, current worker outcome, and a 15-minute
age diagnostic. These are independent. A successful sync does not prove extraction,
complete historical coverage or live reservation verification. Every response says
`interpretation_coverage: partial_manual_review` and `all_mail_interpreted: false`.
No rows/timestamp means unknown, not verified empty. The 15-minute threshold is a
prototype display diagnostic; no scheduler is configured by this feature.

Assistants request bounded changes with a saved opaque UUID cursor. Results carry
record IDs, kind, revision and timestamp—not whole emails, confirmation numbers or
amounts. Fetch only changed records. The feed includes **reviewed memory changes**,
not every new incoming email. Unreviewed mail can contain changes not yet represented.
Each client stores its own cursor; no read consumes another client's changes.
Retain separate cursors per account. Unknown/foreign-account anchors return 404;
after a restore/reset, re-bootstrap rather than treating that error as no changes.

Writers serialize per tenant before allocating a revision; sequence order follows
publication commit order, avoiding timestamp/sequence allocation races. Same-key
retry returns its original result even after a later correction; fetch current
state separately. Same key/different intent is 409. A new key with identical
payload/evidence/quote/trip link records a no-op receipt without advancing the feed.
Changing the source quote or source version is a meaningful provenance change.

## HTTP contract

Prefix: `/v1/accounts/{account_uuid}/memory`. Every route requires current owner
membership and an active account. All reads require `email.evidence.read`.

| Method/path | Result |
|---|---|
| GET `/summary` | Bucket versions and explicitly partial coverage/freshness |
| GET `/changes?after={cursor}&limit=25` | Up to 50 compact events, `next_cursor`, `has_more`; non-consuming |
| GET `/records?after={record_uuid}&limit=25` | Current records, UUID-keyset pagination; live list, not snapshot |
| GET `/records/{record_uuid}` | Current record with quote/citation and source-current flag |
| GET `/records/{record_uuid}?at={cursor}` | Exact historical revision, bound to account and record |
| POST `/candidates/{evidence_uuid}` | Human review/evidence scopes; candidate or explicit abstention; no publication |
| PUT `/records/{record_uuid}` | Human review/evidence scopes; exact reviewed publication |

PUT requires a UUID `Idempotency-Key` header and a closed body:

```json
{
  "expected_revision": 0,
  "evidence_id": "00000000-0000-4000-8000-000000000003",
  "source_quote": "Fictional autumn trip",
  "parent_trip_id": null,
  "payload": {"kind": "trip", "title": "Fictional autumn trip", "status": "planned"},
  "reviewed": true
}
```

Zero means create. Subsequent expected revisions are returned stream revisions,
not necessarily consecutive per record. Typed schemas are in OpenAPI. Existing
32 KiB request limit, scrubbed errors, no-store policy and cookie CSRF apply.
Assistant credentials may read, not publish or run extraction. MCP/client setup
remains pending; these REST capabilities do not imply a working Grok connection.

## Operations, testing and next steps

Stop writers, apply migration 0014 with the administrator, and re-run `grant_runtime`
for the runtime role before deploying. Three new tables are append-only, tenant-RLS
protected; source/parent references are account-bound. No dependency or UPDATE/DELETE
grant is added. Audit stores only identifiers/outcomes. Memory is included in the
populated two-tenant restore fixture and whole-table hash comparison.

Run `uv run pytest -q tests/test_memory.py tests/test_memory_postgres.py` and
`node --test tests/web_memory.test.cjs`. Actual SQL tests require the documented
disposable database; local skips are not passes. Full existing gates still apply.
Rollback disables memory routes/UI and preserves migration/history. No destructive
down migration or provider action is required.

Next: guided nontechnical editor; larger realistic travel corpus; field-level evidence;
evaluated local-model candidates; durable extraction coverage/change notifications;
cross-account explicit grouping; bill reminders; investment/project record types;
MCP compatibility. No automatic scheduling, payment, check-in or mailbox writes.
