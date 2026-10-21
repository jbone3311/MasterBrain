"""Private Email XLSX publication command refuses ambient and broad authority."""

from __future__ import annotations

import hashlib
import json
import secrets
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, Mock
from uuid import UUID, uuid4

import pytest

from masterbrain import cli
from masterbrain import email_xlsx_publication_controller as control

REVIEW_ID = "xrev_" + "a" * 32


def _private(path: Path, value: object) -> None:
    path.write_bytes(value if isinstance(value, bytes) else json.dumps(value).encode())
    path.chmod(0o600)


def _operator(tmp_path: Path) -> tuple[Path, dict[str, object], list[dict[str, object]]]:
    state = tmp_path / "private-state"
    state.mkdir(mode=0o700)
    token = secrets.token_urlsafe(40)
    _private(state / "token", token.encode())
    credentials: list[dict[str, object]] = [{
        "token_sha256": hashlib.sha256(token.encode()).hexdigest(),
        "tenant_id": str(uuid4()), "actor_id": str(uuid4()),
        "scopes": ["brain.source.ingest", "brain.document.publish", "email.evidence.read"],
        "client_kind": "worker",
        "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
    }]
    _private(state / "credentials.json", credentials)
    config: dict[str, object] = {
        "version": 1, "account_id": str(uuid4()),
        "credentials_file": str(state / "credentials.json"),
        "token_file": str(state / "token"),
    }
    path = state / "xlsx-publication.json"
    _private(path, config)
    return path, config, credentials


def test_check_authenticates_without_selected_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    path, _, credentials = _operator(tmp_path)
    store = MagicMock()
    constructor = Mock(return_value=store)
    monkeypatch.setattr(control, "Store", constructor)
    bridge = Mock(side_effect=AssertionError("check must not inspect review"))
    monkeypatch.setattr(control, "EmailXlsxDocumentBridge", bridge)
    assert control.run_email_xlsx_publication_controller(
        path, "tenant-dsn", REVIEW_ID, uuid4(), check=True, tenant_bound_db=True,
    ) == {
        "configuration_valid": True, "execution_verified": False,
        "source_effects": False, "data_effects": False,
    }
    constructor.assert_called_once_with(
        "tenant-dsn", tenant_dsns={UUID(str(credentials[0]["tenant_id"])): "tenant-dsn"},
    )
    store.transaction.assert_called_once()
    bridge.assert_not_called()


def test_execute_binds_account_and_rechecks_worker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    path, config, _ = _operator(tmp_path)
    store = MagicMock()
    monkeypatch.setattr(control, "Store", Mock(return_value=store))
    calls: list[object] = []

    class Bridge:
        def __init__(self, received_store: object) -> None:
            assert received_store is store

        def publish(self, ctx, review_id, idempotency_key, *, expected_account_id, authorize):
            authorize()
            calls.extend([ctx.scopes, review_id, idempotency_key, expected_account_id])
            return {"changed": True, "mailbox_effects": False}

    monkeypatch.setattr(control, "EmailXlsxDocumentBridge", Bridge)
    key = uuid4()
    assert control.run_email_xlsx_publication_controller(
        path, "tenant-dsn", REVIEW_ID, key, tenant_bound_db=True,
    ) == {"changed": True, "mailbox_effects": False}
    assert calls == [
        frozenset({"brain.source.ingest", "brain.document.publish", "email.evidence.read"}),
        REVIEW_ID, key, UUID(str(config["account_id"])),
    ]


@pytest.mark.parametrize("field,value", [
    ("version", True), ("account_id", "not-a-uuid"),
    ("credentials_file", "relative"), ("token_file", "relative"),
    ("unexpected", "bad"),
])
def test_bad_config_refused_before_database(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, field: str, value: object,
) -> None:
    path, config, _ = _operator(tmp_path)
    config[field] = value
    _private(path, config)
    constructor = Mock()
    monkeypatch.setattr(control, "Store", constructor)
    with pytest.raises(control.EmailXlsxPublicationControllerError):
        control.run_email_xlsx_publication_controller(
            path, "tenant-dsn", REVIEW_ID, uuid4(), check=True, tenant_bound_db=True,
        )
    constructor.assert_not_called()


@pytest.mark.parametrize("scopes,kind", [
    (["brain.document.publish"], "worker"),
    (["email.review", "email.evidence.read"], "human"),
    (["brain.source.ingest", "brain.document.publish", "email.evidence.read"], "human"),
])
def test_exact_worker_scope_required(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, scopes: list[str], kind: str,
) -> None:
    path, _, credentials = _operator(tmp_path)
    credentials[0]["scopes"] = scopes
    credentials[0]["client_kind"] = kind
    _private(path.parent / "credentials.json", credentials)
    constructor = Mock()
    monkeypatch.setattr(control, "Store", constructor)
    with pytest.raises(control.EmailXlsxPublicationControllerError):
        control.run_email_xlsx_publication_controller(
            path, "tenant-dsn", REVIEW_ID, uuid4(), check=True, tenant_bound_db=True,
        )
    constructor.assert_not_called()


def test_unbound_or_malformed_request_refused_before_database(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    path, _, _ = _operator(tmp_path)
    constructor = Mock()
    monkeypatch.setattr(control, "Store", constructor)
    for review_id, bound in ((REVIEW_ID, False), ("xrev_bad", True)):
        with pytest.raises(control.EmailXlsxPublicationControllerError):
            control.run_email_xlsx_publication_controller(
                path, "tenant-dsn", review_id, uuid4(), tenant_bound_db=bound,
            )
    constructor.assert_not_called()


def test_cli_exposes_exact_command() -> None:
    args = cli.build_parser().parse_args([
        "email", "publish-reviewed-xlsx", "--config", "/private/xlsx.json",
        "--review-id", REVIEW_ID, "--idempotency-key", str(uuid4()),
        "--tenant-bound-db", "--check",
    ])
    assert args.email_command == "publish-reviewed-xlsx" and args.tenant_bound_db is True
