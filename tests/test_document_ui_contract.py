"""Real SQL/API response shapes through the Node UI, using a known-answer reader."""

import json
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest
import test_document_jobs as documents

from email_brain.pdf_contract import PdfPage

database, tenant = documents.database, documents.tenant
pytestmark = pytest.mark.postgres


@pytest.mark.parametrize("outcome", ["extracted", "partial", "encrypted", "failed"])
def test_actual_api_responses_render_in_document_owner_ui(database, tenant, outcome):
    store, _ = database
    ctx, account = tenant
    jobs, _, worker, _, queued = documents.setup(database, tenant)
    api = documents.client(store, ctx)
    root = f"/v1/accounts/{account}"

    def get(path):
        result = api.get(path)
        assert result.status_code == 200
        return result.json()

    body = api.post("/v1/search", json={"query": "bodyproof"})
    assert body.status_code == 200 and len(body.json()["results"]) == 1
    message = get("/v1/evidence/" + body.json()["results"][0]["evidence_id"])
    before = documents.snapshot(store, ctx)
    packet = {
        "account": str(account),
        "body_search": body.json(),
        "message": message,
        "capabilities": get(root + "/documents"),
        "queued_history": get(root + "/documents/jobs?limit=50"),
    }
    reader = documents.FakePdf()
    original = reader.extract

    def extract(raw, **kwargs):
        result = original(raw, **kwargs)
        if outcome == "partial":
            return replace(
                result,
                status="partial",
                reason="pages_without_text",
                page_count=2,
                pages=(result.pages[0], PdfPage(2, "")),
            )
        if outcome in {"encrypted", "failed"}:
            return replace(
                result,
                status="deferred" if outcome == "encrypted" else "failed",
                reason="encrypted" if outcome == "encrypted" else "invalid_pdf",
                page_count=None,
                pages=(),
            )
        return replace(result, pages=(PdfPage(1, "pdfonlyproof 😀 " + "x" * 2500),))

    reader.extract = extract
    done = jobs.run_once(worker, account, reader)
    assert done["id"] == queued["id"] and done["status"] == "completed"
    assert documents.snapshot(store, ctx) == before
    packet["completed_history"] = get(root + "/documents/jobs?limit=50")
    packet["document"] = get(f"/v1/documents/{done['extraction_id']}")
    result = api.post("/v1/search", json={"query": "pdfonlyproof", "include_documents": True})
    assert result.status_code == 200
    packet["pdf_search"] = result.json()
    run = subprocess.run(
        ["node", "tests/web_document_api_contract.cjs"],
        cwd=Path(__file__).resolve().parents[1],
        input=json.dumps(packet),
        text=True,
        capture_output=True,
        timeout=20,
        check=False,
    )
    assert run.returncode == 0, run.stderr
    assert run.stdout.startswith("PASS: real API shapes")
