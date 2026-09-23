"""Private FileOS operator contract without a live database or Docker."""

from __future__ import annotations

import hashlib
import json
import secrets
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, Mock
from uuid import uuid4

import pytest

from masterbrain import fileos_controller as control
from masterbrain.datacore.fileos import snapshot_tree


def private_write(path: Path, value: object) -> None:
    raw = value if isinstance(value, bytes) else json.dumps(value).encode()
    path.write_bytes(raw)
    path.chmod(0o600)


def controller_files(tmp_path: Path) -> tuple[Path, dict[str, object], list[dict[str, object]]]:
    state = tmp_path / "state"
    source = tmp_path / "source"
    state.mkdir(mode=0o700)
    source.mkdir()
    (source / "note.txt").write_text("controller unit proof")
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
    manifest = snapshot_tree(
        source, source_id="files_primary", observed_at=datetime(2026, 9, 22, tzinfo=UTC)
    )
    private_write(state / "snapshot.json", manifest)
    config: dict[str, object] = {
        "version": 1,
        "source_id": "files_primary",
        "root": str(source),
        "manifest_file": str(state / "snapshot.json"),
        "credentials_file": str(state / "credentials.json"),
        "token_file": str(state / "token"),
        "code_revision": "unit-controller-v1",
    }
    path = state / "controller.json"
    private_write(path, config)
    return path, config, credentials


def test_check_authenticates_runtime_without_publication(tmp_path: Path, monkeypatch) -> None:
    path, _, _ = controller_files(tmp_path)
    store = MagicMock()
    monkeypatch.setattr(control, "Store", Mock(return_value=store))
    adapter = Mock(side_effect=AssertionError("check must not publish"))
    monkeypatch.setattr(control, "FileOSAdapter", adapter)
    assert control.run_fileos_controller(path, "runtime-dsn", uuid4(), check=True) == {
        "configuration_valid": True,
        "execution_verified": False,
        "source_effects": False,
    }
    store.transaction.assert_called_once()
    adapter.assert_not_called()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("version", True),
        ("source_id", "../files"),
        ("root", "relative"),
        ("manifest_file", "relative"),
        ("document_image_id", "latest"),
        ("docker_binary", "/usr/bin/docker"),
        ("shell", "echo unsafe"),
    ],
)
def test_closed_config_fails_before_database(
    tmp_path: Path, monkeypatch, field: str, value: object
) -> None:
    path, config, _ = controller_files(tmp_path)
    config[field] = value
    private_write(path, config)
    store = Mock()
    monkeypatch.setattr(control, "Store", store)
    with pytest.raises(control.FileOSControllerError):
        control.run_fileos_controller(path, "runtime-dsn", uuid4(), check=True)
    store.assert_not_called()


@pytest.mark.parametrize("scopes", [[], ["brain.source.ingest"], ["email.process"]])
def test_exact_worker_scopes_required(tmp_path: Path, monkeypatch, scopes: list[str]) -> None:
    path, _, credentials = controller_files(tmp_path)
    credentials[0]["scopes"] = scopes
    private_write(path.parent / "credentials.json", credentials)
    store = Mock()
    monkeypatch.setattr(control, "Store", store)
    with pytest.raises(control.FileOSControllerError):
        control.run_fileos_controller(path, "runtime-dsn", uuid4(), check=True)
    store.assert_not_called()


def test_source_binding_and_manifest_ambiguity_fail_closed(tmp_path: Path, monkeypatch) -> None:
    path, config, _ = controller_files(tmp_path)
    manifest = json.loads((path.parent / "snapshot.json").read_text())
    manifest["source"]["source_id"] = "different_source"
    private_write(path.parent / "snapshot.json", manifest)
    store = Mock()
    monkeypatch.setattr(control, "Store", store)
    with pytest.raises(control.FileOSControllerError):
        control.run_fileos_controller(path, "runtime-dsn", uuid4(), check=True)
    store.assert_not_called()
    config["source_id"] = "different_source"
    private_write(path, config)
    private_write(path.parent / "snapshot.json", b'{"source":{},"source":{}}')
    with pytest.raises(control.FileOSControllerError):
        control.run_fileos_controller(path, "runtime-dsn", uuid4(), check=True)


def test_incomplete_snapshot_refused_before_database_or_publication(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path, _, _ = controller_files(tmp_path)
    manifest_path = path.parent / "snapshot.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["errors"] = [{"locator": "inaccessible", "code": "directory_unreadable"}]
    manifest["counts"]["errors"] = 1
    private_write(manifest_path, manifest)
    store = Mock()
    adapter = Mock()
    monkeypatch.setattr(control, "Store", store)
    monkeypatch.setattr(control, "FileOSAdapter", adapter)
    with pytest.raises(control.FileOSControllerError):
        control.run_fileos_controller(path, "runtime-dsn", uuid4())
    store.assert_not_called()
    adapter.assert_not_called()
