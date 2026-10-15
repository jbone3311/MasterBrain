"""Disposable, fictional Email/FileOS demo exercised through the real API."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta

import psycopg
import pytest
import test_postgres as pg
from fastapi.testclient import TestClient

from email_brain import cli
from email_brain.api import create_app
from email_brain.auth import Credential, TokenRegistry

pytestmark = pytest.mark.postgres
database, tenant = pg.database, pg.tenant


def test_combined_demo_seeds_and_replays_two_sources_with_cited_project(
    database, tenant, tmp_path, monkeypatch, capsys,
):
    store, _ = database
    ctx, account = tenant
    state = tmp_path / "private-demo"
    state.mkdir(mode=0o700)
    (state / "demo.json").write_text(json.dumps({
        "tenant_id": str(ctx.tenant_id), "actor_id": str(ctx.actor_id),
        "account_id": str(account),
    }))
    (state / "masterbrain-demo.marker").write_text(cli._DEMO_REVISION + "\n")
    monkeypatch.setenv("EMAIL_BRAIN_DSN", store.dsn)
    with psycopg.connect(database[1]) as conn:
        conn.execute(
            "UPDATE tenants SET name='Synthetic demo' WHERE id=%s", (ctx.tenant_id,),
        )
        conn.execute(
            "UPDATE mail_accounts SET address='owner@example.invalid',"
            "secret_ref='synthetic:no-token' WHERE id=%s", (account,),
        )

    cli.seed_masterbrain(state)
    first = capsys.readouterr().out
    project_id = first.split("project ready: ")[1].split(".")[0]
    assert project_id.startswith("project_")
    cli.seed_masterbrain(state)
    assert project_id in capsys.readouterr().out

    token = "synthetic-masterbrain-demo-credential-0001"
    registry = TokenRegistry([Credential(
        token_sha256=hashlib.sha256(token.encode()).hexdigest(),
        tenant_id=ctx.tenant_id, actor_id=ctx.actor_id,
        scopes={"email.search", "brain.search", "brain.content.read",
                "knowledge.search"},
        client_kind="human", expires_at=datetime.now(UTC) + timedelta(days=1),
    )])
    client = TestClient(create_app(store, registry))
    headers = {"Authorization": f"Bearer {token}"}
    email = client.post("/v1/search", json={"query": "Melron"}, headers=headers)
    assert email.status_code == 200 and len(email.json()["results"]) == 2
    combined = client.post(
        "/v1/brain/search", json={"query": "fictional"}, headers=headers,
    )
    assert combined.status_code == 200
    sources = {row["source_id"] for row in combined.json()["results"]}
    assert "files_demo" in sources and len(sources) == 2
    dossier = client.get(
        f"/v1/knowledge/projects/{project_id}/dossier/markdown", headers=headers,
    )
    assert dossier.status_code == 200
    assert "Cedar Harbor fictional planning brief" in dossier.json()["markdown"]
    assert dossier.json()["markdown"].count("citation `") >= 1


def test_combined_demo_refuses_email_only_state(tmp_path, monkeypatch):
    state = tmp_path / "email-only"
    state.mkdir(mode=0o700)
    monkeypatch.setenv("EMAIL_BRAIN_DSN", "unused")
    with pytest.raises(ValueError, match="fresh private MasterBrain demo state"):
        cli.seed_masterbrain(state)


def test_combined_demo_refuses_non_demo_account_before_any_ingest(
    database, tenant, tmp_path, monkeypatch,
):
    store, _ = database
    ctx, account = tenant
    state = tmp_path / "private-demo"
    state.mkdir(mode=0o700)
    (state / "demo.json").write_text(json.dumps({
        "tenant_id": str(ctx.tenant_id), "actor_id": str(ctx.actor_id),
        "account_id": str(account),
    }))
    (state / "masterbrain-demo.marker").write_text(cli._DEMO_REVISION + "\n")
    monkeypatch.setenv("EMAIL_BRAIN_DSN", store.dsn)
    with pytest.raises(ValueError, match="exact fictional demo account"):
        cli.seed_masterbrain(state)
    with store.transaction(ctx) as conn:
        assert conn.execute(
            "SELECT count(*) AS n FROM provider_events WHERE account_id=%s", (account,),
        ).fetchone()["n"] == 0
