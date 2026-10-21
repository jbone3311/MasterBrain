"""Fictional Email XLSX owner/API → two private workers → cited Brain retrieval."""

from __future__ import annotations

import hashlib
import json
import secrets
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import psycopg
import pytest
import test_postgres as pg
from fastapi.testclient import TestClient
from psycopg import sql
from psycopg.conninfo import make_conninfo
from test_email_xlsx_approvals_postgres import VERSION, _prepared
from test_email_xlsx_extraction_controller import IMAGE, _config
from test_email_xlsx_publication_controller import _operator, _private
from test_sandbox_runner import fake_docker

from email_brain.api import create_app
from email_brain.auth import Credential, TokenRegistry
from email_brain.migrate import grant_tenant_runtime
from masterbrain import email_xlsx_extraction_controller as extraction_control
from masterbrain.datacore.contracts import stable_id
from masterbrain.datacore.document_contract import SHEET_TYPE, encode_request
from masterbrain.datacore.document_processor import DockerDocumentProcessor
from masterbrain.datacore.document_worker import process_request
from masterbrain.email_xlsx_extraction_controller import run_email_xlsx_extraction_controller
from masterbrain.email_xlsx_publication_controller import run_email_xlsx_publication_controller

pytestmark = pytest.mark.postgres
database, tenant = pg.database, pg.tenant


def _worker_login(admin: str, tenant_id: UUID, actor_id: UUID, label: str) -> str:
    role = f"test_xlsx_alpha_{label}_{uuid4().hex[:8]}"
    password = secrets.token_urlsafe(32)
    with psycopg.connect(admin) as conn:
        conn.execute(
            "INSERT INTO tenant_memberships(tenant_id,user_id,role) "
            "VALUES (%s,%s,'owner')", (tenant_id, actor_id),
        )
        conn.execute(
            sql.SQL("CREATE ROLE {} LOGIN NOSUPERUSER NOBYPASSRLS PASSWORD {}").format(
                sql.Identifier(role), sql.Literal(password),
            ),
        )
        grant_tenant_runtime(conn, role, tenant_id)
    return make_conninfo(admin, user=role, password=password)


def test_fictional_owner_to_cited_xlsx_document_with_separate_workers(
    database, tenant, tmp_path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, admin, ctx, account, attachment, raw, document = _prepared(database, tenant)
    raw_hash, part_hash = hashlib.sha256(raw).hexdigest(), hashlib.sha256(document).hexdigest()
    version_id = stable_id("version", raw_hash, "1.2", part_hash)
    output = process_request(encode_request(
        document, version_id, "attachment.xlsx", part_hash, SHEET_TYPE,
    ))
    processor, calls, _ = fake_docker(
        monkeypatch, processor=DockerDocumentProcessor(IMAGE), output=output,
    )
    monkeypatch.setattr(
        extraction_control, "DockerDocumentProcessor", lambda *_args, **_kw: processor,
    )
    owner_token = "fictional-xlsx-alpha-" + uuid4().hex
    owner = Credential(
        token_sha256=hashlib.sha256(owner_token.encode()).hexdigest(),
        tenant_id=ctx.tenant_id, actor_id=ctx.actor_id,
        scopes={"email.search", "email.review", "email.evidence.read",
                "brain.search", "brain.content.read"},
        expires_at=datetime.now(UTC) + timedelta(hours=1), client_kind="human",
    )
    headers = {"Authorization": f"Bearer {owner_token}"}
    extract_home = tmp_path / "extract"
    publish_home = tmp_path / "publish"
    extract_home.mkdir()
    publish_home.mkdir()
    extraction_path, extraction_config, extraction_credentials = _config(extract_home)
    publication_path, publication_config, publication_credentials = _operator(publish_home)
    extraction_config["account_id"] = str(account)
    publication_config["account_id"] = str(account)
    extraction_actor, publication_actor = uuid4(), uuid4()
    extraction_credentials[0]["tenant_id"] = str(ctx.tenant_id)
    extraction_credentials[0]["actor_id"] = str(extraction_actor)
    publication_credentials[0]["tenant_id"] = str(ctx.tenant_id)
    publication_credentials[0]["actor_id"] = str(publication_actor)
    _private(extraction_path, extraction_config)
    _private(extraction_path.parent / "credentials.json", extraction_credentials)
    _private(publication_path, publication_config)
    _private(publication_path.parent / "credentials.json", publication_credentials)
    extraction_dsn = _worker_login(admin, ctx.tenant_id, extraction_actor, "extract")
    publication_dsn = _worker_login(admin, ctx.tenant_id, publication_actor, "publish")

    with TestClient(create_app(
        store, TokenRegistry([owner]), xlsx_document_processor_version=VERSION,
    )) as api:
        search = api.post(
            "/v1/search", json={"query": "Fictional workbook"}, headers=headers,
        )
        assert search.status_code == 200
        hit = next(row for row in search.json()["results"] if row["result_type"] == "message")
        evidence = api.get(f"/v1/evidence/{hit['evidence_id']}", headers=headers)
        assert evidence.status_code == 200
        selected = next(
            row for row in evidence.json()["attachments"] if row["id"] == str(attachment)
        )
        assert selected["safe_filename"] == "rent.xlsx"
        assert selected["sha256"] == part_hash
        route = f"/v1/accounts/{account}/attachments/{attachment}/xlsx-approvals"
        approved = api.post(route, headers={**headers, "Idempotency-Key": str(uuid4())})
        assert approved.status_code == 201
        approval_id = approved.json()["approval_id"]
        assert approved.json()["mailbox_effects"] is False
        assert approved.json()["document_published"] is False
        assert not calls
        pre_result = api.post(
            f"/v1/brain/email-xlsx-results/{approval_id}/inspect",
            json={"max_chars": 16000}, headers=headers,
        )
        assert pre_result.status_code == 409
        assert run_email_xlsx_extraction_controller(
            extraction_path, extraction_dsn, approval_id,
            check=True, tenant_bound_db=True,
        )["data_effects"] is False
        assert not calls
        sealed = run_email_xlsx_extraction_controller(
            extraction_path, extraction_dsn, approval_id, tenant_bound_db=True,
        )
        assert sealed["changed"] is True and sealed["document_published"] is False
        assert calls
        inspected = api.post(
            f"/v1/brain/email-xlsx-results/{approval_id}/inspect",
            json={"max_chars": 16000}, headers=headers,
        )
        assert inspected.status_code == 200
        page = inspected.json()
        assert page["next_offset"] is None
        assert page["source"]["attachment_id"] == str(attachment)
        assert page["source"]["parent_version_id"] == hit["evidence_id"]
        assert hashlib.sha256(page["text"].encode()).hexdigest() == sealed["text_sha256"]
        assert "xlsxapprovalproof" in page["text"]
        before = api.post(
            "/v1/brain/email-family-search", json={"query": "xlsxapprovalproof"},
            headers=headers,
        )
        assert before.status_code == 200 and before.json()["layers"]["documents"] == []
        reviewed = api.post(
            f"/v1/brain/email-xlsx-results/{approval_id}/publication-reviews",
            json={"expected_text_sha256": page["text_sha256"],
                  "expected_sheet_count": page["sheet_count"],
                  "expected_cell_count": page["cell_count"]},
            headers={**headers, "Idempotency-Key": str(uuid4())},
        )
        assert reviewed.status_code == 201 and reviewed.json()["document_published"] is False
        ui = subprocess.run(
            ["node", "tests/web_xlsx_review_api_contract.cjs"],
            cwd=Path(__file__).resolve().parents[1],
            input=json.dumps({
                "approval": approval_id, "inspection": page, "review": reviewed.json(),
            }),
            text=True, capture_output=True, timeout=20, check=False,
        )
        assert ui.returncode == 0, ui.stderr
        assert ui.stdout.startswith("PASS: real XLSX API shapes")
        assert run_email_xlsx_publication_controller(
            publication_path, publication_dsn, reviewed.json()["review_id"], uuid4(),
            check=True, tenant_bound_db=True,
        )["data_effects"] is False
        published = run_email_xlsx_publication_controller(
            publication_path, publication_dsn, reviewed.json()["review_id"], uuid4(),
            tenant_bound_db=True,
        )
        assert published["changed"] is True and published["mailbox_effects"] is False
        after = api.post(
            "/v1/brain/email-family-search", json={"query": "xlsxapprovalproof"},
            headers=headers,
        )
        assert after.status_code == 200
        hit = next(row for row in after.json()["layers"]["documents"]
                   if row["document_id"] == published["document_id"])
        content = api.post(
            f"/v1/brain/evidence/{hit['evidence_id']}/content",
            json={"max_chars": 4000}, headers=headers,
        )
        assert content.status_code == 200
        assert "xlsxapprovalproof" in content.json()["content"]
        with store.transaction(ctx) as conn:
            source = conn.execute(
                "SELECT source_id FROM brain_email_xlsx_extraction_approvals "
                "WHERE id=%s", (approval_id,),
            ).fetchone()
            assert source is not None
            conn.execute(
                "UPDATE brain_sources SET status='paused' WHERE id=%s",
                (source["source_id"],),
            )
        hidden = api.post(
            "/v1/brain/email-family-search", json={"query": "xlsxapprovalproof"},
            headers=headers,
        )
        assert hidden.status_code == 200
        assert hidden.json()["layers"]["documents"] == []
        direct = api.post(
            f"/v1/brain/evidence/{hit['evidence_id']}/content",
            json={"max_chars": 4000}, headers=headers,
        )
        assert direct.status_code == 404
    with store.transaction(ctx) as conn:
        assert conn.execute(
            "SELECT count(*) AS n FROM brain_email_xlsx_extraction_approvals "
            "WHERE id=%s", (approval_id,),
        ).fetchone()["n"] == 1
        assert conn.execute(
            "SELECT count(*) AS n FROM brain_email_xlsx_extraction_results "
            "WHERE approval_id=%s", (approval_id,),
        ).fetchone()["n"] == 1
        assert conn.execute(
            "SELECT count(*) AS n FROM brain_email_xlsx_document_bridge_receipts "
            "WHERE approval_id=%s", (approval_id,),
        ).fetchone()["n"] == 1
