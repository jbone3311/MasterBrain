"""The shipped product identity must agree across package, API, and manifest."""

import json
import tomllib
from pathlib import Path
from unittest.mock import MagicMock

from email_brain.api import create_app
from email_brain.auth import TokenRegistry
from email_brain.store import Store
from masterbrain import __version__

ROOT = Path(__file__).resolve().parents[1]


def test_masterbrain_version_is_one_synthetic_alpha_identity() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    lock = tomllib.loads((ROOT / "uv.lock").read_text(encoding="utf-8"))
    manifest = json.loads((ROOT / "MANIFEST.json").read_text(encoding="utf-8"))
    locked = next(item for item in lock["package"] if item["name"] == "masterbrain")
    app = create_app(MagicMock(spec=Store), MagicMock(spec=TokenRegistry))

    assert __version__ == "0.2.0a2"
    assert project["project"]["version"] == locked["version"] == __version__
    assert manifest["product"]["version"] == app.version == __version__
    assert manifest["product"]["status"] == "synthetic-alpha"
    assert (ROOT / "VERSION.md").read_text(encoding="utf-8").splitlines()[2].startswith(
        __version__
    )
