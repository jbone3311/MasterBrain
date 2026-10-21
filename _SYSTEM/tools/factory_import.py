# cw-factory-import-helper: template-sha256=92b77bb031dcacd66269be18f69c39d9a5456c29e80083c6116af3d9eeb0593a — installed by factory_launch.py install-import-helper; do not edit, re-run the installer
"""factory_import.py — let this Product's own scripts IMPORT Factory tools, guarded.

THIS FILE IS FACTORY-BUILT. It is the template `_SYSTEM/templates/product_factory_import.py`,
installed into a Product at `INSTALL_REL` (below) by

    python3 <factory>/_SYSTEM/tools/factory_launch.py install-import-helper --product <product>

and carries a `# cw-factory-import-helper: template-sha256=...` header line so the bind can
say when this copy no longer matches the Factory's template. Never edit the installed copy
and never hand-copy it into another Product: a hand-copied helper is a helper with N
versions, which is exactly the drift this file replaces (Q-485, FACTORY-173).

USE, from any script under the Product's `_SYSTEM/tools/`:

    import factory_import
    factory_import.enable()          # raises FactoryImportError when it cannot
    from _lib import factory_db      # a Factory module, imported in-process
    import product_paths             # a Factory tool module

WHAT enable() DOES, in this order — and nothing it does is a fallback:

  1. Finds this Product from THIS FILE's location (never from the record, never from the
     environment) and checks its `MANIFEST.json` says `role: product`.
  2. Reads the record the bind wrote, `_SYSTEM/_MEMORY/_ACTIVE_SESSION.json`
     (`factory_root`, `product_root`, `binding_token`). No record, an unreadable one, one
     naming another Product, or one whose Factory is gone or is not a Factory -> a
     FactoryImportError that says to run the bind. There is no second place it looks: a
     helper that falls back to `FACTORY_ROOT` or a sibling `../CW-Factory` imports a
     Factory nobody bound.
  3. Checks the recorded Factory with the launcher's static identity test —
     `MANIFEST.json` `role: factory` and `FACTORY.md` present — plus the two files the
     guard needs: `_SYSTEM/tools/_lib/scope_audit_hook.py` and `_SYSTEM/tools/sitecustomize.py`.
  4. Exports the binding environment into `os.environ` exactly as the bind does —
     `PRODUCT_ROOT`, `FACTORY_ROOT`, `CW_BINDING_TOKEN`, `PYTHONDONTWRITEBYTECODE=1`, and
     `<factory>/_SYSTEM/tools` prepended to `PYTHONPATH` — so every CHILD interpreter this
     script starts runs the Factory's `sitecustomize.py` and is guarded at startup.
  5. ARMS the Product-side write guard in THIS process: the Factory's own
     `_lib/scope_audit_hook.install()`, the same entry a bound session and every launcher
     child use. Writes into the Factory, and any access to another registered Product, are
     refused from here on.
  6. APPENDS `<factory>/_SYSTEM/tools` to `sys.path` — last, so a Factory module can never
     shadow the standard library, an installed package, or one of this Product's own
     modules in the enabling process.

Calling enable() twice is a no-op the second time. On any failure the environment is put
back as it was, so a refused enable() leaves no half binding behind.

HONEST LIMITS, stated rather than implied:
  * The record is a CLAIM. The launcher's `run` re-derives the Factory from its own
    location; a file inside a Product cannot, so a Product that rewrites its own record to
    point at a look-alike tree arms the guard around the look-alike. The static identity
    test above is the ceiling here. The agent-layer PreToolUse guard is the layer that does
    not depend on this file.
  * Name collisions are real: a child interpreter imports the Factory's `_lib` package at
    startup (its guard lives there), so a Product package also named `_lib` is shadowed in
    every child. Give Product packages Product-only names.
  * `python3 -S`, `-E` and `-I` skip the startup hook that guards a child; those are the
    agent-layer guard's to refuse.

READS: this Product's `MANIFEST.json` and `_SYSTEM/_MEMORY/_ACTIVE_SESSION.json`; the
recorded Factory's `MANIFEST.json`, and `_SYSTEM/products/*/product.json` (via the guard).
WRITES: nothing on disk. Mutates `os.environ`, `sys.path` and `sys.dont_write_bytecode`,
and installs an audit hook (which cannot be removed from a live process).
CALLED BY: a Product's own scripts. Named tests (in the Factory):
`tests/gates/test_product_factory_import.py`.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys

#: Where the installer puts this file inside a Product, relative to the Product root. The
#: installer reads THIS constant (it never hard-codes the path), and `_product_root()`
#: below derives the Product root from it, so the two cannot disagree.
INSTALL_REL = "_SYSTEM/tools/factory_import.py"

SESSION_REL = ("_SYSTEM", "_MEMORY", "_ACTIVE_SESSION.json")
BINDING_KEYS = ("CW_BINDING_TOKEN", "FACTORY_ROOT", "PRODUCT_ROOT")
_GUARD_MODULE = "_cw_factory_import_scope_audit_hook"

_state: dict = {"enabled": None}


class FactoryImportError(RuntimeError):
    """enable() could not bind this process to a Factory. The message says what to do."""


def _refuse(what: str, fix: str = "") -> FactoryImportError:
    tail = fix or ("run the bind first, from this Product: python3 "
                   "<factory>/_SYSTEM/tools/factory_launch.py bind --product <this Product>")
    return FactoryImportError(f"factory_import: {what} — {tail}")


def _product_root() -> str:
    """The Product this file is installed in, from its own location and INSTALL_REL."""
    here = os.path.realpath(__file__)   # factory-root: a Product-side helper must find ITS Product from where it is installed, never from the record it is about to check
    root = here
    for _ in INSTALL_REL.split("/"):
        root = os.path.dirname(root)
    expected = os.path.realpath(os.path.join(root, *INSTALL_REL.split("/")))
    if expected != here:
        raise _refuse(f"this helper is at {here}, not at <Product>/{INSTALL_REL}",
                      "install it with factory_launch.py install-import-helper --product "
                      "<Product>; it finds its Product from where the installer puts it")
    return root


def _role(root: str) -> str:
    try:
        with open(os.path.join(root, "MANIFEST.json"), encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return ""
    return str(data.get("role", "")) if isinstance(data, dict) else ""


def _same(a: str, b: str) -> bool:
    return os.path.realpath(a) == os.path.realpath(b)


def _read_record(product: str) -> dict:
    path = os.path.join(product, *SESSION_REL)
    if not os.path.isfile(path):
        raise _refuse(f"no bind record at {path} (this Product has not been bound, or the "
                      "record was removed)")
    try:
        with open(path, encoding="utf-8") as f:
            record = json.load(f)
    except (OSError, ValueError) as e:
        raise _refuse(f"the bind record {path} is unreadable ({type(e).__name__}: {e})") from e
    if not isinstance(record, dict):
        raise _refuse(f"the bind record {path} is not a JSON object")
    return record


def _checked_factory(record: dict, product: str) -> tuple:
    claimed_product = record.get("product_root")
    if not isinstance(claimed_product, str) or not claimed_product \
            or not _same(claimed_product, product):
        raise _refuse(f"the bind record names Product {claimed_product!r}, not this one "
                      f"({product}) — a STALE record, most often copied or moved")
    factory = record.get("factory_root")
    if not isinstance(factory, str) or not factory:
        raise _refuse("the bind record names no factory_root")
    factory = os.path.realpath(factory)
    if not os.path.isdir(factory):
        raise _refuse(f"the bind record names a Factory that does not exist ({factory}) — "
                      "a STALE record")
    if _role(factory) != "factory" or not os.path.isfile(os.path.join(factory, "FACTORY.md")):
        raise _refuse(f"the bind record names {factory}, which is not a Factory "
                      "(MANIFEST.json role: factory and FACTORY.md are required)")
    tools = os.path.join(factory, "_SYSTEM", "tools")
    for need in (os.path.join("_lib", "scope_audit_hook.py"), "sitecustomize.py"):
        if not os.path.isfile(os.path.join(tools, need)):
            raise _refuse(f"the Factory at {factory} has no _SYSTEM/tools/{need}, so its "
                          "write guard cannot be armed here or carried into child processes",
                          "update the Factory checkout, then bind again")
    token = record.get("binding_token")
    if not isinstance(token, str) or not token:
        raise _refuse("the bind record carries no binding_token")
    return factory, tools, token


def _load_guard(tools: str):
    """The Factory's own `_lib/scope_audit_hook.py`, loaded by PATH under a private name —
    so a Product package that is itself called `_lib` can neither hide it nor be replaced
    by it in this process."""
    mod = sys.modules.get(_GUARD_MODULE)
    if mod is not None:
        return mod
    path = os.path.join(tools, "_lib", "scope_audit_hook.py")
    spec = importlib.util.spec_from_file_location(_GUARD_MODULE, path)
    if spec is None or spec.loader is None:
        raise _refuse(f"cannot load the write guard from {path}",
                      "update the Factory checkout, then bind again")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    sys.modules[_GUARD_MODULE] = mod
    return mod


def enable() -> str:
    """Bind THIS process to the Factory the bind recorded, guarded. Returns the Factory root.

    Raises FactoryImportError — never a silent fallback — when there is no usable record."""
    if _state["enabled"]:
        return _state["enabled"]
    product = _product_root()
    if _role(product) != "product":
        raise _refuse(f"{product} is not a Product root (MANIFEST.json role: product)",
                      "install this helper only into a Product")
    record = _read_record(product)
    factory, tools, token = _checked_factory(record, product)

    # A process started under a live binding (a launcher child) already carries one. Two
    # opinions about which Factory or Product is bound is a refusal, never a pick.
    for key, want in (("FACTORY_ROOT", factory), ("PRODUCT_ROOT", product)):
        have = os.environ.get(key)
        if have and not _same(have, want):
            raise _refuse(f"{key}={have} in this process's environment disagrees with the "
                          f"bind record ({want})", "re-bind, then start this script again")

    saved = {k: os.environ.get(k) for k in (*BINDING_KEYS, "PYTHONPATH",
                                            "PYTHONDONTWRITEBYTECODE")}
    saved_dwb = sys.dont_write_bytecode
    try:
        os.environ["PRODUCT_ROOT"] = product
        os.environ["FACTORY_ROOT"] = factory
        if not os.environ.get("CW_BINDING_TOKEN"):
            os.environ["CW_BINDING_TOKEN"] = token
        # No bytecode lands in the Factory: an import that wrote a .pyc there would be a
        # Factory write, and the guard armed below would refuse it mid-import.
        os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
        sys.dont_write_bytecode = True
        prev = [p for p in os.environ.get("PYTHONPATH", "").split(os.pathsep) if p and p != tools]
        os.environ["PYTHONPATH"] = os.pathsep.join([tools, *prev])
        guard = _load_guard(tools)
        try:
            armed = guard.install()
        except Exception as e:  # noqa: BLE001 — ScopeViolation and anything else: refuse, loudly
            raise _refuse(f"the Factory write guard refused to arm ({type(e).__name__}: {e})",
                          "fix what it names, then bind again") from e
        if not armed:
            raise _refuse("the Factory write guard did not arm (no binding environment)",
                          "this is a defect in the helper or the guard — report it")
    except BaseException:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        sys.dont_write_bytecode = saved_dwb
        raise
    if tools not in sys.path:
        sys.path.append(tools)
    _state["enabled"] = factory
    return factory


if __name__ == "__main__":
    try:
        root = enable()
    except FactoryImportError as e:
        print(f"✗ {e}", file=sys.stderr)
        raise SystemExit(1) from None
    print(f"✓ factory_import: bound to {root}; the write guard is armed in this process "
          "and in every child it starts")
