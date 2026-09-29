"""在每個已確認方法群組內盲選一份代表 Lean 證明。"""

from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from ..agents.prompts import (
    SELECTION_SYSTEM_PROMPT,
    representative_selection_prompt,
    representative_selection_tool,
)
from ..core.config import ModelConfig
from ..core.io_utils import read_json, utc_now_iso, write_json_atomic
from ..tools.model_api import ApiClient, call_required_tool
from .postprocess import load_complete_problem_state, load_frozen_run


def _selection_validator(valid_ids: set[str]):
    def validate(raw: dict[str, Any]) -> dict[str, str]:
        candidate_id = raw.get("candidate_id")
        reason = raw.get("reason")
        if candidate_id not in valid_ids:
            raise ValueError("candidate_id 不在本方法群組的匿名選項中")
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("reason 必須是非空字串")
        return {"candidate_id": candidate_id, "reason": reason.strip()}

    return validate


def aggregate_selection_votes(
    votes: list[dict[str, Any]], option_to_candidate: dict[str, str]
) -> tuple[str, str]:
    counts = Counter(vote["selection"]["candidate_id"] for vote in votes)
    winner, count = counts.most_common(1)[0]
    if count >= 2:
        return winner, "selected_by_majority"
    # 三票各選一份時，每個選項都已通過 Lean 驗證與方法審查，選哪份都成立；
    # 取候選編號最小（最早入池）的一份，不等人工選定。
    return min(counts, key=option_to_candidate.__getitem__), "selected_by_tiebreak"


def _select_one(
    client: ApiClient,
    model: ModelConfig,
    problem: Any,
    technique: str,
    anonymous_candidates: list[dict[str, Any]],
) -> dict[str, Any]:
    valid_ids = {item["candidate_id"] for item in anonymous_candidates}
    selection, responses = call_required_tool(
        client,
        model,
        system_prompt=SELECTION_SYSTEM_PROMPT,
        user_prompt=representative_selection_prompt(
            problem, technique, anonymous_candidates
        ),
        tool=representative_selection_tool(sorted(valid_ids)),
        tool_name="select_representative",
        validate=_selection_validator(valid_ids),
    )
    return {
        "reviewer_name": model.name,
        "reviewer_model_id": model.model_id,
        "selection": selection,
        "api_responses": responses,
        "recorded_at": utc_now_iso(),
    }


def run_representative_selection(run_dir: Path) -> Path:
    root = run_dir.expanduser().resolve()
    config, problems, _, techniques = load_frozen_run(root)
    clients = {
        model.name: ApiClient(
            config.api_for(model),
            timeout_seconds=config.api_timeout_seconds,
            max_attempts=config.max_api_attempts,
        )
        for model in config.models
    }
    all_results: dict[str, Any] = {}

    for problem_id, problem in problems.items():
        state = load_complete_problem_state(root, problem_id)
        candidate_by_id = {
            candidate["candidate_id"]: candidate
            for candidate in state["shared_pool"]
        }
        review_path = root / "problems" / problem_id / "method_review_summary.json"
        if not review_path.is_file():
            raise ValueError(f"缺少方法審查結果：{review_path}")
        review = read_json(review_path)
        groups: dict[str, list[dict[str, Any]]] = {}
        for row in review.get("candidates", []):
            if row.get("status") != "confirmed":
                continue
            technique = row["claimed_primary_technique"]
            groups.setdefault(technique, []).append(
                candidate_by_id[row["candidate_id"]]
            )

        problem_rows: list[dict[str, Any]] = []
        errors: list[str] = []
        selection_dir = root / "problems" / problem_id / "selection_votes"
        selection_dir.mkdir(parents=True, exist_ok=True)
        for technique_index, technique in enumerate(techniques, start=1):
            candidates = groups.get(technique, [])
            if not candidates:
                continue
            if len(candidates) == 1:
                problem_rows.append(
                    {
                        "primary_technique": technique,
                        "candidate_ids": [candidates[0]["candidate_id"]],
                        "status": "selected_singleton",
                        "selected_candidate_id": candidates[0]["candidate_id"],
                        "votes": [],
                    }
                )
                continue

            # 模型只看匿名選項，候選 ID 不洩漏原始模型或輪次。
            option_to_candidate = {
                f"OPTION_{index:03d}": candidate["candidate_id"]
                for index, candidate in enumerate(candidates, start=1)
            }
            anonymous = [
                {
                    "candidate_id": option,
                    "proof_body": candidate_by_id[candidate_id]["proof_body"],
                }
                for option, candidate_id in option_to_candidate.items()
            ]
            votes: list[dict[str, Any]] = []
            jobs: list[tuple[ModelConfig, Path]] = []
            for model in config.models:
                path = selection_dir / (
                    f"technique_{technique_index:03d}__{model.name}.json"
                )
                if path.exists():
                    vote = read_json(path)
                    if (
                        vote.get("primary_technique") != technique
                        or vote.get("reviewer_name") != model.name
                        or vote.get("option_to_candidate") != option_to_candidate
                    ):
                        raise ValueError(f"既有代表選擇檔案識別不符：{path}")
                    votes.append(vote)
                else:
                    jobs.append((model, path))

            with ThreadPoolExecutor(max_workers=3) as executor:
                futures = {
                    executor.submit(
                        _select_one,
                        clients[model.name],
                        model,
                        problem,
                        technique,
                        anonymous,
                    ): (model, path)
                    for model, path in jobs
                }
                for future in as_completed(futures):
                    model, path = futures[future]
                    try:
                        vote = future.result()
                    except Exception as exc:
                        errors.append(f"{technique}／{model.name}：{exc}")
                        continue
                    vote["schema_version"] = 1
                    vote["problem_id"] = problem_id
                    vote["primary_technique"] = technique
                    vote["option_to_candidate"] = option_to_candidate
                    write_json_atomic(path, vote)
                    votes.append(vote)

            if errors:
                # 這一組票數必定不完整，先跳過，讓其他方法群組把票跑完再一起回報。
                continue

            votes.sort(
                key=lambda item: [m.name for m in config.models].index(
                    item["reviewer_name"]
                )
            )
            if len(votes) != 3:
                raise RuntimeError(f"{technique} 的代表選擇票數不完整")
            winning_option, status = aggregate_selection_votes(
                votes, option_to_candidate
            )
            problem_rows.append(
                {
                    "primary_technique": technique,
                    "candidate_ids": [item["candidate_id"] for item in candidates],
                    "status": status,
                    "selected_candidate_id": option_to_candidate[winning_option],
                    "option_to_candidate": option_to_candidate,
                    "votes": votes,
                }
            )

        if errors:
            raise RuntimeError(
                f"{problem_id} 有 {len(errors)} 筆代表解選擇失敗；已完成的票已保存，"
                f"用相同批次續跑不會重複呼叫：{errors}"
            )

        result = {
            "schema_version": 1,
            "problem_id": problem_id,
            "groups": problem_rows,
            "completed_at": utc_now_iso(),
        }
        write_json_atomic(
            root / "problems" / problem_id / "representatives.json", result
        )
        all_results[problem_id] = result

    output = root / "representatives.json"
    write_json_atomic(
        output,
        {
            "schema_version": 1,
            "problems": all_results,
            "completed_at": utc_now_iso(),
        },
    )
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        print(run_representative_selection(args.run_dir))
    except (ValueError, RuntimeError, OSError) as exc:
        raise SystemExit(f"代表解選擇失敗：{exc}") from exc


if __name__ == "__main__":
    main()
