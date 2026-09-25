"""The trial must handle aliased temporary parents without relaxing source confinement."""

import pytest
import test_postgres as pg
from cross_source_preview import build_preview
from fastapi.testclient import TestClient

database = pg.database


@pytest.mark.postgres
def test_generated_trial_root_is_canonical_under_an_aliased_parent(database, tmp_path):
    store, admin = database
    physical = tmp_path / "physical"
    physical.mkdir()
    alias = tmp_path / "alias"
    alias.symlink_to(physical, target_is_directory=True)
    preview = build_preview(store, admin, alias)
    with TestClient(
        preview.app, base_url="http://127.0.0.1",
        headers={"Authorization": "Bearer " + preview.token},
    ) as client:
        response = client.post("/v1/brain/current-search", json={"query": "Cedar Harbor"})
        assert response.status_code == 200
        assert len(response.json()["layers"]["fileos"]) == 2
    assert alias.is_symlink()
    assert (physical / "owner" / "cedar-term-sheet.txt").is_file()
