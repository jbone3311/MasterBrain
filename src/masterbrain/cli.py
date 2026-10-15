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

from email_brain.cli import main as email_cli_main
from masterbrain.archive_member_controller import (
    run_archive_document_batch_controller,
    run_archive_document_plan_controller,
    run_archive_member_batch_controller,
    run_archive_member_controller,
    run_archive_member_document_controller,
    run_archive_member_image_ocr_controller,
    run_archive_member_plan_controller,
)
from masterbrain.datacore.dedup import DEFAULT_CONFIG, compare_files, file_hash, find_duplicates
from masterbrain.datacore.fileos import snapshot_tree
from masterbrain.email_bridge_controller import (
    run_email_attachment_bridge_controller,
    run_email_bridge_batch_controller,
    run_email_bridge_controller,
    run_email_bridge_plan_controller,
    run_email_document_bridge_controller,
    run_email_part_bridge_batch_controller,
    run_email_part_bridge_plan_controller,
)
from masterbrain.fileos_controller import run_fileos_controller
from masterbrain.fileos_index_controller import run_fileos_index_controller
from masterbrain.source_tier_email_controller import run_source_tier_email_controller
from masterbrain.source_tier_fileos_controller import run_source_tier_fileos_controller
from masterbrain.source_tier_fileos_pdf_controller import run_source_tier_fileos_pdf_controller


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

    demo = commands.add_parser("demo", help="Disposable fictional combined-source demo")
    demo_commands = demo.add_subparsers(dest="demo_command", required=True)
    demo_commands.add_parser("migrate", help="Migrate a fresh disposable database")
    for action in ("init", "seed"):
        demo_commands.add_parser(action).add_argument("--state-dir", type=Path, required=True)
    demo_serve = demo_commands.add_parser("serve", help="Run the loopback-only demo API")
    demo_serve.add_argument("--port", type=int, default=8080)

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
    publish.add_argument("--tenant-bound-db", action="store_true")
    index = file_commands.add_parser("index", help="Build/activate a FileOS index generation")
    index.add_argument("--config", type=Path, required=True)
    target = index.add_mutually_exclusive_group(required=True)
    target.add_argument("--run-id", type=UUID)
    target.add_argument("--generation-id")
    index.add_argument("--idempotency-key", type=UUID, required=True)
    index.add_argument("--check", action="store_true")
    index.add_argument("--tenant-bound-db", action="store_true")
    tier_replay = file_commands.add_parser(
        "replay-tier-text", help="Replay one reviewed FileOS text source with a worker"
    )
    tier_replay.add_argument("--config", type=Path, required=True)
    tier_replay.add_argument("--review-id", required=True)
    tier_replay.add_argument("--check", action="store_true")
    tier_replay.add_argument("--tenant-bound-db", action="store_true")
    pdf_tier_replay = file_commands.add_parser(
        "replay-tier-pdf", help="Replay one reviewed FileOS PDF text layer with a worker"
    )
    pdf_tier_replay.add_argument("--config", type=Path, required=True)
    pdf_tier_replay.add_argument("--review-id", required=True)
    pdf_tier_replay.add_argument("--check", action="store_true")
    pdf_tier_replay.add_argument("--tenant-bound-db", action="store_true")
    archive_text = file_commands.add_parser(
        "archive-text", help="Publish one selected archive text member"
    )
    archive_text.add_argument("--config", type=Path, required=True)
    archive_text.add_argument("--inventory-id", required=True)
    archive_text.add_argument("--member-locator", required=True)
    archive_text.add_argument("--idempotency-key", type=UUID, required=True)
    archive_text.add_argument("--check", action="store_true")
    archive_document = file_commands.add_parser(
        "archive-document", help="Publish one selected archive PDF or Office member"
    )
    archive_document.add_argument("--config", type=Path, required=True)
    archive_document.add_argument("--inventory-id", required=True)
    archive_document.add_argument("--member-locator", required=True)
    archive_document.add_argument("--idempotency-key", type=UUID, required=True)
    archive_document.add_argument("--check", action="store_true")
    archive_image = file_commands.add_parser(
        "archive-image", help="Publish one selected archive image OCR member"
    )
    archive_image.add_argument("--config", type=Path, required=True)
    archive_image.add_argument("--inventory-id", required=True)
    archive_image.add_argument("--member-locator", required=True)
    archive_image.add_argument("--idempotency-key", type=UUID, required=True)
    archive_image.add_argument("--check", action="store_true")
    archive_plan = file_commands.add_parser(
        "archive-text-plan", help="Preview eligible archive text members"
    )
    archive_plan.add_argument("--config", type=Path, required=True)
    archive_plan.add_argument("--inventory-id", required=True)
    archive_plan.add_argument("--after", type=int)
    archive_plan.add_argument("--limit", type=int, default=25)
    archive_plan.add_argument("--check", action="store_true")
    archive_document_plan = file_commands.add_parser(
        "archive-document-plan", help="Preview eligible archive PDF and Office members"
    )
    archive_document_plan.add_argument("--config", type=Path, required=True)
    archive_document_plan.add_argument("--inventory-id", required=True)
    archive_document_plan.add_argument("--after", type=int)
    archive_document_plan.add_argument("--limit", type=int, default=25)
    archive_document_plan.add_argument("--check", action="store_true")
    archive_batch = file_commands.add_parser(
        "archive-text-batch", help="Execute one sealed archive text-member batch"
    )
    archive_batch.add_argument("--config", type=Path, required=True)
    archive_batch.add_argument("--plan", type=Path, required=True)
    archive_batch.add_argument("--check", action="store_true")
    archive_document_batch = file_commands.add_parser(
        "archive-document-batch", help="Execute one sealed archive document batch"
    )
    archive_document_batch.add_argument("--config", type=Path, required=True)
    archive_document_batch.add_argument("--plan", type=Path, required=True)
    archive_document_batch.add_argument("--check", action="store_true")

    email = commands.add_parser("email", help="Explicit Email source migration commands")
    email_commands = email.add_subparsers(dest="email_command", required=True)
    bridge = email_commands.add_parser("bridge", help="Bridge one current Email version")
    bridge.add_argument("--config", type=Path, required=True)
    bridge.add_argument("--evidence-id", type=UUID, required=True)
    bridge.add_argument("--idempotency-key", type=UUID, required=True)
    bridge.add_argument("--check", action="store_true")
    email_tier_replay = email_commands.add_parser(
        "replay-tier-text", help="Replay one reviewed retained Email text source with a worker"
    )
    email_tier_replay.add_argument("--config", type=Path, required=True)
    email_tier_replay.add_argument("--review-id", required=True)
    email_tier_replay.add_argument("--check", action="store_true")
    bridge_plan = email_commands.add_parser(
        "bridge-plan", help="Preview current Email versions for bridging"
    )
    bridge_plan.add_argument("--config", type=Path, required=True)
    bridge_plan.add_argument("--account-id", type=UUID, required=True)
    bridge_plan.add_argument("--after", type=UUID)
    bridge_plan.add_argument("--limit", type=int, default=25)
    bridge_plan.add_argument("--check", action="store_true")
    bridge_batch = email_commands.add_parser(
        "bridge-batch", help="Execute one sealed Email message bridge batch"
    )
    bridge_batch.add_argument("--config", type=Path, required=True)
    bridge_batch.add_argument("--plan", type=Path, required=True)
    bridge_batch.add_argument("--check", action="store_true")
    part_plan = email_commands.add_parser(
        "bridge-parts-plan", help="Preview Email attachment/document bridge candidates"
    )
    part_plan.add_argument("--config", type=Path, required=True)
    part_plan.add_argument("--account-id", type=UUID, required=True)
    part_plan.add_argument("--kind", choices=("attachment", "document"), required=True)
    part_plan.add_argument("--after", type=UUID)
    part_plan.add_argument("--limit", type=int, default=25)
    part_plan.add_argument("--check", action="store_true")
    part_batch = email_commands.add_parser(
        "bridge-parts-batch", help="Execute one sealed Email attachment/document batch"
    )
    part_batch.add_argument("--config", type=Path, required=True)
    part_batch.add_argument("--plan", type=Path, required=True)
    part_batch.add_argument("--check", action="store_true")
    attachment_bridge = email_commands.add_parser(
        "bridge-attachment", help="Bridge one Email attachment occurrence"
    )
    attachment_bridge.add_argument("--config", type=Path, required=True)
    attachment_bridge.add_argument("--attachment-id", type=UUID, required=True)
    attachment_bridge.add_argument("--idempotency-key", type=UUID, required=True)
    attachment_bridge.add_argument("--check", action="store_true")
    document_bridge = email_commands.add_parser(
        "bridge-document", help="Bridge one approved Email PDF extraction"
    )
    document_bridge.add_argument("--config", type=Path, required=True)
    document_bridge.add_argument("--extraction-id", type=UUID, required=True)
    document_bridge.add_argument("--idempotency-key", type=UUID, required=True)
    document_bridge.add_argument("--check", action="store_true")
    for private_command in (
        archive_text,
        archive_document,
        archive_image,
        archive_plan,
        archive_document_plan,
        archive_batch,
        archive_document_batch,
        bridge,
        email_tier_replay,
        bridge_plan,
        bridge_batch,
        part_plan,
        part_batch,
        attachment_bridge,
        document_bridge,
    ):
        private_command.add_argument("--tenant-bound-db", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "version":
            print("masterbrain-manifest-v1")
        elif args.command == "demo":
            if args.demo_command == "migrate":
                email_cli_main(["migrate"])
            elif args.demo_command == "init":
                email_cli_main(["init-masterbrain-demo", "--state-dir", str(args.state_dir)])
            elif args.demo_command == "seed":
                email_cli_main(["seed-masterbrain-demo", "--state-dir", str(args.state_dir)])
            else:
                email_cli_main(["serve", "--port", str(args.port)])
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
                    run_fileos_controller(
                        args.config, dsn, args.idempotency_key,
                        check=args.check, tenant_bound_db=args.tenant_bound_db,
                    )
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
                        tenant_bound_db=args.tenant_bound_db,
                    )
                )
            )
        elif args.command == "fileos" and args.file_command == "replay-tier-text":
            dsn = os.environ.get("MASTERBRAIN_DSN")
            if not dsn:
                raise ValueError("MASTERBRAIN_DSN is required")
            print(_json(run_source_tier_fileos_controller(
                args.config, dsn, args.review_id,
                check=args.check, tenant_bound_db=args.tenant_bound_db,
            )))
        elif args.command == "fileos" and args.file_command == "replay-tier-pdf":
            dsn = os.environ.get("MASTERBRAIN_DSN")
            if not dsn:
                raise ValueError("MASTERBRAIN_DSN is required")
            print(_json(run_source_tier_fileos_pdf_controller(
                args.config, dsn, args.review_id,
                check=args.check, tenant_bound_db=args.tenant_bound_db,
            )))
        elif args.command == "email" and args.email_command == "replay-tier-text":
            dsn = os.environ.get("MASTERBRAIN_DSN")
            if not dsn:
                raise ValueError("MASTERBRAIN_DSN is required")
            print(_json(run_source_tier_email_controller(
                args.config, dsn, args.review_id,
                check=args.check, tenant_bound_db=args.tenant_bound_db,
            )))
        elif args.command == "fileos" and args.file_command == "archive-text":
            dsn = os.environ.get("MASTERBRAIN_DSN")
            if not dsn:
                raise ValueError("MASTERBRAIN_DSN is required")
            print(
                _json(
                    run_archive_member_controller(
                        args.config,
                        dsn,
                        args.inventory_id,
                        args.member_locator,
                        args.idempotency_key,
                        check=args.check,
                        tenant_bound_db=args.tenant_bound_db,
                    )
                )
            )
        elif args.command == "fileos" and args.file_command == "archive-text-plan":
            dsn = os.environ.get("MASTERBRAIN_DSN")
            if not dsn:
                raise ValueError("MASTERBRAIN_DSN is required")
            print(
                _json(
                    run_archive_member_plan_controller(
                        args.config,
                        dsn,
                        args.inventory_id,
                        after=args.after,
                        limit=args.limit,
                        check=args.check,
                        tenant_bound_db=args.tenant_bound_db,
                    )
                )
            )
        elif args.command == "fileos" and args.file_command == "archive-document":
            dsn = os.environ.get("MASTERBRAIN_DSN")
            if not dsn:
                raise ValueError("MASTERBRAIN_DSN is required")
            print(
                _json(
                    run_archive_member_document_controller(
                        args.config,
                        dsn,
                        args.inventory_id,
                        args.member_locator,
                        args.idempotency_key,
                        check=args.check,
                        tenant_bound_db=args.tenant_bound_db,
                    )
                )
            )
        elif args.command == "fileos" and args.file_command == "archive-image":
            dsn = os.environ.get("MASTERBRAIN_DSN")
            if not dsn:
                raise ValueError("MASTERBRAIN_DSN is required")
            print(
                _json(
                    run_archive_member_image_ocr_controller(
                        args.config,
                        dsn,
                        args.inventory_id,
                        args.member_locator,
                        args.idempotency_key,
                        check=args.check,
                        tenant_bound_db=args.tenant_bound_db,
                    )
                )
            )
        elif args.command == "fileos" and args.file_command == "archive-document-plan":
            dsn = os.environ.get("MASTERBRAIN_DSN")
            if not dsn:
                raise ValueError("MASTERBRAIN_DSN is required")
            print(
                _json(
                    run_archive_document_plan_controller(
                        args.config,
                        dsn,
                        args.inventory_id,
                        after=args.after,
                        limit=args.limit,
                        check=args.check,
                        tenant_bound_db=args.tenant_bound_db,
                    )
                )
            )
        elif args.command == "fileos" and args.file_command == "archive-text-batch":
            dsn = os.environ.get("MASTERBRAIN_DSN")
            if not dsn:
                raise ValueError("MASTERBRAIN_DSN is required")
            print(
                _json(
                    run_archive_member_batch_controller(
                        args.config,
                        args.plan,
                        dsn,
                        check=args.check,
                        tenant_bound_db=args.tenant_bound_db,
                    )
                )
            )
        elif args.command == "fileos" and args.file_command == "archive-document-batch":
            dsn = os.environ.get("MASTERBRAIN_DSN")
            if not dsn:
                raise ValueError("MASTERBRAIN_DSN is required")
            print(
                _json(
                    run_archive_document_batch_controller(
                        args.config,
                        args.plan,
                        dsn,
                        check=args.check,
                        tenant_bound_db=args.tenant_bound_db,
                    )
                )
            )
        elif args.command == "email" and args.email_command == "bridge":
            dsn = os.environ.get("MASTERBRAIN_DSN")
            if not dsn:
                raise ValueError("MASTERBRAIN_DSN is required")
            print(
                _json(
                    run_email_bridge_controller(
                        args.config,
                        dsn,
                        args.evidence_id,
                        args.idempotency_key,
                        check=args.check,
                        tenant_bound_db=args.tenant_bound_db,
                    )
                )
            )
        elif args.command == "email" and args.email_command == "bridge-attachment":
            dsn = os.environ.get("MASTERBRAIN_DSN")
            if not dsn:
                raise ValueError("MASTERBRAIN_DSN is required")
            print(
                _json(
                    run_email_attachment_bridge_controller(
                        args.config,
                        dsn,
                        args.attachment_id,
                        args.idempotency_key,
                        check=args.check,
                        tenant_bound_db=args.tenant_bound_db,
                    )
                )
            )
        elif args.command == "email" and args.email_command == "bridge-plan":
            dsn = os.environ.get("MASTERBRAIN_DSN")
            if not dsn:
                raise ValueError("MASTERBRAIN_DSN is required")
            print(
                _json(
                    run_email_bridge_plan_controller(
                        args.config,
                        dsn,
                        args.account_id,
                        after=args.after,
                        limit=args.limit,
                        check=args.check,
                        tenant_bound_db=args.tenant_bound_db,
                    )
                )
            )
        elif args.command == "email" and args.email_command == "bridge-batch":
            dsn = os.environ.get("MASTERBRAIN_DSN")
            if not dsn:
                raise ValueError("MASTERBRAIN_DSN is required")
            print(
                _json(
                    run_email_bridge_batch_controller(
                        args.config,
                        args.plan,
                        dsn,
                        check=args.check,
                        tenant_bound_db=args.tenant_bound_db,
                    )
                )
            )
        elif args.command == "email" and args.email_command == "bridge-parts-plan":
            dsn = os.environ.get("MASTERBRAIN_DSN")
            if not dsn:
                raise ValueError("MASTERBRAIN_DSN is required")
            print(
                _json(
                    run_email_part_bridge_plan_controller(
                        args.config,
                        dsn,
                        args.account_id,
                        args.kind,
                        after=args.after,
                        limit=args.limit,
                        check=args.check,
                        tenant_bound_db=args.tenant_bound_db,
                    )
                )
            )
        elif args.command == "email" and args.email_command == "bridge-parts-batch":
            dsn = os.environ.get("MASTERBRAIN_DSN")
            if not dsn:
                raise ValueError("MASTERBRAIN_DSN is required")
            print(
                _json(
                    run_email_part_bridge_batch_controller(
                        args.config,
                        args.plan,
                        dsn,
                        check=args.check,
                        tenant_bound_db=args.tenant_bound_db,
                    )
                )
            )
        elif args.command == "email" and args.email_command == "bridge-document":
            dsn = os.environ.get("MASTERBRAIN_DSN")
            if not dsn:
                raise ValueError("MASTERBRAIN_DSN is required")
            print(
                _json(
                    run_email_document_bridge_controller(
                        args.config,
                        dsn,
                        args.extraction_id,
                        args.idempotency_key,
                        check=args.check,
                        tenant_bound_db=args.tenant_bound_db,
                    )
                )
            )
    except (OSError, ValueError):
        parser.exit(1, "Operation failed. Check paths, bounds and permissions.\n")


if __name__ == "__main__":
    main()
