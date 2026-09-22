"""Real tenant-enforced FileOS operator publication and replay."""

from __future__ import annotations

import hashlib
import json
import secrets
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import psycopg
import pytest
import test_postgres as pg

from email_brain.domain.models import TenantContext
from masterbrain.datacore.fileos import snapshot_tree
from masterbrain.datacore.persistence import DataCoreStore
from masterbrain.fileos_controller import FileOSControllerError, run_fileos_controller
from masterbrain.fileos_index_controller import (
    FileOSIndexControllerError,
    run_fileos_index_controller,
)

database, tenant = pg.database, pg.tenant
pytestmark = pytest.mark.postgres


def private_write(path: Path, value: object) -> None:
    raw = value if isinstance(value, bytes) else json.dumps(value).encode()
    path.write_bytes(raw)
    path.chmod(0o600)


def setup_controller(
    tmp_path: Path, ctx: TenantContext
) -> tuple[Path, Path, list[dict[str, object]], str]:
    state, source = tmp_path / "state", tmp_path / "source"
    state.mkdir(mode=0o700)
    source.mkdir()
    (source / "brief.txt").write_text("operational FileOS publish proof")
    token = secrets.token_urlsafe(40)
    credentials: list[dict[str, object]] = [
        {
            "token_sha256": hashlib.sha256(token.encode()).hexdigest(),
            "tenant_id": str(ctx.tenant_id),
            "actor_id": str(ctx.actor_id),
            "scopes": ["brain.source.ingest", "brain.document.publish"],
            "client_kind": "worker",
            "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
        }
    ]
    private_write(state / "token", token.encode())
    private_write(state / "credentials.json", credentials)
    manifest = snapshot_tree(
        source,
        source_id="files_operational",
        observed_at=datetime(2026, 9, 22, 12, tzinfo=UTC),
    )
    private_write(state / "snapshot.json", manifest)
    config = {
        "version": 1,
        "source_id": "files_operational",
        "root": str(source),
        "manifest_file": str(state / "snapshot.json"),
        "credentials_file": str(state / "credentials.json"),
        "token_file": str(state / "token"),
        "code_revision": "postgres-controller-v1",
    }
    path = state / "controller.json"
    private_write(path, config)
    return path, source, credentials, token


def setup_index_controller(
    state: Path, ctx: TenantContext, scopes: list[str], *, revision: str
) -> tuple[Path, list[dict[str, object]]]:
    token = secrets.token_urlsafe(40)
    credentials: list[dict[str, object]] = [
        {
            "token_sha256": hashlib.sha256(token.encode()).hexdigest(),
            "tenant_id": str(ctx.tenant_id),
            "actor_id": str(ctx.actor_id),
            "scopes": scopes,
            "client_kind": "worker",
            "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
        }
    ]
    private_write(state / "index-token", token.encode())
    private_write(state / "index-credentials.json", credentials)
    config = {
        "version": 1,
        "source_id": "files_operational",
        "credentials_file": str(state / "index-credentials.json"),
        "token_file": str(state / "index-token"),
        "code_revision": revision,
    }
    path = state / "index-controller.json"
    private_write(path, config)
    return path, credentials


def test_check_publish_replay_and_no_source_mutation(
    database: tuple[object, str],
    tenant: tuple[TenantContext, UUID],
    tmp_path: Path,
) -> None:
    store, _ = database
    ctx, _ = tenant
    path, source, _, _ = setup_controller(tmp_path, ctx)
    before = (source.joinpath("brief.txt").read_bytes(), source.joinpath("brief.txt").stat())
    key = uuid4()
    assert run_fileos_controller(path, store.dsn, key, check=True)["execution_verified"] is False
    first = run_fileos_controller(path, store.dsn, key)
    assert first | {"completion": None} == {
        "source_id": "files_operational",
        "observed_items": 1,
        "new_versions": 1,
        "unchanged_versions": 0,
        "outcomes": {"extracted": 1},
        "published": 1,
        "changed_publications": 1,
        "completion": None,
        "source_effects": False,
    }
    assert first["completion"]["run_id"] == str(key)
    assert first["completion"]["recorded"] is True
    replay = run_fileos_controller(path, store.dsn, key)
    assert replay["new_versions"] == 1
    assert replay["changed_publications"] == 0
    assert replay["completion"] == {
        **first["completion"],
        "recorded": False,
    }
    after = source.joinpath("brief.txt").stat()
    assert source.joinpath("brief.txt").read_bytes() == before[0]
    assert after.st_mtime_ns == before[1].st_mtime_ns


def test_admin_dsn_and_revoked_local_worker_are_refused(
    database: tuple[object, str],
    tenant: tuple[TenantContext, UUID],
    tmp_path: Path,
) -> None:
    store, admin = database
    ctx, _ = tenant
    path, _, credentials, _ = setup_controller(tmp_path, ctx)
    with pytest.raises(FileOSControllerError):
        run_fileos_controller(path, admin, uuid4(), check=True)
    private_write(path.parent / "credentials.json", [])
    with pytest.raises(FileOSControllerError):
        run_fileos_controller(path, store.dsn, uuid4(), check=True)
    with psycopg.connect(admin) as conn:
        assert (
            conn.execute(
                "SELECT count(*) FROM brain_sources WHERE tenant_id=%s AND id='files_operational'",
                (ctx.tenant_id,),
            ).fetchone()[0]
            == 0
        )


def test_index_build_replay_changed_revision_and_rollback(
    database: tuple[object, str],
    tenant: tuple[TenantContext, UUID],
    tmp_path: Path,
) -> None:
    store, _ = database
    ctx, _ = tenant
    publish_path, source, _, _ = setup_controller(tmp_path, ctx)
    before = source.joinpath("brief.txt").read_bytes()
    run_id = uuid4()
    published = run_fileos_controller(publish_path, store.dsn, run_id)
    assert published["completion"]["recorded"] is True

    index_path, _ = setup_index_controller(
        publish_path.parent,
        ctx,
        ["brain.document.publish", "brain.index.activate"],
        revision="index-controller-v1",
    )
    first_key = uuid4()
    assert run_fileos_index_controller(
        index_path, store.dsn, first_key, run_id=run_id, check=True
    )["execution_verified"] is False
    first = run_fileos_index_controller(index_path, store.dsn, first_key, run_id=run_id)
    assert first["operation"] == "build_and_activate"
    assert first["generation"]["recorded"] is True
    assert first["activation"]["recorded"] is True
    replay = run_fileos_index_controller(index_path, store.dsn, first_key, run_id=run_id)
    assert replay["generation"]["recorded"] is False
    assert replay["activation"]["recorded"] is False
    assert replay["generation_id"] == first["generation_id"]

    config = json.loads(index_path.read_text())
    config["code_revision"] = "index-controller-v2"
    private_write(index_path, config)
    second = run_fileos_index_controller(
        index_path, store.dsn, uuid4(), run_id=run_id
    )
    assert second["generation_id"] != first["generation_id"]
    assert second["activation"]["previous_generation_id"] == first["generation_id"]

    rollback_path, _ = setup_index_controller(
        publish_path.parent,
        ctx,
        ["brain.index.activate"],
        revision="index-controller-v2",
    )
    rollback = run_fileos_index_controller(
        rollback_path,
        store.dsn,
        uuid4(),
        generation_id=first["generation_id"],
    )
    assert rollback["operation"] == "activate_existing"
    assert rollback["activation"]["previous_generation_id"] == second["generation_id"]
    assert (
        DataCoreStore(store).fileos_index_status(ctx, "files_operational")[
            "active_generation"
        ]["generation_id"]
        == first["generation_id"]
    )
    assert source.joinpath("brief.txt").read_bytes() == before


def test_index_admin_dsn_and_revoked_worker_are_refused(
    database: tuple[object, str],
    tenant: tuple[TenantContext, UUID],
    tmp_path: Path,
) -> None:
    store, admin = database
    ctx, _ = tenant
    state = tmp_path / "state"
    state.mkdir(mode=0o700)
    path, _ = setup_index_controller(
        state,
        ctx,
        ["brain.document.publish", "brain.index.activate"],
        revision="index-controller-v1",
    )
    with pytest.raises(FileOSIndexControllerError):
        run_fileos_index_controller(path, admin, uuid4(), run_id=uuid4(), check=True)
    private_write(state / "index-credentials.json", [])
    with pytest.raises(FileOSIndexControllerError):
        run_fileos_index_controller(path, store.dsn, uuid4(), run_id=uuid4(), check=True)
