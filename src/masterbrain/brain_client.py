"""Provider-neutral, read-only transport for the scoped Brain API.

This is a reference client, not a hosted assistant integration. Every returned
excerpt and content field remains untrusted source data.
"""

from __future__ import annotations

import json
import re
from typing import Any

import httpx
from pydantic import ValidationError

from masterbrain.schemas import CurrentGroupedSearchRequest, EvidenceContentRequest

MAX_RESPONSE_BYTES = 262_144
_IDENTITY = re.compile(r"^[a-z][a-z0-9_-]{0,127}$")
_CURRENT_LAYERS = frozenset(
    {
        "fileos",
        "archive_members",
        "archive_documents",
        "archive_images",
        "email_messages",
        "email_attachments",
        "email_documents",
        "knowledge",
    }
)


class BrainClientError(RuntimeError):
    """A fixed-code failure that never includes credentials or source content."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class BrainReadClient:
    """Use only the current, progressive, read-only Brain API routes."""

    def __init__(
        self,
        base_url: str,
        bearer_token: str,
        *,
        allow_insecure_loopback: bool = False,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        try:
            origin = httpx.URL(base_url)
        except (TypeError, ValueError):
            raise BrainClientError("invalid_origin") from None
        if (
            origin.host is None
            or origin.username
            or origin.password
            or origin.path not in ("", "/")
            or origin.query
            or origin.fragment
            or (
                origin.scheme != "https"
                and not (
                    allow_insecure_loopback
                    and origin.scheme == "http"
                    and origin.host in {"127.0.0.1", "::1"}
                )
            )
        ):
            raise BrainClientError("invalid_origin")
        if (
            not isinstance(bearer_token, str)
            or not 1 <= len(bearer_token) <= 8192
            or not bearer_token.isascii()
            or any(ord(character) < 33 or ord(character) > 126 for character in bearer_token)
        ):
            raise BrainClientError("invalid_credential")
        self._token = bearer_token
        self._closed = False
        self._http = httpx.Client(
            base_url=str(origin),
            transport=transport,
            timeout=httpx.Timeout(15.0, connect=5.0),
            follow_redirects=False,
            trust_env=False,
            headers={"Accept": "application/json", "Cache-Control": "no-store"},
        )

    def __enter__(self) -> BrainReadClient:
        if self._closed:
            raise BrainClientError("client_closed")
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def close(self) -> None:
        if not self._closed:
            self._closed = True
            self._token = ""
            self._http.close()

    def _request(
        self, method: str, path: str, body: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        if self._closed:
            raise BrainClientError("client_closed")
        self._http.cookies.clear()
        try:
            with self._http.stream(
                method,
                path,
                json=body,
                headers={"Authorization": f"Bearer {self._token}"},
                follow_redirects=False,
            ) as response:
                if response.status_code != 200:
                    if response.status_code in (401, 403):
                        raise BrainClientError("access_denied")
                    if response.status_code == 404:
                        raise BrainClientError("not_found")
                    if response.status_code == 429:
                        raise BrainClientError("rate_limited")
                    if response.status_code >= 500:
                        raise BrainClientError("service_unavailable")
                    raise BrainClientError("request_failed")
                if response.headers.get("content-type", "").split(";", 1)[0].strip().lower() != (
                    "application/json"
                ):
                    raise BrainClientError("invalid_response")
                raw = bytearray()
                for chunk in response.iter_bytes():
                    if len(raw) + len(chunk) > MAX_RESPONSE_BYTES:
                        raise BrainClientError("response_too_large")
                    raw.extend(chunk)
                try:
                    data: Any = json.loads(raw)
                except (UnicodeDecodeError, json.JSONDecodeError):
                    raise BrainClientError("invalid_response") from None
                if not isinstance(data, dict):
                    raise BrainClientError("invalid_response")
                return data
        except httpx.TimeoutException:
            raise BrainClientError("timeout") from None
        except httpx.HTTPError:
            raise BrainClientError("transport_error") from None
        finally:
            self._http.cookies.clear()

    def current_search(self, query: str) -> dict[str, Any]:
        """Return grouped current evidence; ranks are only comparable within a layer."""
        if not isinstance(query, str) or not query.strip() or "\x00" in query:
            raise BrainClientError("invalid_request")
        try:
            request = CurrentGroupedSearchRequest(query=query)
        except ValidationError:
            raise BrainClientError("invalid_request") from None
        data = self._request(
            "POST", "/v1/brain/current-search", request.model_dump(mode="json")
        )
        layers = data.get("layers")
        coverage = data.get("coverage")
        if (
            data.get("mode") != "grouped_current_sources"
            or data.get("ranking") != "within_group_only"
            or data.get("consistency") != "independent_layer_reads"
            or data.get("untrusted_content") is not True
            or not isinstance(layers, dict)
            or not _CURRENT_LAYERS.issubset(layers)
            or any(
                not isinstance(layers[name], list)
                or len(layers[name]) > 20
                or any(not isinstance(hit, dict) for hit in layers[name])
                for name in _CURRENT_LAYERS
            )
            or not isinstance(coverage, dict)
            or coverage.get("complete") is not False
        ):
            raise BrainClientError("invalid_response")
        return data

    def evidence(self, evidence_id: str) -> dict[str, Any]:
        """Expand selected evidence metadata only with the distinct server grant."""
        self._validate_id(evidence_id)
        data = self._request("GET", f"/v1/brain/evidence/{evidence_id}")
        if data.get("id") != evidence_id or not isinstance(data.get("source_kind"), str):
            raise BrainClientError("invalid_response")
        return data

    def evidence_content(self, evidence_id: str, *, max_chars: int = 4000) -> dict[str, Any]:
        """Expand bounded extracted text only with the distinct server grant."""
        self._validate_id(evidence_id)
        try:
            request = EvidenceContentRequest(max_chars=max_chars)
        except ValidationError:
            raise BrainClientError("invalid_request") from None
        data = self._request(
            "POST",
            f"/v1/brain/evidence/{evidence_id}/content",
            request.model_dump(mode="json"),
        )
        if (
            data.get("evidence_id") != evidence_id
            or not isinstance(data.get("content"), str)
            or len(data["content"]) > max_chars
            or not isinstance(data.get("truncated"), bool)
        ):
            raise BrainClientError("invalid_response")
        return data

    def current_coverage(
        self, *, after: str | None = None, limit: int = 25
    ) -> dict[str, Any]:
        """Return only the caller's enrolled source coverage, with bounded paging."""
        return self._status_page("current-coverage", after=after, limit=limit)

    def changes(self, *, after: str | None = None, limit: int = 25) -> dict[str, Any]:
        """Return only changes in enrolled sources, with bounded paging."""
        return self._status_page("changes", after=after, limit=limit)

    def _status_page(
        self, route: str, *, after: str | None, limit: int
    ) -> dict[str, Any]:
        if after is not None:
            self._validate_id(after)
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 50:
            raise BrainClientError("invalid_request")
        query = httpx.QueryParams({"limit": limit, **({"after": after} if after else {})})
        data = self._request("GET", f"/v1/brain/{route}?{query}")
        results = data.get("results")
        cursor = data.get("next_cursor")
        if (
            data.get("limit") != limit
            or not isinstance(results, list)
            or len(results) > limit
            or any(
                not isinstance(row, dict)
                or not isinstance(row.get("source_id"), str)
                or not _IDENTITY.fullmatch(row["source_id"])
                for row in results
            )
            or (
                cursor is not None
                and (not isinstance(cursor, str) or not _IDENTITY.fullmatch(cursor))
            )
            or (route == "current-coverage" and data.get("complete") is not False)
        ):
            raise BrainClientError("invalid_response")
        return data

    @staticmethod
    def _validate_id(evidence_id: str) -> None:
        if not isinstance(evidence_id, str) or not _IDENTITY.fullmatch(evidence_id):
            raise BrainClientError("invalid_request")
