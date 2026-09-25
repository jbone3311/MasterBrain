"""Bounded access-token resource server. No login, enrollment or token persistence."""

from __future__ import annotations

import base64
import ipaddress
import json
import re
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlsplit
from uuid import UUID, uuid4

import httpx
import jwt
import psycopg
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from email_brain.auth import AuthenticationUnavailable, Principal
from email_brain.domain.models import ExternalIdentity, TenantContext
from email_brain.processing_controller import private_bytes
from email_brain.store import AccessDenied, Store


def _text(value: Any, limit: int = 512) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value.encode("utf-8")) > limit
        or not value.isprintable()
        or value != value.strip()
    ):
        raise ValueError("invalid bounded text")
    return value


def _url(value: str) -> str:
    _text(value, 1024)
    parsed = urlsplit(value)
    host = parsed.hostname or ""
    if (
        not value.isascii()
        or parsed.scheme != "https"
        or parsed.username is not None
        or parsed.password is not None
        or parsed.port not in {None, 443}
        or parsed.query
        or parsed.fragment
        or any(c in value for c in "\\%?#")
        or not re.fullmatch(r"[a-z0-9][a-z0-9.-]*[a-z0-9]", host)
        or parsed.netloc not in {host, host + ":443"}
        or "." not in host
        or host.endswith((".localhost", ".local", ".internal"))
        or any(part in {".", ".."} for part in parsed.path.split("/"))
        or "//" in parsed.path
    ):
        raise ValueError("invalid trusted URL")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        if all(c in "0123456789." for c in host):
            raise ValueError("ambiguous IP literal") from None
    else:
        if not address.is_global:
            raise ValueError("private IP literal")
    return value


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _constant(value: str) -> None:
    raise ValueError("nonfinite JSON")


def _object(raw: bytes) -> dict[str, Any]:
    value = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs, parse_constant=_constant)
    if not isinstance(value, dict) or len(value) > 128:
        raise ValueError("JSON object required")
    return value


def _decode(value: str, limit: int) -> bytes:
    if not value or len(value) > limit * 2 or not re.fullmatch(r"[A-Za-z0-9_-]+", value):
        raise ValueError("invalid base64url")
    raw = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    if len(raw) > limit or base64.urlsafe_b64encode(raw).decode().rstrip("=") != value:
        raise ValueError("noncanonical base64url")
    return raw


class OIDCConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=False)

    version: Literal[1]
    profile: Literal["rfc9068", "entra-v2"]
    issuer: str
    discovery_url: str
    jwks_url: str
    audience: str
    client_ids: tuple[str, ...] = Field(min_length=1, max_length=32)
    admission_scope: str = Field(pattern=r"^[A-Za-z0-9._:/-]{1,128}$")
    entra_tenant_id: UUID | None = None

    @field_validator("version", mode="before")
    @classmethod
    def integer_version(cls, value: Any) -> Any:
        if type(value) is not int:
            raise ValueError("integer version required")
        return value

    @model_validator(mode="after")
    def trust_boundary(self) -> OIDCConfig:
        for url in (self.issuer, self.discovery_url, self.jwks_url):
            _url(url)
        _text(self.audience)
        if len(set(self.client_ids)) != len(self.client_ids):
            raise ValueError("duplicate client IDs")
        for client in self.client_ids:
            _text(client)
            if client == self.audience:
                raise ValueError("API audience must differ from clients")
        if self.profile == "entra-v2":
            if self.entra_tenant_id is None:
                raise ValueError("fixed Entra tenant required")
            origin = "https://login.microsoftonline.com/"
            if self.issuer != f"{origin}{self.entra_tenant_id}/v2.0":
                raise ValueError("tenant-specific Entra issuer required")
            if self.discovery_url != self.issuer + "/.well-known/openid-configuration":
                raise ValueError("tenant-specific Entra metadata required")
            if not self.jwks_url.startswith(origin):
                raise ValueError("Entra key origin required")
            if str(UUID(self.audience)) != self.audience or any(
                str(UUID(client)) != client for client in self.client_ids
            ):
                raise ValueError("Entra API/client application UUIDs required")
        elif self.entra_tenant_id is not None:
            raise ValueError("Entra tenant only valid for Entra profile")
        return self

    @classmethod
    def from_file(cls, path: Path) -> OIDCConfig:
        return cls.model_validate(_object(private_bytes(path)))


@dataclass(frozen=True)
class VerifiedToken:
    issuer: str
    subject: str
    client_id: str
    expires_at: datetime


class AccessTokenVerifier:
    """One fixed trust configuration and bounded, atomically replaced signing-key cache."""

    def __init__(
        self,
        config: OIDCConfig,
        *,
        transport: httpx.BaseTransport | None = None,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self.config = config
        self._transport = transport
        self._clock = monotonic
        self._lock = threading.Lock()
        self._changed = threading.Condition(self._lock)
        self._refreshing = False
        self._keys: dict[str, RSAPublicKey] = {}
        self._expires = 0.0
        self._retry = 0.0
        self._failed = False

    def _fetch(self, client: httpx.Client, url: str, limit: int) -> dict[str, Any]:
        started = time.monotonic()
        with client.stream("GET", url, headers={"Accept-Encoding": "identity"}) as response:
            if (
                response.status_code != 200
                or response.headers.get("Content-Encoding", "identity").lower() != "identity"
            ):
                raise ValueError("invalid issuer response")
            length = response.headers.get("Content-Length")
            if length is not None and (not length.isdecimal() or int(length) > limit):
                raise ValueError("issuer response too large")
            data = bytearray()
            # Do not buffer up to a caller-selected chunk size: a slow drip could
            # otherwise postpone the elapsed-time check until that buffer fills.
            for chunk in response.iter_bytes():
                if len(data) + len(chunk) > limit or time.monotonic() - started > 10:
                    raise ValueError("issuer response limit")
                data.extend(chunk)
            if time.monotonic() - started > 10:
                raise ValueError("issuer response deadline exceeded")
            return _object(bytes(data))

    def _refresh(self) -> dict[str, RSAPublicKey]:
        with httpx.Client(
            transport=self._transport,
            trust_env=False,
            follow_redirects=False,
            timeout=httpx.Timeout(5, connect=2),
        ) as client:
            metadata = self._fetch(client, self.config.discovery_url, 131072)
            if (
                metadata.get("issuer") != self.config.issuer
                or metadata.get("jwks_uri") != self.config.jwks_url
            ):
                raise ValueError("metadata trust mismatch")
            document = self._fetch(client, self.config.jwks_url, 262144)
        entries = document.get("keys")
        if not isinstance(entries, list) or not 1 <= len(entries) <= 64:
            raise ValueError("invalid key set")
        keys: dict[str, RSAPublicKey] = {}
        seen: set[str] = set()
        for entry in entries:
            if not isinstance(entry, dict):
                raise ValueError("invalid key entry")
            kid = _text(entry.get("kid"), 256)
            if kid in seen:
                raise ValueError("duplicate key identifier")
            seen.add(kid)
            if entry.get("kty") != "RSA" or entry.get("use", "sig") != "sig":
                continue
            if entry.get("alg", "RS256") != "RS256":
                continue
            if entry.get("key_ops", ["verify"]) != ["verify"] or any(
                part in entry for part in ("d", "p", "q", "dp", "dq", "qi", "oth", "k")
            ):
                raise ValueError("not a public verification key")
            if self.config.profile == "entra-v2" and "issuer" in entry:
                key_issuer = _text(entry["issuer"], 1024).replace(
                    "{tenantid}", str(self.config.entra_tenant_id)
                )
                if key_issuer != self.config.issuer:
                    continue
            _decode(_text(entry.get("n"), 1024), 512)
            _decode(_text(entry.get("e"), 16), 8)
            key = jwt.algorithms.RSAAlgorithm.from_jwk(entry)
            if (
                not isinstance(key, RSAPublicKey)
                or not 2048 <= key.key_size <= 4096
                or key.public_numbers().e != 65537
            ):
                raise ValueError("unsupported RSA key")
            keys[kid] = key
        if not keys:
            raise ValueError("no supported signing keys")
        return keys

    def _key(self, kid: str) -> RSAPublicKey | None:
        with self._changed:
            now = self._clock()
            if now < self._expires and kid in self._keys:
                return self._keys[kid]
            if self._refreshing:
                if not self._changed.wait_for(lambda: not self._refreshing, timeout=5):
                    raise AuthenticationUnavailable() from None
                # A waiter uses the published result, never starts a second refresh.
                now = self._clock()
                if now < self._expires and kid in self._keys:
                    return self._keys[kid]
                if now >= self._expires or self._failed:
                    raise AuthenticationUnavailable() from None
                return None
            if now < self._retry:
                if now >= self._expires and self._failed:
                    raise AuthenticationUnavailable() from None
                return None
            self._retry = now + 30
            self._refreshing = True
        try:
            # Network I/O must not hold the cache lock: valid hits remain available.
            keys = self._refresh()
            with self._changed:
                self._keys = keys
                self._expires = self._clock() + 300
                self._failed = False
                return keys.get(kid)
        except (ValueError, TypeError, RecursionError, httpx.HTTPError, jwt.PyJWTError):
            with self._changed:
                self._failed = True
            raise AuthenticationUnavailable() from None
        finally:
            with self._changed:
                self._refreshing = False
                self._changed.notify_all()

    def verify(self, token: str) -> VerifiedToken | None:
        try:
            if not 1 <= len(token) <= 16384 or not token.isascii():
                return None
            header_part, payload_part, signature = token.split(".")
            header = _object(_decode(header_part, 2048))
            claims = _object(_decode(payload_part, 12288))
            _decode(signature, 512)
            if set(header) - {"alg", "kid", "typ", "x5t", "x5t#S256"}:
                return None
            typ = header.get("typ")
            accepted_types = (
                {"at+jwt", "application/at+jwt"} if self.config.profile == "rfc9068" else {"jwt"}
            )
            if header.get("alg") != "RS256" or not isinstance(typ, str):
                return None
            if typ.lower() not in accepted_types:
                return None
            kid = _text(header.get("kid"), 256)
            if claims.get("iss") != self.config.issuer or claims.get("aud") not in (
                self.config.audience,
                [self.config.audience],
            ):
                return None
            subject = _text(claims.get("sub"))
            now = time.time()
            issued, expires = claims.get("iat"), claims.get("exp")
            if type(issued) is not int or type(expires) is not int:
                return None
            if not 0 < issued <= now < expires <= issued + 7200:
                return None
            if "nbf" in claims and (
                type(claims["nbf"]) is not int
                or not 0 <= claims["nbf"] <= now
                or claims["nbf"] >= expires
            ):
                return None
            if self.config.profile == "entra-v2":
                if (
                    claims.get("ver") != "2.0"
                    or claims.get("tid") != str(self.config.entra_tenant_id)
                    or "nbf" not in claims
                    or claims.get("idtyp") == "app"
                ):
                    return None
                client_id, scope = claims.get("azp"), claims.get("scp")
            else:
                _text(claims.get("jti"))
                client_id, scope = claims.get("client_id"), claims.get("scope")
            client_id = _text(client_id)
            if client_id not in self.config.client_ids:
                return None
            scopes = _text(scope, 4096).split(" ")
            if self.config.admission_scope not in scopes or "" in scopes:
                return None
            key = self._key(kid)
            if key is None:
                return None
            # Actual RSA key, never PyJWK; algorithm policy is not token-selected.
            jwt.decode(
                token,
                key,
                algorithms=["RS256"],
                issuer=self.config.issuer,
                audience=self.config.audience,
                options={"require": ["iss", "sub", "aud", "exp", "iat"]},
            )
            return VerifiedToken(
                self.config.issuer, subject, client_id, datetime.fromtimestamp(expires, UTC)
            )
        except (ValueError, TypeError, RecursionError, jwt.PyJWTError):
            return None


class OIDCAuthenticator:
    def __init__(self, store: Store, verifier: AccessTokenVerifier) -> None:
        self.store, self.verifier = store, verifier

    def resolve(self, verified: VerifiedToken) -> Principal | None:
        """Trusted-service entry point only; no API accepts a VerifiedToken object."""
        try:
            with self.store.connection() as conn:
                binding = self.store.resolve_identity(
                    conn, verified.issuer, verified.subject, verified.client_id
                )
            if binding is None:
                return None
            identity = ExternalIdentity(
                binding["id"],
                verified.issuer,
                verified.subject,
                verified.client_id,
                binding["revision"],
                binding["client_kind"],
                verified.expires_at,
            )
            ctx = TenantContext(
                binding["tenant_id"],
                binding["actor_id"],
                frozenset(binding["scopes"]),
                uuid4(),
                identity,
            )
            with self.store.transaction(ctx):
                pass
            return Principal(ctx, binding["client_kind"])
        except AccessDenied:
            return None
        except psycopg.Error:
            raise AuthenticationUnavailable() from None

    def authenticate(self, token: str) -> Principal | None:
        verified = self.verifier.verify(token)
        return self.resolve(verified) if verified else None
