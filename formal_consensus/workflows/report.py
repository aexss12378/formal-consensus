"""由批次產物建立不呼叫模型的 JSON 與 Markdown 摘要。"""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
from typing import Any

from ..core.io_utils import read_json, utc_now_iso, write_json_atomic
from .postprocess import load_frozen_run


def _round_context_metrics(
    problem_dir: Path, completed_rounds: list[int]
) -> list[dict[str, Any]]:
    metrics: list[dict[str, Any]] = []
    for round_number in completed_rounds:
        round_dir = problem_dir / "rounds" / f"round_{round_number:03d}"
        snapshot = read_json(round_dir / "frozen_pool_before_round.json")
        prompt_tokens: dict[str, int | None] = {}
        api_turns: dict[str, int] = {}
        for agent_path in sorted(round_dir.glob("agent_*.json")):
            # 排除失敗紀錄；它們的檔名以 _error.json 結尾。
            if agent_path.name.endswith("_error.json"):
                continue
            output = read_json(agent_path)
            name = output.get("model_name")
            if not isinstance(name, str):
                continue
            responses = output.get("api_responses", [])
            api_turns[name] = len(responses) if isinstance(responses, list) else 0
            first_usage = (
                responses[0].get("usage", {})
                if isinstance(responses, list) and responses
                else {}
            )
            value = first_usage.get("prompt_tokens")
            prompt_tokens[name] = value if isinstance(value, int) else None
        metrics.append(
            {
                "round": round_number,
                "shared_pool_size_before_round": len(snapshot),
                "first_request_prompt_tokens_by_model": prompt_tokens,
                "api_turns_by_model": api_turns,
            }
        )
    return metrics


def build_report(run_dir: Path) -> tuple[Path, Path]:
    root = run_dir.expanduser().resolve()
    _, problems, _, _ = load_frozen_run(root)
    rows: list[dict[str, Any]] = []
    for problem_id in problems:
        problem_dir = root / "problems" / problem_id
        state = read_json(problem_dir / "state.json")
        statuses = Counter(item["status"] for item in state.get("candidates", []))
        row: dict[str, Any] = {
            "problem_id": problem_id,
            "statement_fidelity_status": problems[
                problem_id
            ].statement_fidelity_status,
            "status": state["status"],
            "stop_reason": state.get("stop_reason"),
            "completed_rounds": state.get("completed_rounds", []),
            "submitted_candidates": len(state.get("candidates", [])),
            "accepted_unique_verified": len(state.get("shared_pool", [])),
            "candidate_status_counts": dict(sorted(statuses.items())),
            "formal_validity_scope": (
                "Lean 通過只證明固定 theorem statement，不證明自然語言轉寫忠實度"
            ),
        }
        row["round_context_metrics"] = _round_context_metrics(
            problem_dir, list(state.get("completed_rounds", []))
        )
        method_path = problem_dir / "method_review_summary.json"
        if method_path.exists():
            method_rows = read_json(method_path).get("candidates", [])
            row["method_review_status_counts"] = dict(
                Counter(item["status"] for item in method_rows)
            )
        representative_path = problem_dir / "representatives.json"
        if representative_path.exists():
            representative_rows = read_json(representative_path).get("groups", [])
            row["representative_status_counts"] = dict(
                Counter(item["status"] for item in representative_rows)
            )
            row["selected_representatives"] = [
                {
                    "primary_technique": item["primary_technique"],
                    "candidate_id": item["selected_candidate_id"],
                }
                for item in representative_rows
                if item.get("selected_candidate_id") is not None
            ]
        rows.append(row)

    report = {
        "schema_version": 1,
        "run_dir": str(root),
        "generated_at": utc_now_iso(),
        "problems": rows,
    }
    json_path = root / "report.json"
    write_json_atomic(json_path, report)

    lines = [
        "# 三模型 Lean 形式溝通實驗摘要",
        "",
        "Lean 驗證只判定固定形式命題的證明是否成立；不等同於自然語言題目與命題的忠實度驗證。",
        "",
    ]
    for row in rows:
        lines.extend(
            [
                f"## {row['problem_id']}",
                "",
                f"- 執行狀態：{row['status']}",
                f"- 命題忠實度狀態：{row['statement_fidelity_status']}",
                f"- 停止原因：{row['stop_reason']}",
                f"- 完成輪次：{row['completed_rounds']}",
                f"- 提交候選數：{row['submitted_candidates']}",
                f"- 唯一且通過驗證的候選數：{row['accepted_unique_verified']}",
                f"- 候選狀態：{row['candidate_status_counts']}",
                f"- 各輪共享池與首請求 token：{row['round_context_metrics']}",
                "",
            ]
        )
        if "method_review_status_counts" in row:
            lines.insert(-1, f"- 方法審查：{row['method_review_status_counts']}")
        if "representative_status_counts" in row:
            lines.insert(-1, f"- 代表選擇：{row['representative_status_counts']}")
    markdown_path = root / "report.md"
    markdown_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return json_path, markdown_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        json_path, markdown_path = build_report(args.run_dir)
    except (ValueError, OSError) as exc:
        raise SystemExit(f"報告建立失敗：{exc}") from exc
    print(json_path)
    print(markdown_path)


if __name__ == "__main__":
    main()
