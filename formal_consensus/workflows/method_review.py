"""由三個固定模型盲審已驗證候選的主要方法標籤。"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from ..agents.prompts import (
    METHOD_REVIEW_SYSTEM_PROMPT,
    METHOD_REVIEW_TOOL,
    method_review_prompt,
)
from ..core.config import ModelConfig
from ..core.io_utils import read_json, utc_now_iso, write_json_atomic
from ..tools.model_api import ApiClient, call_required_tool
from .postprocess import load_complete_problem_state, load_frozen_run, safe_component


def validate_method_review(raw: dict[str, Any]) -> dict[str, str]:
    verdict = raw.get("verdict")
    reason = raw.get("reason")
    if verdict not in {"pass", "questionable", "fail"}:
        raise ValueError("verdict 必須是 pass、questionable 或 fail")
    if not isinstance(reason, str) or not reason.strip():
        raise ValueError("reason 必須是非空字串")
    return {"verdict": verdict, "reason": reason.strip()}


def aggregate_method_votes(votes: list[dict[str, Any]]) -> str:
    counts = {
        verdict: sum(vote["review"]["verdict"] == verdict for vote in votes)
        for verdict in ("pass", "questionable", "fail")
    }
    if counts["pass"] >= 2:
        return "confirmed"
    if counts["fail"] >= 2:
        return "rejected"
    return "unresolved"


def _review_one(
    client: ApiClient,
    model: ModelConfig,
    problem: Any,
    candidate: dict[str, Any],
) -> dict[str, Any]:
    review, responses = call_required_tool(
        client,
        model,
        system_prompt=METHOD_REVIEW_SYSTEM_PROMPT,
        user_prompt=method_review_prompt(problem, candidate),
        tool=METHOD_REVIEW_TOOL,
        tool_name="review_method",
        validate=validate_method_review,
    )
    return {
        "schema_version": 1,
        "candidate_id": candidate["candidate_id"],
        "reviewer_name": model.name,
        "reviewer_model_id": model.model_id,
        "review": review,
        "api_responses": responses,
        "recorded_at": utc_now_iso(),
    }


def run_method_review(run_dir: Path) -> Path:
    root = run_dir.expanduser().resolve()
    config, problems, _, _ = load_frozen_run(root)
    clients = {
        model.name: ApiClient(
            config.api_for(model),
            timeout_seconds=config.api_timeout_seconds,
            max_attempts=config.max_api_attempts,
        )
        for model in config.models
    }

    for problem_id, problem in problems.items():
        state = load_complete_problem_state(root, problem_id)
        candidates = list(state["shared_pool"])
        review_dir = root / "problems" / problem_id / "method_reviews"
        review_dir.mkdir(parents=True, exist_ok=True)
        jobs: list[tuple[dict[str, Any], ModelConfig, Path]] = []
        votes_by_candidate: dict[str, list[dict[str, Any]]] = {
            candidate["candidate_id"]: [] for candidate in candidates
        }
        for candidate in candidates:
            for model in config.models:
                path = review_dir / (
                    f"{safe_component(candidate['candidate_id'])}__{model.name}.json"
                )
                if path.exists():
                    vote = read_json(path)
                    if (
                        vote.get("candidate_id") != candidate["candidate_id"]
                        or vote.get("reviewer_name") != model.name
                        or vote.get("reviewer_model_id") != model.model_id
                    ):
                        raise ValueError(f"既有方法審查檔案識別不符：{path}")
                    validate_method_review(vote.get("review", {}))
                    votes_by_candidate[candidate["candidate_id"]].append(vote)
                else:
                    jobs.append((candidate, model, path))

        # 單一審查失敗不能連累同批已完成的票：逐一保存，最後才一起回報。
        errors: list[str] = []
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {
                executor.submit(
                    _review_one,
                    clients[model.name],
                    model,
                    problem,
                    candidate,
                ): (
                    candidate,
                    model,
                    path,
                )
                for candidate, model, path in jobs
            }
            for future in as_completed(futures):
                candidate, model, path = futures[future]
                try:
                    vote = future.result()
                except Exception as exc:
                    errors.append(
                        f"{candidate['candidate_id']}／{model.name}：{exc}"
                    )
                    continue
                write_json_atomic(path, vote)
                votes_by_candidate[candidate["candidate_id"]].append(vote)

        if errors:
            raise RuntimeError(
                f"{problem_id} 有 {len(errors)} 筆方法審查失敗；已完成的票已保存，"
                f"用相同批次續跑不會重複呼叫：{errors}"
            )

        rows: list[dict[str, Any]] = []
        for candidate in candidates:
            votes = sorted(
                votes_by_candidate[candidate["candidate_id"]],
                key=lambda item: [m.name for m in config.models].index(
                    item["reviewer_name"]
                ),
            )
            if len(votes) != 3:
                raise RuntimeError(f"{candidate['candidate_id']} 方法審查票數不完整")
            counts = {
                verdict: sum(
                    vote["review"]["verdict"] == verdict for vote in votes
                )
                for verdict in ("pass", "questionable", "fail")
            }
            rows.append(
                {
                    "candidate_id": candidate["candidate_id"],
                    "claimed_primary_technique": candidate[
                        "primary_technique_claim"
                    ],
                    "status": aggregate_method_votes(votes),
                    "vote_counts": counts,
                    "votes": votes,
                }
            )
        summary = {
            "schema_version": 1,
            "problem_id": problem_id,
            "aggregation_rule": (
                "confirmed if pass>=2; rejected if fail>=2; otherwise unresolved"
            ),
            "candidates": rows,
            "completed_at": utc_now_iso(),
        }
        write_json_atomic(
            root / "problems" / problem_id / "method_review_summary.json", summary
        )

    return root


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        print(run_method_review(args.run_dir))
    except (ValueError, RuntimeError, OSError) as exc:
        raise SystemExit(f"方法審查失敗：{exc}") from exc


if __name__ == "__main__":
    main()
