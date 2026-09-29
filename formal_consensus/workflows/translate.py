"""把每個方法的代表 proof 翻成學生看得懂的教學步驟解法。"""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any

from ..agents.prompts import (
    TRANSLATION_SYSTEM_PROMPT,
    TRANSLATION_TOOL,
    translation_prompt,
)
from ..core.config import load_config
from ..core.io_utils import read_json, utc_now_iso, write_json_atomic
from ..tools.model_api import ApiClient, call_required_tool
from .postprocess import load_complete_problem_state, load_frozen_run, safe_component

# 教學步驟給學生看，不能出現形式化工具的用語。
FORMAL_WORDS = re.compile(r"\b(lean|mathlib|tactics?)\b", re.IGNORECASE)


def validate_translation(raw: dict[str, Any]) -> dict[str, list[str]]:
    steps = raw.get("steps")
    if (
        not isinstance(steps, list)
        or not steps
        or any(not isinstance(step, str) or not step.strip() for step in steps)
    ):
        raise ValueError("steps 必須是非空字串陣列")
    cleaned = [step.strip() for step in steps]
    for step in cleaned:
        match = FORMAL_WORDS.search(step)
        if match:
            raise ValueError(
                f"steps 不得提到 {match.group(0)}；請改寫成學生看得懂的數學語言"
            )
    return {"steps": cleaned}


def _markdown(problems: dict[str, Any]) -> str:
    # 這份是交付文件：只放題目與解法；翻譯模型與代表解 ID 留在各題的 translations/ 與 representatives.json。
    lines = ["# Solutions", ""]
    for number, item in enumerate(problems.values(), start=1):
        lines += [f"## Problem {number}", "", item["problem_text"], ""]
        if not item["solutions"]:
            lines += ["No verified solution was produced for this problem.", ""]
        for index, row in enumerate(item["solutions"], start=1):
            lines += [f"### Solution {index}: {row['primary_technique']}", ""]
            lines += [
                f"{step_no}. {step}" for step_no, step in enumerate(row["steps"], start=1)
            ]
            lines += [""]
    return "\n".join(lines)


def run_translation(run_dir: Path, config_path: Path) -> Path:
    root = run_dir.expanduser().resolve()
    _, problems, _, _ = load_frozen_run(root)
    # 翻譯模型讀目前的設定檔，不讀批次凍結設定，所以舊批次也能補翻。
    config = load_config(config_path)
    model = config.translation_model
    if model is None:
        raise ValueError(f"{config_path} 沒有設定 translation_model")
    client = ApiClient(
        config.api_for(model),
        timeout_seconds=config.api_timeout_seconds,
        max_attempts=config.max_api_attempts,
    )

    all_results: dict[str, Any] = {}
    errors: list[str] = []
    for problem_id, problem in problems.items():
        state = load_complete_problem_state(root, problem_id)
        proof_by_id = {
            candidate["candidate_id"]: candidate["proof_body"]
            for candidate in state["shared_pool"]
        }
        representatives_path = root / "problems" / problem_id / "representatives.json"
        if not representatives_path.is_file():
            raise ValueError(f"缺少代表解結果：{representatives_path}")
        # 依模型分資料夾，換翻譯模型時舊結果保留，也不會擋住新翻譯。
        translation_dir = (
            root
            / "problems"
            / problem_id
            / "translations"
            / safe_component(model.model_id)
        )
        rows: list[dict[str, Any]] = []
        for group in read_json(representatives_path)["groups"]:
            technique = group["primary_technique"]
            candidate_id = group["selected_candidate_id"]
            path = translation_dir / f"{safe_component(candidate_id)}.json"
            if path.exists():
                record = read_json(path)
                if (
                    record.get("candidate_id") != candidate_id
                    or record.get("translator_model_id") != model.model_id
                ):
                    raise ValueError(f"既有翻譯檔案識別不符：{path}")
                rows.append(record)
                continue
            # 單題翻譯失敗不連累其他已完成的翻譯：逐一保存，最後才一起回報。
            try:
                output, responses = call_required_tool(
                    client,
                    model,
                    system_prompt=TRANSLATION_SYSTEM_PROMPT,
                    user_prompt=translation_prompt(
                        problem, technique, proof_by_id[candidate_id]
                    ),
                    tool=TRANSLATION_TOOL,
                    tool_name="submit_solution",
                    validate=validate_translation,
                )
            except Exception as exc:
                errors.append(f"{problem_id}／{technique}：{exc}")
                continue
            record = {
                "schema_version": 1,
                "problem_id": problem_id,
                "primary_technique": technique,
                "candidate_id": candidate_id,
                "translator_model_id": model.model_id,
                "steps": output["steps"],
                "api_responses": responses,
                "recorded_at": utc_now_iso(),
            }
            write_json_atomic(path, record)
            rows.append(record)
        all_results[problem_id] = {
            "problem_id": problem_id,
            "problem_text": problem.problem_text,
            "solutions": rows,
        }

    if errors:
        raise RuntimeError(
            f"有 {len(errors)} 筆翻譯失敗；已完成的翻譯已保存，"
            f"用相同批次續跑不會重複呼叫：{errors}"
        )

    markdown_path = root / "solutions.md"
    markdown_path.write_text(_markdown(all_results), encoding="utf-8")
    return markdown_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        markdown_path = run_translation(args.run_dir, args.config)
    except (ValueError, RuntimeError, OSError) as exc:
        raise SystemExit(f"翻譯失敗：{exc}") from exc
    print(markdown_path)


if __name__ == "__main__":
    main()
