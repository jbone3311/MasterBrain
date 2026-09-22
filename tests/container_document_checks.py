"""Explicit real restricted-image FileOS document tests; not ordinary discovery."""

from __future__ import annotations

import hashlib
import os
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import pytest
import test_postgres as pg
from test_datacore_documents import hostile_ooxml

from email_brain.domain.models import TenantContext
from email_brain.store import Store
from email_brain.synthetic_formats import SHEET_TYPE, WORD_TYPE, docx_bytes, pdf_bytes, xlsx_bytes
from masterbrain.datacore.document_contract import PDF_TYPE, DocumentUnavailable
from masterbrain.datacore.document_processor import DockerDocumentProcessor
from masterbrain.datacore.extraction import FileOSAdapter
from masterbrain.datacore.fileos import snapshot_tree
from masterbrain.datacore.persistence import DataCoreStore

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
