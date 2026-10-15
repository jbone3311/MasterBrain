"""Fictional confined XLSX row replay, with no FileOS source effects."""

from __future__ import annotations

import hashlib
from io import BytesIO
from pathlib import Path

import pytest
from openpyxl import Workbook
from test_sandbox_runner import IMAGE, fake_docker

from email_brain.synthetic_formats import SHEET_TYPE, xlsx_bytes
from masterbrain.datacore.current_fileos_xlsx_table_replay import (
    CurrentFileOSXlsxTableUnavailable,
    replay_current_fileos_xlsx_tables,
)
from masterbrain.datacore.document_contract import encode_request, source_for
from masterbrain.datacore.document_worker import extract_document
from masterbrain.datacore.fileos import fileos_root_binding_sha256
from masterbrain.datacore.xlsx_tables_processor import DockerXlsxTableProcessor
from masterbrain.datacore.xlsx_tables_worker import process_request


def _case(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, raw: bytes):
    root = tmp_path / "fileos"
    root.mkdir(parents=True)
    path = root / "rent.xlsx"
    path.write_bytes(raw)
    digest = hashlib.sha256(raw).hexdigest()
    version_id = "version_" + digest[:32]
    source = source_for(raw, version_id, path.name, digest, SHEET_TYPE)
    document = extract_document(raw, source)
    response = process_request(encode_request(
        raw, version_id, path.name, digest, SHEET_TYPE,
    ))
    processor, calls, _ = fake_docker(
        monkeypatch, processor=DockerXlsxTableProcessor(IMAGE), output=response,
    )
    args = {
        "locator": path.name,
        "version_id": version_id,
        "root_binding_sha256": fileos_root_binding_sha256(root),
        "source_sha256": digest,
        "source_size_bytes": len(raw),
        "text_sha256": hashlib.sha256(document.text.encode()).hexdigest(),
        "normalizer": "sandbox-fileos-document-v1-" + "a" * 64,
        "processor": processor,
    }
    return root, path, args, document, calls


def test_replays_current_fictional_rows_without_source_effect(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw = xlsx_bytes("Fictional Atlas", 2450, 3, "tableproof")
    root, path, args, document, calls = _case(tmp_path, monkeypatch, raw)
    before_mtime = path.stat().st_mtime_ns
    assert document.status == "extracted"
    proof = replay_current_fileos_xlsx_tables(root, **args)
    assert proof.source_sha256 == args["source_sha256"]
    assert proof.text_sha256 == args["text_sha256"]
    assert proof.sheet_count == 1 and proof.row_count == 2 and proof.cell_count == 8
    assert len(proof.row_layout_sha256) == 64
    assert "tableproof" not in repr(proof)
    assert path.read_bytes() == raw and path.stat().st_mtime_ns == before_mtime
    assert any(command[:2] == ["container", "start"] for command, _, _ in calls)


@pytest.mark.parametrize("field,value", [
    ("source_sha256", "0" * 64),
    ("source_size_bytes", 1),
    ("text_sha256", "0" * 64),
    ("root_binding_sha256", "0" * 64),
    ("normalizer", "sandbox-fileos-document-v1-" + "b" * 64),
    ("locator", "../rent.xlsx"),
])
def test_wrong_basis_refuses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, field: str, value: object,
) -> None:
    raw = xlsx_bytes("Fictional Atlas", 2450, 3, "tableproof")
    root, _, args, _, _ = _case(tmp_path, monkeypatch, raw)
    args[field] = value
    with pytest.raises(CurrentFileOSXlsxTableUnavailable):
        replay_current_fileos_xlsx_tables(root, **args)


def test_changed_or_symlinked_source_refuses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw = xlsx_bytes("Fictional Atlas", 2450, 3, "tableproof")
    root, path, args, _, _ = _case(tmp_path, monkeypatch, raw)
    path.write_bytes(xlsx_bytes("Changed Atlas", 2450, 3, "tableproof"))
    with pytest.raises(CurrentFileOSXlsxTableUnavailable):
        replay_current_fileos_xlsx_tables(root, **args)
    path.unlink()
    outside = tmp_path / "outside.xlsx"
    outside.write_bytes(raw)
    path.symlink_to(outside)
    with pytest.raises(CurrentFileOSXlsxTableUnavailable):
        replay_current_fileos_xlsx_tables(root, **args)


def test_formula_and_mismatched_published_text_refuse(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    book = Workbook()
    book.active.append(["Total", "=50+50"])
    output = BytesIO()
    book.save(output)
    book.close()
    root, _, args, document, _ = _case(tmp_path, monkeypatch, output.getvalue())
    assert document.status == "deferred"
    with pytest.raises(CurrentFileOSXlsxTableUnavailable):
        replay_current_fileos_xlsx_tables(root, **args)
    root2 = tmp_path / "other"
    root2.mkdir()
    root2, _, args2, _, _ = _case(
        root2, monkeypatch, xlsx_bytes("Fictional Atlas", 2450, 3, "tableproof"),
    )
    args2["text_sha256"] = hashlib.sha256(b"invented indexed text").hexdigest()
    with pytest.raises(CurrentFileOSXlsxTableUnavailable):
        replay_current_fileos_xlsx_tables(root2, **args2)


def _layout(*, blank_row: bool, author: str = "") -> bytes:
    book = Workbook()
    book.properties.creator = author
    sheet = book.active
    sheet.append(["Name", "Amount"])
    if blank_row:
        sheet.append([None, None])
    sheet.append(["Fictional", 100])
    output = BytesIO()
    book.save(output)
    book.close()
    return output.getvalue()


def test_layout_digest_distinguishes_blank_row_while_indexed_text_does_not(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    first_root, _, first, _, _ = _case(tmp_path, monkeypatch, _layout(blank_row=False))
    first_proof = replay_current_fileos_xlsx_tables(first_root, **first)
    second_root, _, second, _, _ = _case(
        tmp_path / "second", monkeypatch, _layout(blank_row=True),
    )
    second_proof = replay_current_fileos_xlsx_tables(second_root, **second)
    assert first_proof.text_sha256 == second_proof.text_sha256
    assert first_proof.row_layout_sha256 != second_proof.row_layout_sha256
    third_root, _, third, _, _ = _case(
        tmp_path / "third", monkeypatch,
        _layout(blank_row=False, author="Different fictional package metadata"),
    )
    third_proof = replay_current_fileos_xlsx_tables(third_root, **third)
    assert first_proof.source_sha256 != third_proof.source_sha256
    assert first_proof.row_layout_sha256 == third_proof.row_layout_sha256
