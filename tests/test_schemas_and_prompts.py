from __future__ import annotations

import unittest
from pathlib import Path
from subprocess import CompletedProcess
from tempfile import TemporaryDirectory
from unittest.mock import patch

from formal_consensus.agents.prompts import format_shared_pool
from formal_consensus.core.schemas import (
    Problem,
    SchemaError,
    public_pool_entry,
    validate_agent_submission,
)
from formal_consensus.tools.lean_runner import (
    LeanRunner,
    ReplLeanRunner,
    validate_proof_body,
)


class SchemaAndPromptTests(unittest.TestCase):
    @staticmethod
    def problem() -> Problem:
        return Problem(
            problem_id="q1",
            problem_text="Formal benchmark.",
            lean_imports=("import Mathlib",),
            lean_theorem_header="theorem q1 : True :=",
            taxonomy_version="test",
            statement_fidelity_status="formal_benchmark",
        )

    def test_lean_runner_rejects_sorry_warning_with_backticks(self) -> None:
        completed = CompletedProcess(
            args=["lake", "build"],
            returncode=0,
            stdout="warning: declaration uses `sorry`",
            stderr="",
        )
        with TemporaryDirectory() as temporary, patch(
            "formal_consensus.tools.lean_runner.subprocess.run",
            return_value=completed,
        ):
            result = LeanRunner(Path(temporary), 10).check(
                self.problem(),
                "by\n  apply?",
                "sorry_warning",
            )
        self.assertEqual(result.status, "proof_failed")
        self.assertFalse(result.verified)

    def test_repl_runner_accepts_only_closed_error_free_proof(self) -> None:
        cases = (
            ({"env": 1}, "verified", True),
            (
                {
                    "env": 2,
                    "messages": [
                        {"severity": "error", "data": "unsolved goals"}
                    ],
                },
                "proof_failed",
                False,
            ),
            (
                {
                    "env": 3,
                    "messages": [
                        {
                            "severity": "warning",
                            "data": "declaration uses `sorry`",
                        }
                    ],
                },
                "proof_failed",
                False,
            ),
            (
                {"env": 4, "sorries": [{"goal": "⊢ True"}]},
                "proof_failed",
                False,
            ),
        )
        for response, expected_status, expected_verified in cases:
            with self.subTest(response=response):
                runner = ReplLeanRunner(Path("."), 10, Path("repl"))
                with patch.object(runner, "_base_env", return_value=0), patch.object(
                    runner,
                    "_request",
                    return_value=response,
                ):
                    result = runner.check(self.problem(), "by trivial", "check")
                self.assertEqual(result.status, expected_status)
                self.assertEqual(result.verified, expected_verified)

    def setUp(self) -> None:
        self.labels = ["Power Rule"]

    def test_private_fields_never_enter_public_pool(self) -> None:
        internal = {
            "candidate_id": "q1__C0001",
            "round": 1,
            "derived_from": [],
            "proof_body": "by norm_num",
            "model_name": "gpt",
            "model_id": "secret-model",
            "primary_technique_claim": "Power Rule",
            "proof_hash": "abc",
        }
        public = public_pool_entry(internal)
        self.assertEqual(
            set(public),
            {
                "candidate_id",
                "round",
                "derived_from",
                "primary_technique",
                "proof_body",
            },
        )
        rendered = format_shared_pool([internal])
        self.assertNotIn("secret-model", rendered)
        self.assertNotIn("gpt", rendered)
        # 方法標籤刻意公開，讓下一輪看得出哪些方法已經有人做過。
        self.assertIn("Power Rule", rendered)

    def test_derived_candidate_must_reference_visible_candidate(self) -> None:
        with self.assertRaises(SchemaError):
            validate_agent_submission(
                {
                    "stop": False,
                    "candidates": [
                        {
                            "action": "derived",
                            "derived_from": ["unknown"],
                            "primary_technique": "Power Rule",
                            "proof_body": "by norm_num",
                        }
                    ],
                },
                primary_techniques=self.labels,
                visible_candidate_ids=["q1__C0001"],
                max_candidates=5,
            )

    def test_proof_body_rejects_incomplete_or_natural_language_channels(self) -> None:
        for proof in (
            "by sorry",
            "by\n  admit",
            "by\n  -- use the power rule\n  norm_num",
            "by\n  /- hidden discussion -/\n  norm_num",
            "```lean\nby norm_num\n```",
        ):
            with self.subTest(proof=proof), self.assertRaises(ValueError):
                validate_proof_body(proof)

    def test_complete_proof_body_is_normalized(self) -> None:
        self.assertEqual(validate_proof_body("  by\r\n  norm_num  \r\n"), "by\n  norm_num")


if __name__ == "__main__":
    unittest.main()
