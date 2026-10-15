"""Read-only candidate inventory for ADR-197 Markdown; never stages knowledge."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from masterbrain.project_dossier_markdown import _HEADER

_MAX_BYTES = 65_536
_META = re.compile(
    r"^Project ID: `(project_[a-f0-9]{32})`\. Recorded cutoff: `([^`]{1,40})`\. "
    r"Visibility: `(retained|unsuperseded)`\.$"
)
_EVIDENCE = re.compile(r"citation `(evidence_[a-f0-9]{32})`")
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
            identifier = row.group(1)
            if identifier in seen or (kind == "project" and identifier != project_id):
                raise ValueError("invalid dossier identity")
            seen.add(identifier)
            candidates.append({
                "section": heading, "kind": kind, "claimed_id": identifier,
                "claimed_citation_ids": citations, "untrusted_line": line,
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
