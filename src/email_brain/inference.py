"""Pure inference boundary helpers; no network, tools, provider secrets, or auto-actions."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from email_brain.schemas import Classification


class Route(StrEnum):
    CODE = "code"
    LOCAL = "local"
    REMOTE = "remote"
    HUMAN = "human"


@dataclass(frozen=True)
class RoutingPolicy:
    allow_remote: bool = False
    local_available: bool = False
    remote_budget_remaining: bool = False


def route(
    *, deterministic_match: bool, consequential: bool, local_failed: bool, policy: RoutingPolicy
) -> Route:
    if consequential:
        return Route.HUMAN
    if deterministic_match:
        return Route.CODE
    if policy.local_available and not local_failed:
        return Route.LOCAL
    if policy.allow_remote and policy.remote_budget_remaining:
        return Route.REMOTE
    return Route.HUMAN


def validate_classification(output: str, source_text: str) -> Classification:
    if len(output.encode()) > 4096:
        raise ValueError("model output exceeds limit")
    result = Classification.model_validate_json(output)
    if not result.evidence_excerpt or result.evidence_excerpt not in source_text:
        raise ValueError("model evidence is not present in the source")
    # A model's claimed confidence is telemetry, not authorization or calibrated probability.
    return result


def reciprocal_rank_fusion(rankings: list[list[str]], limit: int = 50) -> list[tuple[str, float]]:
    """Fuse already-authorized candidate IDs; never broaden access after retrieval."""
    if not 1 <= limit <= 50 or len(rankings) > 5 or any(len(r) > 200 for r in rankings):
        raise ValueError("retrieval limits exceeded")
    scores: dict[str, float] = {}
    for ranking in rankings:
        seen: set[str] = set()
        for rank, identifier in enumerate(ranking, start=1):
            if identifier not in seen:
                scores[identifier] = scores.get(identifier, 0.0) + 1 / (60 + rank)
                seen.add(identifier)
    return sorted(scores.items(), key=lambda item: (-item[1], item[0]))[:limit]
