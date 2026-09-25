"""The opt-in service route file is private, exact, and fail-closed."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import Mock
from uuid import uuid4

import pytest

from email_brain import cli
from email_brain.tenant_db import TenantDbRoutes


def _write(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload))
    path.chmod(0o600)


def _routes(tenant: str) -> dict[str, object]:
    return {
        "version": 1,
        "identity_dsn": "dbname=email_brain_test_route user=lookup password=lookup-secret",
        "tenants": {tenant: "dbname=email_brain_test_route user=tenant_one password=tenant-secret"},
    }


def test_private_tenant_database_routes(tmp_path: Path) -> None:
    tmp_path.chmod(0o700)
    tenant = uuid4()
    path = tmp_path / "routes.json"
    _write(path, _routes(str(tenant)))
    routes = TenantDbRoutes.from_file(path)
    assert routes.tenant_dsns[tenant].endswith("tenant-secret")
    assert "secret" not in repr(routes)


def test_serve_uses_opt_in_route_without_shared_dsn(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tmp_path.chmod(0o700)
    tenant = uuid4()
    path = tmp_path / "routes.json"
    _write(path, _routes(str(tenant)))
    monkeypatch.delenv("EMAIL_BRAIN_DSN", raising=False)
    monkeypatch.setenv("EMAIL_BRAIN_CREDENTIALS_FILE", str(tmp_path / "synthetic-tokens"))
    monkeypatch.setattr(sys, "argv", ["email-brain", "serve", "--tenant-db-config", str(path)])
    monkeypatch.setattr(cli.TokenRegistry, "from_file", lambda _path: Mock())
    captured: list[object] = []
    monkeypatch.setattr(cli, "create_app", lambda store, _registry, **_kw: captured.append(store))
    monkeypatch.setattr(cli.uvicorn, "run", lambda *_args, **_kw: None)
    cli.main()
    assert len(captured) == 1
    assert captured[0].tenant_dsns is not None
    assert captured[0].dsn.startswith("dbname=email_brain_test_route user=lookup")
    assert tenant in captured[0].tenant_dsns


@pytest.mark.parametrize(
    "change",
    [
        lambda p: p.update(version=True),
        lambda p: p.update(extra="unaccepted"),
        lambda p: p.update(tenants={}),
        lambda p: p.update(identity_dsn="password=leak"),
        lambda p: p.update(identity_dsn="dbname=other user=lookup password=secret"),
        lambda p: p.update(tenants={next(iter(p["tenants"])): "bad-dsn password=secret"}),
        lambda p: p.update(
            tenants={
                next(
                    iter(p["tenants"])
                ): "dbname=email_brain_test_route user=lookup password=other-secret"
            }
        ),
    ],
)
def test_invalid_route_shape_or_credentials_are_rejected(tmp_path: Path, change: object) -> None:
    tmp_path.chmod(0o700)
    payload = _routes(str(uuid4()))
    change(payload)
    path = tmp_path / "routes.json"
    _write(path, payload)
    with pytest.raises(ValueError) as exc:
        TenantDbRoutes.from_file(path)
    assert "secret" not in str(exc.value)


def test_duplicate_keys_and_unsafe_file_are_rejected(tmp_path: Path) -> None:
    tmp_path.chmod(0o700)
    tenant = str(uuid4())
    path = tmp_path / "routes.json"
    path.write_text(
        '{"version":1,"identity_dsn":"dbname=email_brain_test_route user=lookup '
        'password=secret","tenants":{"' + tenant + '":"dbname=email_brain_test_route '
        'user=first password=secret","' + tenant + '":"dbname=email_brain_test_route '
        'user=second password=secret"}}'
    )
    path.chmod(0o600)
    with pytest.raises(ValueError, match="duplicate"):
        TenantDbRoutes.from_file(path)
    _write(path, _routes(tenant))
    path.chmod(0o644)
    with pytest.raises(ValueError):
        TenantDbRoutes.from_file(path)
    path.chmod(0o600)
    link = tmp_path / "link.json"
    link.symlink_to(path)
    with pytest.raises((ValueError, OSError)):
        TenantDbRoutes.from_file(link)
