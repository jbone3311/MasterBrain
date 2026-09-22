"""Private archive-member operator contract without PostgreSQL or Docker."""

from __future__ import annotations

import hashlib
import json
import secrets
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import ANY, MagicMock, Mock
from uuid import uuid4

import pytest

from masterbrain import archive_member_controller as control


def private_write(path: Path, value: object) -> None:
    raw = value if isinstance(value, bytes) else json.dumps(value).encode()
    path.write_bytes(raw)
    path.chmod(0o600)


def controller_files(
    tmp_path: Path,
) -> tuple[Path, dict[str, object], list[dict[str, object]]]:
    state, root = tmp_path / "state", tmp_path / "source"
    state.mkdir(mode=0o700)
    root.mkdir()
    token = secrets.token_urlsafe(40)
    private_write(state / "token", token.encode())
    credentials: list[dict[str, object]] = [
        {
            "token_sha256": hashlib.sha256(token.encode()).hexdigest(),
            "tenant_id": str(uuid4()),
            "actor_id": str(uuid4()),
            "scopes": ["brain.source.ingest", "brain.document.publish"],
            "client_kind": "worker",
            "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
        }
    ]
    private_write(state / "credentials.json", credentials)
    config: dict[str, object] = {
        "version": 1,
        "root": str(root),
        "archive_image_id": "sha256:" + "a" * 64,
        "docker_binary": "/usr/bin/false",
        "credentials_file": str(state / "credentials.json"),
        "token_file": str(state / "token"),
        "code_revision": "unit-archive-controller-v1",
    }
    path = state / "archive-controller.json"
    private_write(path, config)
    return path, config, credentials


def test_check_preflights_without_target_query_or_worker_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path, _, _ = controller_files(tmp_path)
    store = MagicMock()
    processor = MagicMock()
    monkeypatch.setattr(control, "Store", Mock(return_value=store))
    monkeypatch.setattr(control, "DockerArchiveMemberProcessor", processor)
    core = Mock(side_effect=AssertionError("check must not query an archive target"))
    monkeypatch.setattr(control, "DataCoreStore", core)
    result = control.run_archive_member_controller(
        path,
        "runtime-dsn",
        "archive_inventory_" + "f" * 32,
        "not/queried.txt",
        uuid4(),
        check=True,
    )
    assert result == {
        "configuration_valid": True,
        "execution_verified": False,
        "source_effects": False,
    }
    store.transaction.assert_called_once()
    processor.assert_called_once()
    processor.return_value.read.assert_not_called()
    core.assert_not_called()


def test_preview_check_is_non_consuming_and_normal_run_is_exact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path, _, _ = controller_files(tmp_path)
    store = MagicMock()
    processor = Mock(side_effect=AssertionError("preview must not construct Docker worker"))
    monkeypatch.setattr(control, "Store", Mock(return_value=store))
    monkeypatch.setattr(control, "DockerArchiveMemberProcessor", processor)
    core = MagicMock()
    monkeypatch.setattr(control, "DataCoreStore", Mock(return_value=core))
    inventory = "archive_inventory_" + "a" * 32
    checked = control.run_archive_member_plan_controller(
        path, "runtime-dsn", inventory, after=3, limit=7, check=True
    )
    assert checked == {
        "configuration_valid": True,
        "execution_verified": False,
        "operation": "archive_member_text_plan",
        "source_effects": False,
        "data_effects": False,
    }
    core.archive_member_text_plan.assert_not_called()
    processor.assert_not_called()
    core.archive_member_text_plan.return_value = {
        "inventory_id": inventory,
        "eligible_members": 1,
        "results": [
            {
                "ordinal": 4,
                "member_locator": "folder/proof.md",
                "size_bytes": 5,
                "media_type": "text/markdown",
                "depth": 0,
                "already_published": False,
            }
        ],
        "next_cursor": None,
        "limit": 7,
        "untrusted_metadata": True,
        "source_effects": False,
        "data_effects": False,
    }
    result = control.run_archive_member_plan_controller(
        path, "runtime-dsn", inventory, after=3, limit=7
    )
    assert result["operation"] == "archive_member_text_plan"
    assert result["untrusted_metadata"] is True
    assert result["source_effects"] is False and result["data_effects"] is False
    core.archive_member_text_plan.assert_called_once_with(ANY, inventory, after=3, limit=7)
    processor.assert_not_called()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("version", True),
        ("root", "relative"),
        ("archive_image_id", "masterbrain-archives:latest"),
        ("docker_binary", "docker"),
        ("credentials_file", "relative"),
        ("token_file", "relative"),
        ("code_revision", "bad\x00revision"),
        ("extra", "unsafe"),
    ],
)
def test_closed_config_fails_before_database(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    value: object,
) -> None:
    path, config, _ = controller_files(tmp_path)
    config[field] = value
    private_write(path, config)
    store = Mock()
    monkeypatch.setattr(control, "Store", store)
    with pytest.raises(control.ArchiveMemberControllerError):
        control.run_archive_member_controller(
            path,
            "runtime-dsn",
            "archive_inventory_" + "a" * 32,
            "proof.txt",
            uuid4(),
            check=True,
        )
    store.assert_not_called()


@pytest.mark.parametrize("scopes", [[], ["brain.source.ingest"], ["email.process"]])
def test_exact_worker_scopes_are_required(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, scopes: list[str]
) -> None:
    path, _, credentials = controller_files(tmp_path)
    credentials[0]["scopes"] = scopes
    private_write(path.parent / "credentials.json", credentials)
    store = Mock()
    monkeypatch.setattr(control, "Store", store)
    with pytest.raises(control.ArchiveMemberControllerError):
        control.run_archive_member_controller(
            path,
            "runtime-dsn",
            "archive_inventory_" + "a" * 32,
            "proof.txt",
            uuid4(),
            check=True,
        )
    store.assert_not_called()


@pytest.mark.parametrize(
    "locator",
    ["", "/absolute.txt", "../escape.txt", "a/../b.txt", "a//b.txt", "a\\b.txt", "dir/"],
)
def test_unsafe_member_selection_fails_before_config_read(tmp_path: Path, locator: str) -> None:
    missing = tmp_path / "missing-config.json"
    with pytest.raises(control.ArchiveMemberControllerError):
        control.run_archive_member_controller(
            missing,
            "runtime-dsn",
            "archive_inventory_" + "a" * 32,
            locator,
            uuid4(),
            check=True,
        )


def test_public_or_symlink_config_is_refused(tmp_path: Path) -> None:
    path, _, _ = controller_files(tmp_path)
    path.chmod(0o644)
    with pytest.raises(control.ArchiveMemberControllerError):
        control.run_archive_member_controller(
            path,
            "runtime-dsn",
            "archive_inventory_" + "a" * 32,
            "proof.txt",
            uuid4(),
            check=True,
        )
    path.chmod(0o600)
    alias = path.with_name("alias.json")
    alias.symlink_to(path)
    with pytest.raises(control.ArchiveMemberControllerError):
        control.run_archive_member_controller(
            alias,
            "runtime-dsn",
            "archive_inventory_" + "a" * 32,
            "proof.txt",
            uuid4(),
            check=True,
        )
