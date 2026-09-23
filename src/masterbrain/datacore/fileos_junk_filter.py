#!/usr/bin/env python3
"""
junk_filter.py — THE single source of truth for "what is OS/system junk".

Why this exists
---------------
The ignore-set (`.DS_Store`, `~$` Office locks, `__MACOSX/`, …) used to be copy-pasted
into scan_domains.py, safe_fileops.py, census.py, zip_index.py, … Every copy drifted a
little. A reconciler that walks disk with a DIFFERENT ignore-set than the scanner reports
phantom "gaps" that aren't real. So the scanner AND the reconciler must share ONE filter.
This is that filter. (Same lesson as domain_paths.py: one resolver, imported everywhere.)

Sources (verbatim patterns, July 2026)
--------------------------------------
- github/gitignore  Global/macOS.gitignore   — .DS_Store, ._*, .Spotlight-V100, .Trashes,
                    .fseventsd, .TemporaryItems, .DocumentRevisions-V100, .AppleDouble, …
- github/gitignore  Global/Windows.gitignore — Thumbs.db(+:encryptable), ehthumbs*.db,
                    [Dd]esktop.ini, $RECYCLE.BIN/, *.stackdump
- Microsoft Office lock/owner files          — ~$*   (Word/Excel/PowerPoint open-lock stub)
- LibreOffice lock files                     — .~lock.*#

DESIGN RULE — the dot-directory distinction
--------------------------------------------
A leading '.' on a *directory* does NOT mean junk. `.Spotlight-V100` is junk; `.Investor
Letters` is a user's real content folder. We therefore prune a directory ONLY when it is a
*named* junk/system dir (denylist below) or an AppleDouble `._` dir — never on a blanket
`startswith('.')`. Any other dot-dir is treated as CONTENT and scanned. (Blanket dot-dir
pruning is exactly the bug that silently dropped 36 real docs from partnership-docs.)

macOS `.DS_Store` etc. are Finder/OS-managed — we IGNORE them (never index, never count,
never delete). This module only *classifies*; it never touches the filesystem.
"""
from __future__ import annotations

# ─────────────────────────────────────────────────────────────────────────────
# FILES — exact names to ignore (case-insensitive match applied in is_junk_file)
# ─────────────────────────────────────────────────────────────────────────────
JUNK_FILE_NAMES = {
    # macOS
    ".ds_store", ".localized", ".appledouble", ".lsoverride",
    ".volumeicon.icns", ".com.apple.timemachine.donotpresent",
    "icon\r",                          # custom folder-icon marker (Icon + CR)
    # Windows
    "thumbs.db", "thumbs.db:encryptable", "ehthumbs.db", "ehthumbs_vista.db",
    "desktop.ini",
    # FOS-generated (PERDOMAIN-STATUS, 2026-08-03) — dashboards.py writes this into
    # every domain root at each Q: End. Regenerated meta/status, not a domain document
    # Jim would search for; without this, reconcile flags it as "unindexed" every wrap.
    "_status.html",
}

# FILES — prefixes
JUNK_FILE_PREFIXES = (
    "._",        # AppleDouble resource-fork sidecar
    "~$",        # MS Office lock/owner stub
    ".~lock.",   # LibreOffice lock
    ".~",        # misc temp-lock
)

# FILES — suffixes (kept deliberately tiny; .tmp is NOT here — too often real)
JUNK_FILE_SUFFIXES = (
    ".stackdump",   # Windows crash dump
)

# ─────────────────────────────────────────────────────────────────────────────
# DIRECTORIES — named junk/system dirs to prune (NOT a blanket dot-dir prune)
# ─────────────────────────────────────────────────────────────────────────────
JUNK_DIR_NAMES = {
    # macOS / volume system
    "__macosx", ".spotlight-v100", ".trashes", ".temporaryitems", ".fseventsd",
    ".documentrevisions-v100", ".appledouble", ".appledb", ".appledesktop",
    ".trashcanfolders", ".pkinstallsandboxmanager", ".mobilebackups",
    "backups.backupdb", "network trash folder", "temporary items", "lost+found",
    ".trash", ".thumbnails",
    # Windows
    "$recycle.bin", "system volume information",
    # VCS / dev tooling (rare in doc corpora, but must never be indexed)
    ".git", ".svn", ".hg", ".vscode", ".idea", ".cache", ".venv", ".env",
    ".tox", ".pytest_cache", ".mypy_cache", ".ipynb_checkpoints", "node_modules",
}

# DIRECTORIES — prefixes (AppleDouble dirs)
JUNK_DIR_PREFIXES = ("._",)

# FOS operational dirs — not OS junk, but never part of a domain's document set.
# Scanner prunes these; reconciler treats files under them as "operational" (ignore).
SKIP_SUBDIRS = {"_SYSTEM", "_FILEOP_LOG", "_DocsToAdd", "_DocsToMove"}


# ─────────────────────────────────────────────────────────────────────────────
# API
# ─────────────────────────────────────────────────────────────────────────────
def is_junk_file(name: str) -> bool:
    """True if *name* is an OS/system/lock file that must never be indexed."""
    low = name.lower()
    if low in JUNK_FILE_NAMES:
        return True
    if name.startswith(JUNK_FILE_PREFIXES):
        return True
    if low.endswith(JUNK_FILE_SUFFIXES):
        return True
    return False


def is_junk_dir(name: str) -> bool:
    """True if *name* is a named OS/system/dev junk dir (denylist, not dot-blanket)."""
    if name.lower() in JUNK_DIR_NAMES:
        return True
    if name.startswith(JUNK_DIR_PREFIXES):
        return True
    return False


def is_operational_dir(name: str) -> bool:
    """True if *name* is a FOS operational dir (real, but not a domain document)."""
    return name in SKIP_SUBDIRS


def classify_dir(name: str) -> str:
    """'junk' | 'operational' | 'content'. A dot-dir that is not named junk is CONTENT."""
    if is_junk_dir(name):
        return "junk"
    if is_operational_dir(name):
        return "operational"
    return "content"


def prune_dirs(dirnames: list[str]) -> list[str]:
    """
    In-place os.walk dir pruning: drop junk + operational dirs, KEEP content dot-dirs.
    Usage:  for dp, dns, fns in os.walk(root): junk_filter.prune_dirs(dns)
    Returns the list too (for convenience).
    """
    dirnames[:] = [d for d in dirnames
                   if not is_junk_dir(d) and not is_operational_dir(d)]
    return dirnames


def path_skip_reason(rel_posix: str) -> str | None:
    """
    Classify why a relative path (posix, WITHOUT domain prefix) would be excluded
    from the index — or None if it SHOULD be indexed. Used by the reconciler to
    explain every disk file that is not in the index.

    Returns one of:
      'junk_file'      leaf is an OS/lock file            (ignore — expected)
      'junk_dir'       a path segment is a junk/system dir (ignore — expected)
      'operational'    a path segment is a FOS op dir      (ignore — expected)
      'hidden_content' a segment is a dot-dir NOT on the junk list (FLAG: real
                       content the old blanket-prune skipped; a re-scan indexes it)
      None             should be indexed — if it's missing that's an UNEXPLAINED miss
    """
    parts = rel_posix.split("/")
    leaf = parts[-1]
    if is_junk_file(leaf):
        return "junk_file"
    for seg in parts[:-1]:
        if is_junk_dir(seg):
            return "junk_dir"
        if is_operational_dir(seg):
            return "operational"
    for seg in parts[:-1]:
        if seg.startswith("."):
            return "hidden_content"
    return None


def _selftest() -> int:
    cases = [
        # (name/path, expected)
        (("file", ".DS_Store"), True),
        (("file", "Thumbs.db"), True),
        (("file", "~$Report.docx"), True),
        (("file", "._resource"), True),
        (("file", ".~lock.foo.odt#"), True),
        (("file", "Q1 2026 Investor Letter.pdf"), False),
        (("file", "normal.xlsx"), False),
        (("dir", "__MACOSX"), True),
        (("dir", ".Spotlight-V100"), True),
        (("dir", ".git"), True),
        (("dir", "._hiddendir"), True),
        (("dir", ".Investor Letters"), False),   # ← content, must NOT be junk
        (("dir", "GKL-LIBRARY"), False),
    ]
    fails = 0
    for (kind, val), exp in cases:
        got = is_junk_file(val) if kind == "file" else is_junk_dir(val)
        ok = got == exp
        fails += not ok
        print(f"  {'ok ' if ok else 'FAIL'}  {kind:4} {val!r:40} junk={got} exp={exp}")
    # path_skip_reason cases
    preason = [
        ("GKL-LIBRARY/LT/.Investor Letters/2026/Q1.pdf", "hidden_content"),
        ("GKL-LIBRARY/normal/report.pdf", None),
        ("Melron/~$sheet.xlsx", "junk_file"),
        ("__MACOSX/foo/bar.pdf", "junk_dir"),
        ("_SYSTEM/state.json", "operational"),
    ]
    for rel, exp in preason:
        got = path_skip_reason(rel)
        ok = got == exp
        fails += not ok
        print(f"  {'ok ' if ok else 'FAIL'}  reason {rel!r:48} -> {got} exp={exp}")
    print(f"\n{'PASS' if not fails else 'FAIL'} — {len(cases)+len(preason)} checks, {fails} failed")
    return 1 if fails else 0


if __name__ == "__main__":
    import sys
    sys.exit(_selftest())
