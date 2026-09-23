# Private archive-document publication preview design

Status: checkpoint 4X implemented in `1651c2b`; hosted CI and restore are green.

## Purpose

Give the private operator a bounded, read-only view of PDF/DOCX/XLSX members in one
explicit current archive inventory that are eligible for the existing one-member
`archive-document` command. This is review assistance, not extraction or batch
authority.

## Selection and currency

The caller supplies one `archive_inventory_<32 hex>` identity, an optional returned
integer ordinal cursor and a strict 1–100 limit. One forced-RLS transaction must prove
that the inventory's parent FileOS item still points to its exact source version. It
returns only sealed members no larger than the existing 8 MiB document bound whose
suffix, media hint and container classification agree exactly:

- PDF: `.pdf`, `application/pdf`, non-container;
- DOCX: `.docx`, the exact Word OOXML media type, container; or
- XLSX: `.xlsx`, the exact Spreadsheet OOXML media type, container.

Rows retain sealed inventory ordinals and order strictly by ordinal. A continuation
cursor must name an eligible member in that inventory; arbitrary, stale or ineligible
ordinals fail closed. Parent replacement makes all pages unavailable immediately. No
cross-page atomic snapshot is claimed.

Each row contains only ordinal, virtual member locator, observed size, media hint,
depth, document format and `already_published`. Publication is true when any exact
archive-document receipt exists for that inventory/member; replay receipts must not
duplicate a row. The envelope contains inventory ID, eligible count, limit, next
cursor, `untrusted_metadata: true`, `source_effects: false`, `worker_effects: false`
and `data_effects: false`.

Virtual locators are untrusted private source metadata. Output must not enter ordinary
service logs. The preview returns no archive root, absolute path, member bytes, text,
hash, evidence content, processor identity, credential or generated idempotency key.

## Operator command

`masterbrain fileos archive-document-plan` uses the existing closed private
archive-document configuration and exact shared scopes:

```sh
MASTERBRAIN_DSN='postgresql://least-privileged-runtime/...' \
  masterbrain fileos archive-document-plan \
  --config /private/operator/archive-member.json \
  --inventory-id archive_inventory_0123456789abcdef0123456789abcdef \
  --limit 25 \
  --check
```

`--check` authenticates, validates the private configuration, both immutable image-ID
forms, root and runtime database role, then stops. It does not query an inventory,
construct either worker, access source/member bytes, write data or consume a key.
Normal preview reauthenticates before and after its single read.

## Acceptance

- mixed PDF/DOCX/XLSX, text, image, oversized and misleading suffix/media/container
  fixtures return only exactly eligible members in sealed ordinal pages;
- replayed receipts produce one row with `already_published: true`;
- arbitrary, foreign, ineligible and stale cursors/inventories fail closed;
- parent replacement removes the preview without deleting retained evidence;
- exact scopes, revocation, role preflight and check-mode non-consumption are proven;
- no worker construction, source/member read, receipt, key, evidence, chunk, change
  event or audit data other than the preview audit event is created; and
- PostgreSQL, restore, current search, chained workers, donor parity and existing
  archive/operator gates remain green.

## Non-goals

No sealed batch format or executor, automatic continuation, key generation,
publication, member-byte read, worker call, public API, scheduler, image/OCR format,
automatic fan-out, source effect or FOS-Master cutover is authorized.
