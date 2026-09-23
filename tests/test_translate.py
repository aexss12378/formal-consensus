from __future__ import annotations

import unittest

from formal_consensus.workflows.translate import validate_translation


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


if __name__ == "__main__":
    unittest.main()
