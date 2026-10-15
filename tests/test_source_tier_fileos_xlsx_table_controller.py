"""Private XLSX operator contract and no-source-read check mode."""

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
from masterbrain import source_tier_fileos_xlsx_table_controller as control

REVIEW_ID = "stier_" + "a" * 32
IMAGE = "sha256:" + "b" * 64


def _private(path: Path, value: object) -> None:
    path.write_bytes(value if isinstance(value, bytes) else json.dumps(value).encode())
    path.chmod(0o600)


def _operator(tmp_path: Path) -> tuple[Path, dict[str, object], list[dict[str, object]]]:
    state = tmp_path / "private-state"
    root = tmp_path / "fictional-files"
    state.mkdir(mode=0o700)
    root.mkdir()
    (root / "statement.xlsx").write_bytes(b"fictional source not read by check")
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
        "document_image_id": IMAGE, "docker_binary": "/usr/bin/docker",
        "credentials_file": str(state / "credentials.json"),
        "token_file": str(state / "token"),
    }
    path = state / "xlsx-replay.json"
    _private(path, config)
    return path, config, credentials


def test_check_authenticates_without_selected_workbook_or_processor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    path, _, credentials = _operator(tmp_path)
    store = MagicMock()
    constructor = Mock(return_value=store)
    monkeypatch.setattr(control, "Store", constructor)
    replay = Mock(side_effect=AssertionError("check must not replay"))
    processor = Mock(side_effect=AssertionError("check must not construct processor"))
    monkeypatch.setattr(control, "SourceTierFileOSXlsxTableReplayStore", replay)
    monkeypatch.setattr(control, "DockerXlsxTableProcessor", processor)
    assert control.run_source_tier_fileos_xlsx_table_controller(
        path, "tenant-dsn", REVIEW_ID, check=True, tenant_bound_db=True,
    ) == {
        "configuration_valid": True, "execution_verified": False,
        "source_effects": False, "data_effects": False,
    }
    constructor.assert_called_once_with(
        "tenant-dsn", tenant_dsns={UUID(str(credentials[0]["tenant_id"])): "tenant-dsn"},
    )
    store.transaction.assert_called_once()
    replay.assert_not_called()
    processor.assert_not_called()


def test_execute_rechecks_identity_inside_reviewed_replay(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    path, config, _ = _operator(tmp_path)
    store = MagicMock()
    monkeypatch.setattr(control, "Store", Mock(return_value=store))
    processor = object()
    make_processor = Mock(return_value=processor)
    monkeypatch.setattr(control, "DockerXlsxTableProcessor", make_processor)
    calls: list[dict[str, object]] = []

    class Replay:
        def __init__(self, received_store: object, received_processor: object) -> None:
            assert received_store is store and received_processor is processor

        def record_current_xlsx_table_replay(self, ctx, review_id, root, *,
                                             expected_source_id, authorize):
            authorize()
            calls.append({
                "review_id": review_id, "root": root,
                "source_id": expected_source_id, "scopes": ctx.scopes,
            })
            return {
                "review_id": review_id, "worker_observed_xlsx_table_replay": True,
                "source_effects": False, "financial_claim_approved": False,
            }

    monkeypatch.setattr(control, "SourceTierFileOSXlsxTableReplayStore", Replay)
    result = control.run_source_tier_fileos_xlsx_table_controller(
        path, "tenant-dsn", REVIEW_ID, tenant_bound_db=True,
    )
    assert result["financial_claim_approved"] is False
    make_processor.assert_called_once_with(IMAGE, docker_binary=Path("/usr/bin/docker"))
    assert calls == [{
        "review_id": REVIEW_ID, "root": Path(str(config["root"])).resolve(),
        "source_id": "fictional_fileos",
        "scopes": frozenset({"brain.document.publish"}),
    }]


@pytest.mark.parametrize("field,value", [
    ("version", True), ("source_id", "../files"), ("root", "relative"),
    ("document_image_id", "latest"), ("docker_binary", "docker"),
    ("credentials_file", "relative"), ("unexpected", "bad"),
])
def test_bad_config_refused_before_database(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, field: str, value: object,
) -> None:
    path, config, _ = _operator(tmp_path)
    config[field] = value
    _private(path, config)
    constructor = Mock()
    monkeypatch.setattr(control, "Store", constructor)
    with pytest.raises(control.FileOSTierXlsxTableControllerError):
        control.run_source_tier_fileos_xlsx_table_controller(
            path, "tenant-dsn", REVIEW_ID, check=True, tenant_bound_db=True,
        )
    constructor.assert_not_called()


@pytest.mark.parametrize("scopes", [[], ["brain.source.ingest"], ["email.process"]])
def test_exact_worker_scope_required(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, scopes: list[str],
) -> None:
    path, _, credentials = _operator(tmp_path)
    credentials[0]["scopes"] = scopes
    _private(path.parent / "credentials.json", credentials)
    constructor = Mock()
    monkeypatch.setattr(control, "Store", constructor)
    with pytest.raises(control.FileOSTierXlsxTableControllerError):
        control.run_source_tier_fileos_xlsx_table_controller(
            path, "tenant-dsn", REVIEW_ID, check=True, tenant_bound_db=True,
        )
    constructor.assert_not_called()


def test_unbound_mode_refused_before_config_or_database(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    path, _, _ = _operator(tmp_path)
    constructor = Mock()
    monkeypatch.setattr(control, "Store", constructor)
    with pytest.raises(control.FileOSTierXlsxTableControllerError):
        control.run_source_tier_fileos_xlsx_table_controller(
            path, "shared-dsn", REVIEW_ID, check=True,
        )
    constructor.assert_not_called()


def test_cli_dispatches_exact_review_without_printing_dsn(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    dsn = "postgresql://secret:secret@example.invalid/private"
    monkeypatch.setenv("MASTERBRAIN_DSN", dsn)
    monkeypatch.setattr(
        cli, "run_source_tier_fileos_xlsx_table_controller",
        lambda path, received_dsn, review_id, **options: {
            "config": path == tmp_path / "private.json",
            "dsn": received_dsn == dsn,
            "review_id": review_id == REVIEW_ID,
            "check": options["check"],
            "tenant_bound_db": options["tenant_bound_db"],
        },
    )
    cli.main([
        "fileos", "replay-tier-xlsx-tables", "--config", str(tmp_path / "private.json"),
        "--review-id", REVIEW_ID, "--tenant-bound-db", "--check",
    ])
    output = capsys.readouterr().out
    assert dsn not in output
    assert json.loads(output) == {
        "config": True, "dsn": True, "review_id": True,
        "check": True, "tenant_bound_db": True,
    }
