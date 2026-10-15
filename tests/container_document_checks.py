"""Explicit real restricted-image FileOS document tests; not ordinary discovery."""

from __future__ import annotations

import hashlib
import os
from datetime import UTC, datetime
from email.message import EmailMessage
from pathlib import Path
from uuid import UUID, uuid4

import pytest
import test_postgres as pg
from test_datacore_documents import hostile_ooxml
from test_source_tier_fileos_pdf_replay_postgres import _prepared, _review, worker
from test_source_tier_fileos_xlsx_table_replay_postgres import _prepared as xlsx_prepared

from email_brain.domain.models import TenantContext
from email_brain.store import Store
from email_brain.synthetic_formats import SHEET_TYPE, WORD_TYPE, docx_bytes, pdf_bytes, xlsx_bytes
from masterbrain.datacore.contracts import stable_id
from masterbrain.datacore.current_fileos_xlsx_table_replay import (
    replay_current_fileos_xlsx_tables,
)
from masterbrain.datacore.document_contract import PDF_TYPE, DocumentUnavailable
from masterbrain.datacore.document_processor import DockerDocumentProcessor
from masterbrain.datacore.email_xlsx_derivation import prove_email_attachment_xlsx_derivation
from masterbrain.datacore.email_xlsx_table_derivation import (
    prove_email_attachment_xlsx_table_derivation,
)
from masterbrain.datacore.extraction import FileOSAdapter
from masterbrain.datacore.fileos import fileos_root_binding_sha256, snapshot_tree
from masterbrain.datacore.persistence import DataCoreStore
from masterbrain.datacore.xlsx_tables_processor import DockerXlsxTableProcessor
from masterbrain.source_tier_fileos_pdf_replay import SourceTierFileOSPdfReplayStore
from masterbrain.source_tier_fileos_xlsx_table_replay import (
    SourceTierFileOSXlsxTableReplayStore,
)

database, tenant = pg.database, pg.tenant


@pytest.fixture
def processor() -> DockerDocumentProcessor:
    image = os.environ.get("MASTERBRAIN_DOCUMENT_IMAGE_ID")
    if not image:
        pytest.fail("explicit document container checks require an approved prebuilt image")
    return DockerDocumentProcessor(image)


def identity(raw: bytes, name: str) -> tuple[str, str]:
    digest = hashlib.sha256(raw).hexdigest()
    return "version_" + digest[:32], digest


@pytest.mark.parametrize(
    "name,media_type,raw,marker,reason",
    [
        (
            "report.pdf",
            PDF_TYPE,
            pdf_bytes(("containerpdfproof",)),
            "containerpdfproof",
            "bounded_pdf_v1",
        ),
        (
            "memo.docx",
            WORD_TYPE,
            docx_bytes("containerwordproof"),
            "containerwordproof",
            "bounded_docx_v1",
        ),
        (
            "rent.xlsx",
            SHEET_TYPE,
            xlsx_bytes("Container Atlas", 3100, 7, "containersheetproof"),
            "containersheetproof",
            "bounded_xlsx_v1",
        ),
    ],
)
def test_actual_source_bound_document_profiles(
    processor: DockerDocumentProcessor,
    name: str,
    media_type: str,
    raw: bytes,
    marker: str,
    reason: str,
) -> None:
    version_id, digest = identity(raw, name)
    result = processor.extract(
        raw, version_id=version_id, locator=name, sha256=digest, media_type=media_type
    )
    assert result.status == "extracted" and result.reason == reason
    assert marker in result.text and result.scanner_status == "unscanned"


def test_actual_image_preserves_xlsx_rows_and_cell_positions() -> None:
    image = os.environ.get("MASTERBRAIN_DOCUMENT_IMAGE_ID")
    if not image:
        pytest.fail("explicit document container checks require an approved prebuilt image")
    raw = xlsx_bytes("Container Atlas", 3100, 7, "containercellproof")
    version_id, digest = identity(raw, "rent.xlsx")
    result = DockerXlsxTableProcessor(image).extract(
        raw, version_id=version_id, locator="rent.xlsx",
        sha256=digest, media_type=SHEET_TYPE,
    )
    assert result.status == "extracted" and result.reason == "bounded_xlsx_tables_v1"
    assert result.sheets[0].name == "Rent roll"
    assert result.sheets[0].rows[0].values == (
        "Project", "Monthly rent USD", "Revision", "Evidence marker",
    )
    assert result.sheets[0].rows[1].number == 2
    assert result.sheets[0].rows[1].values == (
        "Container Atlas", "3100", "7", "containercellproof",
    )


def test_actual_image_reacquires_fileos_xlsx_without_source_effects(
    processor: DockerDocumentProcessor, tmp_path: Path,
) -> None:
    image = os.environ.get("MASTERBRAIN_DOCUMENT_IMAGE_ID")
    assert image is not None
    root = tmp_path / "files"
    root.mkdir()
    path = root / "rent.xlsx"
    raw = xlsx_bytes("Container Atlas", 3100, 7, "containerreplayproof")
    path.write_bytes(raw)
    before = path.stat().st_mtime_ns
    version_id, digest = identity(raw, path.name)
    text = processor.extract(
        raw, version_id=version_id, locator=path.name,
        sha256=digest, media_type=SHEET_TYPE,
    )
    assert text.status == "extracted"
    proof = replay_current_fileos_xlsx_tables(
        root, locator=path.name, version_id=version_id,
        root_binding_sha256=fileos_root_binding_sha256(root),
        source_sha256=digest, source_size_bytes=len(raw),
        text_sha256=hashlib.sha256(text.text.encode()).hexdigest(),
        normalizer=processor.processor_version,
        processor=DockerXlsxTableProcessor(image),
    )
    assert proof.sheet_count == 1 and proof.row_count == 2
    assert proof.text_sha256 == hashlib.sha256(text.text.encode()).hexdigest()
    assert path.read_bytes() == raw and path.stat().st_mtime_ns == before


def test_actual_image_binds_retained_email_xlsx_text_and_rows(
    processor: DockerDocumentProcessor,
) -> None:
    image = os.environ.get("MASTERBRAIN_DOCUMENT_IMAGE_ID")
    assert image is not None
    document = xlsx_bytes("Container Atlas", 3100, 7, "containeremailrowproof")
    message = EmailMessage()
    message["From"] = "sender@example.invalid"
    message["To"] = "owner@example.invalid"
    message["Subject"] = "Fictional workbook"
    message.set_content("Synthetic message")
    message.add_attachment(
        document, maintype="application",
        subtype=SHEET_TYPE.removeprefix("application/"), filename="rent.xlsx",
    )
    message.set_boundary("synthetic-email-container-boundary")
    raw_mime = message.as_bytes()
    raw_sha256 = hashlib.sha256(raw_mime).hexdigest()
    part_sha256 = hashlib.sha256(document).hexdigest()
    normalized = processor.extract(
        document,
        version_id=stable_id("version", raw_sha256, "1.2", part_sha256),
        locator="attachment.xlsx", sha256=part_sha256, media_type=SHEET_TYPE,
    )
    assert normalized.status == "extracted"
    text_sha256 = hashlib.sha256(normalized.text.encode()).hexdigest()
    text_proof = prove_email_attachment_xlsx_derivation(
        raw_mime, raw_sha256=raw_sha256, raw_size_bytes=len(raw_mime),
        part_path="1.2", part_sha256=part_sha256, text=normalized.text,
        text_sha256=text_sha256, processor=processor,
    )
    row_proof = prove_email_attachment_xlsx_table_derivation(
        raw_mime, raw_sha256=raw_sha256, raw_size_bytes=len(raw_mime),
        part_path="1.2", part_sha256=part_sha256, text_sha256=text_sha256,
        normalizer=processor.processor_version,
        processor=DockerXlsxTableProcessor(image),
    )
    assert text_proof.raw_sha256 == row_proof.raw_sha256
    assert text_proof.part_sha256 == row_proof.part_sha256
    assert text_proof.text_sha256 == row_proof.text_sha256
    assert row_proof.sheet_count == 1 and row_proof.row_count == 2
    assert "containeremailrowproof" not in repr(row_proof)


def test_actual_child_refuses_source_mismatch_and_external_relationship(
    processor: DockerDocumentProcessor,
) -> None:
    raw = docx_bytes("source binding")
    version_id, digest = identity(raw, "memo.docx")
    with pytest.raises(DocumentUnavailable, match="^document_processing_unavailable$"):
        processor.extract(
            raw,
            version_id=version_id,
            locator="memo.docx",
            sha256="0" * 64,
            media_type=WORD_TYPE,
        )
    external = hostile_ooxml(
        raw,
        "word/_rels/document.xml.rels",
        b'<Relationships><Relationship TargetMode="External" Target="https://example.invalid"/></Relationships>',
    )
    external_version, external_digest = identity(external, "external.docx")
    result = processor.extract(
        external,
        version_id=external_version,
        locator="external.docx",
        sha256=external_digest,
        media_type=WORD_TYPE,
    )
    assert (result.status, result.reason, result.text) == (
        "deferred",
        "unsupported_features",
        "",
    )


@pytest.mark.postgres
def test_actual_fileos_documents_publish_to_shared_search_without_source_writes(
    database: tuple[Store, str],
    tenant: tuple[TenantContext, UUID],
    processor: DockerDocumentProcessor,
    tmp_path: Path,
) -> None:
    store, _ = database
    ctx, _ = tenant
    ctx = pg.datacore_context(ctx)
    fixtures = {
        "brief.pdf": pdf_bytes(("sharedpdfsearchproof",)),
        "memo.docx": docx_bytes("sharedwordsearchproof"),
        "ledger.xlsx": xlsx_bytes("Shared project", 4200, 9, "sharedsheetsearchproof"),
    }
    before: dict[str, tuple[str, int]] = {}
    for name, raw in fixtures.items():
        path = tmp_path / name
        path.write_bytes(raw)
        before[name] = (hashlib.sha256(raw).hexdigest(), path.stat().st_mtime_ns)
    manifest = snapshot_tree(
        tmp_path,
        source_id="files_document_container",
        observed_at=datetime(2026, 9, 22, tzinfo=UTC),
    )
    publication = FileOSAdapter(DataCoreStore(store), processor).publish_snapshot(
        ctx, tmp_path, manifest, uuid4(), code_revision="document-container-v1"
    )
    assert publication.counts == {"extracted": 3}
    assert all(item.publication is not None for item in publication.results)
    for marker in ("sharedpdfsearchproof", "sharedwordsearchproof", "sharedsheetsearchproof"):
        hits = DataCoreStore(store).search(ctx, marker)
        assert len(hits) == 1 and hits[0].source_id == "files_document_container"
    for name, (digest, modified) in before.items():
        path = tmp_path / name
        assert hashlib.sha256(path.read_bytes()).hexdigest() == digest
        assert path.stat().st_mtime_ns == modified


@pytest.mark.postgres
def test_actual_image_replays_one_reviewed_pdf_without_source_effects(
    database: tuple[Store, str],
    tenant: tuple[TenantContext, UUID],
    processor: DockerDocumentProcessor,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exercise ADR-226 through the actual restricted image, not a fake pipe."""
    store, _, ctx, root, _, document_id, _, _, result = _prepared(
        database, tenant, tmp_path, monkeypatch,
        image_id=os.environ["MASTERBRAIN_DOCUMENT_IMAGE_ID"],
    )
    assert result.status == "extracted"
    review_id = _review(store, ctx, document_id)
    source = root / "statement.pdf"
    original = source.read_bytes()
    before_mtime = source.stat().st_mtime_ns
    replay = SourceTierFileOSPdfReplayStore(store, processor)
    receipt = replay.record_current_pdf_replay(worker(ctx), review_id, root)
    assert receipt == {
        "review_id": review_id,
        "worker_observed_pdf_text_replay": True,
        "source_effects": False,
        "financial_claim_approved": False,
    }
    assert source.read_bytes() == original
    assert source.stat().st_mtime_ns == before_mtime
    with store.transaction(worker(ctx)) as conn:
        saved = conn.execute(
            "SELECT source_sha256,source_size_bytes,text_sha256,normalizer,page_count "
            "FROM knowledge_source_tier_fileos_pdf_replays WHERE review_id=%s",
            (review_id,),
        ).fetchone()
    assert saved is not None
    assert saved["source_sha256"] == hashlib.sha256(original).hexdigest()
    assert saved["source_size_bytes"] == len(original)
    assert saved["text_sha256"] == hashlib.sha256(result.text.encode()).hexdigest()
    assert saved["normalizer"] == processor.processor_version
    assert saved["page_count"] == 1


@pytest.mark.postgres
def test_actual_image_seals_one_reviewed_xlsx_layout_without_source_effects(
    database: tuple[Store, str], tenant: tuple[TenantContext, UUID],
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exercise ADR-236 through the actual immutable image, not a fake pipe."""
    image = os.environ.get("MASTERBRAIN_DOCUMENT_IMAGE_ID")
    if not image:
        pytest.fail("explicit document container checks require an approved prebuilt image")
    store, _, ctx, root, processor, review_id, _, _, raw = xlsx_prepared(
        database, tenant, tmp_path, monkeypatch, image_id=image, fake_pipe=False,
    )
    source = root / "statement.xlsx"
    before_mtime = source.stat().st_mtime_ns
    receipt = SourceTierFileOSXlsxTableReplayStore(
        store, processor,
    ).record_current_xlsx_table_replay(worker(ctx), review_id, root)
    assert receipt == {
        "review_id": review_id, "worker_observed_xlsx_table_replay": True,
        "source_effects": False, "financial_claim_approved": False,
    }
    assert source.read_bytes() == raw and source.stat().st_mtime_ns == before_mtime
    with store.transaction(worker(ctx)) as conn:
        saved = conn.execute(
            "SELECT source_sha256,source_size_bytes,text_sha256,normalizer,"
            "table_processor_version,row_layout_sha256,sheet_count,row_count,cell_count "
            "FROM knowledge_source_tier_fileos_xlsx_table_replays WHERE review_id=%s",
            (review_id,),
        ).fetchone()
    assert saved is not None
    assert saved["source_sha256"] == hashlib.sha256(raw).hexdigest()
    assert saved["source_size_bytes"] == len(raw)
    assert saved["normalizer"] == "sandbox-fileos-document-v1-" + image[7:]
    assert saved["table_processor_version"] == processor.processor_version
    assert len(saved["row_layout_sha256"]) == 64
    assert (saved["sheet_count"], saved["row_count"], saved["cell_count"]) == (1, 2, 8)
