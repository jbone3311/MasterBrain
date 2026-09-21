"""Single-process, server-side delegated API sessions; no ID/refresh-token login."""

from __future__ import annotations

import base64
import hashlib
import hmac
import re
import secrets
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlencode, urlsplit

import httpx
import psycopg
from pydantic import BaseModel, ConfigDict, SecretStr, field_validator, model_validator

from email_brain.auth import AuthenticationUnavailable, Principal
from email_brain.oidc import OIDCAuthenticator, OIDCConfig, _object, _text, _url
from email_brain.processing_controller import private_bytes
from email_brain.store import AccessDenied

SESSION_COOKIE = "__Host-emailbrain-session"
FLOW_COOKIE = "__Host-emailbrain-flow"


class BrowserDenied(Exception):
    """Invalid or expired browser authority; never include caller data."""


def _opaque(value: str) -> bool:
    return re.fullmatch(r"[A-Za-z0-9_-]{43}", value) is not None


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("ascii")).hexdigest()


class BrowserConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    version: Literal[1]
    identity: OIDCConfig
    public_origin: str
    authorization_endpoint: str
    token_endpoint: str
    client_id: str
    client_secret: SecretStr
    scopes: tuple[str, ...]

    @field_validator("version", mode="before")
    @classmethod
    def integer_version(cls, value: Any) -> Any:
        if type(value) is not int:
            raise ValueError("integer version required")
        return value

    @model_validator(mode="after")
    def boundaries(self) -> BrowserConfig:
        origin = urlsplit(self.public_origin)
        if (
            origin.scheme != "https"
            or origin.path
            or origin.query
            or origin.fragment
            or origin.username is not None
            or origin.password is not None
            or not origin.hostname
            or not self.public_origin.isascii()
            or origin.netloc != origin.netloc.lower()
            or origin.port == 443
            or self.public_origin != "https://" + origin.netloc
        ):
            raise ValueError("exact HTTPS browser origin required")
        # Explicit loopback TLS is allowed for browser acceptance; never for issuer URLs.
        if origin.hostname in {"localhost", "127.0.0.1"}:
            if origin.netloc not in {origin.hostname, f"{origin.hostname}:{origin.port}"}:
                raise ValueError("invalid loopback origin")
            if origin.port is not None and not 1 <= origin.port <= 65535:
                raise ValueError("invalid browser port")
        else:
            _url(self.public_origin)
        issuer = urlsplit(self.identity.issuer)
        for endpoint in (self.authorization_endpoint, self.token_endpoint):
            _url(endpoint)
            if urlsplit(endpoint).netloc != issuer.netloc:
                raise ValueError("fixed issuer origin required")
        if self.identity.profile == "entra-v2":
            root = f"https://login.microsoftonline.com/{self.identity.entra_tenant_id}"
            if (
                self.authorization_endpoint != root + "/oauth2/v2.0/authorize"
                or self.token_endpoint != root + "/oauth2/v2.0/token"
            ):
                raise ValueError("tenant-specific Entra endpoints required")
        if self.client_id not in self.identity.client_ids:
            raise ValueError("browser client must be an accepted API client")
        secret = self.client_secret.get_secret_value()
        if not 16 <= len(secret) <= 4096 or not secret.isascii() or not secret.isprintable():
            raise ValueError("invalid confidential client secret")
        if not 1 <= len(self.scopes) <= 8 or len(set(self.scopes)) != len(self.scopes):
            raise ValueError("bounded unique API scopes required")
        for scope in self.scopes:
            if not re.fullmatch(r"[A-Za-z0-9._:/-]{1,512}", scope) or scope.casefold() in {
                "openid",
                "profile",
                "email",
                "offline_access",
            }:
                raise ValueError("API scopes only; no ID or refresh tokens")
        return self

    @property
    def redirect_uri(self) -> str:
        return self.public_origin + "/auth/callback"

    @classmethod
    def from_file(cls, path: Path) -> BrowserConfig:
        try:
            return cls.model_validate(_object(private_bytes(path)))
        except (ValueError, OSError, RecursionError):
            raise ValueError("invalid private browser configuration") from None


@dataclass(frozen=True)
class _Flow:
    csrf: str
    deadline: float
    state: str | None = None
    verifier: str | None = None
    previous_session: str | None = None
    claimed: bool = False


@dataclass(frozen=True)
class BrowserSession:
    principal: Principal
    csrf: str
    absolute_expiry: float
    idle_expiry: float
    lifetime_expiry: float


class BrowserAuth:
    """Bounded process-local state. Restart invalidates all cookies and callbacks."""

    def __init__(
        self,
        config: BrowserConfig,
        authenticator: OIDCAuthenticator,
        *,
        transport: httpx.BaseTransport | None = None,
        monotonic: Callable[[], float] = time.monotonic,
        wall_clock: Callable[[], float] = time.time,
    ) -> None:
        if authenticator.verifier.config != config.identity:
            raise ValueError("browser and API trust configurations differ")
        self.config, self.authenticator = config, authenticator
        self._transport, self._clock, self._wall = transport, monotonic, wall_clock
        self._lock = threading.Lock()
        self._flows: dict[str, _Flow] = {}
        self._sessions: dict[str, BrowserSession] = {}

    def _prune(self) -> None:
        now, wall = self._clock(), self._wall()
        self._flows = {key: row for key, row in self._flows.items() if row.deadline > now}
        self._sessions = {
            key: row
            for key, row in self._sessions.items()
            if row.idle_expiry > now and row.lifetime_expiry > now and row.absolute_expiry > wall
        }

    def prepare(self, cookie: str | None) -> tuple[str, str]:
        with self._lock:
            self._prune()
            if cookie and _opaque(cookie):
                row = self._flows.get(_digest(cookie))
                if row is not None and row.state is None and not row.claimed:
                    return cookie, row.csrf
                self._flows.pop(_digest(cookie), None)
            if len(self._flows) >= 128:
                raise AuthenticationUnavailable()
            cookie, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
            self._flows[_digest(cookie)] = _Flow(csrf, self._clock() + 300)
            return cookie, csrf

    def start(self, cookie: str, csrf: str, previous_session: str | None) -> str:
        if not _opaque(cookie) or not _opaque(csrf):
            raise BrowserDenied()
        with self._lock:
            self._prune()
            key = _digest(cookie)
            row = self._flows.get(key)
            if row is None or row.state is not None or not hmac.compare_digest(row.csrf, csrf):
                raise BrowserDenied()
            state, verifier = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
            previous = (
                _digest(previous_session)
                if previous_session and _opaque(previous_session)
                else None
            )
            if previous not in self._sessions:
                previous = None
            self._flows[key] = replace(
                row, state=state, verifier=verifier, previous_session=previous
            )
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
        return (
            self.config.authorization_endpoint
            + "?"
            + urlencode(
                {
                    "client_id": self.config.client_id,
                    "redirect_uri": self.config.redirect_uri,
                    "response_type": "code",
                    "response_mode": "query",
                    "scope": " ".join(self.config.scopes),
                    "state": state,
                    "code_challenge": challenge.decode().rstrip("="),
                    "code_challenge_method": "S256",
                }
            )
        )

    def _exchange(self, code: str, verifier: str) -> Principal:
        started = self._clock()
        try:
            with httpx.Client(
                transport=self._transport,
                follow_redirects=False,
                trust_env=False,
                timeout=httpx.Timeout(5, connect=2),
            ) as client:
                with client.stream(
                    "POST",
                    self.config.token_endpoint,
                    headers={"Accept-Encoding": "identity", "Accept": "application/json"},
                    data={
                        "grant_type": "authorization_code",
                        "code": code,
                        "redirect_uri": self.config.redirect_uri,
                        "client_id": self.config.client_id,
                        "client_secret": self.config.client_secret.get_secret_value(),
                        "code_verifier": verifier,
                    },
                ) as response:
                    if response.status_code >= 500 or response.status_code == 429:
                        raise AuthenticationUnavailable()
                    if (
                        response.status_code != 200
                        or response.headers.get("Content-Encoding", "identity").lower()
                        != "identity"
                    ):
                        raise BrowserDenied()
                    body = bytearray()
                    for chunk in response.iter_bytes():
                        if self._clock() - started > 10:
                            raise AuthenticationUnavailable()
                        if len(body) + len(chunk) > 32768:
                            raise BrowserDenied()
                        body.extend(chunk)
                    if self._clock() - started > 10:
                        raise AuthenticationUnavailable()
                    data = _object(bytes(body))
            if (
                data.get("token_type", "").lower() != "bearer"
                or "refresh_token" in data
                or "id_token" in data
            ):
                raise BrowserDenied()
            token = data.get("access_token")
            if not isinstance(token, str):
                raise BrowserDenied()
            verified = self.authenticator.verifier.verify(token)
            if verified is None or verified.client_id != self.config.client_id:
                raise BrowserDenied()
            if "expires_in" in data:
                expires = data["expires_in"]
                if type(expires) is not int or not 1 <= expires <= 7200:
                    raise BrowserDenied()
                verified = replace(
                    verified,
                    expires_at=min(
                        verified.expires_at, datetime.fromtimestamp(self._wall() + expires, UTC)
                    ),
                )
            principal = self.authenticator.resolve(verified)
            if principal is None or principal.client_kind != "human":
                raise BrowserDenied()
            return principal
        except httpx.HTTPError:
            raise AuthenticationUnavailable() from None
        except (ValueError, TypeError, AttributeError, RecursionError):
            raise BrowserDenied() from None

    def finish(self, cookie: str, params: dict[str, str]) -> str:
        if not _opaque(cookie):
            raise BrowserDenied()
        # Atomically consume once, but retain a cancellable reservation during exchange.
        key = _digest(cookie)
        with self._lock:
            self._prune()
            row = self._flows.get(key)
            if row is None or row.claimed:
                raise BrowserDenied()
            row = replace(row, claimed=True)
            self._flows[key] = row
        try:
            return self._complete(key, row, params)
        finally:
            with self._lock:
                if self._flows.get(key) is row:
                    self._flows.pop(key)

    def _complete(self, key: str, row: _Flow, params: dict[str, str]) -> str:
        if row.state is None or row.verifier is None:
            raise BrowserDenied()
        state = params.get("state", "")
        if not _opaque(state) or not hmac.compare_digest(state, row.state):
            raise BrowserDenied()
        if set(params) - {"code", "state", "iss", "session_state"}:
            raise BrowserDenied()
        if "iss" in params and params["iss"] != self.config.identity.issuer:
            raise BrowserDenied()
        try:
            code = _text(params.get("code"), 4096)
            if not code.isascii():
                raise ValueError("invalid authorization code")
        except (ValueError, TypeError):
            raise BrowserDenied() from None
        principal = self._exchange(code, row.verifier)
        identity = principal.context.identity
        if identity is None:
            raise BrowserDenied()
        with self._lock:
            self._prune()
            wall = self._wall()
            expiry = min(wall + 3600, identity.expires_at.timestamp())
            if self._flows.get(key) is not row or row.deadline <= self._clock() or expiry <= wall:
                raise BrowserDenied()
            if row.previous_session and row.previous_session not in self._sessions:
                raise BrowserDenied()
            if len(self._sessions) >= 1024 and row.previous_session not in self._sessions:
                raise AuthenticationUnavailable()
            cookie = secrets.token_urlsafe(32)
            self._sessions[_digest(cookie)] = BrowserSession(
                principal,
                secrets.token_urlsafe(32),
                expiry,
                self._clock() + 900,
                self._clock() + expiry - wall,
            )
            if row.previous_session:
                self._sessions.pop(row.previous_session, None)
            return cookie

    def authenticate(self, cookie: str, *, csrf: str | None = None) -> BrowserSession:
        if not _opaque(cookie):
            raise BrowserDenied()
        key = _digest(cookie)
        with self._lock:
            self._prune()
            row = self._sessions.get(key)
        if row is None:
            raise BrowserDenied()
        if csrf is not None and (not _opaque(csrf) or not hmac.compare_digest(row.csrf, csrf)):
            raise BrowserDenied()
        try:
            with self.authenticator.store.transaction(row.principal.context):
                pass
        except AccessDenied:
            with self._lock:
                self._sessions.pop(key, None)
            raise BrowserDenied() from None
        except psycopg.Error:
            raise AuthenticationUnavailable() from None
        with self._lock:
            self._prune()
            current = self._sessions.get(key)
            if current is None or current.principal is not row.principal:
                raise BrowserDenied()
            # Preserve identity/revision and absolute expiry; only successful use extends idle.
            renewed = replace(row, idle_expiry=self._clock() + 900)
            self._sessions[key] = renewed
            return renewed

    def logout(self, cookie: str, csrf: str) -> None:
        if not _opaque(cookie) or not _opaque(csrf):
            raise BrowserDenied()
        with self._lock:
            self._prune()
            key = _digest(cookie)
            row = self._sessions.get(key)
            if row is None or not hmac.compare_digest(row.csrf, csrf):
                raise BrowserDenied()
            self._sessions.pop(key)

    def discard_flow(self, cookie: str | None) -> None:
        if cookie and _opaque(cookie):
            with self._lock:
                self._flows.pop(_digest(cookie), None)
