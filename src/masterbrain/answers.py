"""Bounded, extractive answers over the same current Brain evidence as search.

The selector is a data-only port. It has no database, source, tool or credential
authority; its output is checked against freshly authorized evidence before use.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol

from email_brain.domain.models import TenantContext
from email_brain.store import NotFound
from masterbrain.datacore.persistence import DataCoreStore

MAX_PASSAGES = 8
MAX_PASSAGE_CHARS = 1200
MAX_SELECTIONS = 4
MAX_QUOTE_CHARS = 400
_SHA256 = re.compile(r"^[a-f0-9]{64}$")
_LAYERS = (
    "email_messages", "fileos", "email_attachments", "email_documents",
    "archive_members", "archive_documents", "archive_images",
)


class AnswerUnavailable(Exception):
    """Configured selector is absent or unavailable; never include source text."""


class AnswerRejected(Exception):
    """Selector output is not grounded in the authorized evidence."""


class AnswerStale(Exception):
    """Evidence or authority changed during selection."""


@dataclass(frozen=True, slots=True)
class AnswerPassage:
    evidence_id: str
    document_id: str
    source_id: str
    source_kind: str
    content: str = field(repr=False)
    body_sha256: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class QuoteSelection:
    evidence_id: str
    quote: str = field(repr=False)


class AnswerSelector(Protocol):
    """A bounded, separately configured model adapter with no tools or effects."""

    def select(
        self, question: str, passages: tuple[AnswerPassage, ...]
    ) -> Sequence[QuoteSelection]: ...


class LocalExtractiveSelector:
    """Select matching source sentences locally; make no semantic claim."""

    _STOP = frozenset({
        "about", "after", "again", "also", "and", "are", "can", "could",
        "did", "does", "find", "for", "from", "get", "has", "have", "how",
        "into", "just", "latest", "more", "please", "show", "status", "tell",
        "the", "that", "their", "there", "these", "this", "those", "was",
        "were", "what", "when", "where", "which", "will", "with", "would",
        "your",
    })

    def select(
        self, question: str, passages: tuple[AnswerPassage, ...]
    ) -> Sequence[QuoteSelection]:
        terms = {
            term for term in re.findall(r"\w+", question.casefold())
            if len(term) >= 3 and term not in self._STOP
        }
        if not terms:
            return []
        ranked: list[tuple[int, int, QuoteSelection]] = []
        for ordinal, passage in enumerate(passages[:MAX_PASSAGES]):
            best_score = 0
            best_quote = ""
            for match in re.finditer(r"[^.!?\n]+(?:[.!?]+|$)", passage.content):
                sentence = match.group().strip()
                if not sentence:
                    continue
                words = set(re.findall(r"\w+", sentence.casefold()))
                score = len(terms & words)
                if score <= best_score:
                    continue
                if len(sentence) > MAX_QUOTE_CHARS:
                    # Keep the matching term inside an exact, bounded slice.
                    first = next((word for word in sorted(terms) if word in words), None)
                    if first is None:
                        continue
                    found = re.search(r"\b" + re.escape(first) + r"\b", sentence, re.IGNORECASE)
                    if found is None:
                        continue
                    position = found.start()
                    start = max(0, position - MAX_QUOTE_CHARS // 3)
                    sentence = sentence[start:start + MAX_QUOTE_CHARS].strip()
                best_score = score
                best_quote = sentence
            if best_quote:
                ranked.append((
                    best_score, ordinal, QuoteSelection(passage.evidence_id, best_quote)
                ))
        ranked.sort(key=lambda item: (-item[0], item[1]))
        return [item[2] for item in ranked[:MAX_SELECTIONS]]


class GroundedAnswerService:
    def __init__(self, brain: DataCoreStore, selector: AnswerSelector | None) -> None:
        self.brain = brain
        self.selector = selector

    @staticmethod
    def _hits(grouped: dict[str, Any]) -> list[dict[str, Any]]:
        layers = grouped.get("layers")
        if not isinstance(layers, dict):
            raise AnswerRejected()
        candidates: list[dict[str, Any]] = []
        seen: set[str] = set()
        for ordinal in range(2):
            for layer in _LAYERS:
                hits = layers.get(layer)
                if not isinstance(hits, list):
                    raise AnswerRejected()
                if ordinal >= len(hits):
                    continue
                hit = hits[ordinal]
                if not isinstance(hit, dict):
                    raise AnswerRejected()
                evidence_id = hit.get("evidence_id")
                if not isinstance(evidence_id, str) or evidence_id in seen:
                    continue
                seen.add(evidence_id)
                candidates.append(hit)
                if len(candidates) == MAX_PASSAGES:
                    return candidates
        return candidates

    def answer(
        self,
        ctx: TenantContext,
        question: str,
        search_current: Callable[[], dict[str, Any]],
    ) -> dict[str, Any]:
        if self.selector is None:
            raise AnswerUnavailable()
        grouped = search_current()
        coverage = grouped.get("coverage")
        if not isinstance(coverage, dict) or coverage.get("complete") is not False:
            raise AnswerRejected()
        passages: list[AnswerPassage] = []
        for hit in self._hits(grouped):
            evidence_id = hit.get("evidence_id")
            document_id = hit.get("document_id")
            source_id = hit.get("source_id")
            if (
                not isinstance(evidence_id, str)
                or not isinstance(document_id, str)
                or not isinstance(source_id, str)
            ):
                raise AnswerRejected()
            try:
                metadata = self.brain.evidence(ctx, evidence_id)
                content = self.brain.evidence_content(
                    ctx, evidence_id, max_chars=MAX_PASSAGE_CHARS
                )
            except NotFound:
                raise AnswerStale() from None
            body_sha256 = content.get("body_sha256")
            if (
                metadata.get("document_id") != document_id
                or metadata.get("source_id") != source_id
                or content.get("document_id") != document_id
                or not isinstance(metadata.get("source_kind"), str)
                or not isinstance(content.get("content"), str)
                or not isinstance(body_sha256, str)
                or not _SHA256.fullmatch(body_sha256)
            ):
                # One evidence can have multiple derivatives. Do not cite a
                # search hit with another document's extracted body.
                continue
            passages.append(AnswerPassage(
                evidence_id, document_id, source_id, metadata["source_kind"],
                content["content"], body_sha256,
            ))
        if not passages:
            search_current()  # Recheck grants and current visibility before answering.
            return self._response("no_supported_evidence", [], coverage)
        try:
            selected = self.selector.select(question, tuple(passages))
        except AnswerUnavailable:
            raise
        except Exception:
            # Model and transport exceptions may contain private prompts or
            # response bodies. Never propagate or log them here.
            raise AnswerUnavailable() from None
        if not isinstance(selected, (tuple, list)) or len(selected) > MAX_SELECTIONS:
            raise AnswerRejected()
        by_id = {passage.evidence_id: passage for passage in passages}
        citations: list[dict[str, Any]] = []
        cited: set[str] = set()
        for choice in selected:
            if not isinstance(choice, QuoteSelection):
                raise AnswerRejected()
            passage = by_id.get(choice.evidence_id)
            quote = choice.quote
            if (
                passage is None
                or choice.evidence_id in cited
                or not isinstance(quote, str)
                or not quote.strip()
                or "\x00" in quote
                or len(quote) > MAX_QUOTE_CHARS
            ):
                raise AnswerRejected()
            start = passage.content.find(quote)
            if start < 0:
                raise AnswerRejected()
            cited.add(choice.evidence_id)
            citations.append({
                "evidence_id": passage.evidence_id,
                "document_id": passage.document_id,
                "source_id": passage.source_id,
                "source_kind": passage.source_kind,
                "quote": quote,
                "start": start,
                "end": start + len(quote),
                "body_sha256": passage.body_sha256,
            })
        refreshed = self._hits(search_current())
        current = {
            (hit.get("evidence_id"), hit.get("document_id")) for hit in refreshed
        }
        if any((item["evidence_id"], item["document_id"]) not in current for item in citations):
            raise AnswerStale()
        return self._response(
            "quoted_evidence" if citations else "no_supported_answer", citations, coverage
        )

    @staticmethod
    def _response(
        status: str, citations: list[dict[str, Any]], coverage: dict[str, Any]
    ) -> dict[str, Any]:
        return {
            "mode": "grounded_extractive_v1",
            "status": status,
            "answer": (
                "Relevant passages from current indexed evidence are quoted below."
                if citations else "No supported answer from current indexed evidence."
            ),
            "citations": citations,
            "coverage": {
                "complete": False,
                "source_access": coverage.get("source_access"),
                "knowledge": "reviewed_assertions_not_synthesized",
            },
            "untrusted_content": True,
        }
