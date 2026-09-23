from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from formal_consensus.core.schemas import SchemaError
from formal_consensus.workflows.formalize import (
    load_teacher_problems,
    run_formalization,
    statement_validator,
)


class FakeStatementRunner:
    def __init__(self, error: str | None = None):
        self.error = error
        self.checked: list[str] = []

    def check_statement(self, problem):
        self.checked.append(problem.lean_theorem_header)
        return self.error


class FormalizeTests(unittest.TestCase):
    def test_valid_header_is_checked_by_lean(self) -> None:
        runner = FakeStatementRunner()
        validate = statement_validator("q1", runner)
        result = validate({"lean_theorem_header": "  theorem q1 : 1 + 1 = 2 :=  "})
        self.assertEqual(result, {"lean_theorem_header": "theorem q1 : 1 + 1 = 2 :="})
        self.assertEqual(runner.checked, ["theorem q1 : 1 + 1 = 2 :="])

    def test_malformed_headers_are_rejected_before_lean(self) -> None:
        runner = FakeStatementRunner()
        validate = statement_validator("q1", runner)
        for header in (
            "",
            "```lean\ntheorem q1 : 1 + 1 = 2 :=\n```",
            "theorem q1 : 1 + 1 = 2 := by norm_num",
            "theorem q1 : 1 + 1 = 2 := sorry :=",
            "theorem q1 : True :=\ntheorem q2 : 1 + 1 = 2 :=",
        ):
            with self.assertRaises(ValueError):
                validate({"lean_theorem_header": header})
        self.assertEqual(runner.checked, [])

    def test_lean_error_is_sent_back(self) -> None:
        validate = statement_validator("q1", FakeStatementRunner("unknown identifier"))
        with self.assertRaisesRegex(ValueError, "unknown identifier"):
            validate({"lean_theorem_header": "theorem q1 : foo = 2 :="})

    def test_teacher_input_needs_only_id_and_text(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "exam.json"
            path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "problems": [{"problem_id": "q1", "problem_text": " Prove it. "}],
                    }
                ),
                encoding="utf-8",
            )
            self.assertEqual(load_teacher_problems(path), {"q1": "Prove it."})
            path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "problems": [
                            {"problem_id": "q1", "problem_text": "a"},
                            {"problem_id": "q1", "problem_text": "b"},
                        ],
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaises(SchemaError):
                load_teacher_problems(path)

    def test_existing_draft_is_never_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            draft = Path(temporary) / "exam.draft.json"
            draft.write_text("人工修改過的草稿", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "輸出檔已存在"):
                run_formalization(
                    Path(temporary) / "exam.json", draft, Path("config.json")
                )
            self.assertEqual(draft.read_text(encoding="utf-8"), "人工修改過的草稿")


if __name__ == "__main__":
    unittest.main()
