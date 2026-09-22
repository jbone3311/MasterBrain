"""MasterBrain shared command surface. Source effects are intentionally absent."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from masterbrain.datacore.dedup import DEFAULT_CONFIG, compare_files, file_hash, find_duplicates
from masterbrain.datacore.fileos import snapshot_tree
from masterbrain.fileos_controller import run_fileos_controller
from masterbrain.fileos_index_controller import run_fileos_index_controller


def _json(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False)


def _write_output(path: Path | None, payload: str, *, force: bool) -> None:
    if path is None:
        print(payload)
        return
    destination = path.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and not force:
        raise ValueError("output exists; pass --force to replace it")
    descriptor, temporary = tempfile.mkstemp(prefix=f".{destination.name}.", dir=destination.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def _config(args: argparse.Namespace) -> dict[str, Any]:
    config = dict(DEFAULT_CONFIG)
    config["exclude_patterns"] = list(DEFAULT_CONFIG["exclude_patterns"])
    config["max_file_size_mb"] = args.max_file_size_mb
    config["min_file_size"] = args.min_file_size
    if args.include_extension:
        config["include_extensions"] = [
            value.lower() if value.startswith(".") else f".{value.lower()}"
            for value in args.include_extension
        ]
    if args.exclude:
        config["exclude_patterns"].extend(args.exclude)
    return config


def _bounds(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--max-file-size-mb", type=int, default=100)
    parser.add_argument("--min-file-size", type=int, default=0)
    parser.add_argument("--include-extension", action="append", default=[])
    parser.add_argument("--exclude", action="append", default=[])


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="masterbrain")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("version", help="Show the MasterBrain manifest version")

    datacore = commands.add_parser("datacore", help="Shared read-only DataCore commands")
    data_commands = datacore.add_subparsers(dest="data_command", required=True)
    hash_command = data_commands.add_parser("hash", help="Hash one file")
    hash_command.add_argument("path", type=Path)
    hash_command.add_argument("--algorithm", default="sha256")
    compare = data_commands.add_parser("compare", help="Compare two files")
    compare.add_argument("file1", type=Path)
    compare.add_argument("file2", type=Path)
    scan = data_commands.add_parser("duplicates", help="Read-only duplicate scan")
    scan.add_argument("directory", type=Path)
    scan.add_argument("--method", choices=("hash", "name", "both"), default="hash")
    _bounds(scan)

    fileos = commands.add_parser("fileos", help="Read-only FileOS source commands")
    file_commands = fileos.add_subparsers(dest="file_command", required=True)
    snapshot = file_commands.add_parser("snapshot", help="Create a deterministic inventory")
    snapshot.add_argument("root", type=Path)
    snapshot.add_argument("--source-id", required=True)
    snapshot.add_argument("--observed-at", default=None)
    snapshot.add_argument("--follow-file-symlinks", action="store_true")
    snapshot.add_argument("--output", type=Path)
    snapshot.add_argument("--force", action="store_true")
    _bounds(snapshot)
    publish = file_commands.add_parser("publish", help="Publish an authorized snapshot")
    publish.add_argument("--config", type=Path, required=True)
    publish.add_argument("--idempotency-key", type=UUID, required=True)
    publish.add_argument("--check", action="store_true")
    index = file_commands.add_parser("index", help="Build/activate a FileOS index generation")
    index.add_argument("--config", type=Path, required=True)
    target = index.add_mutually_exclusive_group(required=True)
    target.add_argument("--run-id", type=UUID)
    target.add_argument("--generation-id")
    index.add_argument("--idempotency-key", type=UUID, required=True)
    index.add_argument("--check", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "version":
            print("masterbrain-manifest-v1")
        elif args.command == "datacore" and args.data_command == "hash":
            print(
                _json({"algorithm": args.algorithm, "digest": file_hash(args.path, args.algorithm)})
            )
        elif args.command == "datacore" and args.data_command == "compare":
            print(_json(compare_files(args.file1, args.file2, DEFAULT_CONFIG.copy())))
        elif args.command == "datacore":
            print(_json(find_duplicates(args.directory, _config(args), args.method)))
        elif args.command == "fileos" and args.file_command == "snapshot":
            observed = (
                datetime.fromisoformat(args.observed_at) if args.observed_at else datetime.now(UTC)
            )
            manifest = snapshot_tree(
                args.root,
                source_id=args.source_id,
                observed_at=observed,
                config=_config(args),
                follow_file_symlinks=args.follow_file_symlinks,
            )
            _write_output(args.output, _json(manifest), force=args.force)
        elif args.command == "fileos" and args.file_command == "publish":
            dsn = os.environ.get("MASTERBRAIN_DSN")
            if not dsn:
                raise ValueError("MASTERBRAIN_DSN is required")
            print(
                _json(
                    run_fileos_controller(args.config, dsn, args.idempotency_key, check=args.check)
                )
            )
        elif args.command == "fileos" and args.file_command == "index":
            dsn = os.environ.get("MASTERBRAIN_DSN")
            if not dsn:
                raise ValueError("MASTERBRAIN_DSN is required")
            print(
                _json(
                    run_fileos_index_controller(
                        args.config,
                        dsn,
                        args.idempotency_key,
                        run_id=args.run_id,
                        generation_id=args.generation_id,
                        check=args.check,
                    )
                )
            )
    except (OSError, ValueError):
        parser.exit(1, "Operation failed. Check paths, bounds and permissions.\n")


if __name__ == "__main__":
    main()
