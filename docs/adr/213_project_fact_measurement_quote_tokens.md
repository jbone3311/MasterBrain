# ADR-213 — Complete quote tokens for reviewed measurements

Status: implemented for fictional testing on an open PR; hosted exact-head,
independent restore and merged-main gates remain required.

## Problem and decision

ADR-212 required the exact amount and unit/currency strings to occur in the
reviewed source quote, but literal substring matching would accept `100.25`
inside `1100.25`, or `USD` inside `USDA`. That is not a valid measurement
citation. It could mislead a future report even though no totals are enabled.

New typed project facts require a complete lexical amount token and a complete
unit/currency token. The Python write model and migration 0072's database
constraint independently enforce this. A token may be surrounded by ordinary
punctuation, such as `($100.25), in USD;`; it may not be embedded in another
letter/digit/underscore word or a larger decimal. A positive amount must not
match inside a negative amount. This remains a lexical check, not a semantic
number parser, currency registry, source-tier certificate or ownership proof.

Migration 0072 replaces the prior constraint transactionally and validates all
existing rows. If any previously reviewed typed row only passed the weaker
substring test, the migration fails closed. It does not rewrite or delete that
row; an operator must investigate the exact reviewed source and choose an
explicit remediation before retrying. Untyped historical rows remain valid.

## Verification and rollback

Fictional pure-model and PostgreSQL direct-insert tests include prefixed
amounts, negative amounts, longer currency words and a punctuation-valid
counterexample. The SQL test uses a current fictional source quote containing
the misleading text so the existing source-basis trigger does not mask the
new constraint. Migration/recovery tests require 0072 explicitly. Rollback
of application use retains reviewed rows and their stronger constraint; do
not weaken it automatically. No FOS-Master file, live source or external
side effect changes.
