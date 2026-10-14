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
from masterbrain.schemas import MAX_ANSWER_TEXT_BYTES, SourceFocus

MAX_PASSAGES = 8
MAX_PASSAGE_CHARS = 1200
MAX_PASSAGE_BYTES = 2048
MAX_CONTEXT_BYTES = 8192
MAX_SELECTIONS = 4
MAX_QUOTE_CHARS = 400
MAX_REVIEWED_HITS = 4
MAX_REVIEWED_EVIDENCE_IDS = 5
_SHA256 = re.compile(r"^[a-f0-9]{64}$")
_EVIDENCE_ID = re.compile(r"^evidence_[a-f0-9]{32}$")
_KNOWLEDGE_KINDS = frozenset({
    "entity", "relationship", "claim", "event", "project", "commitment", "correction"
})
_LAYERS = (
    "email_messages", "fileos", "email_attachments", "email_documents",
    "archive_members", "archive_documents", "archive_images",
)
_EMAIL_LAYERS = ("email_messages", "email_attachments", "email_documents")
_FILEOS_LAYERS = ("fileos", "archive_members", "archive_documents", "archive_images")
_QUESTION_FILLER = frozenset({
    "a", "about", "again", "also", "an", "and", "are", "at", "by", "can",
    "could", "d", "did", "do", "does", "find", "for", "get", "give",
    "has", "have", "help", "how", "in", "into", "is", "just", "ll",
    "m", "me", "more", "my", "of", "on",
    "please", "show", "status", "tell", "the", "that", "their", "there",
    "these", "this", "those", "to", "t", "re", "s", "ve", "was", "were",
    "what", "when", "where", "which", "will", "with", "would", "you",
    "your",
})


def answer_search_query(question: str) -> str:
    """Remove fixed question boilerplate without inventing search concepts."""
    words = re.findall(r"\w+", question)
    retained = [word for word in words if word.casefold() not in _QUESTION_FILLER]
    return " ".join(retained) if retained else question


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

    def select(
        self, question: str, passages: tuple[AnswerPassage, ...]
    ) -> Sequence[QuoteSelection]:
        terms = {
            term for term in re.findall(r"\w+", question.casefold())
            if term not in _QUESTION_FILLER
        }
        if not terms:
            return []
        # In a "find X for Y" question, X is the requested item and Y is
        # usually identifying context. This is only a deterministic lexical
        # tie-breaker, not a claim that we understood the user's intent.
        before_for, separator, _ = question.casefold().partition(" for ")
        target_terms = (
            {term for term in re.findall(r"\w+", before_for) if term in terms}
            if separator else terms
        ) or terms
        # Prefer a sentence containing the rarer question words when overlap
        # ties. A repeated project name should not outrank the sentence about
        # the specific document or event the person asked for.
        sentences_by_passage: list[list[tuple[str, set[str]]]] = []
        term_frequency = dict.fromkeys(terms, 0)
        for passage in passages[:MAX_PASSAGES]:
            sentences: list[tuple[str, set[str]]] = []
            for match in re.finditer(r"[^.!?\n]+(?:[.!?]+|$)", passage.content):
                sentence = match.group().strip()
                if not sentence:
                    continue
                matched = terms & set(re.findall(r"\w+", sentence.casefold()))
                sentences.append((sentence, matched))
                for term in matched:
                    term_frequency[term] += 1
            sentences_by_passage.append(sentences)
        ranked: list[tuple[int, int, int, int, QuoteSelection]] = []
        for ordinal, (passage, sentences) in enumerate(
            zip(passages[:MAX_PASSAGES], sentences_by_passage, strict=True)
        ):
            best_rank = (0, 0, 0)
            best_quote = ""
            for sentence, matched in sentences:
                rank = (
                    len(target_terms & matched), len(matched),
                    sum(-term_frequency[term] for term in matched),
                )
                if rank <= best_rank:
                    continue
                if len(sentence) > MAX_QUOTE_CHARS:
                    # Keep the matching term inside an exact, bounded slice.
                    priority = target_terms & matched or matched
                    first = min(priority, key=lambda term: (term_frequency[term], term))
                    found = re.search(r"\b" + re.escape(first) + r"\b", sentence, re.IGNORECASE)
                    if found is None:
                        continue
                    position = found.start()
                    start = max(0, position - MAX_QUOTE_CHARS // 3)
                    sentence = sentence[start:start + MAX_QUOTE_CHARS].strip()
                best_rank = rank
                best_quote = sentence
            if best_quote:
                ranked.append((
                    -best_rank[0], -best_rank[1], -best_rank[2], ordinal,
                    QuoteSelection(passage.evidence_id, best_quote)
                ))
        ranked.sort(key=lambda item: item[:4])
        return [item[4] for item in ranked[:MAX_SELECTIONS]]


class GroundedAnswerService:
    def __init__(self, brain: DataCoreStore, selector: AnswerSelector | None) -> None:
        self.brain = brain
        self.selector = selector

    @staticmethod
    def _hits(
        grouped: dict[str, Any], source_focus: SourceFocus = "all"
    ) -> list[dict[str, Any]]:
        layers = grouped.get("layers")
        if not isinstance(layers, dict):
            raise AnswerRejected()
        selected_layers = (
            _LAYERS if source_focus == "all" else
            _EMAIL_LAYERS if source_focus == "email" else _FILEOS_LAYERS
        )
        if any(not isinstance(layers.get(layer), list) for layer in _LAYERS):
            raise AnswerRejected()
        if source_focus != "all" and any(
            layers[layer] for layer in _LAYERS if layer not in selected_layers
        ):
            raise AnswerRejected()
        candidates: list[dict[str, Any]] = []
        seen: set[str] = set()
        for ordinal in range(2):
            for layer in selected_layers:
                hits = layers.get(layer)
                assert isinstance(hits, list)
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

    @staticmethod
    def _knowledge_hits(
        grouped: dict[str, Any], source_focus: SourceFocus = "all"
    ) -> list[tuple[dict[str, Any], tuple[str, ...]]]:
        layers = grouped.get("layers")
        if not isinstance(layers, dict) or not isinstance(layers.get("knowledge"), list):
            raise AnswerRejected()
        if source_focus != "all":
            if layers["knowledge"]:
                raise AnswerRejected()
            return []
        selected: list[tuple[dict[str, Any], tuple[str, ...]]] = []
        seen: set[str] = set()
        for hit in layers["knowledge"][:MAX_REVIEWED_HITS]:
            if not isinstance(hit, dict):
                raise AnswerRejected()
            kind = hit.get("object_kind")
            object_id = hit.get("object_id")
            title = hit.get("title")
            excerpt = hit.get("excerpt")
            evidence_ids = hit.get("evidence_ids")
            if (
                not isinstance(kind, str)
                or kind not in _KNOWLEDGE_KINDS
                or not isinstance(object_id, str)
                or not re.fullmatch(kind + r"_[a-f0-9]{32}", object_id)
                or object_id in seen
                or not isinstance(title, str)
                or not 1 <= len(title) <= 300
                or "\x00" in title
                or not isinstance(excerpt, str)
                or not 1 <= len(excerpt) <= 16000
                or "\x00" in excerpt
                or not isinstance(evidence_ids, (tuple, list))
                or not 1 <= len(evidence_ids) <= 20
                or any(
                    not isinstance(value, str) or not _EVIDENCE_ID.fullmatch(value)
                    for value in evidence_ids
                )
                or len(set(evidence_ids)) != len(evidence_ids)
            ):
                raise AnswerRejected()
            try:
                title.encode("utf-8")
                excerpt.encode("utf-8")
            except UnicodeEncodeError:
                raise AnswerRejected() from None
            seen.add(object_id)
            full_ids = tuple(evidence_ids)
            selected.append(({
                "object_kind": kind,
                "object_id": object_id,
                "title": title,
                "excerpt": excerpt,
                "evidence_ids": list(full_ids[:MAX_REVIEWED_EVIDENCE_IDS]),
                "linked_evidence_count": len(full_ids),
            }, full_ids))
        return selected

    @classmethod
    def _recheck_knowledge(
        cls,
        selected: list[tuple[dict[str, Any], tuple[str, ...]]],
        refreshed: dict[str, Any],
        source_focus: SourceFocus,
    ) -> None:
        current = {
            item["object_id"]: (item, ids)
            for item, ids in cls._knowledge_hits(refreshed, source_focus)
        }
        if any(current.get(item["object_id"]) != (item, ids) for item, ids in selected):
            raise AnswerStale()

    @staticmethod
    def _recheck_focus(grouped: dict[str, Any], source_focus: SourceFocus) -> None:
        coverage = grouped.get("coverage")
        if (
            not isinstance(coverage, dict)
            or coverage.get("complete") is not False
            or coverage.get("source_focus", "all") != source_focus
        ):
            raise AnswerStale()

    @staticmethod
    def _bounded_utf8_prefix(value: str, max_bytes: int) -> tuple[str, bool, int]:
        try:
            encoded = value.encode("utf-8")
        except UnicodeEncodeError:
            raise AnswerRejected() from None
        if len(encoded) <= max_bytes:
            return value, False, len(encoded)
        prefix = encoded[:max_bytes].decode("utf-8", errors="ignore")
        return prefix, True, len(prefix.encode("utf-8"))

    @classmethod
    def _bound_answer_text(
        cls, citations: list[dict[str, Any]], reviewed: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], bool]:
        """Keep exact quotes; shorten or omit reviewed text in stable search order."""
        quote_bytes = 0
        for citation in citations:
            try:
                quote_bytes += len(citation["quote"].encode("utf-8"))
            except UnicodeEncodeError:
                raise AnswerRejected() from None
        if quote_bytes > MAX_ANSWER_TEXT_BYTES:
            # The fixed four-by-400-character quote ceiling currently makes
            # this unreachable, but preserve the invariant if either changes.
            raise AnswerRejected()
        remaining = MAX_ANSWER_TEXT_BYTES - quote_bytes
        bounded: list[dict[str, Any]] = []
        truncated = False
        for item in reviewed:
            title, title_shortened, title_bytes = cls._bounded_utf8_prefix(
                item["title"], remaining
            )
            if title_shortened or not title:
                truncated = True
                break
            excerpt_source = item["excerpt"][:1200]
            excerpt, excerpt_shortened, excerpt_bytes = cls._bounded_utf8_prefix(
                excerpt_source, remaining - title_bytes
            )
            if not excerpt:
                truncated = True
                break
            bounded.append({**item, "title": title, "excerpt": excerpt})
            remaining -= title_bytes + excerpt_bytes
            if len(excerpt_source) < len(item["excerpt"]):
                truncated = True
            if excerpt_shortened:
                truncated = True
                break
        if len(bounded) < len(reviewed):
            truncated = True
        return bounded, truncated

    def answer(
        self,
        ctx: TenantContext,
        question: str,
        search_current: Callable[[], dict[str, Any]],
        *,
        source_focus: SourceFocus = "all",
    ) -> dict[str, Any]:
        if self.selector is None:
            raise AnswerUnavailable()
        if source_focus not in {"all", "email", "fileos"}:
            raise AnswerRejected()
        grouped = search_current()
        coverage = grouped.get("coverage")
        if (
            not isinstance(coverage, dict)
            or coverage.get("complete") is not False
            or coverage.get("source_focus", "all") != source_focus
        ):
            raise AnswerRejected()
        reviewed = self._knowledge_hits(grouped, source_focus)
        passages: list[AnswerPassage] = []
        candidate_hits = self._hits(grouped, source_focus)
        remaining_bytes = MAX_CONTEXT_BYTES
        context_truncated = False
        for ordinal, hit in enumerate(candidate_hits):
            if remaining_bytes == 0:
                context_truncated = True
                break
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
                or not isinstance(content.get("truncated", False), bool)
                or not isinstance(body_sha256, str)
                or not _SHA256.fullmatch(body_sha256)
            ):
                # One evidence can have multiple derivatives. Do not cite a
                # search hit with another document's extracted body.
                continue
            if source_focus != "all" and metadata["source_kind"] != source_focus:
                raise AnswerRejected()
            if content.get("truncated", False):
                context_truncated = True
            bounded, shortened, used_bytes = self._bounded_utf8_prefix(
                content["content"], min(MAX_PASSAGE_BYTES, remaining_bytes)
            )
            if shortened:
                context_truncated = True
            if not bounded:
                context_truncated = True
                break
            remaining_bytes -= used_bytes
            passages.append(AnswerPassage(
                evidence_id, document_id, source_id, metadata["source_kind"],
                bounded, body_sha256,
            ))
            if remaining_bytes == 0 and ordinal + 1 < len(candidate_hits):
                context_truncated = True
                break
        if not passages:
            refreshed_grouped = search_current()
            self._recheck_focus(refreshed_grouped, source_focus)
            self._recheck_knowledge(reviewed, refreshed_grouped, source_focus)
            bounded_reviewed, output_truncated = self._bound_answer_text(
                [], [item for item, _ in reviewed]
            )
            return self._response(
                "no_supported_answer" if bounded_reviewed else "no_supported_evidence",
                [], coverage, bounded_reviewed, context_truncated, output_truncated,
            )
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
        refreshed_grouped = search_current()
        self._recheck_focus(refreshed_grouped, source_focus)
        self._recheck_knowledge(reviewed, refreshed_grouped, source_focus)
        refreshed = self._hits(refreshed_grouped, source_focus)
        current = {
            (hit.get("evidence_id"), hit.get("document_id")) for hit in refreshed
        }
        if any((item["evidence_id"], item["document_id"]) not in current for item in citations):
            raise AnswerStale()
        # Search membership alone cannot prove that a cited body or its source
        # grant stayed the same while the selector was working. Reopen only the
        # selected evidence, bounded to the original passage size, before reply.
        for item in citations:
            passage = by_id[item["evidence_id"]]
            try:
                metadata = self.brain.evidence(ctx, passage.evidence_id)
                content = self.brain.evidence_content(
                    ctx, passage.evidence_id, max_chars=MAX_PASSAGE_CHARS
                )
            except NotFound:
                raise AnswerStale() from None
            if (
                metadata.get("document_id") != passage.document_id
                or metadata.get("source_id") != passage.source_id
                or metadata.get("source_kind") != passage.source_kind
                or content.get("document_id") != passage.document_id
                or content.get("body_sha256") != passage.body_sha256
                or not isinstance(content.get("content"), str)
                or not content["content"].startswith(passage.content)
            ):
                raise AnswerStale()
        bounded_reviewed, output_truncated = self._bound_answer_text(
            citations, [item for item, _ in reviewed]
        )
        return self._response(
            "quoted_evidence" if citations else "no_supported_answer",
            citations, coverage, bounded_reviewed, context_truncated, output_truncated,
        )

    @staticmethod
    def _response(
        status: str,
        citations: list[dict[str, Any]],
        coverage: dict[str, Any],
        reviewed_knowledge: list[dict[str, Any]],
        context_truncated: bool,
        output_truncated: bool,
    ) -> dict[str, Any]:
        return {
            "mode": "grounded_extractive_v1",
            "status": status,
            "answer": (
                "Relevant passages from current indexed evidence are quoted below."
                if citations else (
                    "No exact source quote selected; reviewed knowledge matches are listed below."
                    if reviewed_knowledge else (
                        "No exact quote selected from the bounded current evidence context."
                        if context_truncated else
                        "No supported answer from current indexed evidence."
                    )
                )
            ),
            "citations": citations,
            "reviewed_knowledge": reviewed_knowledge,
            "coverage": {
                "complete": False,
                "answer_context_truncated": context_truncated,
                "answer_output_truncated": output_truncated,
                "source_focus": coverage.get("source_focus", "all"),
                "source_access": coverage.get("source_access"),
                "source_availability": coverage.get("source_availability"),
                "knowledge": (
                    "reviewed_assertions_listed_not_synthesized"
                    if coverage.get("source_focus", "all") == "all" else "not_searched"
                ),
            },
            "untrusted_content": True,
        }
