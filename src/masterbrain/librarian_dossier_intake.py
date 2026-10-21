"""Bounded ADR-197 Markdown inspection and private proposal-only import."""

from __future__ import annotations

import hashlib
import html
import json
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import ConfigDict, Field

from email_brain.domain.models import TenantContext
from email_brain.schemas import ClosedModel
from email_brain.store import AccessDenied, Conflict, Store
from masterbrain.knowledge_proposals import KnowledgeProposalBatches, _canonical, _sha
from masterbrain.knowledge_schema import (
    CommitmentWrite,
    EventWrite,
    KnowledgeProposalStageRequest,
    MemberWrite,
    ProjectWrite,
)
from masterbrain.project_dossier_markdown import (
    _HEADER,
    _quote_label,
    _verified_assertion_citation,
)
from masterbrain.project_facts import _markdown_json_text

_MAX_BYTES = 65_536
_META = re.compile(
    r"^Project ID: `(project_[a-f0-9]{32})`\. Recorded cutoff: `([^`]{1,40})`\. "
    r"Visibility: `(retained|unsuperseded)`\.$"
)
_EVIDENCE = re.compile(r"citation `(evidence_[a-f0-9]{32})`")
_QUOTE_LABEL = re.compile(r"(?:exact quote|quote prefix) ")
_MARKDOWN_UNESCAPE = re.compile(r"\\([\\`*_{}\[\]()#+.!|>-])")
_SECTIONS = (
    ("Project", "project", r"project_[a-f0-9]{32}", 1),
    ("Events", "event", r"event_[a-f0-9]{32}", 25),
    ("Commitments", "commitment", r"commitment_[a-f0-9]{32}", 25),
    ("People and roles", "member", r"member_[a-f0-9]{32}", 25),
    ("Related artifacts", "artifact link", r"partifact_[a-f0-9]{32}", 25),
    ("Source-stated project facts", "fact", r"pfact_[a-f0-9]{32}", 25),
)
_PREFIXES = {
    kind: re.compile(r"^- " + re.escape(kind) + r" `(" + identity + r")`(?:[: (])")
    for _, kind, identity, _ in _SECTIONS
}


class DossierMarkdownInspectRequest(ClosedModel):
    # The shared schema strips strings; this format's trailing newlines are grammar.
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)
    markdown: str = Field(min_length=1, max_length=_MAX_BYTES)


class DossierProposalSelection(ClosedModel):
    claimed_id: str = Field(pattern=r"^[a-z]+_[a-f0-9]{32}$")
    assertion: dict[str, Any]


class DossierProposalStageRequest(ClosedModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)
    markdown: str = Field(min_length=1, max_length=_MAX_BYTES)
    selections: list[DossierProposalSelection] = Field(min_length=1, max_length=50)


def _outside_json_string(line: str) -> list[bool]:
    """Mark syntax positions; source text inside JSON strings is not grammar."""
    outside: list[bool] = []
    quoted = False
    slashes = 0
    for char in line:
        outside.append(not quoted)
        if char == '"' and slashes % 2 == 0:
            quoted = not quoted
        slashes = slashes + 1 if char == "\\" else 0
    if quoted:
        raise ValueError("unclosed dossier string")
    return outside


def _quote_previews(line: str, expected: int) -> list[str]:
    """Recover only canonically escaped export previews, never full quotes."""
    outside = _outside_json_string(line)
    labels = [match for match in _QUOTE_LABEL.finditer(line) if outside[match.start()]]
    citations = list(_EVIDENCE.finditer(line))
    if len(labels) != expected or len(citations) != expected:
        raise ValueError("invalid dossier quote count")
    previews: list[str] = []
    for index, match in enumerate(labels):
        suffix = line[match.end():]
        decoded = _MARKDOWN_UNESCAPE.sub(r"\1", suffix)
        decoded = html.unescape(decoded)
        try:
            value, _ = json.JSONDecoder().raw_decode(decoded)
        except json.JSONDecodeError as exc:
            raise ValueError("invalid dossier quote preview") from exc
        if (not isinstance(value, str) or not value
                or not suffix.startswith(_markdown_json_text(value))
                or not match.end() < citations[index].start()
                or (index + 1 < expected
                    and not citations[index].end() < labels[index + 1].start())):
            raise ValueError("invalid dossier quote preview")
        previews.append(value)
    return previews


def inspect_project_dossier_markdown(markdown: str) -> dict[str, Any]:
    """Parse only the fixed export envelope and inventory untrusted rows.

    An ID/citation in this result is a *claim made by Markdown*, not a verified
    database reference. Callers must not use the result as a publication body.
    """
    if not isinstance(markdown, str):
        raise ValueError("invalid dossier text")
    try:
        encoded = markdown.encode("utf-8", errors="strict")
    except UnicodeError as exc:
        raise ValueError("invalid dossier text") from exc
    if (len(encoded) > _MAX_BYTES or not markdown.startswith(_HEADER)
            or not markdown.endswith("\n")):
        raise ValueError("invalid dossier envelope")
    lines = markdown[len(_HEADER):].splitlines()
    if not lines or (match := _META.fullmatch(lines[0])) is None:
        raise ValueError("invalid dossier metadata")
    project_id, cutoff_text, visibility = match.groups()
    try:
        cutoff = datetime.fromisoformat(cutoff_text)
    except ValueError as exc:
        raise ValueError("invalid dossier cutoff") from exc
    if cutoff.tzinfo is None or cutoff.utcoffset() is None:
        raise ValueError("invalid dossier cutoff")
    index = 1
    candidates: list[dict[str, Any]] = []
    counts: dict[str, int] = {}
    seen: set[str] = set()
    for heading, kind, _, limit in _SECTIONS:
        if lines[index:index + 2] != ["", f"## {heading}"]:
            raise ValueError("invalid dossier section order")
        index += 2
        if index >= len(lines) or lines[index] != "":
            raise ValueError("invalid dossier section spacing")
        index += 1
        count = 0
        while index < len(lines) and lines[index] != "":
            line = lines[index]
            row = _PREFIXES[kind].match(line)
            citations = _EVIDENCE.findall(line)
            expected = 2 if kind == "member" else 1
            if (row is None or not line.endswith(".") or len(citations) != expected
                    or line.count("citation `") != expected):
                raise ValueError("invalid dossier row")
            previews = _quote_previews(line, expected)
            identifier = row.group(1)
            if identifier in seen or (kind == "project" and identifier != project_id):
                raise ValueError("invalid dossier identity")
            seen.add(identifier)
            candidates.append({
                "section": heading, "kind": kind, "claimed_id": identifier,
                "claimed_citation_ids": citations, "untrusted_line": line,
                "claimed_quote_previews": previews,
                "proposal_ready": False,
                "missing_for_proposal": [
                    "current evidence verification", "full assertion payload",
                    "observed time", "explicit human review",
                ],
            })
            count += 1
            if count > limit:
                raise ValueError("dossier section exceeds bound")
            index += 1
        if kind == "project" and count != 1:
            raise ValueError("dossier must contain one project")
        counts[heading] = count
    if index != len(lines):
        raise ValueError("unexpected dossier content")
    return {
        "format": "masterbrain_project_dossier_markdown_v1",
        "claimed_project_id": project_id,
        "claimed_recorded_cutoff_at": cutoff.isoformat(),
        "claimed_visibility": visibility,
        "section_counts": counts,
        "candidates": candidates,
        "untrusted_content": True,
        "proposal_ready": False,
        "staged": False,
    }


@dataclass(slots=True)
class DossierMarkdownInspection:
    store: Store

    def inspect(self, ctx: TenantContext, markdown: str) -> dict[str, Any]:
        """Check every claimed preview against its own current granted evidence."""
        self.store.require(ctx, "knowledge.review")
        self.store.require(ctx, "brain.content.read")
        if ctx.identity is not None and ctx.identity.client_kind != "human":
            raise AccessDenied("human identity required")
        inventory = inspect_project_dossier_markdown(markdown)
        pairs = [
            (evidence_id, preview)
            for candidate in inventory["candidates"]
            for evidence_id, preview in zip(
                candidate["claimed_citation_ids"],
                candidate["claimed_quote_previews"], strict=True,
            )
        ]
        ids = [item[0] for item in pairs]
        previews = [item[1] for item in pairs]
        allowed = sorted(ctx.source_ids) if ctx.source_ids is not None else None
        with self.store.transaction(ctx) as conn:
            rows = conn.execute(
                "WITH requested AS (SELECT q.evidence_id,q.quote_preview,q.ordinality "
                "FROM unnest(%s::text[],%s::text[]) WITH ORDINALITY "
                "AS q(evidence_id,quote_preview,ordinality)) "
                "SELECT q.ordinality, EXISTS (SELECT 1 FROM brain_evidence e "
                "JOIN brain_source_versions v ON v.tenant_id=e.tenant_id "
                "AND v.id=e.source_version_id "
                "JOIN brain_source_items i ON i.tenant_id=v.tenant_id "
                "AND i.id=v.item_id AND i.source_id=v.source_id "
                "JOIN brain_sources s ON s.tenant_id=i.tenant_id AND s.id=i.source_id "
                "WHERE e.tenant_id=%s AND e.id=q.evidence_id "
                "AND i.current_version_id=v.id AND s.status='active' "
                "AND NOT public.brain_email_evidence_is_excluded(e.tenant_id,e.id) "
                "AND (%s::text[] IS NULL OR s.id=ANY(%s::text[])) "
                "AND EXISTS (SELECT 1 FROM brain_normalized_documents d "
                "WHERE d.tenant_id=e.tenant_id AND d.evidence_id=e.id "
                "AND position(q.quote_preview IN d.body)>0)) AS verified "
                "FROM requested q ORDER BY q.ordinality",
                (ids, previews, ctx.tenant_id, allowed, allowed),
            ).fetchall()
            if (len(rows) != len(pairs)
                    or any(row["ordinality"] != index + 1 or not row["verified"]
                           for index, row in enumerate(rows))):
                raise Conflict("dossier citations cannot be verified")
            self.store.audit(conn, ctx, "knowledge.dossier_markdown_inspected", "dossier")
        inventory["citation_spans_checked"] = True
        inventory["source_freshness"] = "not_asserted"
        return inventory


def _expected_selected_line(
    assertion: ProjectWrite | EventWrite | CommitmentWrite,
    claimed_id: str, citation_id: str, project_id: str,
) -> str:
    """Bind supplied typed fields to an exact existing exporter row."""
    if (assertion.supersedes_id is not None or assertion.valid_from is not None
            or assertion.valid_to is not None):
        raise ValueError("unrendered import fields are not supported")
    quote = _quote_label(assertion.source_quote)
    if isinstance(assertion, ProjectWrite):
        if assertion.aliases or claimed_id != project_id:
            raise ValueError("unsupported imported project fields")
        return (
            f"- project `{claimed_id}`: reviewed title "
            f"{_markdown_json_text(assertion.title)}; state `{assertion.state}`; "
            f"reviewed summary {_markdown_json_text(assertion.description)}; "
            f"derivation unspecified; {quote}; citation `{citation_id}`."
        )
    if isinstance(assertion, EventWrite):
        if assertion.project_id != project_id or assertion.ends_at is not None:
            raise ValueError("unsupported imported event fields")
        when = assertion.starts_at.isoformat() if assertion.starts_at else "undated"
        return (
            f"- event `{claimed_id}` ({assertion.event_type}, {when}): "
            f"reviewed title {_markdown_json_text(assertion.title)}; "
            f"reviewed description {_markdown_json_text(assertion.description)}; "
            f"derivation unspecified; {quote}; citation `{citation_id}`."
        )
    if assertion.project_id != project_id:
        raise ValueError("imported commitment project mismatch")
    due = assertion.due_at.isoformat() if assertion.due_at else "undated"
    owner = assertion.owner_entity_id or "unspecified"
    counterparty = assertion.counterparty_entity_id or "unspecified"
    return (
        f"- commitment `{claimed_id}` (due {due}, state `{assertion.state}`): "
        f"reviewed description {_markdown_json_text(assertion.description)}; "
        f"owner `{owner}`; counterparty `{counterparty}`; "
        f"derivation unspecified; {quote}; citation `{citation_id}`."
    )


def _expected_member_line(
    store: Store, ctx: TenantContext, assertion: MemberWrite,
    claimed_id: str, entity_citation: str, member_citation: str,
    project_id: str,
) -> str:
    """Bind both displayed citations to one current local project/entity pair."""
    if (assertion.project_id != project_id or assertion.supersedes_id is not None
            or assertion.valid_from is not None or assertion.valid_to is not None):
        raise ValueError("unsupported imported member fields")
    allowed = sorted(ctx.source_ids) if ctx.source_ids is not None else None
    with store.transaction(ctx) as conn:
        refs = conn.execute(
            "SELECT e.name,e.entity_type,e.source_quote AS entity_quote,"
            "p.source_quote AS project_quote FROM knowledge_entities e "
            "JOIN knowledge_projects p ON p.tenant_id=e.tenant_id "
            "WHERE e.tenant_id=%s AND e.id=%s AND p.id=%s",
            (ctx.tenant_id, assertion.entity_id, project_id),
        ).fetchone()
        if refs is None or refs["entity_type"] not in {"person", "organization"}:
            raise ValueError("imported member references are unavailable")
        _verified_assertion_citation(
            conn, ctx.tenant_id, allowed, "project", project_id,
            refs["project_quote"],
        )
        actual_entity_citation = _verified_assertion_citation(
            conn, ctx.tenant_id, allowed, "entity", assertion.entity_id,
            refs["entity_quote"],
        )
        if actual_entity_citation != entity_citation:
            raise ValueError("imported entity citation mismatch")
    return (
        f"- member `{claimed_id}`: {refs['entity_type']} "
        f"{_markdown_json_text(refs['name'])} "
        f"(entity `{assertion.entity_id}`, {_quote_label(refs['entity_quote'])}, "
        f"citation `{entity_citation}`); reviewed role `{assertion.role}` "
        f"({assertion.assertion_status}; derivation unspecified; "
        f"{_quote_label(assertion.source_quote)}; "
        f"citation `{member_citation}`)."
    )


@dataclass(slots=True)
class DossierProposalImport:
    store: Store

    def stage(
        self, ctx: TenantContext, body: DossierProposalStageRequest,
        idempotency_key: UUID,
    ) -> dict[str, Any]:
        inventory = DossierMarkdownInspection(self.store).inspect(ctx, body.markdown)
        by_id = {row["claimed_id"]: row for row in inventory["candidates"]}
        seen: set[str] = set()
        payloads: list[dict[str, Any]] = []
        claims: list[tuple[str, str]] = []
        entity_citations: list[str | None] = []
        for selected in body.selections:
            if selected.claimed_id in seen or selected.claimed_id not in by_id:
                raise ValueError("invalid dossier selection")
            seen.add(selected.claimed_id)
            candidate = by_id[selected.claimed_id]
            if candidate["kind"] not in {"project", "event", "commitment", "member"}:
                raise ValueError("unsupported dossier selection")
            assertion, payload = _canonical(selected.assertion)
            if not isinstance(assertion, (
                ProjectWrite, EventWrite, CommitmentWrite, MemberWrite,
            )):
                raise ValueError("unsupported dossier assertion")
            if assertion.kind != candidate["kind"]:
                raise ValueError("dossier kind mismatch")
            citations = candidate["claimed_citation_ids"]
            citation_id = citations[-1]
            if isinstance(assertion, MemberWrite):
                expected = _expected_member_line(
                    self.store, ctx, assertion, selected.claimed_id,
                    citations[0], citation_id, inventory["claimed_project_id"],
                )
                entity_citations.append(citations[0])
            else:
                expected = _expected_selected_line(
                    assertion, selected.claimed_id, citation_id,
                    inventory["claimed_project_id"],
                )
                entity_citations.append(None)
            if expected != candidate["untrusted_line"]:
                raise ValueError("dossier row does not match proposed assertion")
            payloads.append(payload)
            claims.append((selected.claimed_id, citation_id))
        context = {
            "format": inventory["format"],
            "markdown_sha256": hashlib.sha256(
                body.markdown.encode("utf-8"),
            ).hexdigest(),
            "claims": claims,
        }
        if any(citation is not None for citation in entity_citations):
            context["member_entity_citations"] = entity_citations
        context_sha = _sha(context)
        result = KnowledgeProposalBatches(self.store).stage(
            ctx, KnowledgeProposalStageRequest(proposals=payloads),
            idempotency_key, import_context_sha256=context_sha,
            import_claims=claims,
            import_entity_citations=entity_citations,
        )
        return {**result, "import_context_sha256": context_sha}
