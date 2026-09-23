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
from email_brain.store import Conflict, NotFound
from email_brain.synthetic_formats import docx_bytes, pdf_bytes, xlsx_bytes
from masterbrain import archive_member_controller as controller
from masterbrain.archive_member_controller import (
    ArchiveMemberControllerError,
    run_archive_member_controller,
    run_archive_member_document_controller,
)
from masterbrain.datacore.archive_contract import source_for
from masterbrain.datacore.archive_member_contract import decode_result, encode_request
from masterbrain.datacore.archive_member_document import (
    extract_archive_member_document,
    publish_extracted_archive_member_document,
)
from masterbrain.datacore.archive_member_worker import process_request
from masterbrain.datacore.archive_worker import inventory_archive
from masterbrain.datacore.document_contract import CONTRACT
from masterbrain.datacore.document_contract import source_for as document_source_for
from masterbrain.datacore.document_worker import extract_document
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


class LocalDocumentProcessor:
    processor_version = CONTRACT + "-synthetic-postgres"

    def __init__(self, image_id: str | None = None, *, docker_binary: Path | None = None) -> None:
        if image_id is not None:
            assert image_id == "sha256:" + "b" * 64
            assert docker_binary == Path("/usr/bin/false")

    def extract(self, raw, *, version_id, locator, sha256, media_type):
        return extract_document(
            raw, document_source_for(raw, version_id, locator, sha256, media_type)
        )


def setup_operator(
    tmp_path: Path,
    ctx: TenantContext,
    store,
    *,
    extra_members: dict[str, bytes] | None = None,
) -> tuple[Path, Path, str, str, bytes]:
    state, root = tmp_path / "state", tmp_path / "source"
    state.mkdir(mode=0o700)
    root.mkdir()
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("folder/proof.md", b"private operator archive proof")
        archive.writestr("sibling.txt", b"must remain unpublished")
        for name, content in (extra_members or {}).items():
            archive.writestr(name, content)
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
        "document_image_id": "sha256:" + "b" * 64,
        "docker_binary": "/usr/bin/false",
        "credentials_file": str(state / "credentials.json"),
        "token_file": str(state / "token"),
        "code_revision": "archive-operator-test-v1",
    }
    path = state / "archive-controller.json"
    private_write(path, config)
    return path, root, inventory.inventory_id, "folder/proof.md", raw


def test_document_selector_is_distinct_and_allows_only_pdf_or_opaque_ooxml(
    database: tuple[object, str],
    tenant: tuple[TenantContext, UUID],
    tmp_path: Path,
) -> None:
    store, _ = database
    ctx, _ = tenant
    _, _, inventory_id, _, _ = setup_operator(
        tmp_path,
        ctx,
        store,
        extra_members={
            "documents/report.pdf": pdf_bytes(("selector pdf proof",)),
            "documents/memo.docx": docx_bytes("selector word proof"),
        },
    )
    core = DataCoreStore(store)
    datacore = pg.datacore_context(ctx)
    pdf = core.archive_document_member_target(datacore, inventory_id, "documents/report.pdf")
    word = core.archive_document_member_target(datacore, inventory_id, "documents/memo.docx")
    assert pdf.member_media_type == "application/pdf"
    assert word.member_media_type.endswith("wordprocessingml.document")
    with pytest.raises(ValueError):
        core.archive_document_member_target(datacore, inventory_id, "folder/proof.md")
    with pytest.raises(NotFound):
        core.archive_member_target(datacore, inventory_id, "documents/memo.docx")


def test_archive_document_publication_is_replayable_and_retains_no_member_bytes(
    database: tuple[object, str],
    tenant: tuple[TenantContext, UUID],
    tmp_path: Path,
) -> None:
    store, _ = database
    ctx, _ = tenant
    path, root, inventory_id, _, raw = setup_operator(
        tmp_path,
        ctx,
        store,
        extra_members={"documents/memo.docx": docx_bytes("archived document proof")},
    )
    core = DataCoreStore(store)
    datacore = pg.datacore_context(ctx)
    target = core.archive_document_member_target(datacore, inventory_id, "documents/memo.docx")
    extraction = extract_archive_member_document(
        root,
        target,
        LocalArchiveMemberProcessor("sha256:" + "a" * 64, docker_binary=Path("/usr/bin/false")),
        LocalDocumentProcessor(),
    )
    key = uuid4()
    first = publish_extracted_archive_member_document(
        core,
        datacore,
        target,
        extraction,
        code_revision="archive-document-test-v1",
        idempotency_key=key,
    )
    replay = publish_extracted_archive_member_document(
        core,
        datacore,
        target,
        extraction,
        code_revision="archive-document-test-v1",
        idempotency_key=key,
    )
    assert first.changed is True and replay.changed is False
    assert first.document_id == replay.document_id and first.chunks > 0
    assert (root / "bundle.zip").read_bytes() == raw
    with store.transaction(datacore) as conn:
        receipt = conn.execute(
            "SELECT document_format,document_processor,chunk_count FROM "
            "brain_archive_member_document_receipts"
        ).fetchone()
        assert receipt == {
            "document_format": "docx",
            "document_processor": CONTRACT + "-synthetic-postgres",
            "chunk_count": first.chunks,
        }
        assert (
            conn.execute(
                "SELECT body FROM brain_normalized_documents WHERE id=%s", (first.document_id,)
            ).fetchone()["body"]
            == "archived document proof"
        )
        assert (
            conn.execute(
                "SELECT count(*) AS n FROM brain_provenance_inputs p JOIN brain_provenance v "
                "ON v.tenant_id=p.tenant_id AND v.id=p.provenance_id "
                "WHERE v.output_id=%s",
                (first.document_id,),
            ).fetchone()["n"]
            == 2
        )


def test_archive_document_private_command_checks_publishes_and_replays(
    database: tuple[object, str],
    tenant: tuple[TenantContext, UUID],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, _ = database
    ctx, _ = tenant
    locator = "documents/report.pdf"
    path, root, inventory_id, _, raw = setup_operator(
        tmp_path,
        ctx,
        store,
        extra_members={locator: pdf_bytes(("archived pdf operator proof",))},
    )
    monkeypatch.setattr(controller, "DockerArchiveMemberProcessor", LocalArchiveMemberProcessor)
    monkeypatch.setattr(controller, "DockerDocumentProcessor", LocalDocumentProcessor)
    key = uuid4()

    checked = run_archive_member_document_controller(
        path, store.dsn, inventory_id, locator, key, check=True
    )
    assert checked == {
        "configuration_valid": True,
        "execution_verified": False,
        "operation": "archive_member_document",
        "source_effects": False,
        "data_effects": False,
    }
    first = run_archive_member_document_controller(path, store.dsn, inventory_id, locator, key)
    replay = run_archive_member_document_controller(path, store.dsn, inventory_id, locator, key)

    assert first["changed"] is True and replay == {**first, "changed": False}
    assert first["operation"] == "archive_member_document"
    assert first["format"] == "pdf"
    assert first["metadata_counts"]["page_count"] == 1
    assert first["chunks"] > 0 and first["source_effects"] is False
    serialized = json.dumps(first) + json.dumps(replay)
    assert locator not in serialized and "archived pdf operator proof" not in serialized
    assert (root / "bundle.zip").read_bytes() == raw
    with store.transaction(pg.datacore_context(ctx)) as conn:
        assert (
            conn.execute(
                "SELECT count(*) AS n FROM brain_archive_member_document_receipts"
            ).fetchone()["n"]
            == 1
        )


def batch_plan(
    path: Path, inventory_id: str
) -> tuple[Path, list[controller.ArchiveMemberBatchItem]]:
    items = [
        controller.ArchiveMemberBatchItem(member_locator=locator, idempotency_key=uuid4())
        for locator in ("folder/proof.md", "sibling.txt")
    ]
    payload = {
        "version": 1,
        "inventory_id": inventory_id,
        "code_revision": "archive-operator-test-v1",
        "items": [
            {
                "member_locator": item.member_locator,
                "idempotency_key": str(item.idempotency_key),
            }
            for item in items
        ],
        "plan_sha256": controller.archive_member_batch_sha256(
            1, inventory_id, "archive-operator-test-v1", items
        ),
    }
    plan = path.parent / "archive-batch.json"
    private_write(plan, payload)
    return plan, items


def document_batch_plan(
    path: Path, inventory_id: str
) -> tuple[Path, list[controller.ArchiveDocumentBatchItem]]:
    items = [
        controller.ArchiveDocumentBatchItem(
            member_locator=locator, document_format=document_format, idempotency_key=uuid4()
        )
        for locator, document_format in (
            ("documents/report.pdf", "pdf"),
            ("documents/memo.docx", "docx"),
            ("documents/sheet.xlsx", "xlsx"),
        )
    ]
    payload = {
        "version": 1,
        "inventory_id": inventory_id,
        "code_revision": "archive-operator-test-v1",
        "items": [
            {
                "member_locator": item.member_locator,
                "document_format": item.document_format,
                "idempotency_key": str(item.idempotency_key),
            }
            for item in items
        ],
        "plan_sha256": controller.archive_document_batch_sha256(
            1, inventory_id, "archive-operator-test-v1", items
        ),
    }
    plan = path.parent / "archive-document-batch.json"
    private_write(plan, payload)
    return plan, items


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


def test_batch_publishes_exact_plan_and_replays_with_content_free_output(
    database: tuple[object, str],
    tenant: tuple[TenantContext, UUID],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, _ = database
    ctx, _ = tenant
    path, root, inventory_id, _, raw = setup_operator(tmp_path, ctx, store)
    plan, items = batch_plan(path, inventory_id)
    monkeypatch.setattr(controller, "DockerArchiveMemberProcessor", LocalArchiveMemberProcessor)
    before = root.joinpath("bundle.zip").stat()
    checked = controller.run_archive_member_batch_controller(path, plan, store.dsn, check=True)
    assert checked["requested"] == 2 and checked["data_effects"] is False
    first = controller.run_archive_member_batch_controller(path, plan, store.dsn)
    replay = controller.run_archive_member_batch_controller(path, plan, store.dsn)
    assert first["complete"] is True and first["recorded"] == 2
    assert replay["complete"] is True and replay["replayed"] == 2
    assert first["results"] == [
        {"item_index": 0, "recorded": True},
        {"item_index": 1, "recorded": True},
    ]
    serialized = json.dumps(first) + json.dumps(replay)
    assert all(item.member_locator not in serialized for item in items)
    assert "private operator archive proof" not in serialized
    assert root.joinpath("bundle.zip").read_bytes() == raw
    assert root.joinpath("bundle.zip").stat().st_mtime_ns == before.st_mtime_ns
    with store.transaction(pg.datacore_context(ctx)) as conn:
        assert (
            conn.execute("SELECT count(*) AS n FROM brain_archive_member_text_receipts").fetchone()[
                "n"
            ]
            == 2
        )


def test_document_batch_fail_stop_exact_retry_and_content_free_output(
    database: tuple[object, str],
    tenant: tuple[TenantContext, UUID],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, _ = database
    ctx, _ = tenant
    path, root, inventory_id, _, raw = setup_operator(
        tmp_path,
        ctx,
        store,
        extra_members={
            "documents/report.pdf": pdf_bytes(("batch pdf proof",)),
            "documents/memo.docx": docx_bytes("batch word proof"),
            "documents/sheet.xlsx": xlsx_bytes("Batch", 1, 1, "batchsheetproof"),
        },
    )
    plan, items = document_batch_plan(path, inventory_id)
    monkeypatch.setattr(controller, "DockerArchiveMemberProcessor", LocalArchiveMemberProcessor)
    monkeypatch.setattr(controller, "DockerDocumentProcessor", LocalDocumentProcessor)
    before = root.joinpath("bundle.zip").stat()
    checked = controller.run_archive_document_batch_controller(path, plan, store.dsn, check=True)
    assert checked["requested"] == 3 and checked["data_effects"] is False

    publish = controller.publish_extracted_archive_member_document
    calls = 0

    def refuse_second(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise Conflict("synthetic document refusal")
        return publish(*args, **kwargs)

    monkeypatch.setattr(controller, "publish_extracted_archive_member_document", refuse_second)
    stopped = controller.run_archive_document_batch_controller(path, plan, store.dsn)
    assert stopped["complete"] is False and stopped["failed_item_index"] == 1
    assert stopped["completed"] == 1 and stopped["recorded"] == 1
    with store.transaction(pg.datacore_context(ctx)) as conn:
        assert (
            conn.execute(
                "SELECT count(*) AS n FROM brain_archive_member_document_receipts "
                "WHERE inventory_id=%s",
                (inventory_id,),
            ).fetchone()["n"]
            == 1
        )

    monkeypatch.setattr(controller, "publish_extracted_archive_member_document", publish)
    completed = controller.run_archive_document_batch_controller(path, plan, store.dsn)
    replay = controller.run_archive_document_batch_controller(path, plan, store.dsn)
    assert completed["complete"] is True
    assert completed["recorded"] == 2 and completed["replayed"] == 1
    assert replay["complete"] is True and replay["replayed"] == 3
    assert [row["item_index"] for row in completed["results"]] == [0, 1, 2]
    serialized = json.dumps(stopped) + json.dumps(completed) + json.dumps(replay)
    assert all(item.member_locator not in serialized for item in items)
    assert not any(item.document_format in serialized for item in items)
    assert "batch pdf proof" not in serialized and "batch word proof" not in serialized
    assert root.joinpath("bundle.zip").read_bytes() == raw
    assert root.joinpath("bundle.zip").stat().st_mtime_ns == before.st_mtime_ns
    with store.transaction(pg.datacore_context(ctx)) as conn:
        assert (
            conn.execute(
                "SELECT count(*) AS n FROM brain_archive_member_document_receipts "
                "WHERE inventory_id=%s",
                (inventory_id,),
            ).fetchone()["n"]
            == 3
        )
