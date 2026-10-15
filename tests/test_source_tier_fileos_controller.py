"""Private operator contract for one synthetic reviewed FileOS text replay."""

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
from masterbrain import source_tier_fileos_controller as control

REVIEW_ID = "stier_" + "a" * 32


def _private(path: Path, value: object) -> None:
    path.write_bytes(value if isinstance(value, bytes) else json.dumps(value).encode())
    path.chmod(0o600)


def _operator(tmp_path: Path) -> tuple[Path, dict[str, object], list[dict[str, object]]]:
    state = tmp_path / "private-state"
    root = tmp_path / "fictional-files"
    state.mkdir(mode=0o700)
    root.mkdir()
    (root / "source.txt").write_text("fictional source")
    token = secrets.token_urlsafe(40)
    _private(state / "token", token.encode())
    credentials: list[dict[str, object]] = [{
        "token_sha256": hashlib.sha256(token.encode()).hexdigest(),
        "tenant_id": str(uuid4()), "actor_id": str(uuid4()),
        "scopes": ["brain.document.publish"], "client_kind": "worker",
        "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
    }]
    _private(state / "credentials.json", credentials)
    config: dict[str, object] = {
        "version": 1, "source_id": "fictional_fileos", "root": str(root),
        "credentials_file": str(state / "credentials.json"),
        "token_file": str(state / "token"),
    }
    config_path = state / "tier-replay.json"
    _private(config_path, config)
    return config_path, config, credentials


def test_check_authenticates_document_only_worker_without_replay(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    path, _, credentials = _operator(tmp_path)
    store = MagicMock()
    constructor = Mock(return_value=store)
    monkeypatch.setattr(control, "Store", constructor)
    replay = Mock(side_effect=AssertionError("check must not replay a source"))
    monkeypatch.setattr(control, "SourceTierFileOSReplayStore", replay)
    result = control.run_source_tier_fileos_controller(
        path, "tenant-dsn", REVIEW_ID, check=True, tenant_bound_db=True,
    )
    assert result == {
        "configuration_valid": True, "execution_verified": False,
        "source_effects": False, "data_effects": False,
    }
    constructor.assert_called_once_with(
        "tenant-dsn", tenant_dsns={UUID(str(credentials[0]["tenant_id"])): "tenant-dsn"},
    )
    store.transaction.assert_called_once()
    replay.assert_not_called()


def test_execute_reauthenticates_inside_replay_and_scrubs_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    path, config, _ = _operator(tmp_path)
    store = MagicMock()
    monkeypatch.setattr(control, "Store", Mock(return_value=store))
    calls: list[dict[str, object]] = []

    class Replay:
        def __init__(self, received_store: object) -> None:
            assert received_store is store

        def record_current_text_replay(self, ctx, review_id, root, *,
                                       expected_source_id, authorize):
            authorize()
            calls.append({
                "review_id": review_id, "root": root,
                "source_id": expected_source_id, "scopes": ctx.scopes,
            })
            return {
                "review_id": review_id, "worker_observed_text_replay": True,
                "source_effects": False, "financial_claim_approved": False,
            }

    monkeypatch.setattr(control, "SourceTierFileOSReplayStore", Replay)
    result = control.run_source_tier_fileos_controller(
        path, "runtime-dsn", REVIEW_ID, tenant_bound_db=True,
    )
    assert result["financial_claim_approved"] is False
    assert calls == [{
        "review_id": REVIEW_ID, "root": Path(str(config["root"])).resolve(),
        "source_id": "fictional_fileos",
        "scopes": frozenset({"brain.document.publish"}),
    }]


@pytest.mark.parametrize("field,value", [
    ("version", True), ("source_id", "../files"), ("root", "relative"),
    ("credentials_file", "relative"), ("unexpected", "bad"),
])
def test_closed_config_fails_before_database(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, field: str, value: object,
) -> None:
    path, config, _ = _operator(tmp_path)
    config[field] = value
    _private(path, config)
    constructor = Mock()
    monkeypatch.setattr(control, "Store", constructor)
    with pytest.raises(control.FileOSTierReplayControllerError):
        control.run_source_tier_fileos_controller(
            path, "runtime-dsn", REVIEW_ID, check=True, tenant_bound_db=True,
        )
    constructor.assert_not_called()


@pytest.mark.parametrize("scopes", [[], ["brain.source.ingest"], ["email.process"]])
def test_document_only_scope_required(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, scopes: list[str],
) -> None:
    path, _, credentials = _operator(tmp_path)
    credentials[0]["scopes"] = scopes
    _private(path.parent / "credentials.json", credentials)
    constructor = Mock()
    monkeypatch.setattr(control, "Store", constructor)
    with pytest.raises(control.FileOSTierReplayControllerError):
        control.run_source_tier_fileos_controller(
            path, "runtime-dsn", REVIEW_ID, check=True, tenant_bound_db=True,
        )
    constructor.assert_not_called()


def test_unbound_mode_is_rejected_before_config_or_database(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    path, _, _ = _operator(tmp_path)
    constructor = Mock()
    monkeypatch.setattr(control, "Store", constructor)
    with pytest.raises(control.FileOSTierReplayControllerError):
        control.run_source_tier_fileos_controller(path, "shared-dsn", REVIEW_ID, check=True)
    constructor.assert_not_called()


def test_cli_dispatches_explicit_review_and_tenant_bound_mode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    dsn = "postgresql://secret:secret@example.invalid/private"
    monkeypatch.setenv("MASTERBRAIN_DSN", dsn)
    monkeypatch.setattr(
        cli, "run_source_tier_fileos_controller",
        lambda path, received_dsn, review_id, **options: {
            "config": path == tmp_path / "private.json",
            "dsn": received_dsn == dsn,
            "review_id": review_id == REVIEW_ID,
            "check": options["check"],
            "tenant_bound_db": options["tenant_bound_db"],
        },
    )
    cli.main([
        "fileos", "replay-tier-text", "--config", str(tmp_path / "private.json"),
        "--review-id", REVIEW_ID, "--tenant-bound-db", "--check",
    ])
    output = capsys.readouterr().out
    assert dsn not in output
    assert json.loads(output) == {
        "config": True, "dsn": True, "review_id": True,
        "check": True, "tenant_bound_db": True,
    }
