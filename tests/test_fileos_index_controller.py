"""Private FileOS index operator contract without a live database."""

from __future__ import annotations

import hashlib
import json
import secrets
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock
from uuid import UUID, uuid4

import pytest

from masterbrain import fileos_index_controller as control


def private_write(path: Path, value: object) -> None:
    raw = value if isinstance(value, bytes) else json.dumps(value).encode()
    path.write_bytes(raw)
    path.chmod(0o600)


def controller_files(
    tmp_path: Path, scopes: list[str]
) -> tuple[Path, dict[str, object], list[dict[str, object]]]:
    state = tmp_path / "state"
    state.mkdir(mode=0o700)
    token = secrets.token_urlsafe(40)
    private_write(state / "token", token.encode())
    credentials: list[dict[str, object]] = [
        {
            "token_sha256": hashlib.sha256(token.encode()).hexdigest(),
            "tenant_id": str(uuid4()),
            "actor_id": str(uuid4()),
            "scopes": scopes,
            "client_kind": "worker",
            "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
        }
    ]
    private_write(state / "credentials.json", credentials)
    config: dict[str, object] = {
        "version": 1,
        "source_id": "files_primary",
        "credentials_file": str(state / "credentials.json"),
        "token_file": str(state / "token"),
        "code_revision": "unit-index-v1",
    }
    path = state / "index.json"
    private_write(path, config)
    return path, config, credentials


@pytest.mark.parametrize(
    ("run_id", "generation_id", "scopes", "operation"),
    [
        (
            uuid4(),
            None,
            ["brain.document.publish", "brain.index.activate"],
            "build_and_activate",
        ),
        (None, "index_generation_abc", ["brain.index.activate"], "activate_existing"),
    ],
)
def test_check_authenticates_without_writes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    run_id: object,
    generation_id: str | None,
    scopes: list[str],
    operation: str,
) -> None:
    path, _, _ = controller_files(tmp_path, scopes)
    store = MagicMock()
    monkeypatch.setattr(control, "Store", Mock(return_value=store))
    core = Mock(side_effect=AssertionError("check must not build or activate"))
    monkeypatch.setattr(control, "DataCoreStore", core)
    result = control.run_fileos_index_controller(
        path,
        "runtime-dsn",
        uuid4(),
        run_id=run_id,  # type: ignore[arg-type]
        generation_id=generation_id,
        check=True,
    )
    assert result == {
        "configuration_valid": True,
        "execution_verified": False,
        "operation": operation,
        "source_effects": False,
        "data_effects": False,
    }
    core.assert_not_called()


def test_build_and_activate_returns_bounded_receipts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path, _, _ = controller_files(
        tmp_path, ["brain.document.publish", "brain.index.activate"]
    )
    store = MagicMock()
    monkeypatch.setattr(control, "Store", Mock(return_value=store))
    core = MagicMock()
    run_id, key = uuid4(), uuid4()
    now = datetime(2026, 9, 22, tzinfo=UTC)
    core.build_fileos_index_generation.return_value = SimpleNamespace(
        generation_id="index_generation_abc",
        run_id=run_id,
        item_count=3,
        document_count=2,
        chunk_count=4,
        plan_sha256="a" * 64,
        ready_at=now,
        recorded=True,
    )
    core.activate_fileos_index_generation.return_value = SimpleNamespace(
        previous_generation_id=None,
        activated_at=now,
        recorded=True,
    )
    monkeypatch.setattr(control, "DataCoreStore", Mock(return_value=core))
    result = control.run_fileos_index_controller(
        path, "runtime-dsn", key, run_id=run_id
    )
    assert result["generation_id"] == "index_generation_abc"
    assert result["generation"]["chunk_count"] == 4
    assert result["activation"]["recorded"] is True
    assert result["source_effects"] is False
    assert "content" not in json.dumps(result)
    core.build_fileos_index_generation.assert_called_once()
    core.activate_fileos_index_generation.assert_called_once()


def test_revocation_after_build_prevents_activation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path, _, _ = controller_files(
        tmp_path, ["brain.document.publish", "brain.index.activate"]
    )
    store = MagicMock()
    monkeypatch.setattr(control, "Store", Mock(return_value=store))
    core = MagicMock()

    def revoke(*args: object, **kwargs: object) -> SimpleNamespace:
        private_write(path.parent / "credentials.json", [])
        return SimpleNamespace(generation_id="index_generation_abc")

    core.build_fileos_index_generation.side_effect = revoke
    monkeypatch.setattr(control, "DataCoreStore", Mock(return_value=core))
    with pytest.raises(control.FileOSIndexControllerError):
        control.run_fileos_index_controller(
            path, "runtime-dsn", uuid4(), run_id=uuid4()
        )
    core.activate_fileos_index_generation.assert_not_called()


@pytest.mark.parametrize(
    ("scopes", "run_id", "generation_id"),
    [
        (["brain.index.activate"], uuid4(), None),
        (["brain.document.publish", "brain.index.activate"], None, "index_generation_abc"),
        (["brain.document.publish"], uuid4(), None),
    ],
)
def test_exact_operation_scopes_required(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    scopes: list[str],
    run_id: object,
    generation_id: str | None,
) -> None:
    path, _, _ = controller_files(tmp_path, scopes)
    store = Mock()
    monkeypatch.setattr(control, "Store", store)
    with pytest.raises(control.FileOSIndexControllerError):
        control.run_fileos_index_controller(
            path,
            "runtime-dsn",
            uuid4(),
            run_id=run_id,  # type: ignore[arg-type]
            generation_id=generation_id,
            check=True,
        )
    store.assert_not_called()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("version", True),
        ("source_id", "../files"),
        ("credentials_file", "relative"),
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
    path, config, _ = controller_files(
        tmp_path, ["brain.document.publish", "brain.index.activate"]
    )
    config[field] = value
    private_write(path, config)
    store = Mock()
    monkeypatch.setattr(control, "Store", store)
    with pytest.raises(control.FileOSIndexControllerError):
        control.run_fileos_index_controller(path, "runtime-dsn", uuid4(), run_id=uuid4())
    store.assert_not_called()


def test_exactly_one_target_is_required(tmp_path: Path) -> None:
    path, _, _ = controller_files(
        tmp_path, ["brain.document.publish", "brain.index.activate"]
    )
    with pytest.raises(control.FileOSIndexControllerError):
        control.run_fileos_index_controller(path, "runtime-dsn", uuid4())
    with pytest.raises(control.FileOSIndexControllerError):
        control.run_fileos_index_controller(
            path,
            "runtime-dsn",
            uuid4(),
            run_id=uuid4(),
            generation_id="index_generation_abc",
        )


def test_build_requires_code_revision_but_rollback_does_not(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path, config, _ = controller_files(tmp_path, ["brain.index.activate"])
    config.pop("code_revision")
    private_write(path, config)
    store = MagicMock()
    monkeypatch.setattr(control, "Store", Mock(return_value=store))
    with pytest.raises(control.FileOSIndexControllerError):
        control.run_fileos_index_controller(path, "runtime-dsn", uuid4(), run_id=uuid4())
    monkeypatch.setattr(control, "DataCoreStore", Mock(side_effect=AssertionError))
    assert control.run_fileos_index_controller(
        path,
        "runtime-dsn",
        uuid4(),
        generation_id="index_generation_abc",
        check=True,
    )["operation"] == "activate_existing"


def test_tenant_bound_mode_binds_authenticated_worker_tenant(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path, _, credentials = controller_files(
        tmp_path, ["brain.document.publish", "brain.index.activate"]
    )
    store = MagicMock()
    factory = Mock(return_value=store)
    monkeypatch.setattr(control, "Store", factory)
    assert control.run_fileos_index_controller(
        path, "runtime-dsn", uuid4(), run_id=uuid4(),
        check=True, tenant_bound_db=True,
    )["configuration_valid"] is True
    factory.assert_called_once_with(
        "runtime-dsn", tenant_dsns={
            UUID(str(credentials[0]["tenant_id"])): "runtime-dsn"
        },
    )
    with pytest.raises(control.FileOSIndexControllerError):
        control.run_fileos_index_controller(
            path, "runtime-dsn", uuid4(), run_id=uuid4(),
            check=True, tenant_bound_db=1,  # type: ignore[arg-type]
        )
