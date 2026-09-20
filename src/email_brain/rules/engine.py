"""A deliberately small, non-executable rule engine.

The first implementation supports exact membership predicates only. Regex,
SQL, templates, and network lookups are intentionally absent. New operators
need bounded-complexity validation and adversarial tests.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType

ALLOWED_FIELDS = frozenset(
    {
        "sender_address",
        "sender_domain",
        "list_id",
        "subject_token",
        "account_id",
        "current_mailbox",
    }
)
ALLOWED_EFFECTS = frozenset(
    {
        "category",
        "project_id",
        "importance",
        "canonical_mailbox",
        "request_extraction",
    }
)
PROTECTED_KEEP_VALUES = frozenset({"always_keep", "always_surface"})


@dataclass(frozen=True, slots=True)
class Predicate:
    field: str
    any_of: frozenset[str]

    def __post_init__(self) -> None:
        if self.field not in ALLOWED_FIELDS:
            raise ValueError(f"unsupported predicate field: {self.field}")
        if not self.any_of or len(self.any_of) > 100:
            raise ValueError("predicate any_of must contain 1..100 values")
        if any(len(value) > 320 for value in self.any_of):
            raise ValueError("predicate value is too long")

    def matches(self, facts: Mapping[str, str | Sequence[str]]) -> bool:
        actual = facts.get(self.field)
        if actual is None:
            return False
        values = {actual} if isinstance(actual, str) else set(actual)
        return bool(values & self.any_of)


@dataclass(frozen=True, slots=True)
class Rule:
    rule_id: str
    version: int
    priority: int
    all_of: tuple[Predicate, ...]
    effects: Mapping[str, str | bool]
    source: str

    def __post_init__(self) -> None:
        if not self.rule_id or self.version < 1:
            raise ValueError("rule requires a stable id and positive version")
        if not self.all_of or len(self.all_of) > 20:
            raise ValueError("rule must contain 1..20 predicates")
        unknown = set(self.effects) - ALLOWED_EFFECTS
        if unknown:
            raise ValueError(f"unsupported effects: {sorted(unknown)}")
        if not self.effects:
            raise ValueError("at least one effect required")
        for key, value in self.effects.items():
            if key == "request_extraction":
                if not isinstance(value, bool):
                    raise ValueError("request_extraction must be boolean")
            elif not isinstance(value, str) or not 1 <= len(value) <= 120:
                raise ValueError("metadata effects must be bounded nonempty strings")
        object.__setattr__(self, "effects", MappingProxyType(dict(self.effects)))

    def matches(self, facts: Mapping[str, str | Sequence[str]]) -> bool:
        return all(predicate.matches(facts) for predicate in self.all_of)


@dataclass(frozen=True, slots=True)
class RuleEvaluation:
    effects: Mapping[str, str | bool]
    matched_rule_versions: tuple[str, ...]
    conflicts: tuple[str, ...] = field(default_factory=tuple)


class RuleEngine:
    """Evaluate immutable rules in deterministic priority/id/version order."""

    def evaluate(
        self, rules: Sequence[Rule], facts: Mapping[str, str | Sequence[str]]
    ) -> RuleEvaluation:
        matched = [rule for rule in rules if rule.matches(facts)]
        matched.sort(key=lambda rule: (-rule.priority, rule.rule_id, -rule.version))

        effects: dict[str, str | bool] = {}
        owners: dict[str, str] = {}
        conflicts: list[str] = []
        for rule in matched:
            identity = f"{rule.rule_id}:v{rule.version}"
            for key, value in rule.effects.items():
                if key not in effects:
                    effects[key] = value
                    owners[key] = identity
                elif effects[key] != value:
                    conflicts.append(f"{key}:{owners[key]}!={identity}")

        # Safety protection is a veto, not an ordinary priority-wins effect.
        if any(rule.effects.get("importance") in PROTECTED_KEEP_VALUES for rule in matched):
            if effects.get("canonical_mailbox") == "review_delete":
                effects.pop("canonical_mailbox")
                conflicts.append("protected_keep_overrode_review_delete")

        return RuleEvaluation(
            effects=effects,
            matched_rule_versions=tuple(f"{rule.rule_id}:v{rule.version}" for rule in matched),
            conflicts=tuple(conflicts),
        )
