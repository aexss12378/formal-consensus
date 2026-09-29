from __future__ import annotations

import dataclasses
import tempfile
import threading
import unittest
from pathlib import Path
from typing import Any, Sequence

from formal_consensus.core.config import ApiConfig, ExperimentConfig, ModelConfig
from formal_consensus.core.io_utils import read_json
from formal_consensus.core.schemas import Problem
from formal_consensus.tools.lean_runner import LeanCheckResult
from formal_consensus.workflows.pipeline import ConsensusPipeline, PipelineError
from formal_consensus.workflows.report import build_report


LABEL = "Power Rule"


class FakeLeanRunner:
    def check(self, problem: Problem, proof_body: str, check_id: str) -> LeanCheckResult:
        verified = "BAD" not in proof_body
        return LeanCheckResult(
            status="verified" if verified else "proof_failed",
            verified=verified,
            lean_file=f"{check_id}.lean",
            module_name=check_id,
            error=None if verified else "synthetic Lean error",
            elapsed_seconds=0.0,
            command=["fake-lake"],
        )


class ToolFailingLeanRunner:
    def check(self, problem: Problem, proof_body: str, check_id: str) -> LeanCheckResult:
        return LeanCheckResult(
            status="tool_failed",
            verified=False,
            lean_file=None,
            module_name=None,
            error="synthetic tool failure",
            elapsed_seconds=0.0,
            command=["fake-lake"],
        )


class ScriptedAgent:
    def __init__(self, model: ModelConfig, scripts: dict[int, dict[str, Any]]):
        self.model = model
        self.scripts = scripts
        self.seen: list[tuple[int, list[dict[str, Any]]]] = []
        self.calls = 0
        self.lock = threading.Lock()

    def run_round(
        self,
        problem: Problem,
        shared_pool: Sequence[dict[str, Any]],
        round_number: int,
        primary_techniques: Sequence[str],
    ) -> dict[str, Any]:
        with self.lock:
            self.calls += 1
            self.seen.append((round_number, list(shared_pool)))
        return {
            "schema_version": 1,
            "model_name": self.model.name,
            "model_id": self.model.model_id,
            "round": round_number,
            "frozen_pool_candidate_ids": [
                item["candidate_id"] for item in shared_pool
            ],
            "started_at": "start",
            "finished_at": "end",
            "submission": self.scripts[round_number],
            "private_lean_verifications": [],
            "api_responses": [],
        }


class FailingAgent(ScriptedAgent):
    def run_round(self, *args, **kwargs):
        with self.lock:
            self.calls += 1
        raise RuntimeError("synthetic API failure")


def submission(
    proof: str | None,
    *,
    stop: bool,
    action: str = "new",
    derived_from: list[str] | None = None,
) -> dict[str, Any]:
    candidates = []
    if proof is not None:
        candidates.append(
            {
                "action": action,
                "derived_from": derived_from or [],
                "primary_technique": LABEL,
                "proof_body": proof,
            }
        )
    return {"stop": stop, "candidates": candidates}


class PipelineTests(unittest.TestCase):
    def make_config(self, root: Path, max_rounds: int = 3) -> ExperimentConfig:
        models = tuple(
            ModelConfig(name, f"provider/{name}", 0.0, 100)
            for name in ("gpt", "gemini", "claude")
        )
        taxonomy = root / "taxonomy.json"
        taxonomy.write_text("{}", encoding="utf-8")
        source = root / "config_source.json"
        source.write_text("{}", encoding="utf-8")
        return ExperimentConfig(
            schema_version=1,
            models=models,
            max_rounds=max_rounds,
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
            lean_project_dir=root / "lean",
            runs_dir=root / "runs",
            taxonomy_path=taxonomy,
            source_path=source,
        )

    @staticmethod
    def problem() -> Problem:
        return Problem(
            problem_id="q1",
            problem_text="Prove one plus one equals two.",
            lean_imports=("import Mathlib",),
            lean_theorem_header="theorem q1 : 1 + 1 = 2 :=",
            taxonomy_version="test-v1",
            statement_fidelity_status="formal_benchmark",
        )

    def test_round_snapshot_is_synchronous_and_public_pool_is_anonymous(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = self.make_config(root)
            models = config.models
            agents = [
                ScriptedAgent(
                    models[0],
                    {
                        1: submission("by norm_num", stop=False),
                        2: submission(
                            "by decide",
                            stop=True,
                            action="derived",
                            derived_from=["q1__C0001"],
                        ),
                        3: submission(None, stop=True),
                    },
                ),
                ScriptedAgent(
                    models[1],
                    {
                        1: submission("by norm_num", stop=False),
                        2: submission(None, stop=True),
                        3: submission(None, stop=True),
                    },
                ),
                ScriptedAgent(
                    models[2],
                    {
                        1: submission("by omega", stop=False),
                        2: submission(None, stop=True),
                        3: submission(None, stop=True),
                    },
                ),
            ]
            lean = FakeLeanRunner()
            pipeline = ConsensusPipeline(
                config,
                {"q1": self.problem()},
                "test-v1",
                [LABEL],
                agents,
                lean,
            )
            run_dir = root / "run"
            pipeline.run(["q1"], run_dir)

            for agent in agents:
                self.assertEqual(agent.seen[0], (1, []))
                round_two_pool = agent.seen[1][1]
                self.assertEqual(
                    [item["candidate_id"] for item in round_two_pool],
                    ["q1__C0001", "q1__C0002"],
                )
                for item in round_two_pool:
                    self.assertEqual(
                        set(item),
                        {
                            "candidate_id",
                            "round",
                            "derived_from",
                            "primary_technique",
                            "proof_body",
                        },
                    )
                round_three_pool = agent.seen[2][1]
                self.assertEqual(
                    [item["candidate_id"] for item in round_three_pool],
                    ["q1__C0001", "q1__C0002", "q1__C0003"],
                )

            state = read_json(run_dir / "problems" / "q1" / "state.json")
            self.assertEqual(state["status"], "complete")
            self.assertEqual(state["stop_reason"], "no_new_verified_candidate")
            self.assertEqual(len(state["shared_pool"]), 3)
            self.assertEqual(
                sum(row["status"] == "duplicate_verified" for row in state["candidates"]),
                1,
            )
            for item in read_json(
                run_dir / "problems" / "q1" / "pool_after_round_002.json"
            ):
                self.assertNotIn("model_name", item)
                self.assertNotIn("primary_technique_claim", item)
                self.assertNotIn("gpt", item["candidate_id"])
                self.assertNotIn("gemini", item["candidate_id"])
                self.assertNotIn("claude", item["candidate_id"])
            report_markdown = build_report(run_dir)
            self.assertIn(
                "唯一且通過驗證的候選數：3", report_markdown.read_text(encoding="utf-8")
            )

    def test_partial_agent_outputs_are_reused_on_resume(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = self.make_config(root, max_rounds=1)
            scripts = {1: submission(None, stop=True)}
            first_agents = [
                ScriptedAgent(config.models[0], scripts),
                FailingAgent(config.models[1], scripts),
                ScriptedAgent(config.models[2], scripts),
            ]
            run_dir = root / "run"
            first = ConsensusPipeline(
                config,
                {"q1": self.problem()},
                "test-v1",
                [LABEL],
                first_agents,
                FakeLeanRunner(),
            )
            with self.assertRaises(PipelineError):
                first.run(["q1"], run_dir)
            self.assertTrue(
                (run_dir / "problems" / "q1" / "rounds" / "round_001" / "agent_gpt.json").exists()
            )
            self.assertTrue(
                (run_dir / "problems" / "q1" / "rounds" / "round_001" / "agent_claude.json").exists()
            )

            second_agents = [
                ScriptedAgent(config.models[0], scripts),
                ScriptedAgent(config.models[1], scripts),
                ScriptedAgent(config.models[2], scripts),
            ]
            resumed = ConsensusPipeline(
                config,
                {"q1": self.problem()},
                "test-v1",
                [LABEL],
                second_agents,
                FakeLeanRunner(),
            )
            resumed.run(["q1"], run_dir)
            self.assertEqual(second_agents[0].calls, 0)
            self.assertEqual(second_agents[1].calls, 1)
            self.assertEqual(second_agents[2].calls, 0)

    def test_lean_tool_failure_never_mutates_shared_pool(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = self.make_config(root, max_rounds=1)
            agents = [
                ScriptedAgent(
                    model,
                    {1: submission("by norm_num", stop=True)},
                )
                for model in config.models
            ]
            run_dir = root / "run"
            pipeline = ConsensusPipeline(
                config,
                {"q1": self.problem()},
                "test-v1",
                [LABEL],
                agents,
                ToolFailingLeanRunner(),
            )
            with self.assertRaises(PipelineError):
                pipeline.run(["q1"], run_dir)
            state = read_json(run_dir / "problems" / "q1" / "state.json")
            self.assertEqual(state["status"], "tool_failed")
            self.assertEqual(state["shared_pool"], [])
            self.assertEqual(state["candidates"], [])
            backend = read_json(
                run_dir
                / "problems"
                / "q1"
                / "rounds"
                / "round_001"
                / "backend_verification.json"
            )
            self.assertTrue(
                all(row["status"] == "tool_failed" for row in backend["records"])
            )


    def test_unconfirmed_statement_is_rejected_before_any_run_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = self.make_config(root)
            agents = [ScriptedAgent(model, {}) for model in config.models]
            problem = dataclasses.replace(
                self.problem(), statement_fidelity_status="unresolved"
            )
            pipeline = ConsensusPipeline(
                config, {"q1": problem}, "test-v1", [LABEL], agents, FakeLeanRunner()
            )
            run_dir = root / "run"
            with self.assertRaises(PipelineError) as caught:
                pipeline.run(["q1"], run_dir)
            self.assertIn("q1", str(caught.exception))
            self.assertFalse(run_dir.exists())
            self.assertEqual([agent.seen for agent in agents], [[], [], []])


if __name__ == "__main__":
    unittest.main()
