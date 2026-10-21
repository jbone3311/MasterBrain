"""Private operator command contract; no mailbox or database required."""

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
from masterbrain import source_tier_email_controller as control

REVIEW_ID = "stier_" + "a" * 32


def _private(path: Path, value: object) -> None:
    path.write_bytes(value if isinstance(value, bytes) else json.dumps(value).encode())
    path.chmod(0o600)


def _operator(tmp_path: Path, *, encrypted: bool = False):
    state = tmp_path / "private-state"
    state.mkdir(mode=0o700)
    token = secrets.token_urlsafe(40)
    _private(state / "token", token.encode())
    tenant_id, account_id = uuid4(), uuid4()
    credentials = [{
        "token_sha256": hashlib.sha256(token.encode()).hexdigest(),
        "tenant_id": str(tenant_id), "actor_id": str(uuid4()),
        "scopes": ["brain.document.publish", "email.evidence.read"],
        "client_kind": "worker",
        "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
    }]
    _private(state / "credentials.json", credentials)
    config: dict[str, object] = {
        "version": 1, "account_id": str(account_id),
        "credentials_file": str(state / "credentials.json"),
        "token_file": str(state / "token"),
    }
    if encrypted:
        root = state / "ciphertext"
        root.mkdir(mode=0o700)
        _private(state / "keys.json", {
            "tenant_id": str(tenant_id),
            "keys": [{"key_id": "test-key", "key_hex": bytes(range(32)).hex()}],
        })
        config.update({"blob_root": str(root), "keys_file": str(state / "keys.json")})
    path = state / "email-tier.json"
    _private(path, config)
    return path, config, credentials


@pytest.mark.parametrize("encrypted", [False, True])
def test_check_authenticates_and_never_reads_mime_or_writes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, encrypted: bool,
) -> None:
    path, config, credentials = _operator(tmp_path, encrypted=encrypted)
    store = MagicMock()
    cursor = store.transaction.return_value.__enter__.return_value
    cursor.execute.return_value.fetchone.return_value = {"status": "active"}
    constructor = Mock(return_value=store)
    monkeypatch.setattr(control, "Store", constructor)
    replay = Mock(side_effect=AssertionError("check must not read a selected message"))
    blobs = Mock(side_effect=AssertionError("check must not construct blob storage"))
    monkeypatch.setattr(control, "SourceTierEmailReplayStore", replay)
    monkeypatch.setattr(control, "EncryptedBlobStore", blobs)
    result = control.run_source_tier_email_controller(
        path, "tenant-dsn", REVIEW_ID, check=True, tenant_bound_db=True,
    )
    assert result == {
        "configuration_valid": True, "execution_verified": False,
        "source_effects": False, "data_effects": False,
    }
    constructor.assert_called_once_with(
        "tenant-dsn", tenant_dsns={UUID(str(credentials[0]["tenant_id"])): "tenant-dsn"},
    )
    assert store.transaction.call_count == 1
    store.transaction.return_value.__enter__.return_value.execute.assert_called_once_with(
        "SELECT status FROM mail_accounts WHERE id=%s", (UUID(str(config["account_id"])),),
    )
    replay.assert_not_called()
    blobs.assert_not_called()


def test_execution_binds_account_and_reauthenticates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    path, config, _ = _operator(tmp_path)
    store = MagicMock()
    cursor = store.transaction.return_value.__enter__.return_value
    cursor.execute.return_value.fetchone.return_value = {"status": "active"}
    monkeypatch.setattr(control, "Store", Mock(return_value=store))
    calls: list[object] = []

    class Replay:
        def __init__(self, received_store: object) -> None:
            assert received_store is store

        def record_current_text_replay(self, ctx, review_id, *, expected_account_id, authorize):
            authorize()
            calls.extend([review_id, expected_account_id, ctx.scopes])
            return {
                "review_id": review_id, "worker_observed_text_replay": True,
                "source_effects": False, "financial_claim_approved": False,
            }

    monkeypatch.setattr(control, "SourceTierEmailReplayStore", Replay)
    result = control.run_source_tier_email_controller(
        path, "tenant-dsn", REVIEW_ID, tenant_bound_db=True,
    )
    assert result["financial_claim_approved"] is False
    assert calls == [
        REVIEW_ID, UUID(str(config["account_id"])),
        frozenset({"brain.document.publish", "email.evidence.read"}),
    ]


@pytest.mark.parametrize("field,value", [
    ("version", True), ("account_id", "not-uuid"), ("credentials_file", "relative"),
    ("blob_root", "/private/only-one"), ("unexpected", "bad"),
])
def test_invalid_closed_config_fails_before_database(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, field: str, value: object,
) -> None:
    path, config, _ = _operator(tmp_path)
    config[field] = value
    _private(path, config)
    constructor = Mock()
    monkeypatch.setattr(control, "Store", constructor)
    with pytest.raises(control.EmailTierReplayControllerError):
        control.run_source_tier_email_controller(
            path, "tenant-dsn", REVIEW_ID, check=True, tenant_bound_db=True,
        )
    constructor.assert_not_called()


@pytest.mark.parametrize("scopes", [[], ["brain.document.publish"], ["email.evidence.read"]])
def test_exact_two_scope_worker_is_required(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, scopes: list[str],
) -> None:
    path, _, credentials = _operator(tmp_path)
    credentials[0]["scopes"] = scopes
    _private(path.parent / "credentials.json", credentials)
    constructor = Mock()
    monkeypatch.setattr(control, "Store", constructor)
    with pytest.raises(control.EmailTierReplayControllerError):
        control.run_source_tier_email_controller(
            path, "tenant-dsn", REVIEW_ID, check=True, tenant_bound_db=True,
        )
    constructor.assert_not_called()


def test_shared_db_mode_refused_before_config_or_database(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    path, _, _ = _operator(tmp_path)
    constructor = Mock()
    monkeypatch.setattr(control, "Store", constructor)
    with pytest.raises(control.EmailTierReplayControllerError):
        control.run_source_tier_email_controller(path, "shared-dsn", REVIEW_ID, check=True)
    constructor.assert_not_called()


def test_cli_dispatches_exact_review_and_tenant_bound_mode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    dsn = "postgresql://secret:secret@example.invalid/private"
    monkeypatch.setenv("MASTERBRAIN_DSN", dsn)
    monkeypatch.setattr(
        cli, "run_source_tier_email_controller",
        lambda path, received_dsn, review_id, **options: {
            "config": path == tmp_path / "private.json",
            "dsn": received_dsn == dsn,
            "review_id": review_id == REVIEW_ID,
            "check": options["check"],
            "tenant_bound_db": options["tenant_bound_db"],
        },
    )
    cli.main([
        "email", "replay-tier-text", "--config", str(tmp_path / "private.json"),
        "--review-id", REVIEW_ID, "--tenant-bound-db", "--check",
    ])
    output = capsys.readouterr().out
    assert dsn not in output
    assert json.loads(output) == {
        "config": True, "dsn": True, "review_id": True,
        "check": True, "tenant_bound_db": True,
    }
