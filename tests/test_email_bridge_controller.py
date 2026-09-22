"""Private Email bridge operator contract without a live database."""

from __future__ import annotations

import hashlib
import json
import secrets
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import ANY, MagicMock, Mock
from uuid import uuid4

import pytest

from masterbrain import email_bridge_controller as control


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
        "credentials_file": str(state / "credentials.json"),
        "token_file": str(state / "token"),
        "code_revision": "unit-email-bridge-v1",
    }
    path = state / "email-bridge.json"
    private_write(path, config)
    return path, config, credentials


def test_check_authenticates_without_read_or_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path, _, _ = controller_files(
        tmp_path, ["brain.source.ingest", "brain.document.publish"]
    )
    store = MagicMock()
    monkeypatch.setattr(control, "Store", Mock(return_value=store))
    core = Mock(side_effect=AssertionError("check must not inspect or bridge evidence"))
    monkeypatch.setattr(control, "DataCoreStore", core)
    result = control.run_email_bridge_controller(
        path, "runtime-dsn", uuid4(), uuid4(), check=True
    )
    assert result == {
        "configuration_valid": True,
        "execution_verified": False,
        "operation": "bridge_current_email_version",
        "source_effects": False,
        "data_effects": False,
    }
    core.assert_not_called()


def test_bridge_returns_only_opaque_bounded_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path, _, _ = controller_files(
        tmp_path, ["brain.source.ingest", "brain.document.publish"]
    )
    store = MagicMock()
    monkeypatch.setattr(control, "Store", Mock(return_value=store))
    core = MagicMock()
    core.bridge_current_email_version.return_value = SimpleNamespace(
        source_id="email_abc",
        item_id="emailitem_abc",
        version_id="emailversion_abc",
        evidence_id="evidence_abc",
        document_id="document_abc",
        chunks=2,
        changed=True,
    )
    monkeypatch.setattr(control, "DataCoreStore", Mock(return_value=core))
    evidence_id, key = uuid4(), uuid4()
    result = control.run_email_bridge_controller(
        path, "runtime-dsn", evidence_id, key
    )
    assert result["recorded"] is True
    assert result["chunks"] == 2
    assert result["source_effects"] is False
    assert not {"subject", "sender", "content", "address"} & result.keys()
    core.bridge_current_email_version.assert_called_once_with(
        ANY,
        evidence_id,
        key,
        code_revision="unit-email-bridge-v1",
    )


def test_revocation_after_database_preflight_prevents_bridge(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path, _, _ = controller_files(
        tmp_path, ["brain.source.ingest", "brain.document.publish"]
    )
    store = MagicMock()
    monkeypatch.setattr(control, "Store", Mock(return_value=store))
    calls = 0
    original = control.WorkerIdentity.authenticate

    def revoke(identity: control.WorkerIdentity) -> object:
        nonlocal calls
        calls += 1
        principal = original(identity)
        if calls == 2:
            private_write(path.parent / "credentials.json", [])
        return principal

    monkeypatch.setattr(control.WorkerIdentity, "authenticate", revoke)
    core = Mock()
    monkeypatch.setattr(control, "DataCoreStore", core)
    with pytest.raises(control.EmailBridgeControllerError):
        control.run_email_bridge_controller(path, "runtime-dsn", uuid4(), uuid4())
    core.assert_not_called()


@pytest.mark.parametrize(
    "scopes",
    [[], ["brain.source.ingest"], ["brain.document.publish"], ["email.ingest"]],
)
def test_exact_worker_scopes_required(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, scopes: list[str]
) -> None:
    path, _, _ = controller_files(tmp_path, scopes)
    store = Mock()
    monkeypatch.setattr(control, "Store", store)
    with pytest.raises(control.EmailBridgeControllerError):
        control.run_email_bridge_controller(
            path, "runtime-dsn", uuid4(), uuid4(), check=True
        )
    store.assert_not_called()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("version", True),
        ("credentials_file", "relative"),
        ("code_revision", "bad\x00revision"),
        ("extra", "unsafe"),
    ],
)
def test_closed_private_config_fails_before_database(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    value: object,
) -> None:
    path, config, _ = controller_files(
        tmp_path, ["brain.source.ingest", "brain.document.publish"]
    )
    config[field] = value
    private_write(path, config)
    store = Mock()
    monkeypatch.setattr(control, "Store", store)
    with pytest.raises(control.EmailBridgeControllerError):
        control.run_email_bridge_controller(path, "runtime-dsn", uuid4(), uuid4())
    store.assert_not_called()


def test_internal_errors_are_scrubbed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path, _, _ = controller_files(
        tmp_path, ["brain.source.ingest", "brain.document.publish"]
    )
    monkeypatch.setattr(control, "Store", MagicMock())
    core = MagicMock()
    core.bridge_current_email_version.side_effect = RuntimeError("private message body")
    monkeypatch.setattr(control, "DataCoreStore", Mock(return_value=core))
    with pytest.raises(control.EmailBridgeControllerError) as error:
        control.run_email_bridge_controller(path, "runtime-dsn", uuid4(), uuid4())
    assert "private message body" not in str(error.value)
