"""Private Email bridge operator contract without a live database."""

from __future__ import annotations

import hashlib
import json
import secrets
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import ANY, MagicMock, Mock
from uuid import UUID, uuid4

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


def batch_plan_file(
    tmp_path: Path,
    *,
    count: int = 3,
    code_revision: str = "unit-email-bridge-v1",
) -> tuple[Path, UUID, list[control.EmailBridgeBatchItem]]:
    account = uuid4()
    items = [
        control.EmailBridgeBatchItem(
            legacy_version_id=uuid4(), idempotency_key=uuid4()
        )
        for _ in range(count)
    ]
    payload = {
        "version": 1,
        "account_id": str(account),
        "code_revision": code_revision,
        "items": [item.model_dump(mode="json") for item in items],
        "plan_sha256": control.email_bridge_batch_sha256(
            1, account, code_revision, items
        ),
    }
    plan_path = tmp_path / "state" / "email-batch.json"
    private_write(plan_path, payload)
    return plan_path, account, items


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


def test_bridge_plan_check_is_non_consuming_and_normal_run_is_content_free(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path, _, _ = controller_files(
        tmp_path, ["brain.source.ingest", "brain.document.publish"]
    )
    store = MagicMock()
    monkeypatch.setattr(control, "Store", Mock(return_value=store))
    core = MagicMock()
    monkeypatch.setattr(control, "DataCoreStore", Mock(return_value=core))
    account, cursor = uuid4(), uuid4()
    checked = control.run_email_bridge_plan_controller(
        path, "runtime-dsn", account, after=cursor, limit=7, check=True
    )
    assert checked == {
        "configuration_valid": True,
        "execution_verified": False,
        "operation": "email_bridge_plan",
        "source_effects": False,
        "data_effects": False,
    }
    core.email_bridge_plan.assert_not_called()
    core.email_bridge_plan.return_value = {
        "account_id": str(account),
        "results": [
            {
                "legacy_version_id": str(cursor),
                "recorded_at": "2026-09-22T00:00:00+00:00",
                "already_bridged": False,
            }
        ],
        "next_cursor": None,
        "limit": 7,
        "source_effects": False,
        "data_effects": False,
    }
    result = control.run_email_bridge_plan_controller(
        path, "runtime-dsn", account, after=cursor, limit=7
    )
    assert result["operation"] == "email_bridge_plan"
    assert result["source_effects"] is False and result["data_effects"] is False
    assert not {"subject", "sender", "content", "provider", "locator"} & result.keys()
    core.email_bridge_plan.assert_called_once_with(ANY, account, after=cursor, limit=7)


def test_batch_check_validates_seal_without_target_access(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_path, _, _ = controller_files(
        tmp_path, ["brain.source.ingest", "brain.document.publish"]
    )
    plan_path, _, items = batch_plan_file(tmp_path)
    monkeypatch.setattr(control, "Store", Mock(return_value=MagicMock()))
    core = Mock(side_effect=AssertionError("check must not inspect batch targets"))
    monkeypatch.setattr(control, "DataCoreStore", core)
    result = control.run_email_bridge_batch_controller(
        config_path, plan_path, "runtime-dsn", check=True
    )
    assert result["requested"] == len(items)
    assert result["execution_verified"] is False
    assert result["data_effects"] is False
    core.assert_not_called()


def test_batch_is_fail_stop_and_exact_retry_replays_completed_items(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_path, _, _ = controller_files(
        tmp_path, ["brain.source.ingest", "brain.document.publish"]
    )
    plan_path, account, items = batch_plan_file(tmp_path)
    monkeypatch.setattr(control, "Store", Mock(return_value=MagicMock()))
    core = MagicMock()
    core.bridge_current_email_version.side_effect = [
        SimpleNamespace(changed=True),
        control.Conflict("synthetic refusal"),
    ]
    monkeypatch.setattr(control, "DataCoreStore", Mock(return_value=core))
    stopped = control.run_email_bridge_batch_controller(
        config_path, plan_path, "runtime-dsn"
    )
    assert stopped["complete"] is False
    assert stopped["completed"] == 1 and stopped["recorded"] == 1
    assert stopped["failed_version_id"] == str(items[1].legacy_version_id)
    assert core.bridge_current_email_version.call_count == 2

    core.bridge_current_email_version.reset_mock()
    core.bridge_current_email_version.side_effect = [
        SimpleNamespace(changed=False),
        SimpleNamespace(changed=True),
        SimpleNamespace(changed=True),
    ]
    completed = control.run_email_bridge_batch_controller(
        config_path, plan_path, "runtime-dsn"
    )
    assert completed["complete"] is True
    assert completed["completed"] == 3
    assert completed["recorded"] == 2 and completed["replayed"] == 1
    assert [call.args[1:3] for call in core.bridge_current_email_version.call_args_list] == [
        (item.legacy_version_id, item.idempotency_key) for item in items
    ]
    assert all(
        call.kwargs
        == {
            "code_revision": "unit-email-bridge-v1",
            "expected_account_id": account,
        }
        for call in core.bridge_current_email_version.call_args_list
    )
    assert not {"subject", "sender", "content", "provider", "locator"} & completed.keys()


@pytest.mark.parametrize("mutation", ["digest", "duplicate_version", "duplicate_key"])
def test_batch_rejects_invalid_seal_before_database(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mutation: str
) -> None:
    config_path, _, _ = controller_files(
        tmp_path, ["brain.source.ingest", "brain.document.publish"]
    )
    plan_path, _, _ = batch_plan_file(tmp_path)
    payload = json.loads(plan_path.read_text())
    if mutation == "digest":
        payload["plan_sha256"] = "0" * 64
    elif mutation == "duplicate_version":
        payload["items"][1]["legacy_version_id"] = payload["items"][0][
            "legacy_version_id"
        ]
    else:
        payload["items"][1]["idempotency_key"] = payload["items"][0]["idempotency_key"]
    private_write(plan_path, payload)
    store = Mock()
    monkeypatch.setattr(control, "Store", store)
    with pytest.raises(control.EmailBridgeControllerError):
        control.run_email_bridge_batch_controller(
            config_path, plan_path, "runtime-dsn", check=True
        )
    store.assert_not_called()


def test_batch_requires_private_plan_and_matching_revision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_path, _, _ = controller_files(
        tmp_path, ["brain.source.ingest", "brain.document.publish"]
    )
    plan_path, _, _ = batch_plan_file(tmp_path, code_revision="other-revision")
    store = Mock()
    monkeypatch.setattr(control, "Store", store)
    with pytest.raises(control.EmailBridgeControllerError):
        control.run_email_bridge_batch_controller(config_path, plan_path, "runtime-dsn")
    plan_path, _, _ = batch_plan_file(tmp_path)
    plan_path.chmod(0o644)
    with pytest.raises(control.EmailBridgeControllerError):
        control.run_email_bridge_batch_controller(config_path, plan_path, "runtime-dsn")
    store.assert_not_called()


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


@pytest.mark.parametrize(
    ("runner", "operation"),
    [
        (control.run_email_attachment_bridge_controller, "bridge_email_attachment"),
        (
            control.run_email_document_bridge_controller,
            "bridge_email_document_extraction",
        ),
    ],
)
def test_part_bridge_checks_are_non_consuming(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    runner: object,
    operation: str,
) -> None:
    path, _, _ = controller_files(
        tmp_path, ["brain.source.ingest", "brain.document.publish"]
    )
    store = MagicMock()
    monkeypatch.setattr(control, "Store", Mock(return_value=store))
    core = Mock(side_effect=AssertionError("check must not inspect the target"))
    monkeypatch.setattr(control, "DataCoreStore", core)
    result = runner(path, "runtime-dsn", uuid4(), uuid4(), check=True)
    assert result == {
        "configuration_valid": True,
        "execution_verified": False,
        "operation": operation,
        "source_effects": False,
        "data_effects": False,
    }
    core.assert_not_called()


def test_part_bridge_dispatch_returns_content_free_receipts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path, _, _ = controller_files(
        tmp_path, ["brain.source.ingest", "brain.document.publish"]
    )
    monkeypatch.setattr(control, "Store", Mock(return_value=MagicMock()))
    core = MagicMock()
    common = {
        "source_id": "email_abc",
        "item_id": "attachmentitem_abc",
        "version_id": "attachmentversion_abc",
        "evidence_id": "evidence_abc",
        "document_id": "document_abc",
        "chunks": 1,
        "changed": True,
    }
    core.bridge_email_attachment.return_value = SimpleNamespace(
        **common, part_id="part_abc", outcome="extracted"
    )
    core.bridge_email_document_extraction.return_value = SimpleNamespace(
        **common, extraction_status="partial"
    )
    monkeypatch.setattr(control, "DataCoreStore", Mock(return_value=core))
    attachment_id, extraction_id, attachment_key, extraction_key = (
        uuid4(),
        uuid4(),
        uuid4(),
        uuid4(),
    )
    attachment = control.run_email_attachment_bridge_controller(
        path, "runtime-dsn", attachment_id, attachment_key
    )
    document = control.run_email_document_bridge_controller(
        path, "runtime-dsn", extraction_id, extraction_key
    )
    assert attachment["part_id"] == "part_abc" and attachment["outcome"] == "extracted"
    assert document["extraction_status"] == "partial"
    assert not {"content", "filename", "subject", "sender", "address"} & (
        attachment.keys() | document.keys()
    )
    core.bridge_email_attachment.assert_called_once_with(
        ANY, attachment_id, attachment_key, code_revision="unit-email-bridge-v1"
    )
    core.bridge_email_document_extraction.assert_called_once_with(
        ANY, extraction_id, extraction_key, code_revision="unit-email-bridge-v1"
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


def test_revocation_after_database_preflight_prevents_bridge_plan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path, _, _ = controller_files(
        tmp_path, ["brain.source.ingest", "brain.document.publish"]
    )
    monkeypatch.setattr(control, "Store", Mock(return_value=MagicMock()))
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
        control.run_email_bridge_plan_controller(path, "runtime-dsn", uuid4())
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
