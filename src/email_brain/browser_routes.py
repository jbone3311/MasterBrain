"""Closed browser-cookie boundary over the existing authorized REST service."""

from urllib.parse import urlsplit

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response

from email_brain.auth import Principal
from email_brain.browser_auth import FLOW_COOKIE, SESSION_COOKIE, BrowserAuth, BrowserDenied


def browser_cookie(request: Request, name: str) -> str | None:
    headers = request.headers.getlist("cookie")
    if len(headers) > 1 or sum(map(len, headers)) > 8192:
        raise BrowserDenied()
    values = []
    for header in headers:
        for part in header.split(";"):
            key, separator, value = part.strip().partition("=")
            if key == name:
                if not separator:
                    raise BrowserDenied()
                values.append(value)
    if len(values) > 1:
        raise BrowserDenied()
    return values[0] if values else None


def browser_guard(
    request: Request, auth: BrowserAuth, *, unsafe: bool = False, callback: bool = False
) -> str:
    if request.headers.getlist("host") != [urlsplit(auth.config.public_origin).netloc]:
        raise HTTPException(403, "browser_request_denied")
    origins = request.headers.getlist("origin")
    if (origins and origins != [auth.config.public_origin]) or (unsafe and not origins):
        raise HTTPException(403, "browser_request_denied")
    sites = request.headers.getlist("sec-fetch-site")
    allowed_sites = {"same-origin", "none"}
    if callback:
        allowed_sites |= {"same-site", "cross-site"}
    if len(sites) > 1 or (sites and sites[0] not in allowed_sites):
        raise HTTPException(403, "browser_request_denied")
    if unsafe:
        csrf = request.headers.getlist("x-csrf-token")
        if len(csrf) != 1 or not csrf[0]:
            raise HTTPException(403, "browser_request_denied")
        return csrf[0]
    return ""


def browser_principal(request: Request, auth: BrowserAuth) -> Principal:
    if request.headers.getlist("authorization"):
        raise BrowserDenied()
    unsafe = request.method not in {"GET", "HEAD", "OPTIONS"}
    csrf = browser_guard(request, auth, unsafe=unsafe)
    cookie = browser_cookie(request, SESSION_COOKIE)
    if cookie is None:
        raise BrowserDenied()
    return auth.authenticate(cookie, csrf=csrf if unsafe else None).principal


def _cookie(response: Response, name: str, value: str, *, flow: bool = False) -> None:
    response.set_cookie(
        name,
        value,
        max_age=300 if flow else 3600,
        path="/",
        secure=True,
        httponly=True,
        samesite="lax" if flow else "strict",
    )


def _clear(response: Response, name: str, *, flow: bool = False) -> None:
    response.delete_cookie(
        name, path="/", secure=True, httponly=True, samesite="lax" if flow else "strict"
    )


def browser_router(auth: BrowserAuth) -> APIRouter:
    router = APIRouter()

    def request_guard(request: Request, *, unsafe: bool = False, callback: bool = False) -> str:
        if request.headers.getlist("authorization"):
            raise BrowserDenied()
        return browser_guard(request, auth, unsafe=unsafe, callback=callback)

    @router.get("/auth/session")
    def session(request: Request) -> JSONResponse:
        request_guard(request)
        cookie = browser_cookie(request, SESSION_COOKIE)
        if cookie is not None:
            try:
                current = auth.authenticate(cookie)
            except BrowserDenied:
                pass
            else:
                return JSONResponse(
                    {
                        "mode": "browser",
                        "authenticated": True,
                        "csrf_token": current.csrf,
                        "expires_at": int(current.absolute_expiry),
                    }
                )
        flow, csrf = auth.prepare(browser_cookie(request, FLOW_COOKIE))
        response = JSONResponse(
            {
                "mode": "browser",
                "authenticated": False,
                "csrf_token": csrf,
                "expires_at": None,
            }
        )
        _cookie(response, FLOW_COOKIE, flow, flow=True)
        _clear(response, SESSION_COOKIE)
        return response

    @router.post("/auth/login")
    def login(request: Request) -> JSONResponse:
        csrf = request_guard(request, unsafe=True)
        flow = browser_cookie(request, FLOW_COOKIE)
        if flow is None:
            raise BrowserDenied()
        url = auth.start(flow, csrf, browser_cookie(request, SESSION_COOKIE))
        return JSONResponse({"authorization_url": url})

    @router.get("/auth/callback")
    def callback(request: Request) -> RedirectResponse:
        request_guard(request, callback=True)
        flow = browser_cookie(request, FLOW_COOKIE)
        if len(request.scope.get("query_string", b"")) > 8192:
            auth.discard_flow(flow)
            raise BrowserDenied()
        pairs = list(request.query_params.multi_items())
        if len(pairs) != len(dict(pairs)):
            auth.discard_flow(flow)
            raise BrowserDenied()
        if flow is None:
            raise BrowserDenied()
        cookie = auth.finish(flow, dict(pairs))
        response = RedirectResponse("/", status_code=303)
        _cookie(response, SESSION_COOKIE, cookie)
        _clear(response, FLOW_COOKIE, flow=True)
        return response

    @router.post("/auth/logout")
    def logout(request: Request) -> Response:
        csrf = request_guard(request, unsafe=True)
        cookie = browser_cookie(request, SESSION_COOKIE)
        if cookie is None:
            raise BrowserDenied()
        flow = browser_cookie(request, FLOW_COOKIE)
        auth.logout(cookie, csrf)
        auth.discard_flow(flow)
        response = Response(status_code=204)
        _clear(response, SESSION_COOKIE)
        _clear(response, FLOW_COOKIE, flow=True)
        return response

    return router
