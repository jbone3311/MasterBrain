from __future__ import annotations

import unittest

from email_brain.rules.engine import Predicate, Rule, RuleEngine


class RuleEngineTests(unittest.TestCase):
    def test_specific_high_priority_rule_wins_and_trace_is_stable(self) -> None:
        rules = [
            Rule(
                rule_id="generic-promo",
                version=1,
                priority=10,
                all_of=(Predicate("sender_domain", frozenset({"example.com"})),),
                effects={"canonical_mailbox": "review_delete"},
                source="learned",
            ),
            Rule(
                rule_id="important-investment",
                version=2,
                priority=100,
                all_of=(Predicate("sender_address", frozenset({"partner@example.com"})),),
                effects={
                    "importance": "always_surface",
                    "canonical_mailbox": "investments",
                },
                source="user",
            ),
        ]

        result = RuleEngine().evaluate(
            rules,
            {
                "sender_domain": "example.com",
                "sender_address": "partner@example.com",
            },
        )

        self.assertEqual(result.effects["canonical_mailbox"], "investments")
        self.assertEqual(result.effects["importance"], "always_surface")
        self.assertEqual(result.matched_rule_versions[0], "important-investment:v2")
        self.assertTrue(result.conflicts)

    def test_unsupported_predicates_and_effects_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            Predicate("python", frozenset({"do_something()"}))

        with self.assertRaises(ValueError):
            Rule(
                rule_id="unsafe",
                version=1,
                priority=1,
                all_of=(Predicate("sender_domain", frozenset({"example.com"})),),
                effects={"execute": "shell"},
                source="model",
            )

    def test_protected_keep_is_a_veto_even_at_lower_priority(self) -> None:
        predicate = (Predicate("sender_domain", frozenset({"example.invalid"})),)
        rules = [
            Rule(
                "promo",
                1,
                100,
                predicate,
                {"importance": "low", "canonical_mailbox": "review_delete"},
                "model",
            ),
            Rule("protected", 1, 1, predicate, {"importance": "always_keep"}, "user"),
        ]
        result = RuleEngine().evaluate(rules, {"sender_domain": "example.invalid"})
        self.assertNotIn("canonical_mailbox", result.effects)
        self.assertIn("protected_keep_overrode_review_delete", result.conflicts)

    def test_rule_effects_cannot_be_mutated_after_validation(self) -> None:
        effects = {"category": "investment"}
        rule = Rule(
            "safe",
            1,
            1,
            (Predicate("sender_domain", frozenset({"example.invalid"})),),
            effects,
            "user",
        )
        effects["category"] = "changed"
        self.assertEqual(rule.effects["category"], "investment")


if __name__ == "__main__":
    unittest.main()
