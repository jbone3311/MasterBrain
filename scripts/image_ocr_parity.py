#!/usr/bin/env python3
"""Live image/OCR golden comparison against the pinned clean FOS-Master donor."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
from io import BytesIO
from pathlib import Path
from types import ModuleType
from typing import Any

from PIL import Image, ImageDraw, ImageFont

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))
worker = importlib.import_module("masterbrain.datacore.image_ocr_worker")
source_for = importlib.import_module("masterbrain.datacore.image_ocr_contract").source_for

DONOR_COMMIT = "218d5caec2f20b9047fd3eb8e027dc671acf0c15"
DONOR_FILES = {
    "_SYSTEM/tools/doc_extract.py": (
        "746932e5ce033a9b8f8bd7155a88dfbb6d1c57a9916aea2230e6afbe1a3ab269"
    ),
    "_SYSTEM/tools/image_triage.py": (
        "b3fbc5ab7bf8ce06072865b5f1c0c3cd57ab968c0490e6996f95ed37c657cfb0"
    ),
    "_SYSTEM/tests/test_doc_extract.py": (
        "823ce03a8d7e2b8c42845ae1685db0ed92391461428b989034b9d83140421a41"
    ),
    "_SYSTEM/tests/test_image_triage.py": (
        "83cff8f74b5736d7efb1fd130f968b6295f12a906d2281f1037781c7a4119335"
    ),
}
FORMATS = {
    "jpeg": ("JPEG", ".jpg"),
    "png": ("PNG", ".png"),
    "tiff": ("TIFF", ".tiff"),
    "bmp": ("BMP", ".bmp"),
    "gif": ("GIF", ".gif"),
    "webp": ("WEBP", ".webp"),
}


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
    ).stdout.strip()


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_donor(root: Path) -> ModuleType:
    if _git(root, "rev-parse", "HEAD") != DONOR_COMMIT or _git(root, "status", "--porcelain"):
        raise RuntimeError("donor commit or cleanliness mismatch")
    for relative, expected in DONOR_FILES.items():
        if _sha(root / relative) != expected:
            raise RuntimeError(f"donor hash mismatch: {relative}")
    tools = str(root / "_SYSTEM/tools")
    sys.path.insert(0, tools)
    try:
        source = root / "_SYSTEM/tools/doc_extract.py"
        spec = importlib.util.spec_from_file_location("pinned_fos_doc_extract_image", source)
        if spec is None or spec.loader is None:
            raise RuntimeError("unable to load pinned donor")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(tools)


def _fixture(kind: str, text: str | None) -> bytes:
    image = Image.new("RGB", (1200, 260), "white")
    if text:
        ImageDraw.Draw(image).text(
            (35, 70), text, fill="black", font=ImageFont.load_default(size=54)
        )
    output = BytesIO()
    options: dict[str, Any] = {"quality": 95} if kind in {"JPEG", "WEBP"} else {}
    image.save(output, format=kind, **options)
    return output.getvalue()


def _donor_ocr(result: dict[str, Any]) -> str:
    text = result.get("full_text")
    if not isinstance(text, str):
        raise AssertionError("donor did not return text")
    marker = "--- OCR ---\n"
    return text.split(marker, 1)[1].strip() if marker in text else ""


def _same_engine_ocr(image: object) -> str:
    import pytesseract  # type: ignore[import-untyped]

    return str(pytesseract.image_to_string(image, lang="eng", config="--psm 3", timeout=20))


def run(donor_root: Path, *, stress_images: int = 0) -> dict[str, Any]:
    if type(stress_images) is not int or not 0 <= stress_images <= 500:
        raise ValueError("stress-images must be 0..500")
    donor = _load_donor(donor_root.resolve(strict=True))
    original_ocr = worker._ocr
    checked: list[str] = []
    try:
        worker._ocr = _same_engine_ocr
        with tempfile.TemporaryDirectory(prefix="masterbrain-image-parity-") as temporary:
            root = Path(temporary)
            for format_name, (pillow_name, suffix) in FORMATS.items():
                for content_name, text in (
                    ("text", "INVOICE NUMBER 4471"),
                    ("blank", None),
                ):
                    raw = _fixture(pillow_name, text)
                    path = root / f"{format_name}-{content_name}{suffix}"
                    path.write_bytes(raw)
                    donor_result = donor.extract_file(path, {"image_ocr": True})
                    if "error" in donor_result:
                        raise AssertionError(f"{format_name}/{content_name}: donor error")
                    digest = hashlib.sha256(raw).hexdigest()
                    source = source_for(raw, suffix=suffix, sha256=digest, format=format_name)
                    result = worker.extract_image_ocr(raw, source)
                    metadata = donor_result["metadata"]
                    donor_dimensions = tuple(
                        int(value) for value in metadata["dimensions"].split("x")
                    )
                    expected_format = "JPEG" if format_name == "jpeg" else format_name.upper()
                    if (
                        result.status != "extracted"
                        or result.detected_format != format_name
                        or (result.width, result.height) != donor_dimensions
                        or metadata["format"] != expected_format
                        or result.mode != metadata["mode"]
                        or result.text != _donor_ocr(donor_result)
                    ):
                        raise AssertionError(f"{format_name}/{content_name}: normalized mismatch")
                    checked.append(f"{format_name}_{content_name}")

            for index in range(stress_images):
                text = f"STRESS RECORD {index:04d} TOTAL {index * 17}"
                raw = _fixture("PNG", text)
                path = root / f"stress-{index:04d}.png"
                path.write_bytes(raw)
                donor_result = donor.extract_file(path, {"image_ocr": True})
                digest = hashlib.sha256(raw).hexdigest()
                source = source_for(raw, suffix=".png", sha256=digest, format="png")
                result = worker.extract_image_ocr(raw, source)
                if (
                    "error" in donor_result
                    or result.status != "extracted"
                    or result.text != _donor_ocr(donor_result)
                ):
                    raise AssertionError(f"stress image {index}: normalized mismatch")

            animated_path = root / "animated.gif"
            frames = [Image.new("RGB", (30, 30), color) for color in ("red", "blue")]
            frames[0].save(
                animated_path, format="GIF", save_all=True, append_images=frames[1:], duration=20
            )
            animated = animated_path.read_bytes()
            digest = hashlib.sha256(animated).hexdigest()
            source = source_for(animated, suffix=".gif", sha256=digest, format="gif")
            result = worker.extract_image_ocr(animated, source)
            if result.reason != "multiframe":
                raise AssertionError("animated GIF was not deliberately refused")
            checked.append("safer_multiframe_refusal")
    finally:
        worker._ocr = original_ocr
    return {
        "donor_commit": DONOR_COMMIT,
        "normalized_equal_cases": 12,
        "deliberate_safer_refusals": 1,
        "stress_equal_cases": stress_images,
        "checked": checked,
        "source_effects": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--donor-root", type=Path, required=True)
    parser.add_argument("--stress-images", type=int, default=0)
    args = parser.parse_args()
    print(json.dumps(run(args.donor_root, stress_images=args.stress_images), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
