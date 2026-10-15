"""Fictional confined PDF replay through the existing restricted pipe contract."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from test_sandbox_runner import IMAGE, fake_docker

from email_brain.synthetic_formats import pdf_bytes, plan_rgb
from masterbrain.datacore.current_fileos_pdf_replay import (
    CurrentFileOSPdfUnavailable,
    replay_current_fileos_pdf,
)
from masterbrain.datacore.document_contract import PDF_TYPE, encode_request
from masterbrain.datacore.document_processor import DockerDocumentProcessor
from masterbrain.datacore.document_worker import process_request
from masterbrain.datacore.fileos import fileos_root_binding_sha256


def _case(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, raw: bytes):
    root = tmp_path / "fileos"
    root.mkdir()
    path = root / "statement.pdf"
    path.write_bytes(raw)
    digest = hashlib.sha256(raw).hexdigest()
    version_id = "version_" + digest[:32]
    request = encode_request(raw, version_id, path.name, digest, PDF_TYPE)
    output = process_request(request)
    processor, calls, _ = fake_docker(
        monkeypatch, processor=DockerDocumentProcessor(IMAGE), output=output,
    )
    from masterbrain.datacore.document_contract import decode_result, source_for
    result = decode_result(output, source_for(raw, version_id, path.name, digest, PDF_TYPE))
    args = {
        "locator": path.name, "version_id": version_id,
        "root_binding_sha256": fileos_root_binding_sha256(root),
        "source_sha256": digest, "source_size_bytes": len(raw),
        "text": result.text,
        "text_sha256": hashlib.sha256(result.text.encode()).hexdigest(),
        "normalizer": processor.processor_version, "processor": processor,
    }
    return root, path, args, result, calls


def test_replays_fictional_pdf_without_writing_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw = pdf_bytes(("Fictional issuer statement", "Amount 125 USD"))
    root, path, args, result, calls = _case(tmp_path, monkeypatch, raw)
    assert result.status == "extracted" and result.metadata.page_count == 1
    proof = replay_current_fileos_pdf(root, **args)
    assert proof.source_sha256 == args["source_sha256"]
    assert proof.source_size_bytes == len(raw)
    assert proof.text_sha256 == args["text_sha256"]
    assert proof.page_count == 1
    assert path.read_bytes() == raw
    assert any(command[:2] == ["container", "start"] for command, _, _ in calls)


@pytest.mark.parametrize("changed", ["source_sha256", "source_size_bytes", "text_sha256",
                                    "normalizer", "root_binding_sha256"])
def test_wrong_pinned_basis_never_succeeds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, changed: str,
) -> None:
    root, _, args, _, _ = _case(tmp_path, monkeypatch, pdf_bytes(("Fictional note",)))
    args[changed] = (
        2 if changed == "source_size_bytes" else
        "sandbox-fileos-document-v1-" + "b" * 64 if changed == "normalizer" else
        "b" * 64
    )
    with pytest.raises(CurrentFileOSPdfUnavailable):
        replay_current_fileos_pdf(root, **args)


def test_changed_or_symlinked_source_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, path, args, _, _ = _case(tmp_path, monkeypatch, pdf_bytes(("Fictional note",)))
    path.write_bytes(pdf_bytes(("Changed note",)))
    with pytest.raises(CurrentFileOSPdfUnavailable):
        replay_current_fileos_pdf(root, **args)
    path.unlink()
    outside = tmp_path / "outside.pdf"
    outside.write_bytes(pdf_bytes(("Fictional note",)))
    path.symlink_to(outside)
    with pytest.raises(CurrentFileOSPdfUnavailable):
        replay_current_fileos_pdf(root, **args)


def test_image_only_pdf_and_altered_text_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, _, args, result, _ = _case(
        tmp_path, monkeypatch, pdf_bytes(rgb=plan_rgb(70)),
    )
    assert result.status == "deferred"
    with pytest.raises(CurrentFileOSPdfUnavailable):
        replay_current_fileos_pdf(root, **args)
    root2 = tmp_path / "other"
    root2.mkdir()
    root2, _, args2, _, _ = _case(
        root2, monkeypatch, pdf_bytes(("Fictional note",)),
    )
    args2["text"] = "Invented financial number"
    args2["text_sha256"] = hashlib.sha256(args2["text"].encode()).hexdigest()
    with pytest.raises(CurrentFileOSPdfUnavailable):
        replay_current_fileos_pdf(root2, **args2)
