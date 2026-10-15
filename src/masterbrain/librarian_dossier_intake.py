"""Read-only candidate inventory for ADR-197 Markdown; never stages knowledge."""

from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from pydantic import ConfigDict, Field

from email_brain.domain.models import TenantContext
from email_brain.schemas import ClosedModel
from email_brain.store import AccessDenied, Conflict, Store
from masterbrain.project_dossier_markdown import _HEADER
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
    if len(encoded) > _MAX_BYTES or not markdown.startswith(_HEADER):
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
