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
