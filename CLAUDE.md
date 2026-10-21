<!-- THIN PRODUCT CLAUDE.md — written 2026-10-21 from ../CW-Factory/_SYSTEM/templates/PRODUCT_CLAUDE.thin.md
     (Factory work order WO-2026-10-21-1 item 2). It replaces factory/CLAUDE.md.template, the staged
     draft, so one template remains. Drift gate: python3 ../CW-Factory/_SYSTEM/tools/assemble_claude.py check --product . -->

# MasterBrain

**Product id:** `masterbrain` · **Domain:** evidence-first email and file knowledge with progressive assistant access · **Unit of work:** source item

This repo is a **Product**. It runs the Factory's shared behaviour; it does not carry a
copy of it. The binding is for DEVELOPMENT sessions only: the deployed MasterBrain
application never imports the Factory at runtime (DECISIONS.md:678).

## The Factory runtime contract

@../CW-Factory/FACTORY.md

That import is the whole shared layer: the session model, the one write rule, what the
bind verifies, the isolation rules, where the commands come from. It is read live from
the sibling Factory checkout — never copied here.

**If the import did not load** (the sections above are missing, or `Q:` commands are
unknown), STOP and say so. Do not improvise the missing rules and do not copy
`FACTORY.md` into this repo. Fix it in this order:

1. add the Factory to this Product's additional-directories / `--add-dir` setting;
2. only if that is impossible, run
   `python3 ../CW-Factory/_SYSTEM/tools/factory_launch.py gen-bootstrap` and paste the
   short section it prints below this line.

## This Product's own layer

See **[`PRODUCT.md`](PRODUCT.md)** — persona, domain rules, Product-only commands, and
the hooks this Product provides at the Factory's session slots.

## Session start

`Q: Start`. Its first mechanical act is the bind:

```bash
python3 ../CW-Factory/_SYSTEM/tools/factory_launch.py bind --product .
```

Line 1 of the output is the binding — the Product, the Factory commit, the branch, the
clean check, the contract version, and PASS. **If line 1 is not a PASS, the session
does not continue.** A Product running against an unverified Factory is a Product
running unknown code.

## What this Product never does

**It never writes to the Factory.** Not the registry, not `PRODUCTS.md`, not the KB,
not `_SYSTEM/products/`. Everything produced here stays here; the Factory pulls what it
wants later. A dirty Factory tree after a session in this repo is, by definition, a bug
in what just ran.
