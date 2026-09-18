from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from formal_consensus.agents.agent import (
    MAX_PROTOCOL_VIOLATIONS,
    ToolCallingProofAgent,
)
from formal_consensus.core.config import ApiConfig, ExperimentConfig, ModelConfig
from formal_consensus.core.schemas import Problem
from formal_consensus.tools.lean_runner import LeanCheckResult
from formal_consensus.tools.model_api import ChatResult


class FakeClient:
    def __init__(self):
        self.calls = 0

    def chat(self, model, messages, tools, *, tool_choice="auto"):
        self.calls += 1
        if self.calls == 1:
            name = "lean_check"
            arguments = '{"proof_body": "by\\n  exact?"}'
        elif self.calls == 2:
            search_result = messages[-1]
            self._search_result_reached_model = (
                search_result["role"] == "tool"
                and "Try this: exact rfl" in search_result["content"]
            )
            name = "lean_submit"
            arguments = (
                '{"action": "new", "derived_from": [], '
                '"primary_technique": "Power Rule", '
                '"proof_body": "by norm_num"}'
            )
        else:
            verify_result = messages[-1]
            self._verify_result_reached_model = (
                verify_result["role"] == "tool"
                and '"candidate_saved": true' in verify_result["content"]
            )
            name = "stop"
            arguments = "{}"
        return ChatResult(
            assistant_message={
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": f"call-{self.calls}",
                        "type": "function",
                        "function": {"name": name, "arguments": arguments},
                    }
                ],
            },
            finish_reason="tool_calls",
            usage={"prompt_tokens": 1},
            response_id=f"response-{self.calls}",
            response_model=model.model_id,
            response_provider="fake-provider",
            attempts=1,
        )


class FakeLean:
    def check(self, problem, proof_body, check_id):
        diagnostics = (
            "Try this: exact rfl" if "private_search" in check_id else None
        )
        return LeanCheckResult(
            status="verified",
            verified=True,
            lean_file="proof.lean",
            module_name="Proof",
            error=None,
            elapsed_seconds=0.0,
            command=["fake-lake"],
            diagnostics=diagnostics,
        )


class ProseOnlyClient:
    """永遠回文字，從不呼叫工具。"""

    def __init__(self):
        self.calls = 0

    def chat(self, model, messages, tools, *, tool_choice="auto"):
        self.calls += 1
        return ChatResult(
            assistant_message={
                "role": "assistant",
                "content": "The proof follows from the power rule.",
            },
            finish_reason="stop",
            usage={"prompt_tokens": 1},
            response_id=f"response-{self.calls}",
            response_model=model.model_id,
            response_provider="fake-provider",
            attempts=1,
        )


class UnusedLean:
    def check(self, problem, proof_body, check_id):
        raise AssertionError("代理沒有呼叫工具時不應該跑 Lean")


class AgentTests(unittest.TestCase):
    def test_agent_uses_private_lean_then_structured_submission(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            model = ModelConfig("gpt", "provider/gpt", 0.0, 100)
            config = ExperimentConfig(
                schema_version=1,
                models=(
                    model,
                    ModelConfig("gemini", "provider/gemini", 0.0, 100),
                    ModelConfig("claude", "provider/claude", 0.0, 100),
                ),
                max_rounds=1,
                max_candidates_per_agent_per_round=5,
                max_searches_per_agent_per_round=40,
                max_api_attempts=1,
                api_timeout_seconds=10,
                lean_timeout_seconds=10,
                apis={
                    "openrouter": ApiConfig(
                        "https://example.invalid", "UNUSED"
                    )
                },
                lean_project_dir=root,
                runs_dir=root,
                taxonomy_path=root / "taxonomy.json",
                source_path=root / "config.json",
            )
            problem = Problem(
                problem_id="q1",
                problem_text="A formal benchmark.",
                lean_imports=("import Mathlib",),
                lean_theorem_header="theorem q1 : 1 + 1 = 2 :=",
                taxonomy_version="test",
                statement_fidelity_status="formal_benchmark",
            )
            client = FakeClient()
            agent = ToolCallingProofAgent(model, config, client, FakeLean())
            result = agent.run_round(problem, [], 1, ["Power Rule"])
            self.assertEqual(client.calls, 3)
            self.assertTrue(client._search_result_reached_model)
            self.assertTrue(client._verify_result_reached_model)
            self.assertEqual(len(result["private_lean_searches"]), 1)
            self.assertEqual(len(result["private_lean_verifications"]), 1)
            self.assertTrue(result["submission"]["stop"])
            self.assertEqual(
                result["submission"]["candidates"][0]["proof_body"],
                "by norm_num",
            )


    def test_agent_aborts_round_after_repeated_protocol_violations(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            model = ModelConfig("gpt", "provider/gpt", 0.0, 100)
            config = ExperimentConfig(
                schema_version=1,
                models=(model,),
                max_rounds=1,
                max_candidates_per_agent_per_round=5,
                max_searches_per_agent_per_round=40,
                max_api_attempts=1,
                api_timeout_seconds=10,
                lean_timeout_seconds=10,
                apis={
                    "openrouter": ApiConfig(
                        "https://example.invalid", "UNUSED"
                    )
                },
                lean_project_dir=root,
                runs_dir=root,
                taxonomy_path=root / "taxonomy.json",
                source_path=root / "config.json",
            )
            problem = Problem(
                problem_id="q1",
                problem_text="A formal benchmark.",
                lean_imports=("import Mathlib",),
                lean_theorem_header="theorem q1 : 1 + 1 = 2 :=",
                taxonomy_version="test",
                statement_fidelity_status="formal_benchmark",
            )
            client = ProseOnlyClient()
            agent = ToolCallingProofAgent(model, config, client, UnusedLean())
            with self.assertRaises(RuntimeError) as caught:
                agent.run_round(problem, [], 1, ["Power Rule"])
            self.assertIn("沒有送出合法的單一工具", str(caught.exception))
            self.assertEqual(client.calls, MAX_PROTOCOL_VIOLATIONS)


if __name__ == "__main__":
    unittest.main()
