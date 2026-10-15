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
from masterbrain import __version__ as MASTERBRAIN_VERSION
from masterbrain.answers import (
    AnswerRejected,
    AnswerSelector,
    AnswerStale,
    AnswerUnavailable,
    GroundedAnswerService,
    LocalExtractiveSelector,
    answer_search_query,
)
from masterbrain.datacore.fileos_v2_index_generation import FileOSV2SearchReviewer
from masterbrain.datacore.persistence import DataCoreStore, SearchHit
from masterbrain.knowledge import KnowledgeCore
from masterbrain.knowledge_proposals import KnowledgeProposalBatches
from masterbrain.knowledge_schema import (
    DueCommitmentsRequest,
    KnowledgeProposalReviewRequest,
    KnowledgeProposalStageRequest,
    KnowledgePublishRequest,
    KnowledgeSearchRequest,
    ProjectAliasLookupRequest,
    ProjectArtifactLinkWrite,
    ProjectArtifactPageRequest,
    ProjectDossierRequest,
    TimelineRequest,
)
from masterbrain.project_artifacts import ProjectArtifactLinks
from masterbrain.schemas import (
    BrainSearchRequest,
    CurrentGroupedSearchRequest,
    EmailFamilySearchRequest,
    EvidenceContentRequest,
    FileOSV2SearchPreviewRequest,
    GroundedAnswerRequest,
    UnifiedSearchRequest,
)
from masterbrain.statement_persistence import StatementProposalReader

log = logging.getLogger("email_brain.requests")
WEB = Path(__file__).parent / "web"
BRAIN_WEB = Path(__file__).parent.parent / "masterbrain" / "web"
_LOCAL_ANSWER_SELECTOR: AnswerSelector = LocalExtractiveSelector()


def _safe_request_failure(request: Request, status: int, code: str, exc: Exception) -> None:
    """Log diagnostic categories only; exception text can contain private evidence."""
    route = getattr(request.scope.get("route"), "path", "unmatched")
    log.error(
        "request_failure id=%s route=%s status=%d code=%s error_type=%s",
        getattr(request.state, "request_id", "missing"),
        route,
        status,
        code,
        type(exc).__name__,
    )


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
    answer_selector: AnswerSelector | None = _LOCAL_ANSWER_SELECTOR,
    recovery_parser_version: str | None = None,
    document_processor_version: str | None = None,
    browser_auth: BrowserAuth | None = None,
) -> FastAPI:
    if browser_auth is not None and browser_auth.authenticator is not registry:
        raise ValueError("browser and API must share the same authenticator")
    app = FastAPI(
        title="MasterBrain — local prototype", version=MASTERBRAIN_VERSION,
        docs_url=None, redoc_url=None,
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
    fileos_v2_reviewer = FileOSV2SearchReviewer(brain)
    knowledge = knowledge_store or KnowledgeCore(store)
    knowledge_proposals = KnowledgeProposalBatches(store)
    project_artifacts = ProjectArtifactLinks(store)
    statement_proposals = StatementProposalReader(store)
    answers = GroundedAnswerService(brain, answer_selector)
    if browser_auth is not None:
        if browser_auth.authenticator.store is not store:
            raise ValueError("browser and API must share the same Store")
        app.include_router(browser_router(browser_auth))

    def require(
        scope: str, *, human: bool = False, assistant_source_aware: bool = False
    ) -> Callable[..., Principal]:
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
            if principal.client_kind == "assistant" and scope.startswith("email."):
                raise HTTPException(403, "scope_denied")
            if principal.client_kind == "assistant" and scope.startswith(("brain.", "knowledge.")):
                if not assistant_source_aware or not principal.context.source_ids:
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
        try:
            response = await call_next(request)
        except Exception as exc:
            _safe_request_failure(request, 500, "internal_error", exc)
            response = JSONResponse({"error": "internal_error"}, status_code=500)
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
        _safe_request_failure(request, 503, "evidence_storage_unavailable", exc)
        return JSONResponse(status_code=503, content={"error": "evidence_storage_unavailable"})

    @app.exception_handler(AuthenticationUnavailable)
    async def authentication_handler(
        request: Request, exc: AuthenticationUnavailable
    ) -> JSONResponse:
        _safe_request_failure(request, 503, "authentication_unavailable", exc)
        return JSONResponse(status_code=503, content={"error": "authentication_unavailable"})

    @app.exception_handler(BrowserDenied)
    async def browser_denied_handler(request: Request, exc: BrowserDenied) -> JSONResponse:
        return JSONResponse(status_code=401, content={"error": "browser_session_denied"})

    @app.exception_handler(RecoveryUnavailable)
    async def recovery_handler(request: Request, exc: RecoveryUnavailable) -> JSONResponse:
        _safe_request_failure(request, 503, "recovery_unavailable", exc)
        return JSONResponse(status_code=503, content={"error": "recovery_unavailable"})

    @app.exception_handler(ReaderUnavailable)
    async def reader_handler(request: Request, exc: ReaderUnavailable) -> JSONResponse:
        _safe_request_failure(request, 503, "message_reader_unavailable", exc)
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
        # Database diagnostics may contain data/DSNs. Log only a fixed code and class.
        _safe_request_failure(request, 503, "database_unavailable", exc)
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

    @app.get("/brain", include_in_schema=False)
    def brain_workspace() -> FileResponse:
        return FileResponse(BRAIN_WEB / "brain.html")

    @app.get("/brain.js", include_in_schema=False)
    def brain_workspace_script() -> FileResponse:
        return FileResponse(BRAIN_WEB / "brain.js", media_type="text/javascript")

    @app.get("/brain.css", include_in_schema=False)
    def brain_workspace_style() -> FileResponse:
        return FileResponse(BRAIN_WEB / "brain.css", media_type="text/css")

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
        principal: Annotated[
            Principal, Depends(require("brain.search", assistant_source_aware=True))
        ],
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
        principal: Annotated[
            Principal, Depends(require("brain.search", assistant_source_aware=True))
        ],
    ) -> dict[str, Any]:
        if "knowledge.search" not in principal.context.scopes:
            raise HTTPException(403, "scope_denied")
        evidence_hits = (
            brain.search_current_fileos(principal.context, body.query, limit=body.evidence_limit)
            if body.evidence_visibility == "current_fileos"
            else brain.search(principal.context, body.query, limit=body.evidence_limit)
        )
        knowledge_hits = knowledge.search(
            principal.context,
            body.query,
            limit=body.knowledge_limit,
            kinds=list(body.knowledge_kinds),
        )
        return {
            "mode": "grouped_lexical",
            "ranking": "within_layer_only",
            "evidence_visibility": (
                "current_fileos_active_generations"
                if body.evidence_visibility == "current_fileos"
                else "retained_history_compatible"
            ),
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

    @app.post("/v1/brain/current-search")
    def current_grouped_search(
        body: CurrentGroupedSearchRequest,
        principal: Annotated[
            Principal, Depends(require("brain.search", assistant_source_aware=True))
        ],
    ) -> dict[str, Any]:
        if "knowledge.search" not in principal.context.scopes:
            raise HTTPException(403, "scope_denied")
        include_files = body.source_focus in {"all", "fileos"}
        include_email = body.source_focus in {"all", "email"}
        fileos_hits = (
            brain.search_current_fileos(principal.context, body.query, limit=body.fileos_limit)
            if include_files else []
        )
        archive_member_hits = (
            brain.search_current_archive_members(
                principal.context, body.query, limit=body.archive_member_limit
            ) if include_files else []
        )
        archive_document_hits = (
            brain.search_current_archive_documents(
                principal.context, body.query, limit=body.archive_document_limit
            ) if include_files else []
        )
        archive_image_hits = (
            brain.search_current_archive_images(
                principal.context, body.query, limit=body.archive_image_limit
            ) if include_files else []
        )
        email_hits = (
            brain.search_current_email_family(
                principal.context,
                body.query,
                message_limit=body.email_message_limit,
                attachment_limit=body.email_attachment_limit,
                document_limit=body.email_document_limit,
            ) if include_email else None
        )
        knowledge_hits = (
            knowledge.search(
                principal.context,
                body.query,
                limit=body.knowledge_limit,
                kinds=list(body.knowledge_kinds),
                visibility="unsuperseded",
            ) if body.source_focus == "all" else []
        )
        source_availability = brain.source_availability(
            principal.context, source_focus=body.source_focus
        )

        def evidence(hits: tuple[SearchHit, ...] | list[SearchHit]) -> list[dict[str, Any]]:
            return [
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
            ]

        return {
            "mode": "grouped_current_sources",
            "ranking": "within_group_only",
            "consistency": "independent_layer_reads",
            "coverage": {
                "source_focus": body.source_focus,
                "source_availability": source_availability,
                "source_access": (
                    "enrolled_sources_only"
                    if principal.context.source_ids is not None else "tenant_sources"
                ),
                "fileos": (
                    "sources_with_active_generation_only" if include_files else "not_searched"
                ),
                "archive_members": (
                    "explicitly_published_current_archive_members_only"
                    if include_files else "not_searched"
                ),
                "archive_documents": (
                    "explicitly_published_current_archive_documents_only"
                    if include_files else "not_searched"
                ),
                "archive_images": (
                    "explicitly_published_current_archive_images_only"
                    if include_files else "not_searched"
                ),
                "email": "explicitly_bridged_current_only" if include_email else "not_searched",
                "knowledge": (
                    "reviewed_unsuperseded_assertions"
                    if body.source_focus == "all" else "not_searched"
                ),
                "complete": False,
            },
            "layers": {
                "fileos": evidence(fileos_hits),
                "archive_members": evidence(archive_member_hits),
                "archive_documents": evidence(archive_document_hits),
                "archive_images": evidence(archive_image_hits),
                "email_messages": evidence(email_hits.messages) if email_hits else [],
                "email_attachments": evidence(email_hits.attachments) if email_hits else [],
                "email_documents": evidence(email_hits.documents) if email_hits else [],
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
                "fileos": body.fileos_limit,
                "archive_members": body.archive_member_limit,
                "archive_documents": body.archive_document_limit,
                "archive_images": body.archive_image_limit,
                "email_messages": body.email_message_limit,
                "email_attachments": body.email_attachment_limit,
                "email_documents": body.email_document_limit,
                "knowledge": body.knowledge_limit,
            },
            "policy": {"scopes": ["brain.search", "knowledge.search"], "redactions": []},
            "untrusted_content": True,
        }

    @app.post("/v1/brain/answers")
    def grounded_answer(
        body: GroundedAnswerRequest,
        principal: Annotated[
            Principal, Depends(require("brain.search", assistant_source_aware=True))
        ],
    ) -> dict[str, Any]:
        required = {
            "knowledge.search", "brain.evidence.read", "brain.content.read"
        }
        if not required.issubset(principal.context.scopes):
            raise HTTPException(403, "scope_denied")
        try:
            return answers.answer(
                principal.context,
                body.question,
                lambda: current_grouped_search(
                    CurrentGroupedSearchRequest(
                        query=answer_search_query(body.question),
                        source_focus=body.source_focus,
                    ),
                    principal,
                ),
                source_focus=body.source_focus,
            )
        except AnswerUnavailable:
            raise HTTPException(503, "answer_unavailable") from None
        except AnswerRejected:
            raise HTTPException(502, "answer_rejected") from None
        except AnswerStale:
            raise HTTPException(409, "answer_stale") from None

    @app.get("/v1/brain/evidence/{evidence_id}")
    def brain_evidence(
        evidence_id: str,
        principal: Annotated[
            Principal, Depends(require("brain.evidence.read", assistant_source_aware=True))
        ],
    ) -> dict[str, Any]:
        return brain.evidence(principal.context, evidence_id)

    @app.post("/v1/brain/evidence/{evidence_id}/content")
    def brain_evidence_content(
        evidence_id: str,
        body: EvidenceContentRequest,
        principal: Annotated[
            Principal, Depends(require("brain.content.read", assistant_source_aware=True))
        ],
    ) -> dict[str, Any]:
        return brain.evidence_content(principal.context, evidence_id, max_chars=body.max_chars)

    @app.get("/v1/brain/changes")
    def brain_changes(
        principal: Annotated[
            Principal, Depends(require("brain.changes.read", assistant_source_aware=True))
        ],
        after: str | None = None,
        limit: Annotated[int, Query(ge=1, le=50)] = 25,
    ) -> dict[str, Any]:
        return brain.changes(principal.context, after=after, limit=limit)

    @app.get("/v1/brain/current-coverage")
    def brain_current_coverage(
        principal: Annotated[
            Principal, Depends(require("brain.changes.read", assistant_source_aware=True))
        ],
        after: str | None = None,
        limit: Annotated[int, Query(ge=1, le=50)] = 25,
    ) -> dict[str, Any]:
        return brain.current_coverage(principal.context, after=after, limit=limit)

    @app.get("/v1/brain/sources/{source_id}/freshness")
    def brain_source_freshness(
        source_id: str,
        principal: Annotated[
            Principal, Depends(require("brain.changes.read", assistant_source_aware=True))
        ],
    ) -> dict[str, Any]:
        return brain.fileos_freshness(principal.context, source_id)

    @app.get("/v1/brain/sources/{source_id}/inventory")
    def brain_source_inventory(
        source_id: str,
        principal: Annotated[
            Principal, Depends(require("brain.changes.read", assistant_source_aware=True))
        ],
    ) -> dict[str, Any]:
        return brain.fileos_inventory(principal.context, source_id)

    @app.get("/v1/brain/sources/{source_id}/rebuild-preview")
    def brain_source_rebuild_preview(
        source_id: str,
        principal: Annotated[
            Principal, Depends(require("brain.changes.read", assistant_source_aware=True))
        ],
        after: str | None = None,
        limit: Annotated[int, Query(ge=1, le=50)] = 25,
    ) -> dict[str, Any]:
        return brain.fileos_rebuild_preview(principal.context, source_id, after=after, limit=limit)

    @app.get("/v1/brain/sources/{source_id}/index")
    def brain_source_index_status(
        source_id: str,
        principal: Annotated[
            Principal, Depends(require("brain.changes.read", assistant_source_aware=True))
        ],
    ) -> dict[str, Any]:
        return brain.fileos_index_status(principal.context, source_id)

    @app.post("/v1/brain/sources/{source_id}/search")
    def brain_source_active_search(
        source_id: str,
        body: BrainSearchRequest,
        principal: Annotated[
            Principal, Depends(require("brain.search", assistant_source_aware=True))
        ],
    ) -> dict[str, Any]:
        hits = brain.search_fileos_active(
            principal.context, source_id, body.query, limit=body.limit
        )
        return {
            "source_id": source_id,
            "results": [
                {
                    "chunk_id": hit.chunk_id,
                    "document_id": hit.document_id,
                    "evidence_id": hit.evidence_id,
                    "locator": hit.locator,
                    "excerpt": hit.excerpt,
                    "rank": hit.rank,
                }
                for hit in hits
            ],
            "active_generation_only": True,
            "untrusted_content": True,
        }

    @app.post("/v1/brain/sources/{source_id}/v2-search-preview")
    def brain_source_v2_search_preview(
        source_id: str,
        body: FileOSV2SearchPreviewRequest,
        principal: Annotated[
            Principal, Depends(require("brain.fileos.transition.review", human=True))
        ],
    ) -> dict[str, Any]:
        try:
            comparison = fileos_v2_reviewer.preview(
                principal, source_id, body.generation_id, body.query, limit=body.limit,
            )
        except ValueError:
            raise HTTPException(422, "invalid_request") from None

        def compact(hits: tuple[SearchHit, ...]) -> list[dict[str, Any]]:
            return [
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
            ]

        return {
            "source_id": comparison.source_id,
            "candidate_generation_id": comparison.candidate_generation_id,
            "active_v1_generation_id": comparison.active_v1_generation_id,
            "candidate_visibility": comparison.candidate_visibility,
            "ranking": "within_generation_only",
            "coverage": "historical_comparison_not_current_fileos",
            "limit_per_generation": body.limit,
            "layers": {
                "active_v1": compact(comparison.active_v1_hits),
                "candidate_v2": compact(comparison.candidate_hits),
            },
            "untrusted_content": True,
        }

    @app.post("/v1/brain/fileos-search")
    def brain_current_fileos_search(
        body: BrainSearchRequest,
        principal: Annotated[
            Principal, Depends(require("brain.search", assistant_source_aware=True))
        ],
    ) -> dict[str, Any]:
        hits = brain.search_current_fileos(principal.context, body.query, limit=body.limit)
        return {
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
            "visibility": "current_fileos_active_generations",
            "untrusted_content": True,
        }

    @app.post("/v1/brain/email-search")
    def brain_current_email_search(
        body: BrainSearchRequest,
        principal: Annotated[
            Principal, Depends(require("brain.search", assistant_source_aware=True))
        ],
    ) -> dict[str, Any]:
        hits = brain.search_current_email(principal.context, body.query, limit=body.limit)
        return {
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
            "visibility": "current_bridged_email",
            "untrusted_content": True,
        }

    @app.post("/v1/brain/email-family-search")
    def brain_current_email_family_search(
        body: EmailFamilySearchRequest,
        principal: Annotated[
            Principal, Depends(require("brain.search", assistant_source_aware=True))
        ],
    ) -> dict[str, Any]:
        family = brain.search_current_email_family(
            principal.context,
            body.query,
            message_limit=body.message_limit,
            attachment_limit=body.attachment_limit,
            document_limit=body.document_limit,
        )

        def compact(hits: tuple[SearchHit, ...]) -> list[dict[str, Any]]:
            return [
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
            ]

        return {
            "layers": {
                "messages": compact(family.messages),
                "attachments": compact(family.attachments),
                "documents": compact(family.documents),
            },
            "visibility": "current_bridged_email_family",
            "ranking": "within_layer_only",
            "untrusted_content": True,
        }

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

    @app.post("/v1/knowledge/proposal-batches", status_code=201)
    def stage_knowledge_proposals(
        body: KnowledgeProposalStageRequest,
        principal: Annotated[Principal, Depends(require("knowledge.review", human=True))],
        idempotency_key: Annotated[UUID, Header()],
    ) -> dict[str, Any]:
        try:
            return knowledge_proposals.stage(principal.context, body, idempotency_key)
        except ValueError:
            raise HTTPException(422, "invalid_knowledge_proposals") from None

    @app.get("/v1/knowledge/proposal-batches/{batch_id}")
    def preview_knowledge_proposals(
        batch_id: str,
        principal: Annotated[Principal, Depends(require("knowledge.review", human=True))],
    ) -> dict[str, Any]:
        if "brain.content.read" not in principal.context.scopes:
            raise HTTPException(403, "scope_denied")
        return knowledge_proposals.preview(principal.context, batch_id)

    @app.post("/v1/knowledge/proposal-batches/{batch_id}/review")
    def review_knowledge_proposals(
        batch_id: str,
        body: KnowledgeProposalReviewRequest,
        principal: Annotated[Principal, Depends(require("knowledge.review", human=True))],
        idempotency_key: Annotated[UUID, Header()],
    ) -> dict[str, Any]:
        try:
            return knowledge_proposals.review(
                principal.context, batch_id, body, idempotency_key,
            )
        except ValueError:
            raise HTTPException(422, "invalid_knowledge_proposal_review") from None

    @app.post("/v1/knowledge/search")
    def search_knowledge(
        body: KnowledgeSearchRequest,
        principal: Annotated[
            Principal, Depends(require("knowledge.search", assistant_source_aware=True))
        ],
    ) -> dict[str, Any]:
        hits = knowledge.search(
            principal.context, body.query, limit=body.limit, kinds=list(body.kinds),
            visibility=body.visibility,
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
            "visibility": body.visibility,
            "untrusted_content": True,
        }

    @app.get("/v1/knowledge/changes")
    def knowledge_changes(
        principal: Annotated[
            Principal, Depends(require("knowledge.changes.read", assistant_source_aware=True))
        ],
        after: str | None = None,
        limit: Annotated[int, Query(ge=1, le=50)] = 25,
    ) -> dict[str, Any]:
        return knowledge.changes(principal.context, after=after, limit=limit)

    @app.get("/v1/knowledge/timeline")
    def knowledge_timeline(
        body: Annotated[TimelineRequest, Query()],
        principal: Annotated[
            Principal, Depends(require("knowledge.search", assistant_source_aware=True))
        ],
    ) -> dict[str, Any]:
        try:
            return knowledge.timeline(principal.context, body)
        except ValueError:
            raise HTTPException(422, "invalid_timeline") from None

    @app.get("/v1/knowledge/commitments-due")
    def knowledge_commitments_due(
        body: Annotated[DueCommitmentsRequest, Query()],
        principal: Annotated[
            Principal, Depends(require("knowledge.search", assistant_source_aware=True))
        ],
    ) -> dict[str, Any]:
        try:
            return knowledge.commitments_due(principal.context, body)
        except ValueError:
            raise HTTPException(422, "invalid_due_commitments") from None

    @app.post("/v1/knowledge/projects/{project_id}/artifacts", status_code=201)
    def publish_project_artifact(
        project_id: str,
        body: ProjectArtifactLinkWrite,
        principal: Annotated[Principal, Depends(require("knowledge.review", human=True))],
        idempotency_key: Annotated[UUID, Header()],
    ) -> dict[str, Any]:
        try:
            return project_artifacts.publish(
                principal.context, project_id, body, idempotency_key,
            )
        except ValueError:
            raise HTTPException(422, "invalid_project_artifact") from None

    @app.get("/v1/knowledge/projects/{project_id}/artifacts")
    def page_project_artifacts(
        project_id: str,
        body: Annotated[ProjectArtifactPageRequest, Query()],
        principal: Annotated[
            Principal, Depends(require("knowledge.search", assistant_source_aware=True))
        ],
    ) -> dict[str, Any]:
        try:
            return project_artifacts.page(principal.context, project_id, body)
        except ValueError:
            raise HTTPException(422, "invalid_project_artifact_page") from None

    @app.get("/v1/knowledge/projects/{project_id}/dossier")
    def knowledge_project_dossier(
        project_id: str,
        body: Annotated[ProjectDossierRequest, Query()],
        principal: Annotated[
            Principal, Depends(require("knowledge.search", assistant_source_aware=True))
        ],
    ) -> dict[str, Any]:
        try:
            return knowledge.project_dossier(principal.context, project_id, body)
        except ValueError:
            raise HTTPException(422, "invalid_project_dossier") from None

    @app.get("/v1/knowledge/projects/resolve")
    def knowledge_project_alias_lookup(
        body: Annotated[ProjectAliasLookupRequest, Query()],
        principal: Annotated[
            Principal, Depends(require("knowledge.search", assistant_source_aware=True))
        ],
    ) -> dict[str, Any]:
        try:
            return knowledge.resolve_project_alias(
                principal.context, body.name, limit=body.limit,
            )
        except ValueError:
            raise HTTPException(422, "invalid_project_resolution") from None

    @app.get("/v1/knowledge/statement-proposals/{proposal_id}")
    def knowledge_statement_proposal(
        proposal_id: str,
        principal: Annotated[Principal, Depends(require("knowledge.read", human=True))],
        after: Annotated[int, Query(ge=-1, le=1999)] = -1,
        limit: Annotated[int, Query(ge=1, le=25)] = 25,
    ) -> dict[str, Any]:
        if "brain.content.read" not in principal.context.scopes:
            raise HTTPException(403, "scope_denied")
        return statement_proposals.read_page(
            principal.context, proposal_id, after=after, limit=limit
        )

    @app.get("/v1/knowledge/{kind}/{object_id}")
    def knowledge_object(
        kind: str,
        object_id: str,
        principal: Annotated[
            Principal, Depends(require("knowledge.read", assistant_source_aware=True))
        ],
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
