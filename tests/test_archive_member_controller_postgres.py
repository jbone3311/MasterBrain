"""Real tenant-enforced one-member archive text operator tests."""

from __future__ import annotations

import hashlib
import io
import json
import secrets
import zipfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, Mock
from uuid import UUID, uuid4

import pytest
import test_postgres as pg

from email_brain.domain.models import TenantContext
from masterbrain import archive_member_controller as controller
from masterbrain.archive_member_controller import (
    ArchiveMemberControllerError,
    run_archive_member_controller,
)
from masterbrain.datacore.archive_contract import source_for
from masterbrain.datacore.archive_member_contract import decode_result, encode_request
from masterbrain.datacore.archive_member_worker import process_request
from masterbrain.datacore.archive_worker import inventory_archive
from masterbrain.datacore.fileos import snapshot_tree
from masterbrain.datacore.persistence import DataCoreStore

database, tenant = pg.database, pg.tenant
pytestmark = pytest.mark.postgres


def private_write(path: Path, value: object) -> None:
    raw = value if isinstance(value, bytes) else json.dumps(value).encode()
    path.write_bytes(raw)
    path.chmod(0o600)


class LocalArchiveMemberProcessor:
    def __init__(self, image_id: str, *, docker_binary: Path) -> None:
        assert image_id == "sha256:" + "a" * 64
        assert docker_binary == Path("/usr/bin/false")

    def read(self, raw, *, source, target):
        return decode_result(process_request(encode_request(raw, source, target)), source, target)


def setup_operator(tmp_path: Path, ctx: TenantContext, store) -> tuple[Path, Path, str, str, bytes]:
    state, root = tmp_path / "state", tmp_path / "source"
    state.mkdir(mode=0o700)
    root.mkdir()
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("folder/proof.md", b"private operator archive proof")
        archive.writestr("sibling.txt", b"must remain unpublished")
    raw = output.getvalue()
    (root / "bundle.zip").write_bytes(raw)
    manifest = snapshot_tree(
        root,
        source_id="files_archive_operator",
        observed_at=datetime(2026, 9, 22, 18, tzinfo=UTC),
    )
    core = DataCoreStore(store)
    core.import_fileos_snapshot(pg.datacore_context(ctx), manifest, uuid4())
    item = manifest["items"][0]
    source = source_for(
        raw,
        item["version_id"],
        item["locator"],
        item["digest"]["value"],
        item["media_type"],
    )
    inventory = core.record_archive_inventory(
        pg.datacore_context(ctx), inventory_archive(raw, source), pg.ARCHIVE_PROCESSOR, uuid4()
    )
    token = secrets.token_urlsafe(40)
    credentials = [
        {
            "token_sha256": hashlib.sha256(token.encode()).hexdigest(),
            "tenant_id": str(ctx.tenant_id),
            "actor_id": str(ctx.actor_id),
            "scopes": ["brain.source.ingest", "brain.document.publish"],
            "client_kind": "worker",
            "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
        }
    ]
    private_write(state / "token", token.encode())
    private_write(state / "credentials.json", credentials)
    config = {
        "version": 1,
        "root": str(root),
        "archive_image_id": "sha256:" + "a" * 64,
        "docker_binary": "/usr/bin/false",
        "credentials_file": str(state / "credentials.json"),
        "token_file": str(state / "token"),
        "code_revision": "archive-operator-test-v1",
    }
    path = state / "archive-controller.json"
    private_write(path, config)
    return path, root, inventory.inventory_id, "folder/proof.md", raw


@pytest.mark.parametrize("selected_locator", ["folder/proof.md", "sibling.txt"])
def test_check_publish_replay_and_content_free_output(
    database: tuple[object, str],
    tenant: tuple[TenantContext, UUID],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    selected_locator: str,
) -> None:
    store, _ = database
    ctx, _ = tenant
    path, root, inventory_id, _, raw = setup_operator(tmp_path, ctx, store)
    locator = selected_locator
    monkeypatch.setattr(controller, "DockerArchiveMemberProcessor", LocalArchiveMemberProcessor)
    authorization_checks = 0
    authenticate_current = controller._current

    def count_authorization_checks(identity, initial):
        nonlocal authorization_checks
        authorization_checks += 1
        return authenticate_current(identity, initial)

    monkeypatch.setattr(controller, "_current", count_authorization_checks)
    before = (root.joinpath("bundle.zip").read_bytes(), root.joinpath("bundle.zip").stat())
    key = uuid4()
    check = run_archive_member_controller(path, store.dsn, inventory_id, locator, key, check=True)
    assert check == {
        "configuration_valid": True,
        "execution_verified": False,
        "source_effects": False,
    }
    first = run_archive_member_controller(path, store.dsn, inventory_id, locator, key)
    replay = run_archive_member_controller(path, store.dsn, inventory_id, locator, key)
    assert first["changed"] is True and replay == {**first, "changed": False}
    assert set(first) == {
        "inventory_id",
        "source_id",
        "item_id",
        "version_id",
        "evidence_id",
        "document_id",
        "chunks",
        "changed",
        "source_effects",
    }
    assert locator not in json.dumps(first) and "operator archive proof" not in json.dumps(first)
    assert root.joinpath("bundle.zip").read_bytes() == before[0] == raw
    assert root.joinpath("bundle.zip").stat().st_mtime_ns == before[1].st_mtime_ns
    assert authorization_checks == 9


def test_check_is_non_consuming_and_revocation_fails_closed(
    database: tuple[object, str],
    tenant: tuple[TenantContext, UUID],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, _ = database
    ctx, _ = tenant
    path, _, inventory_id, locator, _ = setup_operator(tmp_path, ctx, store)
    monkeypatch.setattr(controller, "DockerArchiveMemberProcessor", LocalArchiveMemberProcessor)
    key = uuid4()
    unknown_inventory = "archive_inventory_" + "f" * 32
    run_archive_member_controller(
        path, store.dsn, unknown_inventory, "absent/member.txt", key, check=True
    )
    with store.transaction(pg.datacore_context(ctx)) as conn:
        assert (
            conn.execute("SELECT count(*) AS n FROM brain_archive_member_text_receipts").fetchone()[
                "n"
            ]
            == 0
        )
    private_write(path.parent / "credentials.json", [])
    with pytest.raises(ArchiveMemberControllerError):
        run_archive_member_controller(path, store.dsn, inventory_id, locator, key)


def test_unsafe_selection_and_admin_dsn_are_generic(
    database: tuple[object, str],
    tenant: tuple[TenantContext, UUID],
    tmp_path: Path,
) -> None:
    store, admin = database
    ctx, _ = tenant
    path, _, inventory_id, locator, _ = setup_operator(tmp_path, ctx, store)
    with pytest.raises(ArchiveMemberControllerError, match="sensitive details suppressed"):
        run_archive_member_controller(path, store.dsn, inventory_id, "../secret.txt", uuid4())
    with pytest.raises(ArchiveMemberControllerError, match="sensitive details suppressed"):
        run_archive_member_controller(path, admin, inventory_id, locator, uuid4(), check=True)


def test_processor_fault_is_generic_and_publishes_nothing(
    database: tuple[object, str],
    tenant: tuple[TenantContext, UUID],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, _ = database
    ctx, _ = tenant
    path, _, inventory_id, locator, _ = setup_operator(tmp_path, ctx, store)
    processor = MagicMock()
    processor.return_value.read.side_effect = RuntimeError("sensitive processor fault")
    monkeypatch.setattr(controller, "DockerArchiveMemberProcessor", processor)
    with pytest.raises(
        ArchiveMemberControllerError, match="sensitive details suppressed"
    ) as caught:
        run_archive_member_controller(path, store.dsn, inventory_id, locator, uuid4())
    assert "processor fault" not in str(caught.value)
    with store.transaction(pg.datacore_context(ctx)) as conn:
        assert (
            conn.execute("SELECT count(*) AS n FROM brain_archive_member_text_receipts").fetchone()[
                "n"
            ]
            == 0
        )


def test_preview_pages_without_docker_source_or_receipt_effects(
    database: tuple[object, str],
    tenant: tuple[TenantContext, UUID],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, _ = database
    ctx, _ = tenant
    path, root, inventory_id, _, raw = setup_operator(tmp_path, ctx, store)
    processor = Mock(side_effect=AssertionError("preview must not construct Docker worker"))
    monkeypatch.setattr(controller, "DockerArchiveMemberProcessor", processor)
    before = root.joinpath("bundle.zip").stat()
    first = controller.run_archive_member_plan_controller(path, store.dsn, inventory_id, limit=1)
    assert first["operation"] == "archive_member_text_plan"
    assert first["eligible_members"] == 2
    assert first["next_cursor"] is not None
    second = controller.run_archive_member_plan_controller(
        path, store.dsn, inventory_id, after=first["next_cursor"], limit=1
    )
    assert second["next_cursor"] is None
    assert {row["member_locator"] for row in first["results"] + second["results"]} == {
        "folder/proof.md",
        "sibling.txt",
    }
    assert root.joinpath("bundle.zip").read_bytes() == raw
    assert root.joinpath("bundle.zip").stat().st_mtime_ns == before.st_mtime_ns
    processor.assert_not_called()
    with store.transaction(pg.datacore_context(ctx)) as conn:
        assert (
            conn.execute("SELECT count(*) AS n FROM brain_archive_member_text_receipts").fetchone()[
                "n"
            ]
            == 0
        )
