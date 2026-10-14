"""Provider-neutral, read-only transport for the scoped Brain API.

This is a reference client, not a hosted assistant integration. Every returned
excerpt and content field remains untrusted source data.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any

import httpx
from pydantic import ValidationError

from masterbrain.knowledge_schema import (
    DueCommitmentsRequest,
    KnowledgeVisibility,
    ProjectAliasLookupRequest,
    ProjectDossierRequest,
    TimelineRequest,
    normalize_project_alias,
)
from masterbrain.schemas import (
    MAX_ANSWER_TEXT_BYTES,
    CurrentGroupedSearchRequest,
    EvidenceContentRequest,
    GroundedAnswerRequest,
    SourceFocus,
)

MAX_RESPONSE_BYTES = 262_144
_IDENTITY = re.compile(r"^[a-z][a-z0-9_-]{0,127}$")
_EVENT_ID = re.compile(r"^event_[a-f0-9]{32}$")
_COMMITMENT_ID = re.compile(r"^commitment_[a-f0-9]{32}$")
_ENTITY_ID = re.compile(r"^entity_[a-f0-9]{32}$")
_PROJECT_ID = re.compile(r"^project_[a-f0-9]{32}$")
_EVIDENCE_ID = re.compile(r"^evidence_[a-f0-9]{32}$")
_EVENT_TYPE = re.compile(r"^[a-z][a-z0-9_.-]{0,99}$")
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
_FOCUS_LAYERS = {
    "all": _CURRENT_LAYERS,
    "email": frozenset({"email_messages", "email_attachments", "email_documents"}),
    "fileos": frozenset({
        "fileos", "archive_members", "archive_documents", "archive_images",
    }),
}


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

    def current_search(
        self, query: str, *, source_focus: SourceFocus = "all"
    ) -> dict[str, Any]:
        """Return grouped current evidence; ranks are only comparable within a layer."""
        if not isinstance(query, str) or not query.strip() or "\x00" in query:
            raise BrainClientError("invalid_request")
        try:
            request = CurrentGroupedSearchRequest(query=query, source_focus=source_focus)
        except ValidationError:
            raise BrainClientError("invalid_request") from None
        payload = request.model_dump(mode="json")
        if source_focus == "all":
            payload.pop("source_focus")  # Keep default calls compatible with older servers.
        data = self._request(
            "POST", "/v1/brain/current-search", payload
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
            or coverage.get("source_focus", "all") != source_focus
            or any(layers[name] for name in _CURRENT_LAYERS - _FOCUS_LAYERS[source_focus])
        ):
            raise BrainClientError("invalid_response")
        return data

    def answer(
        self, question: str, *, source_focus: SourceFocus = "all"
    ) -> dict[str, Any]:
        """Ask for server-verified current evidence quotes, never model tools."""
        try:
            request = GroundedAnswerRequest(question=question, source_focus=source_focus)
        except ValidationError:
            raise BrainClientError("invalid_request") from None
        payload = request.model_dump(mode="json")
        if source_focus == "all":
            payload.pop("source_focus")
        data = self._request(
            "POST", "/v1/brain/answers", payload
        )
        citations = data.get("citations")
        reviewed = data.get("reviewed_knowledge", [])
        coverage = data.get("coverage")
        if (
            data.get("mode") != "grounded_extractive_v1"
            or data.get("status") not in {
                "quoted_evidence", "no_supported_evidence", "no_supported_answer"
            }
            or not isinstance(data.get("answer"), str)
            or len(data["answer"]) > 200
            or data.get("untrusted_content") is not True
            or not isinstance(coverage, dict)
            or coverage.get("complete") is not False
            or not isinstance(coverage.get("answer_context_truncated", False), bool)
            or not isinstance(coverage.get("answer_output_truncated", False), bool)
            or coverage.get("source_focus", "all") != source_focus
            or not isinstance(citations, list)
            or len(citations) > 4
            or any(not self._valid_quote_citation(item) for item in citations)
            or (
                source_focus != "all"
                and any(item["source_kind"] != source_focus for item in citations)
            )
            or not isinstance(reviewed, list)
            or len(reviewed) > 4
            or any(not self._valid_reviewed_knowledge(item) for item in reviewed)
            or (source_focus != "all" and bool(reviewed))
            or (data["status"] == "quoted_evidence") != bool(citations)
            or not self._within_answer_text_budget(citations, reviewed)
        ):
            raise BrainClientError("invalid_response")
        return data

    @staticmethod
    def _within_answer_text_budget(
        citations: list[dict[str, Any]], reviewed: list[dict[str, Any]]
    ) -> bool:
        try:
            size = sum(len(item["quote"].encode("utf-8")) for item in citations)
            size += sum(
                len(item["title"].encode("utf-8"))
                + len(item["excerpt"].encode("utf-8")) for item in reviewed
            )
        except UnicodeEncodeError:
            return False
        return size <= MAX_ANSWER_TEXT_BYTES

    @staticmethod
    def _valid_reviewed_knowledge(item: Any) -> bool:
        if not isinstance(item, dict):
            return False
        kind = item.get("object_kind")
        evidence_ids = item.get("evidence_ids")
        count = item.get("linked_evidence_count")
        if not isinstance(kind, str) or not isinstance(evidence_ids, list):
            return False
        if not all(isinstance(value, str) for value in evidence_ids):
            return False
        return bool(
            kind in {
                "entity", "relationship", "claim", "event", "project", "commitment",
                "member", "correction",
            }
            and isinstance(item.get("object_id"), str)
            and re.fullmatch(rf"{kind}_[a-f0-9]{{32}}", item["object_id"])
            and isinstance(item.get("title"), str)
            and 1 <= len(item["title"]) <= 300
            and "\x00" not in item["title"]
            and isinstance(item.get("excerpt"), str)
            and 1 <= len(item["excerpt"]) <= 1200
            and "\x00" not in item["excerpt"]
            and 1 <= len(evidence_ids) <= 5
            and len(set(evidence_ids)) == len(evidence_ids)
            and all(
                isinstance(value, str) and re.fullmatch(r"evidence_[a-f0-9]{32}", value)
                for value in evidence_ids
            )
            and type(count) is int
            and len(evidence_ids) <= count <= 20
        )

    @staticmethod
    def _valid_quote_citation(item: Any) -> bool:
        if not isinstance(item, dict):
            return False
        ids = ("evidence_id", "document_id", "source_id")
        return bool(
            all(isinstance(item.get(key), str) and _IDENTITY.fullmatch(item[key]) for key in ids)
            and isinstance(item.get("source_kind"), str)
            and isinstance(item.get("quote"), str)
            and 1 <= len(item["quote"]) <= 400
            and type(item.get("start")) is int
            and type(item.get("end")) is int
            and item["start"] >= 0
            and item["end"] - item["start"] == len(item["quote"])
            and isinstance(item.get("body_sha256"), str)
            and re.fullmatch(r"[a-f0-9]{64}", item["body_sha256"])
        )

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

    def timeline(
        self,
        start: datetime,
        end: datetime,
        *,
        project_id: str | None = None,
        visibility: KnowledgeVisibility = "unsuperseded",
        limit: int = 25,
        recorded_cutoff_at: datetime | None = None,
        after: str | None = None,
    ) -> dict[str, Any]:
        """Page reviewed event occurrences; every title remains untrusted data."""
        try:
            request = TimelineRequest.model_validate({
                "start": start, "end": end, "project_id": project_id,
                "visibility": visibility, "limit": limit,
                "recorded_cutoff_at": recorded_cutoff_at, "after": after,
            })
        except ValidationError:
            raise BrainClientError("invalid_request") from None
        if (
            type(limit) is not int
            or not isinstance(start, datetime)
            or not isinstance(end, datetime)
        ):
            raise BrainClientError("invalid_request")
        if recorded_cutoff_at is not None and not isinstance(recorded_cutoff_at, datetime):
            raise BrainClientError("invalid_request")
        query = httpx.QueryParams(request.model_dump(mode="json", exclude_none=True))
        data = self._request("GET", f"/v1/knowledge/timeline?{query}")
        rows = data.get("results")
        cursor = data.get("next_cursor")
        cutoff = self._aware_datetime(data.get("recorded_cutoff_at"))
        coverage = data.get("coverage")
        if (
            type(data.get("limit")) is not int or data["limit"] != limit
            or data.get("visibility") != visibility
            or data.get("untrusted_content") is not True
            or not isinstance(coverage, dict)
            or coverage.get("undated_events") != "excluded"
            or coverage.get("source_freshness") != "not_asserted"
            or coverage.get("interpretation") != "reviewed_assertions"
            or cutoff is None
            or (recorded_cutoff_at is not None and cutoff != recorded_cutoff_at)
            or not isinstance(rows, list) or len(rows) > limit
            or any(not self._valid_timeline_row(row, request) for row in rows)
            or len({row["object_id"] for row in rows}) != len(rows)
            or any(row["object_id"] == after for row in rows)
            or cursor is not None and (
                not rows or len(rows) != limit or not isinstance(cursor, str)
                or not _EVENT_ID.fullmatch(cursor) or cursor != rows[-1]["object_id"]
                or cursor == after
            )
        ):
            raise BrainClientError("invalid_response")
        order = [(self._aware_datetime(row["starts_at"]), row["object_id"]) for row in rows]
        if order != sorted(order):
            raise BrainClientError("invalid_response")
        return data

    def commitments_due(
        self,
        start: datetime,
        end: datetime,
        *,
        project_id: str | None = None,
        state: str | None = None,
        visibility: KnowledgeVisibility = "unsuperseded",
        limit: int = 25,
        recorded_cutoff_at: datetime | None = None,
        after: str | None = None,
    ) -> dict[str, Any]:
        """Page evidence-linked due commitments; descriptions are untrusted."""
        try:
            request = DueCommitmentsRequest.model_validate({
                "start": start, "end": end, "project_id": project_id,
                "state": state, "visibility": visibility, "limit": limit,
                "recorded_cutoff_at": recorded_cutoff_at, "after": after,
            })
        except ValidationError:
            raise BrainClientError("invalid_request") from None
        if (
            type(limit) is not int
            or not isinstance(start, datetime)
            or not isinstance(end, datetime)
            or recorded_cutoff_at is not None
            and not isinstance(recorded_cutoff_at, datetime)
        ):
            raise BrainClientError("invalid_request")
        query = httpx.QueryParams(request.model_dump(mode="json", exclude_none=True))
        data = self._request("GET", f"/v1/knowledge/commitments-due?{query}")
        rows = data.get("results")
        cursor = data.get("next_cursor")
        cutoff = self._aware_datetime(data.get("recorded_cutoff_at"))
        coverage = data.get("coverage")
        if (
            type(data.get("limit")) is not int or data["limit"] != limit
            or data.get("visibility") != visibility
            or "state_filter" not in data or data["state_filter"] != state
            or data.get("untrusted_content") is not True
            or not isinstance(coverage, dict)
            or coverage.get("undated_commitments") != "excluded"
            or coverage.get("source_freshness") != "not_asserted"
            or coverage.get("interpretation") != "reviewed_assertions"
            or cutoff is None
            or (recorded_cutoff_at is not None and cutoff != recorded_cutoff_at)
            or not isinstance(rows, list) or len(rows) > limit
            or any(not self._valid_due_row(row, request) for row in rows)
            or len({row["object_id"] for row in rows}) != len(rows)
            or any(row["object_id"] == after for row in rows)
            or cursor is not None and (
                not rows or len(rows) != limit or not isinstance(cursor, str)
                or not _COMMITMENT_ID.fullmatch(cursor)
                or cursor != rows[-1]["object_id"] or cursor == after
            )
        ):
            raise BrainClientError("invalid_response")
        order = [(self._aware_datetime(row["due_at"]), row["object_id"]) for row in rows]
        if order != sorted(order):
            raise BrainClientError("invalid_response")
        return data

    def project_dossier(
        self,
        project_id: str,
        *,
        visibility: KnowledgeVisibility = "unsuperseded",
        event_limit: int = 10,
        commitment_limit: int = 10,
        member_limit: int = 10,
        recorded_cutoff_at: datetime | None = None,
    ) -> dict[str, Any]:
        """Read compact reviewed project context with bounded linked assertions."""
        if not isinstance(project_id, str) or not _PROJECT_ID.fullmatch(project_id):
            raise BrainClientError("invalid_request")
        if any(type(value) is not int for value in (event_limit, commitment_limit, member_limit)):
            raise BrainClientError("invalid_request")
        if recorded_cutoff_at is not None and not isinstance(recorded_cutoff_at, datetime):
            raise BrainClientError("invalid_request")
        try:
            request = ProjectDossierRequest.model_validate({
                "visibility": visibility, "event_limit": event_limit,
                "commitment_limit": commitment_limit,
                "member_limit": member_limit,
                "recorded_cutoff_at": recorded_cutoff_at,
            })
        except ValidationError:
            raise BrainClientError("invalid_request") from None
        query = httpx.QueryParams(request.model_dump(mode="json", exclude_none=True))
        data = self._request(
            "GET", f"/v1/knowledge/projects/{project_id}/dossier?{query}",
        )
        cutoff = self._aware_datetime(data.get("recorded_cutoff_at"))
        project = data.get("project")
        events = data.get("events")
        commitments = data.get("commitments")
        members = data.get("members")
        coverage = data.get("coverage")
        if (
            cutoff is None
            or recorded_cutoff_at is not None and cutoff != recorded_cutoff_at
            or data.get("visibility") != visibility
            or type(data.get("event_limit")) is not int
            or data["event_limit"] != event_limit
            or type(data.get("commitment_limit")) is not int
            or data["commitment_limit"] != commitment_limit
            or type(data.get("member_limit")) is not int
            or data["member_limit"] != member_limit
            or type(data.get("events_truncated")) is not bool
            or type(data.get("commitments_truncated")) is not bool
            or type(data.get("members_truncated")) is not bool
            or data.get("untrusted_content") is not True
            or not isinstance(coverage, dict)
            or coverage.get("order") != "recorded_at_descending"
            or coverage.get("undated_links") != "included"
            or coverage.get("source_freshness") != "not_asserted"
            or coverage.get("interpretation") != "reviewed_assertions_not_current_state"
            or not self._valid_project_dossier_project(project, project_id, cutoff)
            or not isinstance(events, list) or len(events) > event_limit
            or not isinstance(commitments, list) or len(commitments) > commitment_limit
            or not isinstance(members, list) or len(members) > member_limit
            or data["events_truncated"] and len(events) != event_limit
            or data["commitments_truncated"] and len(commitments) != commitment_limit
            or data["members_truncated"] and len(members) != member_limit
            or any(not self._valid_project_dossier_event(row, project_id, cutoff)
                   for row in events)
            or any(not self._valid_project_dossier_commitment(row, project_id, cutoff)
                   for row in commitments)
            or any(not self._valid_project_dossier_member(row, project_id, cutoff)
                   for row in members)
        ):
            raise BrainClientError("invalid_response")
        for rows in (events, commitments, members):
            ids = [row["object_id"] for row in rows]
            order = [(self._aware_datetime(row["recorded_at"]), row["object_id"])
                     for row in rows]
            if len(set(ids)) != len(ids) or order != sorted(order, reverse=True):
                raise BrainClientError("invalid_response")
        return data

    @classmethod
    def _valid_project_dossier_member(
        cls, row: Any, project_id: str, cutoff: datetime
    ) -> bool:
        if not isinstance(row, dict):
            return False
        recorded = cls._aware_datetime(row.get("recorded_at"))
        valid_from = (cls._aware_datetime(row.get("valid_from"))
                      if row.get("valid_from") else None)
        valid_to = (cls._aware_datetime(row.get("valid_to"))
                    if row.get("valid_to") else None)
        name = row.get("entity_name")
        return bool(
            row.get("object_kind") == "member"
            and isinstance(row.get("object_id"), str)
            and re.fullmatch(r"member_[a-f0-9]{32}", row["object_id"])
            and row.get("project_id") == project_id
            and isinstance(row.get("entity_id"), str)
            and _ENTITY_ID.fullmatch(row["entity_id"])
            and isinstance(name, str) and 1 <= len(name) <= 300 and "\x00" not in name
            and row.get("entity_type") in {"person", "organization"}
            and isinstance(row.get("role"), str) and _EVENT_TYPE.fullmatch(row["role"])
            and row.get("assertion_status") in {"asserted", "disputed", "retracted"}
            and recorded is not None and recorded <= cutoff
            and (row.get("valid_from") is None or valid_from is not None)
            and (row.get("valid_to") is None or (valid_from is not None
                 and valid_to is not None and valid_to > valid_from))
            and cls._valid_dossier_evidence(row.get("evidence_ids"))
        )

    def resolve_project_alias(self, name: str, *, limit: int = 25) -> dict[str, Any]:
        """Return bounded reviewed candidates without choosing or merging one."""
        try:
            request = ProjectAliasLookupRequest(name=name, limit=limit)
        except ValidationError:
            raise BrainClientError("invalid_request") from None
        query = httpx.QueryParams(request.model_dump(mode="json"))
        data = self._request("GET", f"/v1/knowledge/projects/resolve?{query}")
        candidates = data.get("candidates")
        if (
            not isinstance(candidates, list) or len(candidates) > limit
            or type(data.get("ambiguous")) is not bool
            or type(data.get("truncated")) is not bool
            or data["ambiguous"] != (len(candidates) > 1 or data["truncated"])
            or data["truncated"] and len(candidates) != limit
            or data.get("resolution") != "reviewed_candidates_only"
            or data.get("visibility") != "retained"
            or data.get("untrusted_content") is not True
        ):
            raise BrainClientError("invalid_response")
        names: list[str] = []
        order: list[tuple[datetime, str]] = []
        for item in candidates:
            if not isinstance(item, dict):
                raise BrainClientError("invalid_response")
            object_id = item.get("object_id")
            title = item.get("title")
            matched = item.get("matched_alias")
            recorded_at = self._aware_datetime(item.get("recorded_at"))
            if (
                item.get("object_kind") != "project"
                or not isinstance(object_id, str) or not _PROJECT_ID.fullmatch(object_id)
                or not isinstance(title, str) or not 1 <= len(title) <= 300
                or not isinstance(matched, str) or not 1 <= len(matched) <= 300
                or normalize_project_alias(matched) != normalize_project_alias(name)
                or item.get("alias_kind") not in (
                    "title", "name", "address", "legal_entity", "folder", "other",
                    "legacy_title",
                )
                or not isinstance(item.get("evidence_id"), str)
                or not _EVIDENCE_ID.fullmatch(item["evidence_id"])
                or recorded_at is None
            ):
                raise BrainClientError("invalid_response")
            names.append(object_id)
            order.append((recorded_at, object_id))
        if len(set(names)) != len(names) or order != sorted(order, reverse=True):
            raise BrainClientError("invalid_response")
        return data

    @staticmethod
    def _valid_dossier_evidence(value: Any) -> bool:
        return bool(
            isinstance(value, list) and 1 <= len(value) <= 20
            and len(set(item for item in value if isinstance(item, str))) == len(value)
            and all(isinstance(item, str) and _EVIDENCE_ID.fullmatch(item)
                    for item in value)
        )

    @classmethod
    def _valid_project_dossier_project(
        cls, row: Any, project_id: str, cutoff: datetime
    ) -> bool:
        if not isinstance(row, dict):
            return False
        recorded = cls._aware_datetime(row.get("recorded_at"))
        title, summary = row.get("title"), row.get("summary")
        return bool(
            row.get("object_kind") == "project" and row.get("object_id") == project_id
            and isinstance(title, str) and 1 <= len(title) <= 300 and "\x00" not in title
            and isinstance(summary, str) and len(summary) <= 300 and "\x00" not in summary
            and type(row.get("summary_truncated")) is bool
            and row.get("state") in {
                "proposed", "active", "blocked", "completed", "cancelled", "unknown",
            }
            and recorded is not None and recorded <= cutoff
            and cls._valid_dossier_evidence(row.get("evidence_ids"))
        )

    @classmethod
    def _valid_project_dossier_event(
        cls, row: Any, project_id: str, cutoff: datetime
    ) -> bool:
        if not isinstance(row, dict):
            return False
        recorded = cls._aware_datetime(row.get("recorded_at"))
        starts = cls._aware_datetime(row.get("starts_at")) if row.get("starts_at") else None
        ends = cls._aware_datetime(row.get("ends_at")) if row.get("ends_at") else None
        title, event_type = row.get("title"), row.get("event_type")
        return bool(
            row.get("object_kind") == "event"
            and row.get("project_id") == project_id
            and isinstance(row.get("object_id"), str)
            and _EVENT_ID.fullmatch(row["object_id"])
            and isinstance(title, str) and 1 <= len(title) <= 300 and "\x00" not in title
            and isinstance(event_type, str) and _EVENT_TYPE.fullmatch(event_type)
            and recorded is not None and recorded <= cutoff
            and (row.get("starts_at") is None or starts is not None)
            and (row.get("ends_at") is None or starts is not None and ends is not None
                 and ends > starts)
            and cls._valid_dossier_evidence(row.get("evidence_ids"))
        )

    @classmethod
    def _valid_project_dossier_commitment(
        cls, row: Any, project_id: str, cutoff: datetime
    ) -> bool:
        if not isinstance(row, dict):
            return False
        recorded = cls._aware_datetime(row.get("recorded_at"))
        due = cls._aware_datetime(row.get("due_at")) if row.get("due_at") else None
        summary = row.get("summary")
        owner, counterparty = row.get("owner_entity_id"), row.get("counterparty_entity_id")
        return bool(
            row.get("object_kind") == "commitment"
            and row.get("project_id") == project_id
            and isinstance(row.get("object_id"), str)
            and _COMMITMENT_ID.fullmatch(row["object_id"])
            and isinstance(summary, str) and 1 <= len(summary) <= 300
            and "\x00" not in summary
            and type(row.get("summary_truncated")) is bool
            and row.get("state") in {
                "proposed", "open", "completed", "cancelled", "overdue", "unknown",
            }
            and recorded is not None and recorded <= cutoff
            and (row.get("due_at") is None or due is not None)
            and (owner is None or isinstance(owner, str) and _ENTITY_ID.fullmatch(owner))
            and (counterparty is None or isinstance(counterparty, str)
                 and _ENTITY_ID.fullmatch(counterparty))
            and cls._valid_dossier_evidence(row.get("evidence_ids"))
        )

    @classmethod
    def _valid_due_row(cls, row: Any, request: DueCommitmentsRequest) -> bool:
        if not isinstance(row, dict):
            return False
        due = cls._aware_datetime(row.get("due_at"))
        summary = row.get("summary")
        evidence = row.get("evidence_ids")
        project = row.get("project_id")
        owner = row.get("owner_entity_id")
        counterparty = row.get("counterparty_entity_id")
        return bool(
            row.get("object_kind") == "commitment"
            and isinstance(row.get("object_id"), str)
            and _COMMITMENT_ID.fullmatch(row["object_id"])
            and isinstance(summary, str) and 1 <= len(summary) <= 300
            and "\x00" not in summary
            and type(row.get("summary_truncated")) is bool
            and row.get("state") in {
                "proposed", "open", "completed", "cancelled", "overdue", "unknown"
            }
            and (request.state is None or row["state"] == request.state)
            and due is not None and request.start <= due < request.end
            and (project is None or isinstance(project, str) and _PROJECT_ID.fullmatch(project))
            and (request.project_id is None or project == request.project_id)
            and (owner is None or isinstance(owner, str) and _ENTITY_ID.fullmatch(owner))
            and (counterparty is None or isinstance(counterparty, str)
                 and _ENTITY_ID.fullmatch(counterparty))
            and isinstance(evidence, list) and 1 <= len(evidence) <= 20
            and len(set(item for item in evidence if isinstance(item, str))) == len(evidence)
            and all(isinstance(item, str) and _EVIDENCE_ID.fullmatch(item) for item in evidence)
        )

    @staticmethod
    def _aware_datetime(value: Any) -> datetime | None:
        if not isinstance(value, str):
            return None
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            return None
        return parsed if parsed.tzinfo is not None and parsed.utcoffset() is not None else None

    @classmethod
    def _valid_timeline_row(cls, row: Any, request: TimelineRequest) -> bool:
        if not isinstance(row, dict):
            return False
        starts = cls._aware_datetime(row.get("starts_at"))
        ends = cls._aware_datetime(row.get("ends_at")) if row.get("ends_at") is not None else None
        evidence = row.get("evidence_ids")
        project = row.get("project_id")
        title = row.get("title")
        event_type = row.get("event_type")
        return bool(
            row.get("object_kind") == "event"
            and isinstance(row.get("object_id"), str)
            and _EVENT_ID.fullmatch(row["object_id"])
            and isinstance(event_type, str) and _EVENT_TYPE.fullmatch(event_type)
            and isinstance(title, str) and 1 <= len(title) <= 300
            and "\x00" not in title
            and starts is not None and request.start <= starts < request.end
            and (row.get("ends_at") is None or ends is not None and ends > starts)
            and (project is None or isinstance(project, str) and _PROJECT_ID.fullmatch(project))
            and (request.project_id is None or project == request.project_id)
            and isinstance(evidence, list) and 1 <= len(evidence) <= 20
            and len(set(item for item in evidence if isinstance(item, str))) == len(evidence)
            and all(isinstance(item, str) and _EVIDENCE_ID.fullmatch(item) for item in evidence)
        )

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
