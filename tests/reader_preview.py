"""Explicit fictional UI preview; no database, mailbox, identity service or worker.

This is a usability fixture, NOT end-to-end product/authorization acceptance.
Run with --synthetic-preview. All content is generated here, never loaded from mail.
"""

import argparse
import hashlib
import socket
from dataclasses import asdict
from email.message import EmailMessage
from typing import Annotated, Any
from uuid import UUID

import uvicorn
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, Response

from email_brain.api import WEB
from email_brain.attachments import receive_attachments
from email_brain.auth import Principal
from email_brain.domain.models import TenantContext
from email_brain.message_reader import MessageReader
from email_brain.normalize import MAX_ISOLATED_RAW_BYTES, normalize
from email_brain.schemas import DownloadRequest, SearchRequest
from email_brain.store import NotFound, Store
from email_brain.synthetic_formats import SHEET_TYPE, WORD_TYPE, docx_bytes, pdf_bytes, xlsx_bytes

TOKEN = "synthetic-reader-preview-only-not-a-secret"
ACCOUNT = UUID("00000000-0000-4000-8000-000000000001")
PRINCIPAL = Principal(
    TenantContext(ACCOUNT, ACCOUNT, frozenset({"email.evidence.read"}), ACCOUNT), "human"
)


def fixtures() -> dict[UUID, dict[str, Any]]:
    results = {}
    for number in range(1, 5):
        mail = EmailMessage()
        mail["From"] = "Alex Example <alex@example.invalid>"
        mail["To"] = "Jim Example <jim@example.invalid>"
        mail["Date"] = "Mon, 21 Sep 2026 12:00:00 +0000"
        mail["Subject"] = [
            "Readerproof: long conversation",
            "Readerproof: HTML-only safety",
            "Readerproof: project documents",
            "Readerproof: large original boundary",
        ][number - 1]
        if number == 1:
            mail.set_content(
                "Fictional project update. This is not real mail.\n\n"
                + "Quoted conversation continues here.\n" * 4000
                + "\nFINALTAIL — end of the complete email 😀"
            )
        elif number == 2:
            mail.set_content(
                "<html><head><style>hidden</style></head><body><h1>Fictional HTML email</h1>"
                "<p>This message is displayed as inert text.</p><script>do_not_execute()</script>"
                '<img src="https://tracker.invalid/pixel">'
                "<p>FINALTAIL — no images loaded.</p></body></html>",
                subtype="html",
            )
        elif number == 3:
            mail.set_content(
                "Fictional Melron packet: attached are a PDF, an Excel workbook, "
                "a Word document and a CSV.\nTheir contents are invented. "
                "Binary extraction is separate from downloading.\nFINALTAIL"
            )
            for filename, raw, media in [
                (
                    "brief.pdf",
                    pdf_bytes(("Fictional Melron project brief", "No real business data")),
                    "application/pdf",
                ),
                ("rents.xlsx", xlsx_bytes("Fictional Melron", 2500, 1, "READERPROOF"), SHEET_TYPE),
                ("memo.docx", docx_bytes("Fictional project memo. Readerproof."), WORD_TYPE),
                ("costs.csv", b"project,cost\nFictional Melron,1250\n", "text/csv"),
            ]:
                main, sub = media.split("/")
                mail.add_attachment(raw, maintype=main, subtype=sub, filename=filename)
        else:
            mail.set_content(
                "Fictional oversized body.\n" + "Large email example.\n" * 60000 + "\nFINALTAIL"
            )
        raw = mail.as_bytes()
        normalized = normalize(raw, max_raw_bytes=MAX_ISOLATED_RAW_BYTES)
        identifier = UUID(f"00000000-0000-4000-8000-{number + 10:012}")
        attachments = []
        for index, receipt in enumerate(
            receive_attachments(raw, max_raw_bytes=MAX_ISOLATED_RAW_BYTES)
        ):
            part = asdict(receipt)
            part.pop("original_filename")
            part.pop("text")
            part.update(
                id=UUID(f"00000000-0000-4000-8000-{number * 100 + index:012}"),
                scanner_status="not_scanned",
            )
            attachments.append(part)
        results[identifier] = {
            "id": identifier,
            "message_id": identifier,
            "account_id": ACCOUNT,
            "raw_sha256": normalized.raw_sha256,
            "raw_size": len(raw),
            "raw": raw,
            "snapshot": {
                "subject": normalized.subject,
                "sender": normalized.sender,
                "text": normalized.text,
                "truncated": normalized.truncated,
                "received_at": "2026-09-21T12:00:00+00:00",
            },
            "attachments": attachments,
        }
    return results


class FictionalReader(MessageReader):
    """In-memory fixture replacing SQL only in this explicit preview process."""

    def __init__(self, rows: dict[UUID, dict[str, Any]]) -> None:
        super().__init__(Store("preview-never-connects"))
        self.rows = rows

    def _source(self, principal: Principal, evidence_id: UUID) -> dict[str, Any]:
        if principal != PRINCIPAL or evidence_id not in self.rows:
            raise NotFound()
        return self.rows[evidence_id]

    def _raw(self, principal: Principal, source: dict[str, Any]) -> bytes:
        return bytes(source["raw"])

    def _finish(self, principal: Principal, evidence_id: UUID, event: str) -> None:
        self._source(principal, evidence_id)  # No durable audit is claimed in this fixture.


def preview_app() -> FastAPI:
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    rows = fixtures()
    reader = FictionalReader(rows)

    def owner(authorization: Annotated[str | None, Header()] = None) -> Principal:
        if authorization != f"Bearer {TOKEN}":
            raise HTTPException(401, "synthetic_preview_token_required")
        return PRINCIPAL

    @app.middleware("http")
    async def safety_headers(request, call_next):
        result = await call_next(request)
        result.headers["Cache-Control"] = "no-store"
        result.headers["X-Content-Type-Options"] = "nosniff"
        result.headers["Referrer-Policy"] = "no-referrer"
        if "Content-Security-Policy" not in result.headers:
            result.headers["Content-Security-Policy"] = (
                "default-src 'self'; img-src 'none'; frame-ancestors 'none'; base-uri 'none'"
            )
        return result

    @app.exception_handler(NotFound)
    async def missing(request, exc):
        return Response(status_code=404)

    @app.get("/")
    def index():
        html = (WEB / "index.html").read_text()
        html = html.replace(
            "<body><main>",
            "<body><main><section><h2>Fictional reader test</h2>"
            "<p>No real mail or database is connected. Search Readerproof, choose Read email, "
            "then try the downloads. Other product controls are not connected "
            "in this preview.</p></section>",
        )
        html = html.replace(
            'id="token" type="password"', f'id="token" value="{TOKEN}" type="password"'
        )
        html = html.replace('id="query" maxlength=', 'id="query" value="Readerproof" maxlength=')
        return HTMLResponse(html)

    @app.get("/readyz", dependencies=[Depends(owner)])
    def ready():
        return {"status": "synthetic-preview-only"}

    @app.get("/{asset}")
    def asset(asset: str):
        allowed = {"app.js", "document_review.js", "message_reader.js", "style.css"}
        if asset not in allowed:
            raise HTTPException(404)
        return FileResponse(
            WEB / asset, media_type="text/css" if asset.endswith(".css") else "text/javascript"
        )

    @app.post("/v1/search", dependencies=[Depends(owner)])
    def search(query: SearchRequest):
        results = [
            {
                "id": row["message_id"],
                "evidence_id": row["id"],
                "account_id": ACCOUNT,
                "subject": row["snapshot"]["subject"],
                "sender": row["snapshot"]["sender"],
                "excerpt": row["snapshot"]["text"][:500],
                "result_type": "message",
            }
            for row in rows.values()
            if query.query.casefold() in row["snapshot"]["subject"].casefold()
        ]
        return {"mode": "lexical", "untrusted_content": True, "results": results[: query.limit]}

    @app.get("/v1/reader/{evidence_id}")
    def read(evidence_id: UUID, principal: Annotated[Principal, Depends(owner)]):
        return reader.read(principal, evidence_id)

    def download(evidence_id: UUID, principal: Principal, receipt_id: UUID | None = None):
        data, name = reader.download(principal, evidence_id, receipt_id)
        return Response(
            data,
            media_type="application/octet-stream",
            headers={
                "Content-Disposition": f'attachment; filename="{name}"',
                "X-Content-SHA256": hashlib.sha256(data).hexdigest(),
                "Content-Security-Policy": "default-src 'none'; sandbox; frame-ancestors 'none'",
            },
        )

    @app.post("/v1/reader/{evidence_id}/original")
    def original(
        evidence_id: UUID, body: DownloadRequest, principal: Annotated[Principal, Depends(owner)]
    ):
        return download(evidence_id, principal)

    @app.post("/v1/reader/{evidence_id}/attachments/{receipt_id}")
    def attachment(
        evidence_id: UUID,
        receipt_id: UUID,
        body: DownloadRequest,
        principal: Annotated[Principal, Depends(owner)],
    ):
        return download(evidence_id, principal, receipt_id)

    return app


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--synthetic-preview", action="store_true", required=True)
    parser.parse_args()
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        print(f"Fictional reader preview: http://127.0.0.1:{listener.getsockname()[1]}", flush=True)
        server = uvicorn.Server(
            uvicorn.Config(preview_app(), access_log=False, log_level="warning")
        )
        server.run(sockets=[listener])
