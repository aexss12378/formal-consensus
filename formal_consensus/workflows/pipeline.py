"""三模型同步共享池候選產生流程。"""

from __future__ import annotations

import argparse
import copy
import json
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Mapping, Sequence

from ..agents.agent import RoundAgent, build_default_agents
from ..core.config import ExperimentConfig, load_config, load_taxonomy
from ..core.io_utils import (
    create_unique_directory,
    read_json,
    utc_now_iso,
    write_json_atomic,
)
from ..core.schemas import (
    AgentSubmission,
    Problem,
    SchemaError,
    compute_proof_hash,
    load_problem_bank,
    public_pool_entry,
    validate_agent_submission,
)
from ..tools.lean_runner import LeanRunner


class PipelineError(RuntimeError):
    """批次無法在不破壞實驗條件的情況下繼續。"""


class ConsensusPipeline:
    def __init__(
        self,
        config: ExperimentConfig,
        problems: Mapping[str, Problem],
        taxonomy_version: str,
        primary_techniques: Sequence[str],
        agents: Sequence[RoundAgent],
        lean_runner: LeanRunner,
    ):
        self.config = config
        self.problems = dict(problems)
        self.taxonomy_version = taxonomy_version
        self.primary_techniques = tuple(primary_techniques)
        self.agents = list(agents)
        self.lean_runner = lean_runner
        configured_names = [model.name for model in config.models]
        agent_names = [agent.model.name for agent in agents]
        if agent_names != configured_names:
            raise PipelineError(
                "agents 的順序與名稱必須和 config.models 完全相同；"
                f"預期 {configured_names}，實際 {agent_names}"
            )

    def select_problems(self, problem_ids: Sequence[str]) -> list[Problem]:
        selected: list[Problem] = []
        for problem_id in problem_ids:
            if problem_id not in self.problems:
                raise PipelineError(f"題庫沒有 problem_id：{problem_id}")
            problem = self.problems[problem_id]
            if problem.taxonomy_version != self.taxonomy_version:
                raise PipelineError(
                    f"{problem_id} 的 taxonomy_version "
                    f"({problem.taxonomy_version}) 與 taxonomy.json "
                    f"({self.taxonomy_version}) 不同"
                )
            selected.append(problem)
        if not selected:
            raise PipelineError("至少要選一題")
        # 系統起草的命題必須經人確認才能證明：命題寫錯時 Lean 照樣會通過。
        unconfirmed = [
            problem.problem_id
            for problem in selected
            if problem.statement_fidelity_status == "unresolved"
        ]
        if unconfirmed:
            raise PipelineError(
                f"以下題目的 Lean 命題尚未經人確認：{unconfirmed}。"
                "請比對命題與原題，一致後把 statement_fidelity_status 改成 confirmed"
            )
        return selected

    def run(self, problem_ids: Sequence[str], run_dir: Path | None = None) -> Path:
        selected = self.select_problems(problem_ids)

        target = (
            run_dir.expanduser().resolve()
            if run_dir is not None
            else create_unique_directory(self.config.runs_dir)
        )
        target.mkdir(parents=True, exist_ok=True)
        self._freeze_or_validate_run_inputs(target, selected)

        run_state_path = target / "run_state.json"
        run_state = self._load_or_initialize_run_state(run_state_path, selected)
        try:
            for problem in selected:
                self._run_problem(target, problem)
                run_state["problems"][problem.problem_id] = self._problem_summary(
                    target, problem.problem_id
                )
                run_state["updated_at"] = utc_now_iso()
                write_json_atomic(run_state_path, run_state)
        except Exception as exc:
            run_state["status"] = "interrupted"
            run_state["error"] = str(exc)
            run_state["updated_at"] = utc_now_iso()
            for problem in selected:
                state_path = target / "problems" / problem.problem_id / "state.json"
                if state_path.exists():
                    run_state["problems"][problem.problem_id] = self._problem_summary(
                        target, problem.problem_id
                    )
            write_json_atomic(run_state_path, run_state)
            raise

        summaries = list(run_state["problems"].values())
        run_state["status"] = (
            "complete"
            if all(item.get("status") == "complete" for item in summaries)
            else "interrupted"
        )
        run_state.pop("error", None)
        run_state["updated_at"] = utc_now_iso()
        write_json_atomic(run_state_path, run_state)
        return target

    def _freeze_or_validate_run_inputs(
        self, run_dir: Path, selected: Sequence[Problem]
    ) -> None:
        frozen = {
            "config.json": self.config.to_dict(),
            "taxonomy.json": {
                "version": self.taxonomy_version,
                "primary_techniques": list(self.primary_techniques),
            },
            "input.json": {
                "schema_version": 1,
                "problems": [problem.to_dict() for problem in selected],
            },
        }
        for filename, expected in frozen.items():
            path = run_dir / filename
            if path.exists():
                actual = read_json(path)
                if actual != expected:
                    raise PipelineError(
                        f"續跑拒絕：{filename} 與該批次凍結內容不同"
                    )
            else:
                write_json_atomic(path, expected)

    @staticmethod
    def _load_or_initialize_run_state(
        path: Path, selected: Sequence[Problem]
    ) -> dict[str, Any]:
        if path.exists():
            state = read_json(path)
            frozen_ids = state.get("problem_ids")
            expected_ids = [problem.problem_id for problem in selected]
            if frozen_ids != expected_ids:
                raise PipelineError("run_state.json 的題目集合或順序不同")
            return state
        now = utc_now_iso()
        state = {
            "schema_version": 1,
            "status": "running",
            "problem_ids": [problem.problem_id for problem in selected],
            "problems": {},
            "created_at": now,
            "updated_at": now,
        }
        write_json_atomic(path, state)
        return state

    def _run_problem(self, run_dir: Path, problem: Problem) -> None:
        problem_dir = run_dir / "problems" / problem.problem_id
        problem_dir.mkdir(parents=True, exist_ok=True)
        state_path = problem_dir / "state.json"
        state = self._load_or_initialize_problem_state(state_path, problem)
        if state["status"] == "complete":
            return
        state["status"] = "running"
        state.pop("last_error", None)
        self._save_problem_state(problem_dir, state)

        while state["status"] != "complete":
            round_number = state["next_round"]
            if round_number > self.config.max_rounds:
                state["status"] = "complete"
                state["stop_reason"] = "max_rounds"
                self._save_problem_state(problem_dir, state)
                break
            self._run_round(problem_dir, problem, state, round_number)
            state = read_json(state_path)

    @staticmethod
    def _load_or_initialize_problem_state(
        path: Path, problem: Problem
    ) -> dict[str, Any]:
        if path.exists():
            state = read_json(path)
            if state.get("problem_id") != problem.problem_id:
                raise PipelineError(f"state.json 題號不符：{path}")
            return state
        now = utc_now_iso()
        state = {
            "schema_version": 1,
            "problem_id": problem.problem_id,
            "statement_fidelity_status": problem.statement_fidelity_status,
            "status": "running",
            "next_round": 1,
            "completed_rounds": [],
            "stop_reason": None,
            "shared_pool": [],
            "candidates": [],
            "failures": [],
            "created_at": now,
            "updated_at": now,
        }
        write_json_atomic(path, state)
        return state

    def _run_round(
        self,
        problem_dir: Path,
        problem: Problem,
        state: dict[str, Any],
        round_number: int,
    ) -> None:
        round_dir = problem_dir / "rounds" / f"round_{round_number:03d}"
        round_dir.mkdir(parents=True, exist_ok=True)
        snapshot = [public_pool_entry(item) for item in state["shared_pool"]]
        snapshot_path = round_dir / "frozen_pool_before_round.json"
        if snapshot_path.exists() and read_json(snapshot_path) != snapshot:
            raise PipelineError(
                f"第 {round_number} 輪的既有共享池快照與 state.json 不一致"
            )
        write_json_atomic(snapshot_path, snapshot)

        try:
            outputs = self._collect_agent_outputs(
                round_dir, problem, snapshot, round_number
            )
        except Exception as exc:
            state["status"] = "api_failed"
            state["last_error"] = str(exc)
            state["updated_at"] = utc_now_iso()
            self._save_problem_state(problem_dir, state)
            raise
        records, accepted, failures, tool_failed = self._verify_round(
            problem, state, outputs, round_number
        )
        write_json_atomic(
            round_dir / "backend_verification.json",
            {
                "schema_version": 1,
                "round": round_number,
                "records": records,
            },
        )

        if tool_failed:
            state["status"] = "tool_failed"
            state["last_error"] = (
                "後端 Lean 工具層失敗；本輪尚未入池，可在修復工具後續跑"
            )
            state["updated_at"] = utc_now_iso()
            self._save_problem_state(problem_dir, state)
            raise PipelineError(state["last_error"])

        # 本輪所有模型完成且所有候選均經後端驗證後，才原子性更新共享池。
        state["candidates"].extend(records)
        state["failures"].extend(failures)
        state["shared_pool"].extend(accepted)
        state["completed_rounds"].append(round_number)
        state["next_round"] = round_number + 1

        # 只要共享池有新增內容，就必須再開一輪，讓其他模型真的看見它。
        # 代理只有呼叫 stop 才會結束一輪，所以旗標恆為 True，不再用它分辨停止原因；
        # 想知道本輪有沒有人交了卻沒通過，查 failures.json。
        if not accepted:
            state["status"] = "complete"
            state["stop_reason"] = "no_new_verified_candidate"
        elif round_number >= self.config.max_rounds:
            state["status"] = "complete"
            state["stop_reason"] = "max_rounds"
        else:
            state["status"] = "running"
            state["stop_reason"] = None
        state["updated_at"] = utc_now_iso()

        write_json_atomic(
            problem_dir / f"pool_after_round_{round_number:03d}.json",
            [public_pool_entry(item) for item in state["shared_pool"]],
        )
        self._save_problem_state(problem_dir, state)

    def _collect_agent_outputs(
        self,
        round_dir: Path,
        problem: Problem,
        snapshot: Sequence[dict[str, Any]],
        round_number: int,
    ) -> dict[str, dict[str, Any]]:
        outputs: dict[str, dict[str, Any]] = {}
        missing: list[RoundAgent] = []
        for agent in self.agents:
            path = round_dir / f"agent_{agent.model.name}.json"
            if path.exists():
                output = read_json(path)
                self._validate_agent_output(
                    output, agent, snapshot, round_number
                )
                outputs[agent.model.name] = output
            else:
                missing.append(agent)

        errors: list[dict[str, str]] = []
        if missing:
            with ThreadPoolExecutor(max_workers=len(missing)) as executor:
                futures = {
                    executor.submit(
                        agent.run_round,
                        problem,
                        copy.deepcopy(list(snapshot)),
                        round_number,
                        self.primary_techniques,
                    ): agent
                    for agent in missing
                }
                for future in as_completed(futures):
                    agent = futures[future]
                    try:
                        output = future.result()
                        self._validate_agent_output(
                            output, agent, snapshot, round_number
                        )
                        outputs[agent.model.name] = output
                        write_json_atomic(
                            round_dir / f"agent_{agent.model.name}.json", output
                        )
                    except Exception as exc:
                        error = {
                            "model_name": agent.model.name,
                            "error": str(exc),
                            "traceback": traceback.format_exc(),
                            "recorded_at": utc_now_iso(),
                        }
                        errors.append(error)
                        write_json_atomic(
                            round_dir / f"agent_{agent.model.name}_error.json", error
                        )

        if errors:
            names = [item["model_name"] for item in errors]
            raise PipelineError(
                f"第 {round_number} 輪模型呼叫失敗：{names}；"
                "已完成的模型輸出已保存，續跑時不會重複呼叫"
            )
        expected = [model.name for model in self.config.models]
        if sorted(outputs) != sorted(expected):
            raise PipelineError(f"第 {round_number} 輪模型輸出不完整")
        return outputs

    def _validate_agent_output(
        self,
        output: Any,
        agent: RoundAgent,
        snapshot: Sequence[dict[str, Any]],
        round_number: int,
    ) -> AgentSubmission:
        if not isinstance(output, dict) or output.get("schema_version") != 1:
            raise PipelineError(f"{agent.model.name} 輸出 schema 不合法")
        if output.get("model_name") != agent.model.name:
            raise PipelineError(f"{agent.model.name} 輸出 model_name 不符")
        if output.get("model_id") != agent.model.model_id:
            raise PipelineError(f"{agent.model.name} 輸出 model_id 不符")
        if output.get("round") != round_number:
            raise PipelineError(f"{agent.model.name} 輸出 round 不符")
        visible_ids = [item["candidate_id"] for item in snapshot]
        if output.get("frozen_pool_candidate_ids") != visible_ids:
            raise PipelineError(f"{agent.model.name} 讀到的共享池快照不符")
        try:
            return validate_agent_submission(
                output.get("submission"),
                primary_techniques=self.primary_techniques,
                visible_candidate_ids=visible_ids,
                max_candidates=self.config.max_candidates_per_agent_per_round,
            )
        except SchemaError as exc:
            raise PipelineError(f"{agent.model.name} submission 不合法：{exc}") from exc

    def _verify_round(
        self,
        problem: Problem,
        state: dict[str, Any],
        outputs: Mapping[str, dict[str, Any]],
        round_number: int,
    ) -> tuple[
        list[dict[str, Any]],
        list[dict[str, Any]],
        list[dict[str, Any]],
        bool,
    ]:
        records: list[dict[str, Any]] = []
        accepted: list[dict[str, Any]] = []
        failures: list[dict[str, Any]] = []
        known_hashes = {
            item["proof_hash"]: item["candidate_id"] for item in state["shared_pool"]
        }
        tool_failed = False

        # 固定依 config.models 排序，不受 API 回覆快慢影響候選編號與去重結果。
        for model in self.config.models:
            output = outputs[model.name]
            submission = self._validate_agent_output(
                output,
                next(agent for agent in self.agents if agent.model.name == model.name),
                [public_pool_entry(item) for item in state["shared_pool"]],
                round_number,
            )
            for index, candidate in enumerate(submission.candidates, start=1):
                submission_id = (
                    f"{problem.problem_id}__r{round_number:03d}__"
                    f"{model.name}__c{index:03d}"
                )
                proof_hash = compute_proof_hash(candidate.proof_body)
                checked = self.lean_runner.check(
                    problem,
                    candidate.proof_body,
                    f"backend_{submission_id}",
                )
                record: dict[str, Any] = {
                    "submission_id": submission_id,
                    "problem_id": problem.problem_id,
                    "round": round_number,
                    "model_name": model.name,
                    "model_id": model.model_id,
                    "action": candidate.action,
                    "derived_from": list(candidate.derived_from),
                    "primary_technique_claim": candidate.primary_technique,
                    "proof_body": candidate.proof_body,
                    "proof_hash": proof_hash,
                    "backend_lean_check": checked.to_dict(),
                    "recorded_at": utc_now_iso(),
                }
                if checked.status == "tool_failed":
                    record["status"] = "tool_failed"
                    failures.append(record)
                    tool_failed = True
                elif not checked.verified:
                    record["status"] = checked.status
                    failures.append(record)
                elif proof_hash in known_hashes:
                    record["status"] = "duplicate_verified"
                    record["duplicate_of"] = known_hashes[proof_hash]
                else:
                    candidate_id = (
                        f"{problem.problem_id}__C"
                        f"{len(state['shared_pool']) + len(accepted) + 1:04d}"
                    )
                    record["candidate_id"] = candidate_id
                    record["status"] = "accepted_verified"
                    known_hashes[proof_hash] = candidate_id
                    accepted.append(record)
                records.append(record)
        return records, accepted, failures, tool_failed

    @staticmethod
    def _save_problem_state(problem_dir: Path, state: dict[str, Any]) -> None:
        write_json_atomic(problem_dir / "state.json", state)
        write_json_atomic(problem_dir / "candidates.json", state["candidates"])
        write_json_atomic(problem_dir / "failures.json", state["failures"])

    @staticmethod
    def _problem_summary(run_dir: Path, problem_id: str) -> dict[str, Any]:
        state = read_json(run_dir / "problems" / problem_id / "state.json")
        return {
            "status": state["status"],
            "stop_reason": state.get("stop_reason"),
            "completed_rounds": list(state.get("completed_rounds", [])),
            "shared_pool_size": len(state.get("shared_pool", [])),
            "submitted_candidate_count": len(state.get("candidates", [])),
            "failure_count": len(state.get("failures", [])),
        }


def build_pipeline(config_path: Path, input_path: Path) -> ConsensusPipeline:
    config = load_config(config_path)
    taxonomy_version, techniques = load_taxonomy(config.taxonomy_path)
    problems = load_problem_bank(input_path)
    lean_runner = LeanRunner(
        config.lean_project_dir,
        config.lean_timeout_seconds,
        config.repl_path,
    )
    agents = build_default_agents(config, lean_runner)
    return ConsensusPipeline(
        config,
        problems,
        taxonomy_version,
        techniques,
        agents,
        lean_runner,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--unit", help="只執行指定 problem_id")
    selection.add_argument("--all", action="store_true", help="依輸入順序執行全部題目")
    parser.add_argument(
        "--run-dir",
        type=Path,
        help="指定新批次資料夾，或續跑既有批次",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    pipeline = build_pipeline(args.config, args.input)
    problem_ids = list(pipeline.problems) if args.all else [args.unit]
    try:
        run_dir = pipeline.run(problem_ids, args.run_dir)
    except (PipelineError, SchemaError, ValueError, OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"執行失敗：{exc}") from exc
    finally:
        pipeline.lean_runner.close()
    print(run_dir)


if __name__ == "__main__":
    main()
