"""以單一模型與單一題目驗證完整 Lean 工具迴圈。"""

from __future__ import annotations

import argparse
import json
import traceback
from pathlib import Path
from typing import Any

from ..agents.agent import ToolCallingProofAgent
from ..core.config import load_config, load_taxonomy
from ..core.io_utils import (
    create_unique_directory,
    read_json,
    utc_now_iso,
    write_json_atomic,
)
from ..core.schemas import SchemaError, load_problem_bank
from ..tools.lean_runner import LeanRunner
from ..tools.model_api import ApiClient, ApiError


class PreflightError(RuntimeError):
    """單模型工具迴圈未完成或沒有產生通過驗證的 proof。"""


def run_preflight(
    config_path: Path,
    input_path: Path,
    model_name: str,
    problem_id: str,
) -> Path:
    config = load_config(config_path)
    taxonomy_version, techniques = load_taxonomy(config.taxonomy_path)
    problems = load_problem_bank(input_path)

    models = {model.name: model for model in config.models}
    if model_name not in models:
        raise PreflightError(
            f"找不到模型 {model_name}；可用模型：{', '.join(models)}"
        )
    if problem_id not in problems:
        raise PreflightError(
            f"找不到題目 {problem_id}；可用題目：{', '.join(problems)}"
        )

    problem = problems[problem_id]
    if problem.taxonomy_version != taxonomy_version:
        raise PreflightError(
            f"{problem_id} 的 taxonomy_version 與 taxonomy.json 不同"
        )

    model = models[model_name]
    output_dir = create_unique_directory(config.runs_dir / "preflight")
    output_path = output_dir / "result.json"
    result: dict[str, Any] = {
        "schema_version": 1,
        "status": "running",
        "purpose": "technical_preflight_not_research_data",
        "model": model.to_dict(),
        "problem": problem.to_dict(),
        "shared_pool": [],
        "started_at": utc_now_iso(),
    }
    write_json_atomic(output_path, result)

    lean_runner = LeanRunner(
        config.lean_project_dir,
        config.lean_timeout_seconds,
        config.repl_path,
    )
    client = ApiClient(
        config.api_for(model),
        timeout_seconds=config.api_timeout_seconds,
        max_attempts=config.max_api_attempts,
    )
    agent = ToolCallingProofAgent(model, config, client, lean_runner)

    try:
        agent_result = agent.run_round(problem, [], 1, techniques)
        backend_results: list[dict[str, Any]] = []
        for index, candidate in enumerate(
            agent_result["submission"]["candidates"], start=1
        ):
            checked = lean_runner.check(
                problem,
                candidate["proof_body"],
                f"preflight_backend_{problem_id}_{model_name}_{index:03d}",
            )
            backend_results.append(
                {
                    "candidate_index": index,
                    "proof_body": candidate["proof_body"],
                    "primary_technique": candidate["primary_technique"],
                    "lean_result": checked.to_dict(),
                }
            )

        passed = any(
            item["lean_result"]["verified"] for item in backend_results
        )
        result.update(
            {
                "status": "passed" if passed else "failed",
                "agent_result": agent_result,
                "backend_results": backend_results,
                "verified_candidate_count": sum(
                    item["lean_result"]["verified"] for item in backend_results
                ),
                "finished_at": utc_now_iso(),
            }
        )
        if not backend_results:
            result["failure_reason"] = "模型沒有提交候選 proof"
        elif not passed:
            result["failure_reason"] = "所有候選都未通過後端 Lean 重驗"
        write_json_atomic(output_path, result)
        return output_path
    except Exception as exc:
        result.update(
            {
                "status": "error",
                "error_type": type(exc).__name__,
                "error": str(exc),
                "traceback": traceback.format_exc(),
                "finished_at": utc_now_iso(),
            }
        )
        write_json_atomic(output_path, result)
        raise PreflightError(f"preflight 執行錯誤；紀錄位於 {output_path}") from exc
    finally:
        lean_runner.close()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--problem", required=True)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    try:
        output = run_preflight(
            args.config,
            args.input,
            args.model,
            args.problem,
        )
    except (
        PreflightError,
        SchemaError,
        ApiError,
        ValueError,
        OSError,
        json.JSONDecodeError,
    ) as exc:
        raise SystemExit(f"preflight 失敗：{exc}") from exc
    outcome = read_json(output)
    print(output)
    if outcome.get("status") != "passed":
        raise SystemExit(
            f"preflight 未通過：{outcome.get('failure_reason', '未知原因')}"
        )


if __name__ == "__main__":
    main()
