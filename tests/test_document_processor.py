"""Parent document boundary and fixed-profile regression, without local Docker."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest
from test_sandbox_runner import CID, IMAGE, fake_docker

from email_brain.synthetic_formats import WORD_TYPE, docx_bytes
from masterbrain.datacore import document_processor as parent
from masterbrain.datacore.document_contract import (
    MAX_OUTPUT_BYTES,
    DocumentUnavailable,
    encode_request,
)
from masterbrain.datacore.document_worker import process_request


def fixture() -> tuple[bytes, str, str]:
    raw = docx_bytes("isolated document parent proof")
    digest = hashlib.sha256(raw).hexdigest()
    return raw, "version_" + digest[:32], digest


def prepared(monkeypatch, **kwargs):
    raw, version_id, digest = fixture()
    request = encode_request(raw, version_id, "memo.docx", digest, WORD_TYPE)
    processor, calls, _ = fake_docker(
        monkeypatch,
        processor=parent.DockerDocumentProcessor(IMAGE),
        output=process_request(request),
        **kwargs,
    )
    return processor, raw, version_id, digest, request, calls


def test_document_profile_uses_only_bounded_pipes_and_fixed_child(monkeypatch) -> None:
    processor, raw, version_id, digest, request, calls = prepared(monkeypatch)
    result = processor.extract(
        raw,
        version_id=version_id,
        locator="memo.docx",
        sha256=digest,
        media_type=WORD_TYPE,
    )
    assert result.reason == "bounded_docx_v1" and "parent proof" in result.text
    assert processor.processor_version == "sandbox-fileos-document-v1-" + "a" * 64
    create = next(args for args, _, _ in calls if args[:2] == ["container", "create"])
    assert create[-5:] == [IMAGE, "-I", "-B", "-m", "masterbrain.datacore.document_worker"]
    assert create[create.index("--name") + 1].startswith("eb-document-")
    assert all("parent proof" not in arg and digest not in arg for arg in create)
    assert [(args, value, bounds) for args, value, bounds in calls if value] == [
        (
            ["container", "start", "--attach", "--interactive", CID],
            request,
            {"limit": MAX_OUTPUT_BYTES, "timeout": 30},
        )
    ]
    assert calls[-1][0] == ["container", "rm", "--force", CID]


def test_document_isolation_failure_prevents_source_disclosure(monkeypatch) -> None:
    processor, raw, version_id, digest, _, calls = prepared(
        monkeypatch, mutate=lambda state: state["HostConfig"].update(NetworkMode="host")
    )
    with pytest.raises(DocumentUnavailable):
        processor.extract(
            raw,
            version_id=version_id,
            locator="memo.docx",
            sha256=digest,
            media_type=WORD_TYPE,
        )
    assert not any(data for _, data, _ in calls)
    assert calls[-1][0] == ["container", "rm", "--force", CID]


def test_substituted_document_source_is_rejected_and_cleaned(monkeypatch) -> None:
    raw, version_id, digest = fixture()
    request = encode_request(raw, version_id, "memo.docx", digest, WORD_TYPE)
    output = json.loads(process_request(request))
    output["source"]["sha256"] = "c" * 64
    processor, calls, _ = fake_docker(
        monkeypatch,
        processor=parent.DockerDocumentProcessor(IMAGE),
        output=json.dumps(output).encode(),
    )
    with pytest.raises(DocumentUnavailable):
        processor.extract(
            raw,
            version_id=version_id,
            locator="memo.docx",
            sha256=digest,
            media_type=WORD_TYPE,
        )
    assert calls[-1][0] == ["container", "rm", "--force", CID]


def test_invalid_input_never_invokes_docker_and_parent_is_dependency_light(monkeypatch) -> None:
    processor = parent.DockerDocumentProcessor(IMAGE)
    invoke = Mock(side_effect=AssertionError("must not invoke"))
    monkeypatch.setattr(processor, "_invoke", invoke)
    raw, version_id, _ = fixture()
    with pytest.raises(DocumentUnavailable):
        processor.extract(
            raw,
            version_id=version_id,
            locator="../memo.docx",
            sha256="a" * 64,
            media_type=WORD_TYPE,
        )
    invoke.assert_not_called()
    probe = subprocess.run(
        [
            sys.executable,
            "-B",
            "-c",
            "import sys; import masterbrain.datacore.document_processor; "
            "assert all(x not in sys.modules for x in ('pypdf','openpyxl','docx'))",
        ],
        env={
            "PATH": os.environ.get("PATH", ""),
            "PYTHONPATH": str(Path(__file__).parents[1] / "src"),
        },
        capture_output=True,
        timeout=10,
        check=False,
    )
    assert probe.returncode == 0
