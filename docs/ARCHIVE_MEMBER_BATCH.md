# Sealed archive-member text batch

Status: checkpoint 4U implemented and accepted in `1a3fd58`.

## Purpose

Execute a finite, owner-reviewed set of existing one-member archive text publications
without turning the preview cursor or inventory into automatic fan-out. The batch is an
ordered retry envelope around the checkpoint 4R primitive, not a new extraction path.

## Closed plan

The owner-private JSON plan contains exactly:

```json
{
  "version": 1,
  "inventory_id": "archive_inventory_0123456789abcdef0123456789abcdef",
  "code_revision": "deployed-revision",
  "items": [
    {
      "member_locator": "reports/summary.md",
      "idempotency_key": "93c5a004-81ab-45b6-8652-e8ced2b40e47"
    }
  ],
  "plan_sha256": "<64 lowercase hex characters>"
}
```

There are 1–100 ordered items. Locators and UUID keys are each unique. Locators obey
the existing safe relative virtual-path contract. `plan_sha256` is SHA-256 over
canonical compact JSON containing version, inventory ID, code revision and the exact
ordered locator/key pairs. The revision must equal the closed controller config.

The operator creates the keys and seal outside the command. Preview does not generate
either. Reuse the unchanged plan after an uncertain or partial result; never reseal a
partially completed intent with new keys.

## Check and execution

Add `masterbrain fileos archive-text-batch --config ... --plan ... [--check]` using the
same exact scopes, authorized root, immutable archive image and private-file rules as
the one-member operator.

`--check` validates both closed private files, canonical seal, uniqueness, revision,
authentication and least-privileged database role. It does not query the inventory,
construct Docker, read source/member bytes, invoke the normalizer, publish a receipt or
consume any key.

Normal execution processes only the plan's order. For each item it:

1. reauthenticates and resolves the exact current inventory/member through forced RLS;
2. reauthenticates before the no-follow, hash-bound restricted worker read;
3. accepts only the existing bounded text-normalizer result;
4. reauthenticates before the existing transaction-time publication fence;
5. publishes or exactly replays that caller-supplied key; and
6. reauthenticates before recording the item outcome in command output.

The first refused selection, stale parent, read/normalization failure, key conflict or
publication conflict stops the loop. Completed earlier items remain valid append-only
receipts. An exact retry replays them and resumes in plan order. Unexpected controller
or infrastructure faults remain one generic top-level error rather than inventing a
success/partial claim.

## Output

Output contains the operation, plan hash, requested/completed/recorded/replayed counts,
ordered item indexes with recorded/replayed state, complete flag, failed item index,
generic `member_refused` code and `source_effects: false`. It returns no locator, path,
bytes, text, hash, evidence content, Docker details, exception or credentials.

## Acceptance

- canonical digest fixtures prove key/order/inventory/revision binding;
- unknown fields, public/symlink plan, malformed/duplicate locator or key, wrong
  revision, zero/101 items and altered seal fail before database access;
- check mode proves no DataCore, Docker, source, receipt or key use;
- a mixed flat/nested plan publishes in exact order with content-free output;
- failure on item two stops item three; exact retry replays item one and completes the
  remaining items using the original keys;
- stale parent/member, unsupported/oversized content, processor fault, revoked worker,
  tenant isolation and admin DSN fail closed without a false completion;
- source bytes/metadata remain unchanged and no unplanned sibling is published;
- full PostgreSQL, restore, real restricted image, donor parity and existing search
  gates remain green.

Accepted evidence: 2,568 local Python cases (2,185 passed, 383 environment-gated),
134 browser cases, the repository deployment gate, the pinned donor's 47 archive
tests and six-case live parity corpus passed. Hosted
[CI 35803130109](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35803130109)
and [restore 35803130165](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35803130165)
passed, including real PostgreSQL publication/replay and all restricted worker images.

## Non-goals

No discovery, preview continuation, generated keys, best-effort skip/continue,
parallelism, scheduler, public API, automatic inventory-wide publication, archive
upload, non-text extraction, source effect or FOS-Master cutover is authorized.
