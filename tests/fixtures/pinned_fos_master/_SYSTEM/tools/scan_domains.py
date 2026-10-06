#!/usr/bin/env python3
"""scan_domains.py — Direct Dropbox FOS-* domain scanner (v2.0 architecture).

Replaces the MasterUpdate ZIP workflow. Walks Dropbox FOS-* folders directly
and syncs the unified_index (FTS5) without spoke cooperation or ZIP files.

Usage:
    python3 scan_domains.py --all                      # scan all registered domains
    python3 scan_domains.py --domain FOS-Personal      # scan one domain
    python3 scan_domains.py --all --dry-run            # preview without writing
    python3 scan_domains.py --all --changed-since 7d   # only files modified in last 7 days

Output:
    Per-domain: added / removed / unchanged counts
    Updates: unified_index, unified_index_fts, domain registry last_scan
"""

import argparse
import hashlib
import json
import os
import re
import sqlite3
import sys
import zlib
from datetime import date, datetime, timedelta
from pathlib import Path

# THE single shared OS-junk ignore-set (one source of truth for scanner+reconciler).
sys.path.insert(0, str(Path(__file__).resolve().parent))
import junk_filter

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

DROPBOX = Path("~/Library/CloudStorage/Dropbox").expanduser()
ROOT = Path(__file__).parent.parent.parent   # FOS-Master root
DB_PATH = ROOT / "_SYSTEM" / "tools" / "spoke_state.db"
DOMAIN_REGISTRY = ROOT / "_SYSTEM" / "_MEMORY" / "_DOMAIN_REGISTRY.json"

# Seed map (the original 8). The live map is built by load_domain_map(), which
# merges in any domain registered in _DOMAIN_REGISTRY.json — so adding a domain
# needs only a registry entry (folder_name + id), NEVER a code edit here.
DEFAULT_DOMAIN_MAP = {
    "FOS-Personal":          "personal",
    "FOS-Work":              "work",
    "FOS-Investments":       "investments",
    # FOS-Divorce dissolved 2026-07-06 (files merged into FOS-Personal; 0 index rows,
    # removed from _DOMAIN_REGISTRY.json). Seed line removed so reconcile stops flagging
    # its vanished root. Its history stays queryable via file_history (prev_domain='divorce').
    "FOS-Art-Studio":        "art-studio",
    "FOS-9990PrivateEquity": "9990privateequity",
    "FOS-FileCabinet":       "filecabinet",
    "FOS-PCS-DOCS":          "pcs-docs",
}


def load_domain_map() -> dict:
    """Build {folder_name: domain_id} — registry-driven (STD v2.0 add-domain).

    Seeded by DEFAULT_DOMAIN_MAP, then overlaid with every domain in
    _DOMAIN_REGISTRY.json that carries a folder_name + id. New domains are
    picked up automatically; no hardcoded edit required."""
    m = dict(DEFAULT_DOMAIN_MAP)
    try:
        data = json.loads(DOMAIN_REGISTRY.read_text())
        for d in data.get("domains", []):
            folder = d.get("folder_name")
            did = d.get("id") or d.get("domain_id")
            if folder and did:
                m[folder] = did
    except Exception:
        pass  # registry missing/unreadable → fall back to defaults
    return m


def domain_abs_path(domain_id: str, folder_name: str) -> Path:
    """Resolve a domain's scan ROOT. A registry entry may carry an `abs_path`
    (a corpus living OUTSIDE Dropbox — e.g. a OneDrive folder); when present the
    corpus is scanned in place. Otherwise the root is DROPBOX/<folder_name> (the
    v2.0 default). This is the in-place bridge for non-Dropbox corpora — no files
    are moved and nothing is re-uploaded; full_path stays `domain_id/<rel>`."""
    try:
        data = json.loads(DOMAIN_REGISTRY.read_text())
        for d in data.get("domains", []):
            did = d.get("id") or d.get("domain_id")
            if did == domain_id and d.get("abs_path"):
                return Path(d["abs_path"]).expanduser()
    except Exception:
        pass
    return DROPBOX / folder_name

# Junk/system files + dirs are delegated to junk_filter.py (imported above) —
# THE single shared ignore-set. Do NOT re-list the patterns here: a scanner whose
# ignore-set drifts from the reconciler's manufactures phantom "gaps". The old
# local copy also blanket-pruned every dot-dir, which silently dropped real
# content folders (e.g. ".Investor Letters"). junk_filter fixes both.

DOC_TYPES = {
    ".pdf":  "PDF Document",
    ".docx": "Word Document",
    ".doc":  "Word Document",
    ".xlsx": "Excel Spreadsheet",
    ".xls":  "Excel Spreadsheet",
    ".xlsm": "Excel Spreadsheet",
    ".pptx": "PowerPoint",
    ".ppt":  "PowerPoint",
    ".txt":  "Text Document",
    ".md":   "Markdown",
    ".html": "HTML",
    ".htm":  "HTML",
    ".jpg":  "Image",
    ".jpeg": "Image",
    ".png":  "Image",
    ".heic": "Image",
    ".gif":  "Image",
    ".tiff": "Image",
    ".mp4":  "Video",
    ".mov":  "Video",
    ".mp3":  "Audio",
    ".m4a":  "Audio",
    ".zip":  "Archive",
    ".csv":  "CSV",
    ".json": "JSON",
    ".msg":  "Email Message",
    ".eml":  "Email",
    ".pages": "Pages Document",
    ".numbers": "Numbers Spreadsheet",
    ".key":  "Keynote",
}


def get_doc_type(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    return DOC_TYPES.get(ext, "Document")


def is_junk(name: str) -> bool:
    return junk_filter.is_junk_file(name)


def parse_changed_since(spec: str):
    """Parse '7d', '24h', '2w' into a cutoff datetime."""
    if not spec:
        return None
    m = re.match(r"^(\d+)([dhw])$", spec)
    if not m:
        return None
    n, unit = int(m.group(1)), m.group(2)
    delta = {"d": timedelta(days=n), "h": timedelta(hours=n), "w": timedelta(weeks=n)}[unit]
    return datetime.now() - delta


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def ensure_schema(conn: sqlite3.Connection) -> None:
    """Create unified_index + FTS5 if not present. Adds change-detection columns if missing."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS unified_index (
            id                    INTEGER PRIMARY KEY AUTOINCREMENT,
            domain                TEXT NOT NULL,
            subfolder             TEXT,
            filename              TEXT NOT NULL,
            doc_type              TEXT,
            full_path             TEXT UNIQUE NOT NULL,
            sha256                TEXT,
            mtime                 REAL,
            size_bytes            INTEGER,
            crc32                 INTEGER,
            title                 TEXT,
            author                TEXT,
            text_preview          TEXT,
            created_date          TEXT,
            metadata_extracted    INTEGER DEFAULT 0,
            metadata_retry_count  INTEGER DEFAULT 0,
            embedding             BLOB,
            embedding_model       TEXT
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_unified_domain ON unified_index(domain)")
    # Add any missing columns to existing tables (idempotent)
    existing_cols = {r[1] for r in conn.execute("PRAGMA table_info(unified_index)").fetchall()}
    new_cols = [
        ("sha256",               "TEXT"),
        ("mtime",                "REAL"),
        ("size_bytes",           "INTEGER"),
        ("crc32",                "INTEGER"),
        ("title",                "TEXT"),
        ("author",               "TEXT"),
        ("text_preview",         "TEXT"),
        ("created_date",         "TEXT"),
        ("metadata_extracted",   "INTEGER DEFAULT 0"),
        ("metadata_retry_count", "INTEGER DEFAULT 0"),
        ("embedding",            "BLOB"),
        ("embedding_model",      "TEXT"),
        # S28 STD-FILE-ROUTING-001 — routing decision audit columns
        ("routing_source",       "TEXT"),
        ("routing_reason",       "TEXT"),
        ("routing_decided_at",   "TEXT"),
        ("routing_operation",    "TEXT"),
        ("last_extracted_at",    "TEXT"),
        # date fields (per Jim): when added/updated in the DB + filesystem birth time
        ("indexed_at",           "TEXT"),   # first added to the index (ISO)
        ("updated_at",           "TEXT"),   # row last changed in the index (ISO)
        ("file_created",         "REAL"),   # filesystem st_birthtime (epoch)
    ]
    for col, ctype in new_cols:
        if col not in existing_cols:
            conn.execute(f"ALTER TABLE unified_index ADD COLUMN {col} {ctype}")
    # FTS5 with trigram tokenizer — 7 columns (includes title + text_preview for content search)
    existing = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='unified_index_fts'"
    ).fetchone()
    if not existing:
        conn.execute("""
            CREATE VIRTUAL TABLE unified_index_fts USING fts5(
                domain, subfolder, filename, doc_type, full_path, title, text_preview,
                content=unified_index, content_rowid=id,
                tokenize='trigram'
            )
        """)
        # Auto-sync triggers (7-column version)
        conn.execute("""CREATE TRIGGER IF NOT EXISTS unified_fts_ai
            AFTER INSERT ON unified_index BEGIN
                INSERT INTO unified_index_fts(rowid, domain, subfolder, filename, doc_type, full_path, title, text_preview)
                VALUES(new.id, new.domain, new.subfolder, new.filename, new.doc_type, new.full_path, new.title, new.text_preview);
            END""")
        conn.execute("""CREATE TRIGGER IF NOT EXISTS unified_fts_ad
            AFTER DELETE ON unified_index BEGIN
                INSERT INTO unified_index_fts(unified_index_fts, rowid, domain, subfolder, filename, doc_type, full_path, title, text_preview)
                VALUES('delete', old.id, old.domain, old.subfolder, old.filename, old.doc_type, old.full_path, old.title, old.text_preview);
            END""")
        conn.execute("""CREATE TRIGGER IF NOT EXISTS unified_fts_au
            AFTER UPDATE ON unified_index BEGIN
                INSERT INTO unified_index_fts(unified_index_fts, rowid, domain, subfolder, filename, doc_type, full_path, title, text_preview)
                VALUES('delete', old.id, old.domain, old.subfolder, old.filename, old.doc_type, old.full_path, old.title, old.text_preview);
                INSERT INTO unified_index_fts(rowid, domain, subfolder, filename, doc_type, full_path, title, text_preview)
                VALUES(new.id, new.domain, new.subfolder, new.filename, new.doc_type, new.full_path, new.title, new.text_preview);
            END""")
    conn.commit()


def get_existing_with_mtime(conn: sqlite3.Connection, domain_id: str) -> dict:
    """Return dict of full_path → (mtime, size_bytes, crc32) for fast-path skip."""
    rows = conn.execute(
        "SELECT full_path, mtime, size_bytes, crc32 FROM unified_index WHERE domain = ?",
        (domain_id,)
    ).fetchall()
    return {r[0]: (r[1], r[2], r[3]) for r in rows}


def file_changed(stored: tuple | None, fpath: Path) -> bool:
    """Fast-path change detection. Returns True if file needs re-indexing."""
    if stored is None:
        return True  # new file
    stored_mtime, stored_size, stored_crc = stored
    try:
        st = fpath.stat()
    except OSError:
        return True
    if stored_mtime and abs(stored_mtime - st.st_mtime) < 1.0 and stored_size == st.st_size:
        return False  # definitely unchanged
    if stored_crc is not None:
        try:
            crc = zlib.crc32(fpath.read_bytes()) & 0xFFFFFFFF
        except OSError:
            # unreadable right now (cloud-placeholder timeout, permission, vanished
            # mid-scan) -- same conservative "treat as changed" as the stat() failure
            # above, not a crash that kills the whole scan over one file.
            return True
        return crc != stored_crc
    return True  # no CRC stored yet — treat as changed


def insert_files(conn: sqlite3.Connection, rows: list[tuple]) -> int:
    """Insert new/updated rows into unified_index. Returns count inserted.

    S28 STD-FILE-ROUTING-001: also sets routing_source='path_match' +
    routing_operation='discovery' with a reason explaining the domain
    assignment came from the file's parent folder. Includes sha256 (B4 fix:
    audit trail unusable without it).

    Accepts either 8-tuple (legacy: no sha256) or 9-tuple (sha256 included).
    """
    if not rows:
        return 0
    today = date.today().isoformat()
    now = datetime.now().isoformat(timespec="seconds")
    augmented = []
    for r in rows:
        domain, subfolder, filename, doc_type, full_path = r[0], r[1], r[2], r[3], r[4]
        mtime, size_bytes, crc32, sha = r[5], r[6], r[7], r[8]
        birthtime = r[9] if len(r) > 9 else None
        reason = f"scan_domains: discovered in FOS-{domain}/{subfolder or ''} (path-based domain assignment)"
        augmented.append((domain, subfolder, filename, doc_type, full_path,
                          mtime, size_bytes, crc32, sha, birthtime,
                          "path_match", reason, today, "discovery", now, now))
    conn.executemany(
        "INSERT OR IGNORE INTO unified_index "
        "(domain, subfolder, filename, doc_type, full_path, mtime, size_bytes, crc32, sha256, file_created, "
        " routing_source, routing_reason, routing_decided_at, routing_operation, indexed_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        augmented,
    )
    conn.commit()
    return len(rows)


def backfill_hashes(conn: sqlite3.Connection, rows: list[tuple]) -> int:
    """Write crc32+sha256 for files whose content is UNCHANGED but were indexed without a
    hash (--no-hash → sha256 NULL) and are now local. Touches ONLY the hash columns —
    enrichment (title/facts/embedding) is preserved (content didn't change)."""
    if not rows:
        return 0
    has_updated = any(r[1] == "updated_at" for r in conn.execute("PRAGMA table_info(unified_index)"))
    if has_updated:
        now = datetime.now().isoformat(timespec="seconds")
        payload = [(r[7], r[8], now, r[4]) for r in rows]   # (crc32, sha256, updated_at, full_path)
        conn.executemany(
            "UPDATE unified_index SET crc32=?, sha256=?, updated_at=? WHERE full_path=?", payload)
    else:
        payload = [(r[7], r[8], r[4]) for r in rows]
        conn.executemany(
            "UPDATE unified_index SET crc32=?, sha256=? WHERE full_path=?", payload)
    conn.commit()
    return len(rows)


def update_changed(conn: sqlite3.Connection, rows: list[tuple]) -> int:
    """UPDATE identity columns for files whose CONTENT changed (same path) — H1 fix.

    INSERT OR IGNORE can't update an existing full_path, so changed files were silently
    dropped (stale row + perpetual re-flagging). This refreshes mtime/size/crc/sha AND
    invalidates enrichment (facts/metadata/embedding) so stale derived data is recomputed
    on the next Extract/Embed pass. Enrichment is otherwise preserved (we never blanket
    INSERT OR REPLACE the row, which would wipe title/facts/embedding on every scan)."""
    if not rows:
        return 0
    cols = {r[1] for r in conn.execute("PRAGMA table_info(unified_index)")}
    today = date.today().isoformat()
    now = datetime.now().isoformat(timespec="seconds")
    set_parts = ["mtime=?", "size_bytes=?", "crc32=?", "sha256=?"]
    has_updated = "updated_at" in cols
    use_today = "routing_decided_at" in cols
    if has_updated:
        set_parts.append("updated_at=?")
    if use_today:
        set_parts.append("routing_decided_at=?")
    # invalidate stale enrichment — only for columns that exist in THIS db (schema varies, L5)
    INVALIDATE = {"facts_extracted": "NULL", "metadata_extracted": "0",
                  "last_extracted_at": "NULL", "embedding": "NULL", "embedding_model": "NULL"}
    set_parts += [f"{c}={lit}" for c, lit in INVALIDATE.items() if c in cols]
    sql = f"UPDATE unified_index SET {', '.join(set_parts)} WHERE full_path=?"
    payload = []
    for r in rows:
        full_path, mtime, size_bytes, crc32, sha = r[4], r[5], r[6], r[7], r[8]
        vals = [mtime, size_bytes, crc32, sha]
        if has_updated:
            vals.append(now)
        if use_today:
            vals.append(today)
        vals.append(full_path)
        payload.append(tuple(vals))
    conn.executemany(sql, payload)
    conn.commit()
    return len(rows)


def remove_paths(conn: sqlite3.Connection, paths: set[str]) -> int:
    """Remove stale entries + cascade their intelligence rows (M3 fix).

    Plain DELETE orphaned entity_mentions/document_facts (the FK is declared but not
    enforced unless foreign_keys=ON). We resolve the doc ids first, delete dependents,
    then the rows. Chunked to stay under SQLite's bound-variable limit."""
    if not paths:
        return 0
    plist = list(paths)
    ids = []
    for i in range(0, len(plist), 400):
        chunk = plist[i:i + 400]
        q = ",".join("?" * len(chunk))
        ids += [r[0] for r in conn.execute(
            f"SELECT id FROM unified_index WHERE full_path IN ({q})", chunk)]
    for tbl in ("entity_mentions", "document_facts"):
        for i in range(0, len(ids), 400):
            chunk = ids[i:i + 400]
            q = ",".join("?" * len(chunk))
            try:
                conn.execute(f"DELETE FROM {tbl} WHERE doc_id IN ({q})", chunk)
            except sqlite3.OperationalError:
                pass  # intelligence table not present in this DB
    conn.executemany("DELETE FROM unified_index WHERE full_path = ?", [(p,) for p in plist])
    conn.commit()
    return len(paths)


def rebuild_fts(conn: sqlite3.Connection) -> None:
    """Rebuild FTS5 index from unified_index content."""
    conn.execute("INSERT INTO unified_index_fts(unified_index_fts) VALUES('rebuild')")
    conn.commit()


# ---------------------------------------------------------------------------
# Domain scanner
# ---------------------------------------------------------------------------

SF_DATALESS = 0x40000000               # macOS dataless flag: cloud-only placeholder (reading downloads it).
                                       # NOTE: 0x40 is UF_TRACKED (set on ~all files) — NOT dataless.
MAX_HASH_BYTES = 2 * 1024 ** 3         # don't load files >2GB into RAM to hash


def _is_dataless(p: Path) -> bool:
    """True if the file is a Dropbox/cloud online-only placeholder — reading it
    would trigger a download. Never hash these (STD-DOCUMENT-HISTORY-001 §4)."""
    try:
        return bool(getattr(p.stat(), "st_flags", 0) & SF_DATALESS)
    except OSError:
        return False


def _hash_streaming(p: Path):
    """crc32 + sha256 read in 1MB chunks (no whole-file load → no OOM on big media)."""
    crc = 0
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            crc = zlib.crc32(chunk, crc)
            h.update(chunk)
    return crc & 0xFFFFFFFF, h.hexdigest()


def scan_domain(folder_name, domain_id, conn, changed_since=None, dry_run=False, no_hash=False, rehash=False, force_prune=False):
    """Walk a FOS-* folder and sync unified_index for that domain.

    no_hash=True → catalog by metadata only (stat size/mtime, NO byte read), so
    cloud-only / online-only files (Dropbox dataless placeholders) are indexed
    WITHOUT materializing them. sha256/crc are left NULL. Use for large online-only
    corpora that would otherwise trigger a full download."""
    domain_root = domain_abs_path(domain_id, folder_name)
    if not domain_root.exists():
        return {"domain": domain_id, "folder": folder_name, "error": "folder not found"}

    existing_data = get_existing_with_mtime(conn, domain_id)
    # --rehash: backfill content hashes for rows indexed with --no-hash (sha256 NULL),
    # now that the files are local. Forces a read of just those (unchanged) files.
    null_sha_paths: set[str] = set()
    if rehash and not no_hash:
        null_sha_paths = {r[0] for r in conn.execute(
            "SELECT full_path FROM unified_index WHERE domain=? AND sha256 IS NULL", (domain_id,))}
    seen_paths: set[str] = set()
    new_rows: list[tuple] = []
    changed_rows: list[tuple] = []
    rehash_rows: list[tuple] = []

    for dirpath, dirnames, filenames in os.walk(domain_root):
        dirpath_obj = Path(dirpath)

        # Prune junk + operational dirs in-place — but KEEP hidden CONTENT dirs.
        # junk_filter denylists real system dirs (.Spotlight-V100/.git/__MACOSX/…);
        # it deliberately does NOT blanket-prune every dot-dir, so a user's hidden
        # content folder (".Investor Letters") is scanned instead of silently dropped.
        junk_filter.prune_dirs(dirnames)

        for fname in filenames:
            if is_junk(fname):
                continue

            fpath = dirpath_obj / fname

            # changed_since filter
            if changed_since:
                try:
                    mtime = datetime.fromtimestamp(fpath.stat().st_mtime)
                    if mtime < changed_since:
                        continue
                except OSError:
                    continue

            # Build relative path components
            try:
                rel = fpath.relative_to(domain_root)
            except ValueError:
                continue

            parts = rel.parts
            subfolder = str(Path(*parts[:-1])) if len(parts) > 1 else ""
            full_path = f"{domain_id}/{rel.as_posix()}"

            seen_paths.add(full_path)

            stored = existing_data.get(full_path)
            changed = file_changed(stored, fpath)
            force_rehash = full_path in null_sha_paths   # backfill a missing hash (content unchanged)
            if not changed and not force_rehash:
                continue

            try:
                st = fpath.stat()                 # metadata only — safe on dataless placeholders
                if no_hash or _is_dataless(fpath) or st.st_size > MAX_HASH_BYTES:
                    crc = sha = None               # never read: online-only or too-big → no download/OOM
                else:
                    crc, sha = _hash_streaming(fpath)
                row = (domain_id, subfolder, fname, get_doc_type(fname), full_path,
                       st.st_mtime, st.st_size, crc, sha, getattr(st, "st_birthtime", None))
                if stored is None:
                    new_rows.append(row)            # H1: new path → INSERT
                elif changed:
                    changed_rows.append(row)        # content changed → UPDATE + invalidate enrichment
                else:
                    rehash_rows.append(row)         # unchanged, just backfilling the hash
            except OSError:
                continue

    stale_paths = set(existing_data.keys()) - seen_paths
    # Incremental scans (--changed-since) only enumerate RECENT files, so stale_paths
    # would wrongly include every older record. NEVER delete in incremental mode (data-loss guard).
    if changed_since:
        stale_paths = set()

    # MASS-PRUNE TRIPWIRE: a domain that "lost" most of its files at once is far
    # more likely unmounted / partially-synced / conflict-renamed than truly
    # emptied (2026-07: FOS-LT Lending vanished from OneDrive → 664 stale rows;
    # pruning cascades facts/embeddings — real derived-data loss). Refuse the
    # sweep; a human verifies the folder and reruns with --force-prune.
    prune_refused = 0
    if (stale_paths and not force_prune
            and len(stale_paths) >= 10
            and len(stale_paths) / max(1, len(existing_data)) >= 0.5):
        print(f"  🔴 {domain_id}: REFUSING to prune {len(stale_paths)}/{len(existing_data)} "
              f"index rows — ≥50% of the domain vanished in one scan (root unmounted, "
              f"partial sync, or conflict-renamed?). Verify the folder on disk, then "
              f"rerun with --force-prune if the removal is real.")
        prune_refused = len(stale_paths)
        stale_paths = set()

    added = updated = rehashed = removed = 0
    if not dry_run:
        added = insert_files(conn, new_rows)
        updated = update_changed(conn, changed_rows)
        rehashed = backfill_hashes(conn, rehash_rows)
        removed = remove_paths(conn, stale_paths)

    return {
        "domain":    domain_id,
        "folder":    folder_name,
        "scanned":   len(seen_paths),
        "added":     len(new_rows) if dry_run else added,
        "updated":   len(changed_rows) if dry_run else updated,
        "rehashed":  len(rehash_rows) if dry_run else rehashed,
        "removed":   len(stale_paths) if dry_run else removed,
        "prune_refused": prune_refused,
        "unchanged": len(seen_paths) - len(new_rows) - len(changed_rows) - len(rehash_rows),
        "dry_run":   dry_run,
    }


# ---------------------------------------------------------------------------
# Registry update
# ---------------------------------------------------------------------------

def update_registry(results: list[dict]) -> None:
    """Update domain registry with scan timestamp and doc counts."""
    if not DOMAIN_REGISTRY.exists():
        return
    try:
        data = json.loads(DOMAIN_REGISTRY.read_text())
    except Exception:
        return

    today = str(date.today())
    by_domain = {r["domain"]: r for r in results if "error" not in r}

    for domain in data.get("domains", []):
        did = domain.get("id")
        if did in by_domain:
            domain["last_scan"] = today
            domain["doc_count_scanned"] = by_domain[did]["scanned"]

    DOMAIN_REGISTRY.write_text(json.dumps(data, indent=2))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scan FOS-* Dropbox folders and sync unified_index."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--all", action="store_true", help="Scan all registered domains")
    group.add_argument("--domain", metavar="FOS-Name", help="Scan one domain folder")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    parser.add_argument(
        "--changed-since",
        metavar="SPEC",
        help="Only files modified within this window (e.g. 7d, 24h, 2w)",
    )
    parser.add_argument(
        "--no-hash", action="store_true",
        help="Catalog by metadata only (no byte read) — for cloud-only/online-only "
             "files that would otherwise download. Leaves sha256/crc NULL.",
    )
    parser.add_argument(
        "--rehash", action="store_true",
        help="Backfill content hashes for rows indexed with --no-hash (sha256 NULL), now "
             "that files are local. Reads + hashes ONLY those files; preserves enrichment.",
    )
    parser.add_argument(
        "--force-prune", action="store_true",
        help="Override the mass-prune tripwire (≥50%% of a domain stale in one scan). "
             "Only after verifying on disk that the removal is real.",
    )
    args = parser.parse_args()

    changed_since = parse_changed_since(args.changed_since) if args.changed_since else None

    domain_map = load_domain_map()
    if args.domain and args.domain not in domain_map:
        # accept a domain_id ("divorce") as well as a folder name ("FOS-Divorce")
        rev = {v: k for k, v in domain_map.items()}
        if args.domain in rev:
            args.domain = rev[args.domain]
        else:
            print(f"ERROR: Unknown domain '{args.domain}'. Known: {', '.join(domain_map)}")
            sys.exit(1)

    if args.force_prune and args.all:
        # One override must not disarm the tripwire for EVERY domain in a sweep —
        # the human verified ONE folder, not eight (the FOS-LT-Lending class).
        print("ERROR: --force-prune requires --domain (verify one domain at a time).")
        sys.exit(1)

    targets = list(domain_map.items()) if args.all else [(args.domain, domain_map[args.domain])]

    conn = sqlite3.connect(str(DB_PATH), timeout=30)
    conn.execute("PRAGMA busy_timeout=30000")   # M4: wait on locks instead of erroring under concurrency
    conn.execute("PRAGMA journal_mode=WAL")
    ensure_schema(conn)

    results = []
    total_added = total_updated = total_rehashed = total_removed = total_scanned = 0

    for folder_name, domain_id in targets:
        result = scan_domain(folder_name, domain_id, conn, changed_since, args.dry_run, args.no_hash, args.rehash, force_prune=args.force_prune)
        results.append(result)
        if "error" not in result:
            total_added    += result["added"]
            total_updated  += result["updated"]
            total_rehashed += result["rehashed"]
            total_removed  += result["removed"]
            total_scanned  += result["scanned"]

    # FTS5 is maintained by auto-sync triggers — no explicit rebuild needed.
    # rebuild_fts() is kept for manual recovery use only.
    # Domains whose prune was REFUSED are excluded from the registry stamp:
    # stamping last_scan=today would make an unreconciled domain read as fresh
    # to fos_boot / Q: Sync Status (false-fresh) while the exit code says fatal.
    if not args.dry_run and (total_added or total_updated or total_rehashed or total_removed):
        update_registry([r for r in results if not r.get("prune_refused")])

    conn.close()

    # Report
    mode = "[DRY RUN] " if args.dry_run else ""
    print(f"\n{mode}scan_domains — {date.today()}")
    print(f"{'Domain':<22} {'Folder':<26} {'Scanned':>8} {'Added':>7} {'Updated':>8} {'Removed':>8} {'Unchgd':>8}")
    print("-" * 96)

    for r in results:
        if "error" in r:
            print(f"{r['domain']:<22} {'':26} ERROR: {r['error']}")
        else:
            print(
                f"{r['domain']:<22} {r['folder']:<26} "
                f"{r['scanned']:>8,} {r['added']:>7,} {r['updated']:>8,} {r['removed']:>8,} {r['unchanged']:>8,}"
            )

    print("-" * 96)
    print(f"{'TOTAL':<49} {total_scanned:>8,} {total_added:>7,} {total_updated:>8,} {total_removed:>8,}")

    if total_added or total_updated or total_rehashed or total_removed:
        verb = "Would apply" if args.dry_run else "Applied"
        print(f"\n{verb}: +{total_added:,} added, ~{total_updated:,} updated, #{total_rehashed:,} hashed, "
              f"-{total_removed:,} removed → {total_scanned:,} total documents indexed")
    else:
        print("\nIndex is current — no changes.")

    if args.dry_run:
        print("\nRe-run without --dry-run to apply.")

    # FALSE-CLEAR GUARD: a tripped mass-prune tripwire must be loud AND carried
    # in the exit code (STD-ERROR-VISIBILITY-001 R8) — pipelines branch on rc and
    # would otherwise treat a refused (unreconciled) prune as a clean scan.
    total_refused = sum(r.get("prune_refused", 0) for r in results if "error" not in r)
    if total_refused:
        print(f"\n🔴 PRUNE REFUSED: {total_refused:,} stale index row(s) NOT pruned "
              f"(≥50% of a domain vanished at once — root unmounted/partial-sync?). "
              f"Verify the folder on disk, then rerun that domain with --force-prune.")
        if not args.dry_run:
            sys.exit(1)   # a preview is a preview — only a real run fails automation


if __name__ == "__main__":
    main()
