"""Bootstrap REST service and owner review screen; no mailbox effects or inference tools."""

import hashlib
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import replace
from pathlib import Path
from typing import Annotated, Any
from uuid import UUID, uuid4

import psycopg
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from email_brain.auth import AuthenticationUnavailable, Authenticator, Principal
from email_brain.blobs import BlobError
from email_brain.browser_auth import SESSION_COOKIE, BrowserAuth, BrowserDenied
from email_brain.browser_routes import browser_cookie, browser_principal, browser_router
from email_brain.document_jobs import DocumentJobs
from email_brain.memory import Memory
from email_brain.memory_schema import MemoryWrite
from email_brain.message_reader import MessageReader, ReaderUnavailable
from email_brain.recovery import Recovery, RecoveryUnavailable
from email_brain.recovery_jobs import RecoveryJobs
from email_brain.rules.control import RuleControl
from email_brain.schemas import (
    DocumentRequest,
    DownloadRequest,
    ProposalRequest,
    RecoveryRequest,
    ReviewRequest,
    RuleActivationRequest,
    RuleRollbackRequest,
    RuleSimulationRequest,
    SearchRequest,
)
from email_brain.store import AccessDenied, Conflict, NotFound, Store
from masterbrain.datacore.persistence import DataCoreStore
from masterbrain.knowledge import KnowledgeCore
from masterbrain.knowledge_schema import KnowledgePublishRequest, KnowledgeSearchRequest
from masterbrain.schemas import BrainSearchRequest, EvidenceContentRequest, UnifiedSearchRequest

log = logging.getLogger("email_brain.requests")
WEB = Path(__file__).parent / "web"


class BodyLimit:
    """Bound streamed request bodies before JSON decoding, including chunked requests."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] not in {"POST", "PUT", "PATCH"}:
            await self.app(scope, receive, send)
            return
        chunks: list[bytes] = []
        total = 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            total += len(chunk)
            if total > 32768:
                await JSONResponse({"error": "request_too_large"}, status_code=413)(
                    scope, receive, send
                )
                return
            chunks.append(chunk)
            if not message.get("more_body", False):
                break
        delivered = False

        async def replay() -> Message:
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": b"".join(chunks), "more_body": False}
            return await receive()

        await self.app(scope, replay, send)


def create_app(
    store: Store,
    registry: Authenticator,
    *,
    brain_store: DataCoreStore | None = None,
    knowledge_store: KnowledgeCore | None = None,
    recovery_parser_version: str | None = None,
    document_processor_version: str | None = None,
    browser_auth: BrowserAuth | None = None,
) -> FastAPI:
    if browser_auth is not None and browser_auth.authenticator is not registry:
        raise ValueError("browser and API must share the same authenticator")
    app = FastAPI(
        title="MasterBrain — local prototype", version="0.1.0", docs_url=None, redoc_url=None
    )
    app.add_middleware(BodyLimit)
    bearer = HTTPBearer(auto_error=False)
    rule_control = RuleControl(store)
    recovery_control = Recovery(store)
    recovery_jobs = RecoveryJobs(store, recovery_parser_version)
    document_jobs = DocumentJobs(store, document_processor_version)
    message_reader = MessageReader(store)
    memory = Memory(store)
    brain = brain_store or DataCoreStore(store)
    knowledge = knowledge_store or KnowledgeCore(store)
    if browser_auth is not None:
        if browser_auth.authenticator.store is not store:
            raise ValueError("browser and API must share the same Store")
        app.include_router(browser_router(browser_auth))

    def require(scope: str, *, human: bool = False) -> Callable[..., Principal]:
        def dependency(
            request: Request,
            credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
        ) -> Principal:
            authorization = request.headers.getlist("authorization")
            principal: Principal | None
            if browser_auth is not None and browser_cookie(request, SESSION_COOKIE) is not None:
                principal = browser_principal(request, browser_auth)
            else:
                principal = (
                    registry.authenticate(credentials.credentials)
                    if credentials and len(authorization) == 1
                    else None
                )
            if principal is None:
                raise HTTPException(
                    401,
                    "invalid_or_expired_credential",
                    headers={
                        "WWW-Authenticate": (
                            'Bearer error="invalid_token"' if authorization else "Bearer"
                        )
                    },
                )
            if scope not in principal.context.scopes or (
                human and principal.client_kind != "human"
            ):
                raise HTTPException(403, "scope_denied")
            return replace(
                principal,
                context=replace(principal.context, request_id=UUID(request.state.request_id)),
            )

        return dependency

    @app.middleware("http")
    async def request_metadata(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        started = time.monotonic()
        request_id = str(uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        content_policy = response.headers.get("Content-Security-Policy")
        response.headers.update(
            {
                "X-Request-ID": request_id,
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
                "Referrer-Policy": "no-referrer",
                "Content-Security-Policy": "default-src 'self'; script-src 'self'; "
                "style-src 'self'; "
                "img-src 'none'; frame-ancestors 'none'; base-uri 'none'",
            }
        )
        if content_policy is not None:
            response.headers["Content-Security-Policy"] = content_policy
        # Fixed route templates, not URLs, queries, auth headers, or exception strings.
        route = getattr(request.scope.get("route"), "path", "unmatched")
        log.info(
            "request id=%s route=%s status=%s duration_ms=%.1f",
            request_id,
            route,
            response.status_code,
            (time.monotonic() - started) * 1000,
        )
        return response

    @app.exception_handler(BlobError)
    async def storage_handler(request: Request, exc: BlobError) -> JSONResponse:
        return JSONResponse(status_code=503, content={"error": "evidence_storage_unavailable"})

    @app.exception_handler(AuthenticationUnavailable)
    async def authentication_handler(
        request: Request, exc: AuthenticationUnavailable
    ) -> JSONResponse:
        return JSONResponse(status_code=503, content={"error": "authentication_unavailable"})

    @app.exception_handler(BrowserDenied)
    async def browser_denied_handler(request: Request, exc: BrowserDenied) -> JSONResponse:
        return JSONResponse(status_code=401, content={"error": "browser_session_denied"})

    @app.exception_handler(RecoveryUnavailable)
    async def recovery_handler(request: Request, exc: RecoveryUnavailable) -> JSONResponse:
        return JSONResponse(status_code=503, content={"error": "recovery_unavailable"})

    @app.exception_handler(ReaderUnavailable)
    async def reader_handler(request: Request, exc: ReaderUnavailable) -> JSONResponse:
        return JSONResponse(status_code=503, content={"error": "message_reader_unavailable"})

    @app.exception_handler(Conflict)
    async def conflict_handler(request: Request, exc: Conflict) -> JSONResponse:
        return JSONResponse({"error": "conflict", "retryable": False}, status_code=409)

    @app.exception_handler(NotFound)
    async def missing_handler(request: Request, exc: NotFound) -> JSONResponse:
        return JSONResponse({"error": "not_found"}, status_code=404)

    @app.exception_handler(AccessDenied)
    async def denied_handler(request: Request, exc: AccessDenied) -> JSONResponse:
        return JSONResponse({"error": "access_denied"}, status_code=403)

    @app.exception_handler(psycopg.Error)
    async def database_handler(request: Request, exc: psycopg.Error) -> JSONResponse:
        # Database diagnostics may contain data/DSNs. Deliberately do not log exc.
        return JSONResponse({"error": "database_unavailable", "retryable": True}, status_code=503)

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        # Pydantic error details may echo submitted private content; omit input values.
        return JSONResponse({"error": "invalid_request"}, status_code=422)

    @app.get("/healthz")
    def health() -> dict[str, str]:
        return {"status": "alive", "mode": "local-prototype", "mailbox_writes": "disabled"}

    @app.get("/readyz")
    def ready(principal: Annotated[Principal, Depends(require("email.search"))]) -> dict[str, str]:
        with store.transaction(principal.context) as conn:
            conn.execute("SELECT 1 FROM messages LIMIT 1")
        return {"status": "ready"}

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(WEB / "index.html")

    @app.get("/app.js", include_in_schema=False)
    def javascript() -> FileResponse:
        return FileResponse(WEB / "app.js", media_type="text/javascript")

    @app.get("/document_review.js", include_in_schema=False)
    def document_javascript() -> FileResponse:
        return FileResponse(WEB / "document_review.js", media_type="text/javascript")

    @app.get("/style.css", include_in_schema=False)
    def stylesheet() -> FileResponse:
        return FileResponse(WEB / "style.css", media_type="text/css")

    @app.get("/message_reader.js", include_in_schema=False)
    def reader_javascript() -> FileResponse:
        return FileResponse(WEB / "message_reader.js", media_type="text/javascript")

    @app.get("/v1/reader/{evidence_id}")
    def read_message(
        evidence_id: UUID,
        principal: Annotated[Principal, Depends(require("email.evidence.read", human=True))],
    ) -> dict[str, Any]:
        return message_reader.read(principal, evidence_id)

    @app.get("/memory", include_in_schema=False)
    def memory_page() -> FileResponse:
        return FileResponse(WEB / "memory.html")

    @app.get("/memory.js", include_in_schema=False)
    def memory_script() -> FileResponse:
        return FileResponse(WEB / "memory.js", media_type="text/javascript")

    @app.get("/v1/accounts/{account_id}/memory/summary")
    def memory_summary(
        account_id: UUID,
        principal: Annotated[Principal, Depends(require("email.evidence.read"))],
    ) -> dict[str, Any]:
        return memory.summary(principal.context, account_id)

    @app.get("/v1/accounts/{account_id}/memory/changes")
    def memory_changes(
        account_id: UUID,
        principal: Annotated[Principal, Depends(require("email.evidence.read"))],
        after: UUID | None = None,
        limit: Annotated[int, Query(ge=1, le=50)] = 25,
    ) -> dict[str, Any]:
        return memory.changes(principal.context, account_id, after=after, limit=limit)

    @app.get("/v1/accounts/{account_id}/memory/records")
    def memory_records(
        account_id: UUID,
        principal: Annotated[Principal, Depends(require("email.evidence.read"))],
        after: UUID | None = None,
        limit: Annotated[int, Query(ge=1, le=50)] = 25,
    ) -> dict[str, Any]:
        return memory.records(principal.context, account_id, after=after, limit=limit)

    @app.get("/v1/accounts/{account_id}/memory/records/{record_id}")
    def memory_record(
        account_id: UUID,
        record_id: UUID,
        principal: Annotated[Principal, Depends(require("email.evidence.read"))],
        at: UUID | None = None,
    ) -> dict[str, Any]:
        return memory.get(principal.context, account_id, record_id, at=at)

    @app.post("/v1/accounts/{account_id}/memory/candidates/{evidence_id}")
    def memory_candidate(
        account_id: UUID,
        evidence_id: UUID,
        principal: Annotated[Principal, Depends(require("email.review", human=True))],
    ) -> dict[str, Any]:
        return memory.candidate(principal, account_id, evidence_id)

    @app.put("/v1/accounts/{account_id}/memory/records/{record_id}")
    def memory_publish(
        account_id: UUID,
        record_id: UUID,
        body: MemoryWrite,
        principal: Annotated[Principal, Depends(require("email.review", human=True))],
        idempotency_key: Annotated[UUID, Header()],
    ) -> dict[str, Any]:
        return memory.publish(principal, account_id, record_id, body, idempotency_key)

    def download_response(data: bytes, name: str) -> Response:
        return Response(
            data,
            media_type="application/octet-stream",
            headers={
                "Content-Disposition": f'attachment; filename="{name}"',
                "Content-Security-Policy": "default-src 'none'; sandbox; frame-ancestors 'none'",
                "X-Content-SHA256": hashlib.sha256(data).hexdigest(),
            },
        )

    @app.post("/v1/reader/{evidence_id}/original")
    def original_download(
        evidence_id: UUID,
        body: DownloadRequest,
        principal: Annotated[Principal, Depends(require("email.evidence.read", human=True))],
    ) -> Response:
        return download_response(*message_reader.download(principal, evidence_id))

    @app.post("/v1/reader/{evidence_id}/attachments/{receipt_id}")
    def attachment_download(
        evidence_id: UUID,
        receipt_id: UUID,
        body: DownloadRequest,
        principal: Annotated[Principal, Depends(require("email.evidence.read", human=True))],
    ) -> Response:
        return download_response(*message_reader.download(principal, evidence_id, receipt_id))

    @app.post("/v1/search")
    def search(
        body: SearchRequest, principal: Annotated[Principal, Depends(require("email.search"))]
    ) -> dict[str, Any]:
        return {
            "mode": "lexical",
            "untrusted_content": True,
            "results": store.search(principal.context, body),
        }

    @app.post("/v1/brain/search")
    def brain_search(
        body: BrainSearchRequest,
        principal: Annotated[Principal, Depends(require("brain.search"))],
    ) -> dict[str, Any]:
        hits = brain.search(principal.context, body.query, limit=body.limit)
        return {
            "mode": "lexical",
            "results": [
                {
                    "chunk_id": hit.chunk_id,
                    "document_id": hit.document_id,
                    "evidence_id": hit.evidence_id,
                    "source_id": hit.source_id,
                    "locator": hit.locator,
                    "excerpt": hit.excerpt,
                    "rank": hit.rank,
                }
                for hit in hits
            ],
            "page": {"next_cursor": None, "truncated": False},
            "policy": {"scope": "brain.search", "redactions": []},
            "untrusted_content": True,
        }

    @app.post("/v1/brain/unified-search")
    def unified_search(
        body: UnifiedSearchRequest,
        principal: Annotated[Principal, Depends(require("brain.search"))],
    ) -> dict[str, Any]:
        if "knowledge.search" not in principal.context.scopes:
            raise HTTPException(403, "scope_denied")
        evidence_hits = brain.search(principal.context, body.query, limit=body.evidence_limit)
        knowledge_hits = knowledge.search(
            principal.context,
            body.query,
            limit=body.knowledge_limit,
            kinds=list(body.knowledge_kinds),
        )
        return {
            "mode": "grouped_lexical",
            "ranking": "within_layer_only",
            "layers": {
                "evidence": [
                    {
                        "chunk_id": hit.chunk_id,
                        "document_id": hit.document_id,
                        "evidence_id": hit.evidence_id,
                        "source_id": hit.source_id,
                        "locator": hit.locator,
                        "excerpt": hit.excerpt,
                        "rank": hit.rank,
                    }
                    for hit in evidence_hits
                ],
                "knowledge": [
                    {
                        "object_kind": hit.object_kind,
                        "object_id": hit.object_id,
                        "title": hit.title,
                        "excerpt": hit.excerpt,
                        "rank": hit.rank,
                        "evidence_ids": hit.evidence_ids,
                    }
                    for hit in knowledge_hits
                ],
            },
            "limits": {
                "evidence": body.evidence_limit,
                "knowledge": body.knowledge_limit,
            },
            "policy": {"scopes": ["brain.search", "knowledge.search"], "redactions": []},
            "untrusted_content": True,
        }

    @app.get("/v1/brain/evidence/{evidence_id}")
    def brain_evidence(
        evidence_id: str,
        principal: Annotated[Principal, Depends(require("brain.evidence.read"))],
    ) -> dict[str, Any]:
        return brain.evidence(principal.context, evidence_id)

    @app.post("/v1/brain/evidence/{evidence_id}/content")
    def brain_evidence_content(
        evidence_id: str,
        body: EvidenceContentRequest,
        principal: Annotated[Principal, Depends(require("brain.content.read"))],
    ) -> dict[str, Any]:
        return brain.evidence_content(principal.context, evidence_id, max_chars=body.max_chars)

    @app.get("/v1/brain/changes")
    def brain_changes(
        principal: Annotated[Principal, Depends(require("brain.changes.read"))],
        after: str | None = None,
        limit: Annotated[int, Query(ge=1, le=50)] = 25,
    ) -> dict[str, Any]:
        return brain.changes(principal.context, after=after, limit=limit)

    @app.post("/v1/knowledge/assertions", status_code=201)
    def publish_knowledge(
        body: KnowledgePublishRequest,
        principal: Annotated[Principal, Depends(require("knowledge.review", human=True))],
        idempotency_key: Annotated[UUID, Header()],
    ) -> dict[str, Any]:
        result = knowledge.publish(principal.context, body.assertion, idempotency_key)
        return {
            "object_kind": result.object_kind,
            "object_id": result.object_id,
            "changed": result.changed,
            "reviewed": True,
        }

    @app.post("/v1/knowledge/search")
    def search_knowledge(
        body: KnowledgeSearchRequest,
        principal: Annotated[Principal, Depends(require("knowledge.search"))],
    ) -> dict[str, Any]:
        hits = knowledge.search(
            principal.context, body.query, limit=body.limit, kinds=list(body.kinds)
        )
        return {
            "results": [
                {
                    "object_kind": hit.object_kind,
                    "object_id": hit.object_id,
                    "title": hit.title,
                    "excerpt": hit.excerpt,
                    "rank": hit.rank,
                    "evidence_ids": hit.evidence_ids,
                }
                for hit in hits
            ],
            "page": {"next_cursor": None, "truncated": False},
            "untrusted_content": True,
        }

    @app.get("/v1/knowledge/changes")
    def knowledge_changes(
        principal: Annotated[Principal, Depends(require("knowledge.changes.read"))],
        after: str | None = None,
        limit: Annotated[int, Query(ge=1, le=50)] = 25,
    ) -> dict[str, Any]:
        return knowledge.changes(principal.context, after=after, limit=limit)

    @app.get("/v1/knowledge/{kind}/{object_id}")
    def knowledge_object(
        kind: str,
        object_id: str,
        principal: Annotated[Principal, Depends(require("knowledge.read"))],
    ) -> dict[str, Any]:
        return knowledge.get(principal.context, kind, object_id)

    @app.get("/v1/accounts/{account_id}/quarantine")
    def quarantine(
        account_id: UUID,
        principal: Annotated[Principal, Depends(require("email.evidence.read"))],
        after: UUID | None = None,
        limit: Annotated[int, Query(ge=1, le=50)] = 50,
    ) -> dict[str, Any]:
        return store.quarantines(principal.context, account_id, after=after, limit=limit)

    @app.post("/v1/accounts/{account_id}/quarantine/{receipt_id}/retry")
    def retry_quarantine(
        account_id: UUID,
        receipt_id: UUID,
        request: RecoveryRequest,
        principal: Annotated[Principal, Depends(require("email.review", human=True))],
    ) -> dict[str, Any]:
        return recovery_control.retry(
            principal, account_id, receipt_id, request.expected_parser_version
        )

    @app.get("/v1/accounts/{account_id}/sync-status")
    def sync_status(
        account_id: UUID, principal: Annotated[Principal, Depends(require("email.search"))]
    ) -> dict[str, Any]:
        return store.sync_status(principal.context, account_id)

    @app.get("/v1/accounts/{account_id}/processing")
    def processing_capabilities(
        account_id: UUID,
        principal: Annotated[Principal, Depends(require("email.evidence.read"))],
    ) -> dict[str, Any]:
        return recovery_jobs.capabilities(principal.context, account_id)

    @app.post("/v1/accounts/{account_id}/quarantine/{receipt_id}/jobs", status_code=202)
    def enqueue_recovery(
        account_id: UUID,
        receipt_id: UUID,
        body: RecoveryRequest,
        principal: Annotated[Principal, Depends(require("email.review", human=True))],
        idempotency_key: Annotated[UUID, Header()],
    ) -> dict[str, Any]:
        return recovery_jobs.enqueue(
            principal, account_id, receipt_id, body.expected_parser_version, idempotency_key
        )

    @app.get("/v1/accounts/{account_id}/processing/jobs")
    def processing_history(
        account_id: UUID,
        principal: Annotated[Principal, Depends(require("email.evidence.read"))],
        after: UUID | None = None,
        limit: Annotated[int, Query(ge=1, le=50)] = 50,
    ) -> dict[str, Any]:
        return recovery_jobs.list(principal.context, account_id, after=after, limit=limit)

    @app.get("/v1/accounts/{account_id}/processing/{job_id}")
    def processing_status(
        account_id: UUID,
        job_id: UUID,
        principal: Annotated[Principal, Depends(require("email.evidence.read"))],
    ) -> dict[str, Any]:
        return recovery_jobs.get(principal.context, account_id, job_id)

    @app.post("/v1/accounts/{account_id}/processing/{job_id}/cancel")
    def cancel_processing(
        account_id: UUID,
        job_id: UUID,
        principal: Annotated[Principal, Depends(require("email.review", human=True))],
    ) -> dict[str, Any]:
        return recovery_jobs.cancel(principal, account_id, job_id)

    @app.get("/v1/accounts/{account_id}/documents")
    def document_capabilities(
        account_id: UUID,
        principal: Annotated[Principal, Depends(require("email.evidence.read"))],
    ) -> dict[str, Any]:
        return document_jobs.capabilities(principal.context, account_id)

    @app.post("/v1/accounts/{account_id}/attachments/{receipt_id}/jobs", status_code=202)
    def enqueue_document(
        account_id: UUID,
        receipt_id: UUID,
        body: DocumentRequest,
        principal: Annotated[Principal, Depends(require("email.review", human=True))],
        idempotency_key: Annotated[UUID, Header()],
    ) -> dict[str, Any]:
        return document_jobs.enqueue(
            principal,
            account_id,
            receipt_id,
            body.expected_processor_version,
            body.policy_version,
            idempotency_key,
        )

    @app.get("/v1/accounts/{account_id}/documents/jobs")
    def document_history(
        account_id: UUID,
        principal: Annotated[Principal, Depends(require("email.evidence.read"))],
        after: UUID | None = None,
        limit: Annotated[int, Query(ge=1, le=50)] = 50,
    ) -> dict[str, Any]:
        return document_jobs.list(principal.context, account_id, limit=limit, after=after)

    @app.get("/v1/accounts/{account_id}/documents/jobs/{job_id}")
    def document_status(
        account_id: UUID,
        job_id: UUID,
        principal: Annotated[Principal, Depends(require("email.evidence.read"))],
    ) -> dict[str, Any]:
        return document_jobs.get(principal.context, account_id, job_id)

    @app.post("/v1/accounts/{account_id}/documents/jobs/{job_id}/cancel")
    def cancel_document(
        account_id: UUID,
        job_id: UUID,
        principal: Annotated[Principal, Depends(require("email.review", human=True))],
    ) -> dict[str, Any]:
        return document_jobs.cancel(principal, account_id, job_id)

    @app.get("/v1/documents/{document_id}")
    def document_evidence(
        document_id: UUID,
        principal: Annotated[Principal, Depends(require("email.evidence.read"))],
    ) -> dict[str, Any]:
        return store.document_evidence(principal.context, document_id)

    @app.get("/v1/evidence/{evidence_id}")
    def evidence(
        evidence_id: UUID, principal: Annotated[Principal, Depends(require("email.evidence.read"))]
    ) -> dict[str, Any]:
        return store.evidence(principal.context, evidence_id)

    @app.post("/v1/proposals", status_code=201)
    def propose(
        body: ProposalRequest,
        principal: Annotated[Principal, Depends(require("email.proposal.create"))],
        idempotency_key: Annotated[UUID, Header()],
    ) -> dict[str, Any]:
        return store.propose(principal.context, body, idempotency_key)

    @app.get("/v1/proposals")
    def proposals(
        principal: Annotated[Principal, Depends(require("email.proposal.read"))],
    ) -> dict[str, Any]:
        return {"results": store.proposals(principal.context), "limit": 50}

    @app.post("/v1/proposals/{proposal_id}/reviews")
    def review(
        proposal_id: UUID,
        body: ReviewRequest,
        principal: Annotated[Principal, Depends(require("email.review", human=True))],
    ) -> dict[str, Any]:
        return {
            "proposal": store.review(principal.context, proposal_id, body),
            "applied": False,
            "mailbox_effects": False,
        }

    @app.get("/v1/rules")
    def rules(principal: Annotated[Principal, Depends(require("email.search"))]) -> dict[str, Any]:
        return rule_control.list(principal.context)

    @app.post("/v1/proposals/{proposal_id}/simulation", status_code=201)
    def simulate_rule(
        proposal_id: UUID,
        body: RuleSimulationRequest,
        principal: Annotated[Principal, Depends(require("email.review", human=True))],
    ) -> dict[str, Any]:
        return rule_control.simulate(principal, proposal_id, body.expected_version)

    @app.post("/v1/rules/activations")
    def activate_rule(
        body: RuleActivationRequest,
        principal: Annotated[Principal, Depends(require("email.review", human=True))],
    ) -> dict[str, Any]:
        return rule_control.activate(principal, body.simulation_id)

    @app.post("/v1/rules/rollback")
    def rollback_rules(
        body: RuleRollbackRequest,
        principal: Annotated[Principal, Depends(require("email.review", human=True))],
    ) -> dict[str, Any]:
        return rule_control.rollback(principal, body.expected_revision, body.target_revision)

    return app
