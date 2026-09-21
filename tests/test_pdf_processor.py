"""Parent boundary and fixed-profile regression, with no local Docker dependency."""

import json
import subprocess
import sys
from unittest.mock import Mock

import pytest
from pdf_samples import mail_packet, variant
from test_sandbox_runner import CID, IMAGE, fake_docker

from email_brain import pdf_processor as parent
from email_brain.pdf_contract import MAX_OUTPUT_BYTES, PdfUnavailable
from email_brain.pdf_worker import process_request


def prepared(monkeypatch, **kwargs):
    raw, source, request = mail_packet(variant("text"))
    processor, calls, _ = fake_docker(
        monkeypatch,
        processor=parent.DockerPdfProcessor(IMAGE),
        output=process_request(request),
        **kwargs,
    )
    return processor, raw, source, request, calls


def extract(processor, raw, source):
    return processor.extract(raw, part_path=source.part_path, part_sha256=source.part_sha256)


def test_pdf_profile_and_bounded_source_pipes_never_share_mime_identity(monkeypatch):
    processor, raw, source, request, calls = prepared(monkeypatch)
    parsed = extract(processor, raw, source)
    assert parsed.source == source and "pdfonlyproof" in parsed.pages[0].text
    assert processor.processor_version == "sandbox-pdf-v1-" + "a" * 64
    assert not hasattr(processor, "prepare") and not hasattr(processor, "parser_version")
    create = next(args for args, _, _ in calls if args[:2] == ["container", "create"])
    assert create[-5:] == [IMAGE, "-I", "-B", "-m", "email_brain.pdf_worker"]
    assert create[create.index("--name") + 1].startswith("eb-pdf-")
    assert create[create.index("--label") + 1].startswith("org.cw.email-brain.pdf-run=")
    assert all("bodyproof" not in arg and "base64" not in arg for arg in create)
    assert source.raw_sha256 not in create and source.part_sha256 not in create
    assert [(args, value, bounds) for args, value, bounds in calls if value] == [
        (
            ["container", "start", "--attach", "--interactive", CID],
            request,
            {"limit": MAX_OUTPUT_BYTES, "timeout": 30},
        )
    ]
    assert calls[-1][0] == ["container", "rm", "--force", CID]


@pytest.mark.parametrize(
    "section,key,value",
    [
        ("HostConfig", "NetworkMode", "host"),
        ("HostConfig", "Privileged", True),
        ("HostConfig", "Memory", 0),
        ("HostConfig", "Binds", ["/private:/private"]),
        ("HostConfig", "SecurityOpt", ["seccomp=unconfined"]),
        ("HostConfig", "LogConfig", {"Type": "json-file"}),
        ("Config", "Cmd", ["-I", "-B", "-m", "email_brain.mime_sandbox"]),
        ("Config", "Env", ["SECRET=private"]),
        ("Config", "User", "0"),
    ],
)
def test_pdf_isolation_failure_prevents_any_source_disclosure(monkeypatch, section, key, value):
    processor, raw, source, _, calls = prepared(
        monkeypatch, mutate=lambda state: state[section].update({key: value})
    )
    with pytest.raises(PdfUnavailable):
        extract(processor, raw, source)
    assert not any(data for _, data, _ in calls)
    assert calls[-1][0] == ["container", "rm", "--force", CID]


def test_pdf_invalid_input_never_invokes_docker(monkeypatch):
    processor = parent.DockerPdfProcessor(IMAGE)
    invoke = Mock(side_effect=AssertionError("must not invoke"))
    monkeypatch.setattr(processor, "_invoke", invoke)
    with pytest.raises(PdfUnavailable):
        processor.extract(b"private", part_path="../path", part_sha256="a" * 64)
    invoke.assert_not_called()


@pytest.mark.parametrize(
    "change",
    [
        {"ExitCode": 70},
        {"ExitCode": False},
        {"OOMKilled": True},
        {"Status": "running"},
    ],
)
def test_child_crash_cannot_be_overruled_by_valid_pdf_output(monkeypatch, change):
    def mutate(state):
        if state["State"]["Status"] == "exited":
            state["State"].update(change)

    processor, raw, source, _, calls = prepared(monkeypatch, mutate=mutate)
    with pytest.raises(PdfUnavailable, match="^pdf_processing_unavailable$"):
        extract(processor, raw, source)
    assert calls[-1][0] == ["container", "rm", "--force", CID]


def test_unowned_pdf_container_is_never_deleted(monkeypatch):
    processor, raw, source, _, calls = prepared(
        monkeypatch, mutate=lambda state: state.update(Name="/someone-else")
    )
    with pytest.raises(PdfUnavailable):
        extract(processor, raw, source)
    assert not any(data for _, data, _ in calls)
    assert not any(args[:2] == ["container", "rm"] for args, _, _ in calls)


def test_valid_pdf_output_cannot_bypass_cleanup_failure(monkeypatch):
    processor, raw, source, _, _ = prepared(monkeypatch)
    monkeypatch.setattr(processor, "_cleanup", Mock(side_effect=RuntimeError("private path")))
    with pytest.raises(PdfUnavailable, match="^pdf_processing_unavailable$"):
        extract(processor, raw, source)


def test_substituted_child_source_hash_is_rejected_and_owned_child_removed(monkeypatch):
    raw, source, request = mail_packet(variant("text"))
    output = json.loads(process_request(request))
    output["source"]["raw_sha256"] = "c" * 64
    processor, calls, _ = fake_docker(
        monkeypatch, processor=parent.DockerPdfProcessor(IMAGE), output=json.dumps(output).encode()
    )
    with pytest.raises(PdfUnavailable):
        extract(processor, raw, source)
    assert calls[-1][0] == ["container", "rm", "--force", CID]


@pytest.mark.parametrize("image", ["latest", "tag:v1", IMAGE + "\n"])
def test_pdf_image_requires_exact_local_identity(image):
    with pytest.raises(PdfUnavailable):
        parent.DockerPdfProcessor(image)


def test_parent_import_does_not_import_optional_pdf_reader():
    probe = subprocess.run(
        [
            sys.executable,
            "-I",
            "-B",
            "-c",
            "import sys; import email_brain.pdf_processor; assert 'pypdf' not in sys.modules",
        ],
        capture_output=True,
        timeout=10,
        check=False,
    )
    assert probe.returncode == 0
