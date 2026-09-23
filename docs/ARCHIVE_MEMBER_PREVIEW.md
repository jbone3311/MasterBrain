# Private archive-member publication preview design

Status: implemented in `0a8c430`, with the non-bomb oversized fixture correction in
`5befc42`. The corrected runtime passed 2,560 hosted Python tests and all restricted
worker gates in [CI 35799779137](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35799779137),
plus [restore 35799779396](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35799779396).

## Purpose

Give the private operator a bounded, read-only way to review which members of one
explicit persisted archive inventory are eligible for the existing one-member text
publication command. This is selection assistance, not execution authority.

## Selection and currency

The caller supplies one `archive_inventory_<32 hex>` identity, an optional returned
integer ordinal cursor and a 1–100 limit. One forced-RLS transaction requires the
inventory's parent FileOS item to still point at the inventory's exact source version.
It returns only sealed non-container members that:

- have one of the existing text/Markdown/HTML/CSV suffixes; and
- are no larger than the existing 1 MiB text-normalization limit.

Rows retain the sealed inventory ordinal and order strictly by ordinal. A continuation
cursor must name an eligible member in that same inventory; an arbitrary or stale
ordinal fails closed. Parent replacement makes every page unavailable immediately.
No cross-page atomic snapshot is claimed.

Each result contains the ordinal, virtual member locator, observed size, media hint,
depth and `already_published`. The publication label is true when any exact derivative
receipt exists for that inventory/member; replay receipts cannot duplicate a row. The
response also contains the inventory ID, eligible count, limit, next cursor,
`untrusted_metadata: true`, `source_effects: false` and `data_effects: false`.

Virtual member locators are untrusted source metadata and may be sensitive. This is an
owner-private local command; output must not enter ordinary service logs. It returns no
archive root, absolute source path, member bytes, normalized text, hash, evidence text,
credentials or generated idempotency key.

## Operator command

Add `masterbrain fileos archive-text-plan` using the same closed private configuration
and exact `brain.source.ingest` plus `brain.document.publish` worker scopes as
`archive-text`:

```sh
MASTERBRAIN_DSN='postgresql://least-privileged-runtime/...' \
  masterbrain fileos archive-text-plan \
  --config /private/operator/archive-member.json \
  --inventory-id archive_inventory_0123456789abcdef0123456789abcdef \
  --limit 25 \
  --check
```

`--check` authenticates, validates the private configuration, immutable image syntax,
root and runtime database role, and then stops. It does not query an inventory, inspect
a member, instantiate or invoke Docker, access source bytes, write data or consume a
key. Normal preview reauthenticates before and after the query and remains read-only.

## Acceptance

- flat, nested and mixed eligible/ineligible inventories return only eligible members
  in sealed ordinal order with exact page boundaries;
- repeated receipts produce one row with `already_published: true`;
- arbitrary, foreign, container, ineligible and stale cursors/inventories fail closed;
- parent source replacement makes preview unavailable without deleting retained data;
- exact scopes, revocation, runtime-role preflight, check-mode non-consumption and
  content-free database effects are proven;
- no Docker construction/read, source access, receipt, key, change event or audit data
  other than the preview audit event is created;
- PostgreSQL, restore, donor parity and all existing archive/operator/search gates stay
  green.

## Non-goals

No sealed batch format, batch executor, automatic continuation, key generation,
publication, member byte read, Docker call, public API, scheduler, source effect,
unsupported-member listing, non-text extraction or FOS-Master cutover is authorized.

## Implemented result

`DataCoreStore.archive_member_text_plan` performs the current-parent and cursor fences
inside forced RLS, filters eligibility in SQL, uses `EXISTS` for replay-deduplicated
publication state and records only a preview audit event. The private controller
preflights the runtime role and reauthenticates around the query; check mode never
constructs DataCore or the Docker worker. The CLI returns sealed ordinal pages and
explicitly labels member metadata untrusted. PostgreSQL acceptance proves mixed
eligibility, page boundaries, replay labels, arbitrary-cursor refusal, stale-parent
refusal, no source access and zero derivative receipts.
