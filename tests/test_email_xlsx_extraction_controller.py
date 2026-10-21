"""Private XLSX extraction command keeps owner approval and worker authority separate."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, Mock
from uuid import UUID

import pytest
from test_email_xlsx_publication_controller import _operator, _private

from masterbrain import cli
from masterbrain import email_xlsx_extraction_controller as control

APPROVAL_ID = "xapp_" + "a" * 32
IMAGE = "sha256:" + "a" * 64


def _config(tmp_path: Path) -> tuple[Path, dict[str, object], list[dict[str, object]]]:
    path, config, credentials = _operator(tmp_path)
    config["document_image_id"] = IMAGE
    config["docker_binary"] = "/usr/bin/docker"
    credentials[0]["scopes"] = ["email.document.process", "email.evidence.read"]
    _private(path, config)
    _private(path.parent / "credentials.json", credentials)
    return path, config, credentials


def test_check_authenticates_and_checks_synthetic_account_without_selected_mime(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    path, config, credentials = _config(tmp_path)
    store = MagicMock()
    account_row = store.transaction.return_value.__enter__.return_value.execute.return_value
    account_row.fetchone.return_value = {
        "provider_account_id": None, "secret_ref": "synthetic:none",
    }
    constructor = Mock(return_value=store)
    monkeypatch.setattr(control, "Store", constructor)
    processor = Mock(side_effect=AssertionError("check must not run image"))
    monkeypatch.setattr(control, "DockerDocumentProcessor", processor)
    assert control.run_email_xlsx_extraction_controller(
        path, "tenant-dsn", APPROVAL_ID, check=True, tenant_bound_db=True,
    ) == {
        "configuration_valid": True, "execution_verified": False,
        "source_effects": False, "data_effects": False,
    }
    constructor.assert_called_once_with(
        "tenant-dsn", tenant_dsns={UUID(str(credentials[0]["tenant_id"])): "tenant-dsn"},
    )
    store.transaction.return_value.__enter__.return_value.execute.assert_called_once_with(
        "SELECT provider_account_id,secret_ref FROM mail_accounts "
        "WHERE id=%s AND status='active'", (UUID(str(config["account_id"])),),
    )
    processor.assert_not_called()


def test_execute_pins_account_and_rechecks_worker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    path, config, _ = _config(tmp_path)
    store = MagicMock()
    account_row = store.transaction.return_value.__enter__.return_value.execute.return_value
    account_row.fetchone.return_value = {
        "provider_account_id": None, "secret_ref": "synthetic:none",
    }
    monkeypatch.setattr(control, "Store", Mock(return_value=store))
    processor = object()
    image = Mock(return_value=processor)
    monkeypatch.setattr(control, "DockerDocumentProcessor", image)
    calls: list[object] = []

    class Results:
        def __init__(self, received_store: object, received_processor: object) -> None:
            assert received_store is store and received_processor is processor

        def record(self, ctx, approval_id, *, expected_account_id, authorize):
            authorize()
            calls.extend([ctx.scopes, approval_id, expected_account_id])
            return {"changed": True, "document_published": False, "mailbox_effects": False}

    monkeypatch.setattr(control, "EmailXlsxResults", Results)
    assert control.run_email_xlsx_extraction_controller(
        path, "tenant-dsn", APPROVAL_ID, tenant_bound_db=True,
    ) == {"changed": True, "document_published": False, "mailbox_effects": False}
    image.assert_called_once_with(IMAGE, docker_binary=Path("/usr/bin/docker"))
    assert calls == [
        frozenset({"email.document.process", "email.evidence.read"}),
        APPROVAL_ID, UUID(str(config["account_id"])),
    ]


@pytest.mark.parametrize("field,value", [
    ("document_image_id", "sha256:wrong"), ("docker_binary", "relative"),
    ("blob_root", "relative"), ("unexpected", "bad"),
])
def test_bad_config_refused_before_database(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, field: str, value: object,
) -> None:
    path, config, _ = _config(tmp_path)
    config[field] = value
    _private(path, config)
    constructor = Mock()
    monkeypatch.setattr(control, "Store", constructor)
    with pytest.raises(control.EmailXlsxExtractionControllerError):
        control.run_email_xlsx_extraction_controller(
            path, "tenant-dsn", APPROVAL_ID, check=True, tenant_bound_db=True,
        )
    constructor.assert_not_called()


@pytest.mark.parametrize("scopes,kind", [
    (["email.document.process"], "worker"),
    (["email.document.process", "email.evidence.read"], "human"),
    (["email.document.process", "email.evidence.read", "brain.document.publish"], "worker"),
])
def test_exact_worker_scope_required(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, scopes: list[str], kind: str,
) -> None:
    path, _, credentials = _config(tmp_path)
    credentials[0]["scopes"] = scopes
    credentials[0]["client_kind"] = kind
    _private(path.parent / "credentials.json", credentials)
    constructor = Mock()
    monkeypatch.setattr(control, "Store", constructor)
    with pytest.raises(control.EmailXlsxExtractionControllerError):
        control.run_email_xlsx_extraction_controller(
            path, "tenant-dsn", APPROVAL_ID, check=True, tenant_bound_db=True,
        )
    constructor.assert_not_called()


def test_unbound_malformed_or_live_account_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    path, _, _ = _config(tmp_path)
    constructor = Mock()
    monkeypatch.setattr(control, "Store", constructor)
    for approval_id, bound in ((APPROVAL_ID, False), ("xapp_bad", True)):
        with pytest.raises(control.EmailXlsxExtractionControllerError):
            control.run_email_xlsx_extraction_controller(
                path, "tenant-dsn", approval_id, check=True, tenant_bound_db=bound,
            )
    constructor.assert_not_called()
    store = MagicMock()
    account_row = store.transaction.return_value.__enter__.return_value.execute.return_value
    account_row.fetchone.return_value = {
        "provider_account_id": "live-provider", "secret_ref": "synthetic:none",
    }
    monkeypatch.setattr(control, "Store", Mock(return_value=store))
    with pytest.raises(control.EmailXlsxExtractionControllerError):
        control.run_email_xlsx_extraction_controller(
            path, "tenant-dsn", APPROVAL_ID, check=True, tenant_bound_db=True,
        )


def test_cli_exposes_exact_command() -> None:
    args = cli.build_parser().parse_args([
        "email", "extract-approved-xlsx", "--config", "/private/xlsx.json",
        "--approval-id", APPROVAL_ID, "--tenant-bound-db", "--check",
    ])
    assert args.email_command == "extract-approved-xlsx" and args.tenant_bound_db is True
