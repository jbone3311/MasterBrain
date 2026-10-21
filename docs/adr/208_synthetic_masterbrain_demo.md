# ADR-208 — Disposable combined-source MasterBrain demo

Status: accepted for synthetic, loopback-only implementation. No live source,
hosted identity, automatic Knowledge inference, FileOS effect or FOS-Master
cutover is authorized.

## Context

The existing `init-demo`/`seed-demo` path demonstrates the internal Email
capability only. Its human token deliberately lacks Brain and Knowledge read
scopes, and its seed stops before the shared DataCore bridge. A fresh local
PostgreSQL/API smoke can therefore search fictional Email but receives 403 from
`/v1/brain/search`. That is correct for the old demo but insufficient for
testing the combined MasterBrain product.

## Decision

- Keep the Email-only commands and their credential scopes unchanged. Add
  separate `init-masterbrain-demo` and `seed-masterbrain-demo` commands for a
  fresh disposable database and private state directory outside Dropbox.
  Expose the same migration, initialization, seed and loopback serve flow
  through `masterbrain demo` so the product entry point is MasterBrain while
  the internal Email CLI remains compatible.
  The new owner token gains only Email, Brain and Knowledge **read** scopes,
  plus `knowledge.review` to exercise explicit owner decisions. It never gets
  worker intake/index scopes, source effects, or assistant privileges.
- Seed a small fictional Email set through the existing ingestion path, bridge
  its current versions through DataCore, and import/publish one local fictional
  text file through the existing FileOS snapshot and text primitives. The
  fixture uses deterministic content, a dedicated source ID and replay-safe
  keys; it does not read any user-selected root, mail account or token. The
  generated local file lives only in the private demo state directory.
- Publish one explicitly synthetic, reviewed project joining an Email and a
  FileOS evidence occurrence. Both source bodies must contain the project's
  exact quote; a merely linked but unrelated email is not acceptable evidence.
  Complete and activate the fictional FileOS run/index so both sources appear
  in current search, not only historical combined search. The current Brain
  API and cited dossier can then be exercised. This is a fixture, not model
  judgment or an assertion about real financial records. Never make the demo
  seed a production enrollment.
- Add only source-supported fictional dossier rows: an undated briefing event,
  a proposed reply request whose relative due date remains unresolved, a
  source-stated project note and a link to the generated text file. Each has
  an exact quote, current evidence and a deterministic replay key. Do not
  fabricate a person/role assertion from the email sender or treat the reply
  request as an accepted commitment.
- Refuse the combined seed when the state marker was not created by the
  combined initializer. Before any ingest or publication, verify the database
  tenant and account exactly match the initializer's fictional tenant name,
  inactive provider binding, invalid-domain address and synthetic secret
  reference. Preserve the old commands and require the normal runtime
  database role; the CLI never uses an administrative DSN for seeding.

## Verification and rollback

Use a fresh disposable PostgreSQL 17 database and private fictional state.
Check old token scopes unchanged; combined token has no worker/effect scopes;
wrong account/state refuses before any provider event;
seed/replay; Email and FileOS Brain search; cited combined project dossier;
exact quote in both linked original source bodies; owner-only Markdown
inspection without automatic publication; source presence/absence; no live
network or source effects. Confirm that replay does not duplicate dossier
rows and that the relative due date stays null. Run full local,
browser, docs and deployment gates. Hosted exact-head CI remains mandatory
before merge. Rollback removes the two new commands while preserving any
already-generated fictional test records for normal disposable-state cleanup.
