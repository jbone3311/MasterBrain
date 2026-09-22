from __future__ import annotations

import json
from pathlib import Path

import pytest

from masterbrain import cli
from masterbrain.cli import main


def test_cli_hash_and_compare(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    first = tmp_path / "one.txt"
    second = tmp_path / "two.txt"
    first.write_text("same", encoding="utf-8")
    second.write_text("same", encoding="utf-8")
    main(["datacore", "hash", str(first)])
    hashed = json.loads(capsys.readouterr().out)
    assert hashed["algorithm"] == "sha256"
    assert len(hashed["digest"]) == 64
    main(["datacore", "compare", str(first), str(second)])
    assert json.loads(capsys.readouterr().out)["identical"] is True


def test_cli_duplicate_scan(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    (tmp_path / "one.txt").write_text("same", encoding="utf-8")
    (tmp_path / "two.txt").write_text("same", encoding="utf-8")
    main(["datacore", "duplicates", str(tmp_path)])
    result = json.loads(capsys.readouterr().out)
    assert result["duplicate_groups"] == 1
    assert result["duplicate_files"] == 1


def test_cli_snapshot_writes_atomically_and_refuses_overwrite(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    (root / "one.txt").write_text("one", encoding="utf-8")
    output = tmp_path / "manifest.json"
    args = [
        "fileos",
        "snapshot",
        str(root),
        "--source-id",
        "files_test",
        "--observed-at",
        "2026-09-22T12:00:00+00:00",
        "--output",
        str(output),
    ]
    main(args)
    assert json.loads(output.read_text())["counts"]["items"] == 1
    with pytest.raises(SystemExit) as denied:
        main(args)
    assert denied.value.code == 1
    main([*args, "--force"])
    assert not list(tmp_path.glob(".manifest.json.*"))


def test_cli_errors_do_not_echo_sensitive_path(capsys: pytest.CaptureFixture[str]) -> None:
    secret = "/private/very-sensitive-name.txt"
    with pytest.raises(SystemExit):
        main(["datacore", "hash", secret])
    assert secret not in capsys.readouterr().err


def test_cli_publish_uses_masterbrain_dsn_and_scrubs_it(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    key = "93c5a004-81ab-45b6-8652-e8ced2b40e47"
    config = tmp_path / "controller.json"
    config.write_text("not opened by this dispatch test")
    dsn = "postgresql://secret:secret@example.invalid/private"
    monkeypatch.setenv("MASTERBRAIN_DSN", dsn)
    run = monkeypatch.setattr(
        cli,
        "run_fileos_controller",
        lambda path, received_dsn, received_key, check: {
            "config": path == config,
            "dsn": received_dsn == dsn,
            "key": str(received_key) == key,
            "check": check,
            "source_effects": False,
        },
    )
    assert run is None
    main(
        [
            "fileos",
            "publish",
            "--config",
            str(config),
            "--idempotency-key",
            key,
            "--check",
        ]
    )
    output = capsys.readouterr().out
    assert json.loads(output) == {
        "check": True,
        "config": True,
        "dsn": True,
        "key": True,
        "source_effects": False,
    }
    assert dsn not in output


def test_cli_index_uses_masterbrain_dsn_and_explicit_target(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    key = "93c5a004-81ab-45b6-8652-e8ced2b40e47"
    run_id = "b22f0f5c-a784-46a1-95a7-b2b96e1f8396"
    config = tmp_path / "index.json"
    config.write_text("not opened by this dispatch test")
    dsn = "postgresql://secret:secret@example.invalid/private"
    monkeypatch.setenv("MASTERBRAIN_DSN", dsn)
    monkeypatch.setattr(
        cli,
        "run_fileos_index_controller",
        lambda path, received_dsn, received_key, **options: {
            "config": path == config,
            "dsn": received_dsn == dsn,
            "key": str(received_key) == key,
            "run_id": str(options["run_id"]) == run_id,
            "generation_id": options["generation_id"],
            "check": options["check"],
            "source_effects": False,
        },
    )
    main(
        [
            "fileos",
            "index",
            "--config",
            str(config),
            "--run-id",
            run_id,
            "--idempotency-key",
            key,
            "--check",
        ]
    )
    output = capsys.readouterr().out
    assert json.loads(output) == {
        "check": True,
        "config": True,
        "dsn": True,
        "generation_id": None,
        "key": True,
        "run_id": True,
        "source_effects": False,
    }
    assert dsn not in output


def test_cli_archive_text_uses_explicit_member_and_scrubs_dsn(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    key = "93c5a004-81ab-45b6-8652-e8ced2b40e47"
    inventory = "archive_inventory_" + "a" * 32
    locator = "nested/proof.md"
    config = tmp_path / "archive.json"
    config.write_text("not opened by this dispatch test")
    dsn = "postgresql://secret:secret@example.invalid/private"
    monkeypatch.setenv("MASTERBRAIN_DSN", dsn)
    monkeypatch.setattr(
        cli,
        "run_archive_member_controller",
        lambda path, received_dsn, received_inventory, received_locator, received_key, check: {
            "config": path == config,
            "dsn": received_dsn == dsn,
            "inventory": received_inventory == inventory,
            "locator": received_locator == locator,
            "key": str(received_key) == key,
            "check": check,
            "source_effects": False,
        },
    )
    main(
        [
            "fileos",
            "archive-text",
            "--config",
            str(config),
            "--inventory-id",
            inventory,
            "--member-locator",
            locator,
            "--idempotency-key",
            key,
            "--check",
        ]
    )
    output = capsys.readouterr().out
    assert json.loads(output) == {
        "check": True,
        "config": True,
        "dsn": True,
        "inventory": True,
        "key": True,
        "locator": True,
        "source_effects": False,
    }
    assert dsn not in output


def test_cli_archive_text_plan_uses_explicit_inventory_and_bounds(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    inventory = "archive_inventory_" + "b" * 32
    config = tmp_path / "archive.json"
    config.write_text("not opened by this dispatch test")
    dsn = "postgresql://secret:secret@example.invalid/private"
    monkeypatch.setenv("MASTERBRAIN_DSN", dsn)
    monkeypatch.setattr(
        cli,
        "run_archive_member_plan_controller",
        lambda path, received_dsn, received_inventory, after, limit, check: {
            "config": path == config,
            "dsn": received_dsn == dsn,
            "inventory": received_inventory == inventory,
            "after": after == 4,
            "limit": limit == 9,
            "check": check,
            "source_effects": False,
        },
    )
    main(
        [
            "fileos",
            "archive-text-plan",
            "--config",
            str(config),
            "--inventory-id",
            inventory,
            "--after",
            "4",
            "--limit",
            "9",
            "--check",
        ]
    )
    output = capsys.readouterr().out
    assert json.loads(output) == {
        "after": True,
        "check": True,
        "config": True,
        "dsn": True,
        "inventory": True,
        "limit": True,
        "source_effects": False,
    }
    assert dsn not in output


def test_cli_email_bridge_uses_explicit_evidence_and_scrubs_dsn(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    key = "93c5a004-81ab-45b6-8652-e8ced2b40e47"
    evidence = "b22f0f5c-a784-46a1-95a7-b2b96e1f8396"
    config = tmp_path / "email-bridge.json"
    config.write_text("not opened by this dispatch test")
    dsn = "postgresql://secret:secret@example.invalid/private"
    monkeypatch.setenv("MASTERBRAIN_DSN", dsn)
    monkeypatch.setattr(
        cli,
        "run_email_bridge_controller",
        lambda path, received_dsn, received_evidence, received_key, check: {
            "config": path == config,
            "dsn": received_dsn == dsn,
            "evidence": str(received_evidence) == evidence,
            "key": str(received_key) == key,
            "check": check,
            "source_effects": False,
        },
    )
    main(
        [
            "email",
            "bridge",
            "--config",
            str(config),
            "--evidence-id",
            evidence,
            "--idempotency-key",
            key,
            "--check",
        ]
    )
    output = capsys.readouterr().out
    assert json.loads(output) == {
        "check": True,
        "config": True,
        "dsn": True,
        "evidence": True,
        "key": True,
        "source_effects": False,
    }
    assert dsn not in output


def test_cli_email_bridge_plan_uses_explicit_account_and_bounds(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    account = "b22f0f5c-a784-46a1-95a7-b2b96e1f8396"
    cursor = "93c5a004-81ab-45b6-8652-e8ced2b40e47"
    config = tmp_path / "email-bridge.json"
    config.write_text("not opened by this dispatch test")
    dsn = "postgresql://secret:secret@example.invalid/private"
    monkeypatch.setenv("MASTERBRAIN_DSN", dsn)
    monkeypatch.setattr(
        cli,
        "run_email_bridge_plan_controller",
        lambda path, received_dsn, received_account, after, limit, check: {
            "config": path == config,
            "dsn": received_dsn == dsn,
            "account": str(received_account) == account,
            "after": str(after) == cursor,
            "limit": limit,
            "check": check,
            "source_effects": False,
            "data_effects": False,
        },
    )
    main(
        [
            "email",
            "bridge-plan",
            "--config",
            str(config),
            "--account-id",
            account,
            "--after",
            cursor,
            "--limit",
            "7",
            "--check",
        ]
    )
    output = capsys.readouterr().out
    assert json.loads(output) == {
        "account": True,
        "after": True,
        "check": True,
        "config": True,
        "data_effects": False,
        "dsn": True,
        "limit": 7,
        "source_effects": False,
    }
    assert dsn not in output


def test_cli_email_part_bridge_plan_uses_explicit_kind_and_bounds(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    account = "b22f0f5c-a784-46a1-95a7-b2b96e1f8396"
    cursor = "93c5a004-81ab-45b6-8652-e8ced2b40e47"
    config = tmp_path / "email-bridge.json"
    config.write_text("not opened by this dispatch test")
    dsn = "postgresql://secret:secret@example.invalid/private"
    monkeypatch.setenv("MASTERBRAIN_DSN", dsn)
    monkeypatch.setattr(
        cli,
        "run_email_part_bridge_plan_controller",
        lambda path, received_dsn, received_account, kind, after, limit, check: {
            "config": path == config,
            "dsn": received_dsn == dsn,
            "account": str(received_account) == account,
            "kind": kind,
            "after": str(after) == cursor,
            "limit": limit,
            "check": check,
            "source_effects": False,
            "data_effects": False,
        },
    )
    main(
        [
            "email",
            "bridge-parts-plan",
            "--config",
            str(config),
            "--account-id",
            account,
            "--kind",
            "document",
            "--after",
            cursor,
            "--limit",
            "11",
            "--check",
        ]
    )
    output = capsys.readouterr().out
    assert json.loads(output) == {
        "account": True,
        "after": True,
        "check": True,
        "config": True,
        "data_effects": False,
        "dsn": True,
        "kind": "document",
        "limit": 11,
        "source_effects": False,
    }
    assert dsn not in output


def test_cli_email_part_batch_uses_explicit_private_plan(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    config = tmp_path / "email-bridge.json"
    plan = tmp_path / "email-parts-batch.json"
    config.write_text("not opened by this dispatch test")
    plan.write_text("not opened by this dispatch test")
    dsn = "postgresql://secret:secret@example.invalid/private"
    monkeypatch.setenv("MASTERBRAIN_DSN", dsn)
    monkeypatch.setattr(
        cli,
        "run_email_part_bridge_batch_controller",
        lambda path, plan_path, received_dsn, check: {
            "config": path == config,
            "plan": plan_path == plan,
            "dsn": received_dsn == dsn,
            "check": check,
            "source_effects": False,
            "data_effects": False,
        },
    )
    main(
        [
            "email",
            "bridge-parts-batch",
            "--config",
            str(config),
            "--plan",
            str(plan),
            "--check",
        ]
    )
    output = capsys.readouterr().out
    assert json.loads(output) == {
        "check": True,
        "config": True,
        "data_effects": False,
        "dsn": True,
        "plan": True,
        "source_effects": False,
    }
    assert dsn not in output


def test_cli_email_bridge_batch_uses_explicit_private_plan(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    config = tmp_path / "email-bridge.json"
    plan = tmp_path / "email-batch.json"
    config.write_text("not opened by this dispatch test")
    plan.write_text("not opened by this dispatch test")
    dsn = "postgresql://secret:secret@example.invalid/private"
    monkeypatch.setenv("MASTERBRAIN_DSN", dsn)
    monkeypatch.setattr(
        cli,
        "run_email_bridge_batch_controller",
        lambda config_path, plan_path, received_dsn, check: {
            "config": config_path == config,
            "plan": plan_path == plan,
            "dsn": received_dsn == dsn,
            "check": check,
            "source_effects": False,
            "data_effects": False,
        },
    )
    main(
        [
            "email",
            "bridge-batch",
            "--config",
            str(config),
            "--plan",
            str(plan),
            "--check",
        ]
    )
    output = capsys.readouterr().out
    assert json.loads(output) == {
        "check": True,
        "config": True,
        "data_effects": False,
        "dsn": True,
        "plan": True,
        "source_effects": False,
    }
    assert dsn not in output


@pytest.mark.parametrize(
    ("command", "flag", "attribute"),
    [
        ("bridge-attachment", "--attachment-id", "run_email_attachment_bridge_controller"),
        ("bridge-document", "--extraction-id", "run_email_document_bridge_controller"),
    ],
)
def test_cli_email_part_bridges_use_explicit_targets_and_scrub_dsn(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    command: str,
    flag: str,
    attribute: str,
) -> None:
    key = "93c5a004-81ab-45b6-8652-e8ced2b40e47"
    target = "b22f0f5c-a784-46a1-95a7-b2b96e1f8396"
    config = tmp_path / "email-bridge.json"
    config.write_text("not opened by this dispatch test")
    dsn = "postgresql://secret:secret@example.invalid/private"
    monkeypatch.setenv("MASTERBRAIN_DSN", dsn)
    monkeypatch.setattr(
        cli,
        attribute,
        lambda path, received_dsn, received_target, received_key, check: {
            "config": path == config,
            "dsn": received_dsn == dsn,
            "target": str(received_target) == target,
            "key": str(received_key) == key,
            "check": check,
            "source_effects": False,
        },
    )
    main(
        [
            "email",
            command,
            "--config",
            str(config),
            flag,
            target,
            "--idempotency-key",
            key,
            "--check",
        ]
    )
    output = capsys.readouterr().out
    assert json.loads(output) == {
        "check": True,
        "config": True,
        "dsn": True,
        "key": True,
        "source_effects": False,
        "target": True,
    }
    assert dsn not in output
