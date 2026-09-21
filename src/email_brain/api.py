"""Bootstrap REST service and owner review screen; no mailbox effects or inference tools."""

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

from email_brain.auth import Principal, TokenRegistry
from email_brain.rules.control import RuleControl
from email_brain.schemas import (
    ProposalRequest,
    ReviewRequest,
    RuleActivationRequest,
    RuleRollbackRequest,
    RuleSimulationRequest,
    SearchRequest,
)
from email_brain.store import AccessDenied, Conflict, NotFound, Store

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


def create_app(store: Store, registry: TokenRegistry) -> FastAPI:
    app = FastAPI(
        title="Email Brain — local prototype", version="0.1.0", docs_url=None, redoc_url=None
    )
    app.add_middleware(BodyLimit)
    bearer = HTTPBearer(auto_error=False)
    rule_control = RuleControl(store)

    def require(scope: str, *, human: bool = False) -> Callable[..., Principal]:
        def dependency(
            request: Request,
            credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
        ) -> Principal:
            principal = registry.authenticate(credentials.credentials) if credentials else None
            if principal is None:
                raise HTTPException(
                    401, "invalid_or_expired_credential", headers={"WWW-Authenticate": "Bearer"}
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

    @app.get("/style.css", include_in_schema=False)
    def stylesheet() -> FileResponse:
        return FileResponse(WEB / "style.css", media_type="text/css")

    @app.post("/v1/search")
    def search(
        body: SearchRequest, principal: Annotated[Principal, Depends(require("email.search"))]
    ) -> dict[str, Any]:
        return {
            "mode": "lexical",
            "untrusted_content": True,
            "results": store.search(principal.context, body),
        }

    @app.get("/v1/accounts/{account_id}/quarantine")
    def quarantine(
        account_id: UUID,
        principal: Annotated[Principal, Depends(require("email.evidence.read"))],
        after: UUID | None = None,
        limit: Annotated[int, Query(ge=1, le=50)] = 50,
    ) -> dict[str, Any]:
        return store.quarantines(principal.context, account_id, after=after, limit=limit)

    @app.get("/v1/accounts/{account_id}/sync-status")
    def sync_status(
        account_id: UUID, principal: Annotated[Principal, Depends(require("email.search"))]
    ) -> dict[str, Any]:
        return store.sync_status(principal.context, account_id)

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
