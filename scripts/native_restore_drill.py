"""Opt-in synthetic restore proof in two fresh local PostgreSQL 17 clusters.

This is a local complement to the Docker CI drill, not a production backup tool.
There are no DSN, input archive, output path or existing-cluster arguments.
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import shutil
import socket
import stat
import subprocess
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from uuid import UUID, uuid4

import psycopg
import restore_drill as drill
from psycopg.conninfo import make_conninfo

from email_brain.blobs import BlobError, EncryptedBlobStore
from email_brain.migrate import migrate


def binaries() -> Path:
    candidates = [
        Path("/opt/homebrew/opt/postgresql@17/bin"),
        Path("/usr/local/opt/postgresql@17/bin"),
        Path("/usr/lib/postgresql/17/bin"),
    ]
    found = shutil.which("pg_config")
    if found is not None:
        candidates.append(Path(found).resolve().parent)
    required = ("initdb", "pg_ctl", "createdb", "pg_dump", "pg_restore")
    for directory in candidates:
        if all((directory / name).is_file() for name in required):
            try:
                version = subprocess.run(
                    [str(directory / "pg_dump"), "--version"],
                    capture_output=True, timeout=5, check=True,
                ).stdout
            except (OSError, subprocess.SubprocessError):
                continue
            if version.startswith(b"pg_dump (PostgreSQL) 17."):
                return directory
    raise drill.DrillFailure("local PostgreSQL 17 utilities unavailable")


def _command(args: list[str], *, timeout: int = 180) -> None:
    try:
        result = subprocess.run(args, capture_output=True, timeout=timeout, check=False)
    except (OSError, subprocess.SubprocessError):
        raise drill.DrillFailure(
            "local PostgreSQL command unavailable; output suppressed"
        ) from None
    drill.require(result.returncode == 0, "local PostgreSQL command failed; output suppressed")


def _unused_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


@contextmanager
def owned_temp_root(utility_dir: Path) -> Iterator[Path]:
    root = Path(tempfile.mkdtemp(prefix="masterbrain-native-restore-")).resolve()
    root.chmod(0o700)
    try:
        yield root
    finally:
        # Preserve a cluster if shutdown failed. Never remove a live data dir.
        data_dirs = [path for path in root.iterdir() if (path / "PG_VERSION").is_file()]
        safe_to_remove = True
        for data in data_dirs:
            try:
                status = subprocess.run(
                    [str(utility_dir / "pg_ctl"), "-D", str(data), "status"],
                    capture_output=True, timeout=10, check=False,
                )
            except (OSError, subprocess.SubprocessError):
                safe_to_remove = False
                break
            if status.returncode != 3:
                safe_to_remove = False
                break
        if safe_to_remove:
            shutil.rmtree(root)


@contextmanager
def cluster(root: Path, name: str, utility_dir: Path) -> Iterator[str]:
    """Create and stop only an exact newly generated cluster under our temp root."""
    drill.database_name(name)
    data = root / name
    data.mkdir(mode=0o700)
    _command([
        str(utility_dir / "initdb"), "-D", str(data),
        "--auth-local=trust", "--auth-host=trust",
    ])
    port = _unused_port()
    started = False
    try:
        _command([
            str(utility_dir / "pg_ctl"), "-D", str(data),
            "-o", f"-h 127.0.0.1 -p {port}", "-l", str(data / "server.log"), "start",
        ], timeout=30)
        started = True
        _command([
            str(utility_dir / "createdb"), "-h", "127.0.0.1", "-p", str(port), name,
        ], timeout=30)
        dsn = make_conninfo(
            host="127.0.0.1", hostaddr="127.0.0.1", port=port,
            dbname=name, user=getpass.getuser(), connect_timeout=2,
            options="-c statement_timeout=10000 -c lock_timeout=3000",
        )
        with psycopg.connect(dsn) as conn:
            version = conn.execute("SHOW server_version").fetchone()
            drill.require(
                version is not None and str(version[0]).startswith("17."),
                "local PostgreSQL server version mismatch",
            )
        yield dsn
    finally:
        if started:
            _command([
                str(utility_dir / "pg_ctl"), "-D", str(data), "-m", "fast", "stop",
            ], timeout=30)


def run_native_drill() -> dict[str, object]:
    drill.require(
        not any(key.startswith("PG") for key in os.environ),
        "ambient PostgreSQL settings are forbidden for this disposable drill",
    )
    utility_dir = binaries()
    nonce = uuid4().hex[:16]
    base = drill.PREFIX + nonce
    source_name, target_name = base + "_source", base + "_target"
    with owned_temp_root(utility_dir) as root:
        with cluster(root, source_name, utility_dir) as source_dsn:
            with cluster(root, target_name, utility_dir) as target_dsn:
                drill.bootstrap_restored_marker_roles(target_dsn)
                migrations = Path(__file__).resolve().parents[1] / "migrations"
                drill.stage("migrate_and_seed_synthetic_source")
                migrate(source_dsn, migrations)
                source_store = drill.make_runtime(source_dsn, "native_restore_source_runtime")
                keys: dict[tuple[UUID, str], bytes] = {}
                tenants = drill.seed(
                    source_dsn, source_store, object_root=root / "source_objects", keys=keys,
                )
                xlsx_seed = drill.seed_email_xlsx_publication(source_store, tenants[0])
                source_bound = [
                    (
                        f"native_restore_source_tenant_{index}",
                        drill.make_tenant_runtime(
                            source_dsn, f"native_restore_source_tenant_{index}",
                            tenant.context.tenant_id,
                        ),
                    ) for index, tenant in enumerate(tenants)
                ]
                drill.verify_tenant_bound_isolation(source_dsn, tenants, source_bound)
                before = drill.snapshot(source_dsn, source_store.blobs)
                shutil.copytree(root / "source_objects", root / "backup_objects")
                with psycopg.connect(target_dsn) as conn:
                    drill.require(
                        conn.execute(
                            "SELECT count(*) FROM pg_tables WHERE schemaname='public'"
                        ).fetchone() == (0,),
                        "restore target is not empty",
                    )
                archive = root / "synthetic.dump"
                descriptor = os.open(archive, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                os.close(descriptor)
                drill.stage("dump_synthetic_source")
                _command([
                    str(utility_dir / "pg_dump"), f"--dbname={source_dsn}",
                    "--format=custom", "--no-acl", f"--file={archive}",
                ])
                drill.require(
                    stat.S_IMODE(archive.stat().st_mode) == 0o600
                    and 0 < archive.stat().st_size <= drill.MAX_ARCHIVE_BYTES,
                    "synthetic archive size or permissions invalid",
                )
                drill.stage("restore_into_empty_target")
                _command([
                    str(utility_dir / "pg_restore"), f"--dbname={target_dsn}",
                    "--exit-on-error", "--single-transaction", "--no-owner", "--no-acl",
                    str(archive),
                ])
                try:
                    drill.snapshot(target_dsn)
                except drill.DrillFailure:
                    pass
                else:
                    raise drill.DrillFailure("database-only restore accepted absent evidence")
                target_blobs = EncryptedBlobStore(
                    root / "target_objects", keys, {tenant: key for tenant, key in keys},
                )
                try:
                    drill.snapshot(target_dsn, target_blobs)
                except BlobError:
                    pass
                else:
                    raise drill.DrillFailure("empty object restore accepted missing evidence")
                shutil.copytree(
                    root / "backup_objects", root / "target_objects", dirs_exist_ok=True,
                )
                drill.require(
                    drill.snapshot(target_dsn, target_blobs) == before,
                    "restored table counts or content digests differ",
                )
                drill.require(migrate(target_dsn, migrations) == [], "restored migrations differ")
                restored_store = drill.make_runtime(target_dsn, "native_restore_target_runtime")
                restored_store.blobs = target_blobs
                drill.verify_restored(target_dsn, restored_store, tenants, xlsx_seed)
                drill.verify_restored_xlsx(
                    restored_store, xlsx_seed, tenants[1].context,
                )
                drill.retire_unrestored_bindings(
                    target_dsn, tenants, [role for role, _ in source_bound],
                )
                target_bound = [
                    (
                        f"native_restore_target_tenant_{index}",
                        drill.make_tenant_runtime(
                            target_dsn, f"native_restore_target_tenant_{index}",
                            tenant.context.tenant_id,
                        ),
                    ) for index, tenant in enumerate(tenants)
                ]
                drill.verify_tenant_bound_isolation(target_dsn, tenants, target_bound)
                return {
                    "status": "passed", "synthetic_only": True,
                    "postgres_major": 17, "tables_verified": len(before),
                    "rows_verified": sum(count for count, _ in before.values()),
                    "tenants_verified": len(tenants), "content_hashes_equal": True,
                    "rls_verified": True, "external_objects_verified": sum(
                        len(target_blobs.object_keys(t.context.tenant_id, t.account_id))
                        for t in tenants
                    ),
                }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-disposable", action="store_true", required=True)
    parser.parse_args()
    try:
        print(json.dumps(run_native_drill(), sort_keys=True))
        return 0
    except drill.DrillFailure as error:
        print(json.dumps({"status": "failed", "detail": str(error), "synthetic_only": True}))
        return 1
    except Exception:
        print(json.dumps({
            "status": "failed", "detail": "Native restore failed; details suppressed",
            "synthetic_only": True,
        }))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
