from __future__ import annotations

import hashlib
import json
from io import BytesIO

import pytest
from PIL import Image
from test_sandbox_runner import CID, IMAGE, fake_docker

from masterbrain.datacore import image_ocr_processor as parent
from masterbrain.datacore import image_ocr_worker as worker
from masterbrain.datacore.image_ocr_contract import (
    MAX_OUTPUT_BYTES,
    ImageOcrUnavailable,
    encode_request,
)


def fixture() -> tuple[bytes, str]:
    output = BytesIO()
    Image.new("RGB", (40, 30), "white").save(output, format="PNG")
    raw = output.getvalue()
    return raw, hashlib.sha256(raw).hexdigest()


def response(monkeypatch: pytest.MonkeyPatch) -> bytes:
    raw, digest = fixture()
    monkeypatch.setattr(worker, "_ocr", lambda image: "isolated image proof")
    request = encode_request(raw, suffix=".png", sha256=digest, format="png")
    return worker.process_request(request)


def test_image_profile_has_fixed_scratch_child_and_bounded_pipes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw, digest = fixture()
    processor = parent.DockerImageOcrProcessor(IMAGE)
    processor, calls, _ = fake_docker(
        monkeypatch, processor=processor, output=response(monkeypatch)
    )
    result = processor.extract(raw, suffix=".png", sha256=digest, format="png")
    assert result.text == "isolated image proof"
    assert processor.processor_version == "sandbox-fileos-image-ocr-v1-" + "a" * 64
    create = next(args for args, _, _ in calls if args[:2] == ["container", "create"])
    assert create[-5:] == [IMAGE, "-I", "-B", "-m", "masterbrain.datacore.image_ocr_worker"]
    assert create[create.index("--name") + 1].startswith("eb-image-ocr-")
    assert create[create.index("--shm-size") + 1] == str(32 * 1024 * 1024)
    assert all(digest not in value for value in create)
    assert [(args, bounds) for args, value, bounds in calls if value] == [
        (
            ["container", "start", "--attach", "--interactive", CID],
            {"limit": MAX_OUTPUT_BYTES, "timeout": 30},
        )
    ]
    assert calls[-1][0] == ["container", "rm", "--force", CID]


def test_isolation_and_substituted_result_fail_before_acceptance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw, digest = fixture()
    processor, calls, _ = fake_docker(
        monkeypatch,
        processor=parent.DockerImageOcrProcessor(IMAGE),
        output=response(monkeypatch),
        mutate=lambda state: state["HostConfig"].update(ShmSize=0),
    )
    with pytest.raises(ImageOcrUnavailable):
        processor.extract(raw, suffix=".png", sha256=digest, format="png")
    assert not any(data for _, data, _ in calls)

    payload = json.loads(response(monkeypatch))
    payload["source"]["sha256"] = "c" * 64
    processor, _, _ = fake_docker(
        monkeypatch,
        processor=parent.DockerImageOcrProcessor(IMAGE),
        output=json.dumps(payload).encode(),
    )
    with pytest.raises(ImageOcrUnavailable):
        processor.extract(raw, suffix=".png", sha256=digest, format="png")
