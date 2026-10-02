"""Private archive-member operator contract without PostgreSQL or Docker."""

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

from masterbrain import archive_member_controller as control
from masterbrain.datacore.extraction import ExtractionStatus


def private_write(path: Path, value: object) -> None:
    raw = value if isinstance(value, bytes) else json.dumps(value).encode()
    path.write_bytes(raw)
    path.chmod(0o600)


def controller_files(
    tmp_path: Path,
) -> tuple[Path, dict[str, object], list[dict[str, object]]]:
    state, root = tmp_path / "state", tmp_path / "source"
    state.mkdir(mode=0o700)
    root.mkdir()
    token = secrets.token_urlsafe(40)
    private_write(state / "token", token.encode())
    credentials: list[dict[str, object]] = [
        {
            "token_sha256": hashlib.sha256(token.encode()).hexdigest(),
            "tenant_id": str(uuid4()),
            "actor_id": str(uuid4()),
            "scopes": ["brain.source.ingest", "brain.document.publish"],
            "client_kind": "worker",
            "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
        }
    ]
    private_write(state / "credentials.json", credentials)
    config: dict[str, object] = {
        "version": 1,
        "root": str(root),
        "archive_image_id": "sha256:" + "a" * 64,
        "docker_binary": "/usr/bin/false",
        "credentials_file": str(state / "credentials.json"),
        "token_file": str(state / "token"),
        "code_revision": "unit-archive-controller-v1",
    }
    path = state / "archive-controller.json"
    private_write(path, config)
    return path, config, credentials


def test_every_archive_operator_can_bind_authenticated_tenant(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path, config, credentials = controller_files(tmp_path)
    config["document_image_id"] = "sha256:" + "b" * 64
    config["image_ocr_image_id"] = "sha256:" + "c" * 64
    private_write(path, config)
    text_plan, _, _ = batch_plan_file(tmp_path)
    document_plan, _, _ = document_batch_plan_file(tmp_path)
    inventory = "archive_inventory_" + "f" * 32
    factory = Mock(return_value=MagicMock())
    monkeypatch.setattr(control, "Store", factory)
    operations = (
        (control.run_archive_member_controller, (path, "runtime-dsn", inventory, "a.txt", uuid4())),
        (control.run_archive_member_plan_controller, (path, "runtime-dsn", inventory)),
        (control.run_archive_document_plan_controller, (path, "runtime-dsn", inventory)),
        (
            control.run_archive_member_document_controller,
            (path, "runtime-dsn", inventory, "a.pdf", uuid4()),
        ),
        (
            control.run_archive_member_image_ocr_controller,
            (path, "runtime-dsn", inventory, "a.png", uuid4()),
        ),
        (control.run_archive_member_batch_controller, (path, text_plan, "runtime-dsn")),
        (control.run_archive_document_batch_controller, (path, document_plan, "runtime-dsn")),
    )
    expected_tenant = UUID(str(credentials[0]["tenant_id"]))
    for operation, args in operations:
        factory.reset_mock()
        result = operation(*args, check=True, tenant_bound_db=True)
        assert result["configuration_valid"] is True
        factory.assert_called_once_with(
            "runtime-dsn", tenant_dsns={expected_tenant: "runtime-dsn"}
        )
    factory.reset_mock()
    with pytest.raises(control.ArchiveMemberControllerError):
        control.run_archive_member_plan_controller(
            path, "runtime-dsn", inventory, check=True,
            tenant_bound_db=1,  # type: ignore[arg-type]
        )
    factory.assert_not_called()


def batch_plan_file(
    tmp_path: Path, *, code_revision: str = "unit-archive-controller-v1"
) -> tuple[Path, str, list[control.ArchiveMemberBatchItem]]:
    inventory = "archive_inventory_" + "b" * 32
    items = [
        control.ArchiveMemberBatchItem(member_locator=locator, idempotency_key=uuid4())
        for locator in ("a.txt", "nested/b.md", "final.csv")
    ]
    payload = {
        "version": 1,
        "inventory_id": inventory,
        "code_revision": code_revision,
        "items": [
            {
                "member_locator": item.member_locator,
                "idempotency_key": str(item.idempotency_key),
            }
            for item in items
        ],
        "plan_sha256": control.archive_member_batch_sha256(1, inventory, code_revision, items),
    }
    path = tmp_path / "state" / "archive-batch.json"
    private_write(path, payload)
    return path, inventory, items


def document_batch_plan_file(
    tmp_path: Path, *, code_revision: str = "unit-archive-controller-v1"
) -> tuple[Path, str, list[control.ArchiveDocumentBatchItem]]:
    inventory = "archive_inventory_" + "d" * 32
    items = [
        control.ArchiveDocumentBatchItem(
            member_locator=locator, document_format=document_format, idempotency_key=uuid4()
        )
        for locator, document_format in (
            ("a.pdf", "pdf"),
            ("nested/b.docx", "docx"),
            ("final.xlsx", "xlsx"),
        )
    ]
    payload = {
        "version": 1,
        "inventory_id": inventory,
        "code_revision": code_revision,
        "items": [
            {
                "member_locator": item.member_locator,
                "document_format": item.document_format,
                "idempotency_key": str(item.idempotency_key),
            }
            for item in items
        ],
        "plan_sha256": control.archive_document_batch_sha256(1, inventory, code_revision, items),
    }
    path = tmp_path / "state" / "archive-document-batch.json"
    private_write(path, payload)
    return path, inventory, items


def test_check_preflights_without_target_query_or_worker_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path, _, _ = controller_files(tmp_path)
    store = MagicMock()
    processor = MagicMock()
    monkeypatch.setattr(control, "Store", Mock(return_value=store))
    monkeypatch.setattr(control, "DockerArchiveMemberProcessor", processor)
    core = Mock(side_effect=AssertionError("check must not query an archive target"))
    monkeypatch.setattr(control, "DataCoreStore", core)
    result = control.run_archive_member_controller(
        path,
        "runtime-dsn",
        "archive_inventory_" + "f" * 32,
        "not/queried.txt",
        uuid4(),
        check=True,
    )
    assert result == {
        "configuration_valid": True,
        "execution_verified": False,
        "source_effects": False,
    }
    store.transaction.assert_called_once()
    processor.assert_called_once()
    processor.return_value.read.assert_not_called()
    core.assert_not_called()


def test_preview_check_is_non_consuming_and_normal_run_is_exact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path, _, _ = controller_files(tmp_path)
    store = MagicMock()
    processor = Mock(side_effect=AssertionError("preview must not construct Docker worker"))
    monkeypatch.setattr(control, "Store", Mock(return_value=store))
    monkeypatch.setattr(control, "DockerArchiveMemberProcessor", processor)
    core = MagicMock()
    monkeypatch.setattr(control, "DataCoreStore", Mock(return_value=core))
    inventory = "archive_inventory_" + "a" * 32
    checked = control.run_archive_member_plan_controller(
        path, "runtime-dsn", inventory, after=3, limit=7, check=True
    )
    assert checked == {
        "configuration_valid": True,
        "execution_verified": False,
        "operation": "archive_member_text_plan",
        "source_effects": False,
        "data_effects": False,
    }
    core.archive_member_text_plan.assert_not_called()
    processor.assert_not_called()
    core.archive_member_text_plan.return_value = {
        "inventory_id": inventory,
        "eligible_members": 1,
        "results": [
            {
                "ordinal": 4,
                "member_locator": "folder/proof.md",
                "size_bytes": 5,
                "media_type": "text/markdown",
                "depth": 0,
                "already_published": False,
            }
        ],
        "next_cursor": None,
        "limit": 7,
        "untrusted_metadata": True,
        "source_effects": False,
        "data_effects": False,
    }
    result = control.run_archive_member_plan_controller(
        path, "runtime-dsn", inventory, after=3, limit=7
    )
    assert result["operation"] == "archive_member_text_plan"
    assert result["untrusted_metadata"] is True
    assert result["source_effects"] is False and result["data_effects"] is False
    core.archive_member_text_plan.assert_called_once_with(ANY, inventory, after=3, limit=7)
    processor.assert_not_called()


def test_archive_document_check_constructs_neither_worker_or_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path, config, _ = controller_files(tmp_path)
    config["document_image_id"] = "sha256:" + "b" * 64
    private_write(path, config)
    store = MagicMock()
    monkeypatch.setattr(control, "Store", Mock(return_value=store))
    archive = Mock(side_effect=AssertionError("check must not construct archive worker"))
    document = Mock(side_effect=AssertionError("check must not construct document worker"))
    core = Mock(side_effect=AssertionError("check must not inspect target"))
    monkeypatch.setattr(control, "DockerArchiveMemberProcessor", archive)
    monkeypatch.setattr(control, "DockerDocumentProcessor", document)
    monkeypatch.setattr(control, "DataCoreStore", core)
    result = control.run_archive_member_document_controller(
        path,
        "runtime-dsn",
        "archive_inventory_" + "d" * 32,
        "documents/proof.pdf",
        uuid4(),
        check=True,
    )
    assert result["operation"] == "archive_member_document"
    assert result["data_effects"] is False and result["source_effects"] is False
    archive.assert_not_called()
    document.assert_not_called()
    core.assert_not_called()


def test_archive_document_preview_is_non_consuming_and_exact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path, config, _ = controller_files(tmp_path)
    config["document_image_id"] = "sha256:" + "b" * 64
    private_write(path, config)
    store = MagicMock()
    monkeypatch.setattr(control, "Store", Mock(return_value=store))
    archive = Mock(side_effect=AssertionError("preview must not construct archive worker"))
    document = Mock(side_effect=AssertionError("preview must not construct document worker"))
    monkeypatch.setattr(control, "DockerArchiveMemberProcessor", archive)
    monkeypatch.setattr(control, "DockerDocumentProcessor", document)
    core = MagicMock()
    monkeypatch.setattr(control, "DataCoreStore", Mock(return_value=core))
    inventory = "archive_inventory_" + "e" * 32
    checked = control.run_archive_document_plan_controller(
        path, "runtime-dsn", inventory, after=4, limit=7, check=True
    )
    assert checked == {
        "configuration_valid": True,
        "execution_verified": False,
        "operation": "archive_member_document_plan",
        "source_effects": False,
        "worker_effects": False,
        "data_effects": False,
    }
    core.archive_member_document_plan.assert_not_called()
    archive.assert_not_called()
    document.assert_not_called()
    core.archive_member_document_plan.return_value = {
        "inventory_id": inventory,
        "eligible_members": 1,
        "results": [],
        "next_cursor": None,
        "limit": 7,
        "untrusted_metadata": True,
        "source_effects": False,
        "worker_effects": False,
        "data_effects": False,
    }
    result = control.run_archive_document_plan_controller(
        path, "runtime-dsn", inventory, after=4, limit=7
    )
    assert result["operation"] == "archive_member_document_plan"
    assert result["worker_effects"] is False
    core.archive_member_document_plan.assert_called_once_with(ANY, inventory, after=4, limit=7)
    archive.assert_not_called()
    document.assert_not_called()


def test_archive_document_runs_exact_target_and_content_free_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path, config, _ = controller_files(tmp_path)
    config["document_image_id"] = "sha256:" + "b" * 64
    private_write(path, config)
    monkeypatch.setattr(control, "Store", Mock(return_value=MagicMock()))
    core = MagicMock()
    target = SimpleNamespace()
    core.archive_document_member_target.return_value = target
    monkeypatch.setattr(control, "DataCoreStore", Mock(return_value=core))
    archive = MagicMock()
    document = MagicMock()
    monkeypatch.setattr(control, "DockerArchiveMemberProcessor", archive)
    monkeypatch.setattr(control, "DockerDocumentProcessor", document)
    extraction = SimpleNamespace(
        status=ExtractionStatus.EXTRACTED,
        metadata={"format": "pdf", "page_count": 2, "title": "must not escape"},
    )
    monkeypatch.setattr(control, "extract_archive_member_document", Mock(return_value=extraction))
    published = SimpleNamespace(
        inventory_id="archive_inventory_" + "d" * 32,
        source_id="files",
        item_id="archiveitem_opaque",
        version_id="archiveversion_opaque",
        evidence_id="evidence_opaque",
        document_id="document_opaque",
        chunks=3,
        changed=True,
    )
    publish = Mock(return_value=published)
    monkeypatch.setattr(control, "publish_extracted_archive_member_document", publish)
    key = uuid4()
    result = control.run_archive_member_document_controller(
        path,
        "runtime-dsn",
        published.inventory_id,
        "documents/proof.pdf",
        key,
    )
    core.archive_document_member_target.assert_called_once_with(
        ANY, published.inventory_id, "documents/proof.pdf"
    )
    publish.assert_called_once_with(
        core,
        ANY,
        target,
        extraction,
        code_revision="unit-archive-controller-v1",
        idempotency_key=key,
    )
    assert result["metadata_counts"] == {"page_count": 2}
    assert "title" not in json.dumps(result) and "member_locator" not in result


def image_controller_file(tmp_path: Path) -> Path:
    path, config, _ = controller_files(tmp_path)
    config["image_ocr_image_id"] = "sha256:" + "c" * 64
    private_write(path, config)
    return path


def test_archive_image_check_is_non_consuming_and_requires_both_images(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = image_controller_file(tmp_path)
    monkeypatch.setattr(control, "Store", Mock(return_value=MagicMock()))
    core = Mock(side_effect=AssertionError("check inspected a member"))
    archive = Mock(side_effect=AssertionError("check constructed archive worker"))
    image = Mock(side_effect=AssertionError("check constructed image worker"))
    monkeypatch.setattr(control, "DataCoreStore", core)
    monkeypatch.setattr(control, "DockerArchiveMemberProcessor", archive)
    monkeypatch.setattr(control, "DockerImageOcrProcessor", image)
    checked = control.run_archive_member_image_ocr_controller(
        path, "runtime-dsn", "archive_inventory_" + "d" * 32, "images/proof.png", uuid4(),
        check=True,
    )
    assert checked == {
        "configuration_valid": True,
        "execution_verified": False,
        "operation": "archive_member_image_ocr",
        "source_effects": False,
        "data_effects": False,
    }
    core.assert_not_called()
    archive.assert_not_called()
    image.assert_not_called()

    config = json.loads(path.read_text())
    del config["image_ocr_image_id"]
    private_write(path, config)
    with pytest.raises(control.ArchiveMemberControllerError):
        control.run_archive_member_image_ocr_controller(
            path, "runtime-dsn", "archive_inventory_" + "d" * 32,
            "images/proof.png", uuid4(), check=True,
        )


@pytest.mark.parametrize("scopes", [[], ["brain.source.ingest"], ["brain.search"]])
def test_archive_image_requires_exact_publication_scopes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, scopes: list[str]
) -> None:
    path = image_controller_file(tmp_path)
    credentials = json.loads((path.parent / "credentials.json").read_text())
    credentials[0]["scopes"] = scopes
    private_write(path.parent / "credentials.json", credentials)
    store = Mock()
    monkeypatch.setattr(control, "Store", store)
    with pytest.raises(control.ArchiveMemberControllerError):
        control.run_archive_member_image_ocr_controller(
            path, "runtime-dsn", "archive_inventory_" + "d" * 32,
            "images/proof.png", uuid4(), check=True,
        )
    store.assert_not_called()


def test_archive_image_publishes_exact_member_and_scrubs_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = image_controller_file(tmp_path)
    monkeypatch.setattr(control, "Store", Mock(return_value=MagicMock()))
    core = MagicMock()
    target = SimpleNamespace(member_locator="images/private-proof.png")
    core.archive_member_target.return_value = target
    monkeypatch.setattr(control, "DataCoreStore", Mock(return_value=core))
    archive = MagicMock()
    image = MagicMock()
    monkeypatch.setattr(control, "DockerArchiveMemberProcessor", archive)
    monkeypatch.setattr(control, "DockerImageOcrProcessor", image)
    extraction = SimpleNamespace(
        status=ExtractionStatus.EXTRACTED,
        metadata={
            "format": "png", "width": 240, "height": 90, "frame_count": 1,
            "image_reason": "bounded_image_ocr_v1", "private_note": "secret evidence text",
        },
        text="secret evidence text",
    )
    extract = Mock(return_value=extraction)
    monkeypatch.setattr(control, "extract_archive_member_image_ocr", extract)
    published = SimpleNamespace(
        inventory_id="archive_inventory_" + "d" * 32,
        source_id="files", item_id="archiveitem_opaque", version_id="archiveversion_opaque",
        evidence_id="evidence_opaque", document_id="document_opaque", chunks=1, changed=True,
    )
    replayed = SimpleNamespace(**{**vars(published), "changed": False})
    publish = Mock(side_effect=[published, replayed])
    monkeypatch.setattr(control, "publish_extracted_archive_member_image_ocr", publish)
    key = uuid4()
    args = (path, "runtime-dsn", published.inventory_id, target.member_locator, key)
    first = control.run_archive_member_image_ocr_controller(*args)
    replay = control.run_archive_member_image_ocr_controller(*args)
    assert core.archive_member_target.call_count == 2
    assert all(
        call.args[1:] == (published.inventory_id, target.member_locator)
        for call in core.archive_member_target.call_args_list
    )
    assert extract.call_count == publish.call_count == 2
    assert all(call.args[1] is target for call in extract.call_args_list)
    publish.assert_any_call(
        core, ANY, target, extraction,
        code_revision="unit-archive-controller-v1", idempotency_key=key,
    )
    assert first["changed"] is True and replay["changed"] is False
    for result in (first, replay):
        encoded = json.dumps(result)
        assert result["operation"] == "archive_member_image_ocr"
        assert result["source_effects"] is False
        assert target.member_locator not in encoded
        assert "secret evidence text" not in encoded
        assert "runtime-dsn" not in encoded


@pytest.mark.parametrize(
    "status", [ExtractionStatus.EMPTY, ExtractionStatus.DEFERRED, ExtractionStatus.FAILED]
)
def test_archive_image_refuses_unpublishable_results(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, status: ExtractionStatus
) -> None:
    path = image_controller_file(tmp_path)
    monkeypatch.setattr(control, "Store", Mock(return_value=MagicMock()))
    core = MagicMock()
    core.archive_member_target.return_value = SimpleNamespace()
    monkeypatch.setattr(control, "DataCoreStore", Mock(return_value=core))
    monkeypatch.setattr(control, "DockerArchiveMemberProcessor", MagicMock())
    monkeypatch.setattr(control, "DockerImageOcrProcessor", MagicMock())
    monkeypatch.setattr(
        control, "extract_archive_member_image_ocr",
        Mock(return_value=SimpleNamespace(status=status, text="untrusted detail")),
    )
    publish = Mock()
    monkeypatch.setattr(control, "publish_extracted_archive_member_image_ocr", publish)
    with pytest.raises(control.ArchiveMemberControllerError) as denied:
        control.run_archive_member_image_ocr_controller(
            path, "runtime-dsn", "archive_inventory_" + "d" * 32, "proof.png", uuid4()
        )
    assert "untrusted detail" not in str(denied.value)
    publish.assert_not_called()


@pytest.mark.parametrize("failure", ["reauth", "stale"])
def test_archive_image_refuses_revoked_or_stale_publication(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    path = image_controller_file(tmp_path)
    monkeypatch.setattr(control, "Store", Mock(return_value=MagicMock()))
    core = MagicMock()
    core.archive_member_target.return_value = SimpleNamespace()
    monkeypatch.setattr(control, "DataCoreStore", Mock(return_value=core))
    monkeypatch.setattr(control, "DockerArchiveMemberProcessor", MagicMock())
    monkeypatch.setattr(control, "DockerImageOcrProcessor", MagicMock())
    monkeypatch.setattr(
        control, "extract_archive_member_image_ocr",
        Mock(return_value=SimpleNamespace(status=ExtractionStatus.EXTRACTED)),
    )
    publish = Mock(side_effect=control.Conflict("stale private member path"))
    monkeypatch.setattr(control, "publish_extracted_archive_member_image_ocr", publish)
    if failure == "reauth":
        counter = 0

        def revoked(*args: object) -> None:
            nonlocal counter
            counter += 1
            if counter >= 4:
                raise control.ArchiveMemberControllerError()

        monkeypatch.setattr(control, "_current", revoked)
    with pytest.raises(control.ArchiveMemberControllerError) as denied:
        control.run_archive_member_image_ocr_controller(
            path, "runtime-dsn", "archive_inventory_" + "d" * 32, "proof.png", uuid4()
        )
    assert "private member path" not in str(denied.value)
    if failure == "reauth":
        publish.assert_not_called()
    else:
        publish.assert_called_once()


def test_batch_check_validates_seal_without_target_or_worker_access(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config, _, _ = controller_files(tmp_path)
    plan, _, items = batch_plan_file(tmp_path)
    monkeypatch.setattr(control, "Store", Mock(return_value=MagicMock()))
    core = Mock(side_effect=AssertionError("check must not inspect batch targets"))
    processor = Mock(side_effect=AssertionError("check must not construct Docker worker"))
    monkeypatch.setattr(control, "DataCoreStore", core)
    monkeypatch.setattr(control, "DockerArchiveMemberProcessor", processor)
    result = control.run_archive_member_batch_controller(config, plan, "runtime-dsn", check=True)
    assert result["requested"] == len(items)
    assert result["execution_verified"] is False
    assert result["data_effects"] is False and result["source_effects"] is False
    core.assert_not_called()
    processor.assert_not_called()


def test_batch_is_fail_stop_and_exact_retry_replays_completed_items(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config, _, _ = controller_files(tmp_path)
    plan, inventory, items = batch_plan_file(tmp_path)
    monkeypatch.setattr(control, "Store", Mock(return_value=MagicMock()))
    core = MagicMock()
    core.archive_member_target.side_effect = [SimpleNamespace(), SimpleNamespace()]
    monkeypatch.setattr(control, "DataCoreStore", Mock(return_value=core))
    monkeypatch.setattr(control, "DockerArchiveMemberProcessor", MagicMock())
    extracted = SimpleNamespace(status=ExtractionStatus.EXTRACTED)
    monkeypatch.setattr(control, "extract_archive_member_text", Mock(return_value=extracted))
    publish = Mock(
        side_effect=[SimpleNamespace(changed=True), control.Conflict("synthetic refusal")]
    )
    monkeypatch.setattr(control, "publish_extracted_archive_member_text", publish)
    stopped = control.run_archive_member_batch_controller(config, plan, "runtime-dsn")
    assert stopped["complete"] is False and stopped["completed"] == 1
    assert stopped["failed_item_index"] == 1
    assert stopped["recorded"] == 1 and stopped["replayed"] == 0
    assert core.archive_member_target.call_count == 2

    core.archive_member_target.reset_mock()
    core.archive_member_target.side_effect = [SimpleNamespace() for _ in items]
    publish.reset_mock()
    publish.side_effect = [
        SimpleNamespace(changed=False),
        SimpleNamespace(changed=True),
        SimpleNamespace(changed=True),
    ]
    completed = control.run_archive_member_batch_controller(config, plan, "runtime-dsn")
    assert completed["complete"] is True and completed["completed"] == 3
    assert completed["recorded"] == 2 and completed["replayed"] == 1
    assert completed["results"] == [
        {"item_index": 0, "recorded": False},
        {"item_index": 1, "recorded": True},
        {"item_index": 2, "recorded": True},
    ]
    assert [call.args[1:] for call in core.archive_member_target.call_args_list] == [
        (inventory, item.member_locator) for item in items
    ]
    assert all(
        call.kwargs["idempotency_key"] == item.idempotency_key
        for call, item in zip(publish.call_args_list, items, strict=True)
    )
    assert not any(item.member_locator in json.dumps(completed) for item in items)


@pytest.mark.parametrize("mutation", ["digest", "duplicate_locator", "duplicate_key"])
def test_batch_rejects_invalid_seal_before_database(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
) -> None:
    config, _, _ = controller_files(tmp_path)
    plan, _, _ = batch_plan_file(tmp_path)
    payload = json.loads(plan.read_text())
    if mutation == "digest":
        payload["plan_sha256"] = "0" * 64
    elif mutation == "duplicate_locator":
        payload["items"][1]["member_locator"] = payload["items"][0]["member_locator"]
    else:
        payload["items"][1]["idempotency_key"] = payload["items"][0]["idempotency_key"]
    private_write(plan, payload)
    store = Mock()
    monkeypatch.setattr(control, "Store", store)
    with pytest.raises(control.ArchiveMemberControllerError):
        control.run_archive_member_batch_controller(config, plan, "runtime-dsn", check=True)
    store.assert_not_called()


def test_batch_requires_private_plan_and_matching_revision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config, _, _ = controller_files(tmp_path)
    plan, _, _ = batch_plan_file(tmp_path, code_revision="other-revision")
    store = Mock()
    monkeypatch.setattr(control, "Store", store)
    with pytest.raises(control.ArchiveMemberControllerError):
        control.run_archive_member_batch_controller(config, plan, "runtime-dsn")
    plan, _, _ = batch_plan_file(tmp_path)
    plan.chmod(0o644)
    with pytest.raises(control.ArchiveMemberControllerError):
        control.run_archive_member_batch_controller(config, plan, "runtime-dsn")
    store.assert_not_called()


def test_document_batch_check_constructs_neither_worker_or_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_path, config, _ = controller_files(tmp_path)
    config["document_image_id"] = "sha256:" + "b" * 64
    private_write(config_path, config)
    plan, _, items = document_batch_plan_file(tmp_path)
    monkeypatch.setattr(control, "Store", Mock(return_value=MagicMock()))
    core = Mock(side_effect=AssertionError("check must not inspect document targets"))
    archive = Mock(side_effect=AssertionError("check must not construct archive worker"))
    document = Mock(side_effect=AssertionError("check must not construct document worker"))
    monkeypatch.setattr(control, "DataCoreStore", core)
    monkeypatch.setattr(control, "DockerArchiveMemberProcessor", archive)
    monkeypatch.setattr(control, "DockerDocumentProcessor", document)
    result = control.run_archive_document_batch_controller(
        config_path, plan, "runtime-dsn", check=True
    )
    assert result["requested"] == len(items)
    assert result["execution_verified"] is False and result["data_effects"] is False
    core.assert_not_called()
    archive.assert_not_called()
    document.assert_not_called()


def test_document_batch_is_fail_stop_and_exact_retry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_path, config, _ = controller_files(tmp_path)
    config["document_image_id"] = "sha256:" + "b" * 64
    private_write(config_path, config)
    plan, inventory, items = document_batch_plan_file(tmp_path)
    monkeypatch.setattr(control, "Store", Mock(return_value=MagicMock()))
    core = MagicMock()
    core.archive_document_member_target.side_effect = [SimpleNamespace(), SimpleNamespace()]
    monkeypatch.setattr(control, "DataCoreStore", Mock(return_value=core))
    monkeypatch.setattr(control, "DockerArchiveMemberProcessor", MagicMock())
    monkeypatch.setattr(control, "DockerDocumentProcessor", MagicMock())
    extractions = [
        SimpleNamespace(
            status=ExtractionStatus.EXTRACTED, metadata={"format": item.document_format}
        )
        for item in items
    ]
    extract = Mock(side_effect=extractions[:2])
    monkeypatch.setattr(control, "extract_archive_member_document", extract)
    publish = Mock(
        side_effect=[SimpleNamespace(changed=True), control.Conflict("synthetic refusal")]
    )
    monkeypatch.setattr(control, "publish_extracted_archive_member_document", publish)
    stopped = control.run_archive_document_batch_controller(config_path, plan, "runtime-dsn")
    assert stopped["complete"] is False and stopped["failed_item_index"] == 1
    assert stopped["completed"] == 1 and stopped["recorded"] == 1

    core.archive_document_member_target.reset_mock()
    core.archive_document_member_target.side_effect = [SimpleNamespace() for _ in items]
    extract.reset_mock()
    extract.side_effect = extractions
    publish.reset_mock()
    publish.side_effect = [
        SimpleNamespace(changed=False),
        SimpleNamespace(changed=True),
        SimpleNamespace(changed=True),
    ]
    completed = control.run_archive_document_batch_controller(config_path, plan, "runtime-dsn")
    assert completed["complete"] is True
    assert completed["recorded"] == 2 and completed["replayed"] == 1
    assert [call.args[1:] for call in core.archive_document_member_target.call_args_list] == [
        (inventory, item.member_locator) for item in items
    ]
    assert all(
        call.kwargs["idempotency_key"] == item.idempotency_key
        for call, item in zip(publish.call_args_list, items, strict=True)
    )
    serialized = json.dumps(completed)
    assert not any(item.member_locator in serialized for item in items)
    assert not any(item.document_format in serialized for item in items)


@pytest.mark.parametrize("mutation", ["digest", "format", "duplicate_locator", "duplicate_key"])
def test_document_batch_rejects_invalid_plan_before_database(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mutation: str
) -> None:
    config_path, config, _ = controller_files(tmp_path)
    config["document_image_id"] = "sha256:" + "b" * 64
    private_write(config_path, config)
    plan, _, _ = document_batch_plan_file(tmp_path)
    payload = json.loads(plan.read_text())
    if mutation == "digest":
        payload["plan_sha256"] = "0" * 64
    elif mutation == "format":
        payload["items"][0]["document_format"] = "docx"
    elif mutation == "duplicate_locator":
        payload["items"][1]["member_locator"] = payload["items"][0]["member_locator"]
        payload["items"][1]["document_format"] = "pdf"
    else:
        payload["items"][1]["idempotency_key"] = payload["items"][0]["idempotency_key"]
    private_write(plan, payload)
    store = Mock()
    monkeypatch.setattr(control, "Store", store)
    with pytest.raises(control.ArchiveMemberControllerError):
        control.run_archive_document_batch_controller(config_path, plan, "runtime-dsn")
    store.assert_not_called()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("version", True),
        ("root", "relative"),
        ("archive_image_id", "masterbrain-archives:latest"),
        ("docker_binary", "docker"),
        ("credentials_file", "relative"),
        ("token_file", "relative"),
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
    path, config, _ = controller_files(tmp_path)
    config[field] = value
    private_write(path, config)
    store = Mock()
    monkeypatch.setattr(control, "Store", store)
    with pytest.raises(control.ArchiveMemberControllerError):
        control.run_archive_member_controller(
            path,
            "runtime-dsn",
            "archive_inventory_" + "a" * 32,
            "proof.txt",
            uuid4(),
            check=True,
        )
    store.assert_not_called()


@pytest.mark.parametrize("scopes", [[], ["brain.source.ingest"], ["email.process"]])
def test_exact_worker_scopes_are_required(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, scopes: list[str]
) -> None:
    path, _, credentials = controller_files(tmp_path)
    credentials[0]["scopes"] = scopes
    private_write(path.parent / "credentials.json", credentials)
    store = Mock()
    monkeypatch.setattr(control, "Store", store)
    with pytest.raises(control.ArchiveMemberControllerError):
        control.run_archive_member_controller(
            path,
            "runtime-dsn",
            "archive_inventory_" + "a" * 32,
            "proof.txt",
            uuid4(),
            check=True,
        )
    store.assert_not_called()


@pytest.mark.parametrize(
    "locator",
    ["", "/absolute.txt", "../escape.txt", "a/../b.txt", "a//b.txt", "a\\b.txt", "dir/"],
)
def test_unsafe_member_selection_fails_before_config_read(tmp_path: Path, locator: str) -> None:
    missing = tmp_path / "missing-config.json"
    with pytest.raises(control.ArchiveMemberControllerError):
        control.run_archive_member_controller(
            missing,
            "runtime-dsn",
            "archive_inventory_" + "a" * 32,
            locator,
            uuid4(),
            check=True,
        )


def test_public_or_symlink_config_is_refused(tmp_path: Path) -> None:
    path, _, _ = controller_files(tmp_path)
    path.chmod(0o644)
    with pytest.raises(control.ArchiveMemberControllerError):
        control.run_archive_member_controller(
            path,
            "runtime-dsn",
            "archive_inventory_" + "a" * 32,
            "proof.txt",
            uuid4(),
            check=True,
        )
    path.chmod(0o600)
    alias = path.with_name("alias.json")
    alias.symlink_to(path)
    with pytest.raises(control.ArchiveMemberControllerError):
        control.run_archive_member_controller(
            alias,
            "runtime-dsn",
            "archive_inventory_" + "a" * 32,
            "proof.txt",
            uuid4(),
            check=True,
        )
