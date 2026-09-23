# Sealed archive-document batch design

Status: checkpoint 4Y accepted design; runtime not yet implemented.

## Purpose

Execute a finite, owner-reviewed set of existing one-document archive publications
without turning preview or an inventory into automatic fan-out. The batch is an
ordered retry envelope around the checkpoint-4V primitive, not a new extraction or
publication path.

## Closed plan

The owner-private JSON plan contains exactly:

```json
{
  "version": 1,
  "inventory_id": "archive_inventory_0123456789abcdef0123456789abcdef",
  "code_revision": "deployed-revision",
  "items": [
    {
      "member_locator": "reports/quarterly.pdf",
      "document_format": "pdf",
      "idempotency_key": "93c5a004-81ab-45b6-8652-e8ced2b40e47"
    }
  ],
  "plan_sha256": "<64 lowercase hex characters>"
}
```

There are 1–100 ordered items. Locators and UUID keys are each unique. Every locator
obeys the existing safe relative virtual-path contract and its suffix must exactly
match its declared `pdf`, `docx` or `xlsx` format. `plan_sha256` is SHA-256 over
canonical compact JSON containing the version, inventory ID, code revision and exact
ordered locator/format/key triples. The revision must equal the closed controller
configuration.

The operator supplies keys and the seal outside the command. Preview generates
neither. After any uncertain or partial result, reuse the byte-for-byte logical plan;
never reseal completed intent with new keys.

## Check and execution

Add `masterbrain fileos archive-document-batch --config ... --plan ... [--check]`
using the one-document operator's exact scopes, authorized root, two immutable image
IDs and private-file rules.

`--check` validates both closed private files, canonical seal, uniqueness, revision,
format/suffix agreement, authentication and least-privileged database role. It does
not query an inventory, construct either worker, read source/member bytes, publish a
receipt or consume a key.

Normal execution processes only the sealed order. For each item it:

1. reauthenticates and resolves the exact current inventory/member through the
   existing forced-RLS document selector;
2. confirms the resolved selection still agrees with the sealed expected format;
3. reauthenticates before constructing/using the existing hash-bound archive-member
   reader and bounded document worker;
4. accepts only the existing PDF/Office extraction contract;
5. reauthenticates before the existing transaction-time publication fence;
6. publishes or exactly replays the caller-supplied key; and
7. reauthenticates before adding the content-free item result.

The first refused selection, format mismatch, stale parent, worker/extraction failure,
key conflict or publication conflict stops the loop. Earlier append-only receipts stay
valid. Exact retry replays them and resumes in order. Unexpected infrastructure faults
remain one generic top-level error rather than a false partial-success claim.

## Output

Output contains operation, plan hash, requested/completed/recorded/replayed counts,
ordered item indexes with recorded/replayed state, complete flag, failed item index,
generic `document_refused` code, and explicit false source effects. It returns no
locator, format, path, bytes, text, hash, evidence content, metadata, image/container
details, exception or credentials.

## Acceptance

- canonical fixtures prove order/inventory/revision/locator/format/key binding;
- unknown fields, public/symlink plan, malformed or duplicate locator/key, suffix/
  format mismatch, wrong revision, zero/101 items and altered seal fail before data or
  worker access;
- check mode proves no DataCore, worker, source, receipt or key use;
- a mixed PDF/DOCX/XLSX plan publishes in exact order with content-free output;
- failure at item two prevents item three; exact retry replays item one and completes
  remaining items using original keys;
- stale parent/member, hash substitution, unsupported/oversized content, either worker
  fault, revocation, tenant isolation and admin DSN fail closed;
- source bytes/timestamps remain unchanged and no unplanned sibling is read or
  published; and
- full PostgreSQL, restore, real two-image chain, donor parity and existing preview/
  search/operator gates remain green.

## Non-goals

No discovery, preview continuation, key generation, best-effort continuation,
parallelism, scheduler, public API, inventory-wide publication, archive upload,
image/OCR format, source effect or FOS-Master cutover is authorized.
