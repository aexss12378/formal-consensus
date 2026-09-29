from __future__ import annotations

import unittest

from formal_consensus.workflows.translate import _markdown, validate_translation


class TranslationTests(unittest.TestCase):
    def test_steps_are_trimmed(self) -> None:
        self.assertEqual(
            validate_translation({"steps": ["  Let x > 0. ", "Hence f is continuous."]}),
            {"steps": ["Let x > 0.", "Hence f is continuous."]},
        )

    def test_empty_or_non_string_steps_are_rejected(self) -> None:
        for raw in ({}, {"steps": []}, {"steps": ["ok", " "]}, {"steps": [1]}):
            with self.assertRaises(ValueError):
                validate_translation(raw)

    def test_formal_tool_words_are_rejected(self) -> None:
        for step in ("By the Lean proof, ...", "Use the linarith tactic.", "From Mathlib"):
            with self.assertRaises(ValueError):
                validate_translation({"steps": [step]})

    def test_ordinary_words_containing_lean_are_allowed(self) -> None:
        validate_translation({"steps": ["A clean factorization gives x + 2."]})

    def test_markdown_numbers_problems_and_solutions_without_internal_ids(self) -> None:
        text = _markdown(
            {
                "q4": {
                    "problem_text": "Show that f is continuous.",
                    "solutions": [
                        {"primary_technique": "Case Analysis", "candidate_id": "q4__C0001", "steps": ["a", "b"]},
                        {"primary_technique": "One-Sided Limits", "candidate_id": "q4__C0002", "steps": ["c"]},
                    ],
                },
                "q5": {"problem_text": "Find the limit.", "solutions": []},
            }
        )
        self.assertIn("## Problem 1\n\nShow that f is continuous.", text)
        self.assertIn("### Solution 1: Case Analysis\n\n1. a\n2. b", text)
        self.assertIn("### Solution 2: One-Sided Limits\n\n1. c", text)
        self.assertIn("## Problem 2\n\nFind the limit.\n\nNo verified solution", text)
        self.assertNotIn("C0001", text)
        self.assertNotIn("q4", text)


if __name__ == "__main__":
    unittest.main()
