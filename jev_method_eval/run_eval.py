"""透過 OpenRouter 試測 Jev 的課本主要方法分類，結果集中於 results/。"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sys
from datetime import datetime
import urllib.request
from zoneinfo import ZoneInfo

sys.dont_write_bytecode = True

EVAL_DIR = Path(__file__).resolve().parent
API_URL = "https://openrouter.ai/api/alpha/decisions"
MODEL = "typesafe/jev-1.13"
INSTRUCTIONS = (
    "判斷這份 Lean 證明實際使用的課本主要方法，從固定選項中選出一個。"
    "主要方法是組織整份解答、完成主要目標的數學策略；"
    "只用於局部計算、化簡或中間步驟的方法，屬於輔助方法。"
    "同一主要方法中的不同數學推導、參數選擇、證明順序或 tactic 寫法，"
    "不另算一種方法。請根據實際證明結構判斷，"
    "不要只依題目要求、命題形式、個別關鍵字或某個定理是否出現來分類。"
)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def build_request(case: dict, labels: list[str]) -> dict:
    """只取分類所需欄位；移除 theorem 名稱，不傳標準答案或來源。"""
    match = re.fullmatch(
        r"\s*theorem\s+\S+\s*:\s*(.*?)\s*:=\s*",
        case["lean_theorem_header"],
        flags=re.DOTALL,
    )
    if match is None:
        raise ValueError("Lean 命題須為 theorem 名稱 : 命題 := 格式")
    return {
        "model": MODEL,
        "state": {
            "problem_text": case["problem_text"],
            "lean_imports": case["lean_imports"],
            "lean_statement": match.group(1),
            "proof_body": case["proof_body"],
        },
        "questions": {
            "primary_method": {
                "type": "choice",
                "instructions": INSTRUCTIONS,
                "criteria": {label: None for label in labels},
            }
        },
    }


def call_jev(payload: dict, api_key: str) -> dict:
    request = urllib.request.Request(
        API_URL,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.loads(response.read().decode("utf-8"))


def prediction_from_response(response: dict, labels: list[str]) -> dict:
    answer = response["answers"]["primary_method"]
    if answer["type"] != "choice" or answer["choice"] not in labels:
        raise ValueError("API 回覆未提供有效的 Choice 方法標籤")
    probabilities = answer["probabilities"]
    values = [*probabilities.values(), answer["confidence"]]
    if set(probabilities) != set(labels) or any(
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or not 0 <= value <= 1
        for value in values
    ):
        raise ValueError("API 回覆的完整機率分布或信心值不符合格式")
    if not math.isclose(sum(probabilities.values()), 1, abs_tol=1e-5):
        raise ValueError("API 回覆的機率總和不為 1")
    if probabilities[answer["choice"]] < max(probabilities.values()) - 1e-5:
        raise ValueError("API 回覆的 Choice 不是最高機率選項")
    return {
        "primary_technique": answer["choice"],
        "probabilities": probabilities,
        "confidence": answer["confidence"],
    }


def summarize(records: list[dict]) -> dict:
    """只有分類齊全時才計算正確率與種類數，避免缺失資料扭曲結果。"""
    completed = [row for row in records if row["prediction"] is not None]
    correct = sum(
        row["prediction"]["primary_technique"] == row["reference"]["primary_technique"]
        for row in completed
    )
    complete = len(completed) == len(records)
    by_case_type = {}
    case_types = sorted({tag for row in records for tag in row["reference"]["case_types"]})
    for tag in case_types:
        rows = [row for row in records if tag in row["reference"]["case_types"]]
        ready = [row for row in rows if row["prediction"] is not None]
        hits = sum(row["correct"] is True for row in ready)
        by_case_type[tag] = {
            "total": len(rows),
            "classified": len(ready),
            "correct": hits,
            "accuracy": hits / len(rows) if len(ready) == len(rows) else None,
        }
    by_problem = {}
    for problem_id in sorted({row["problem_id"] for row in records}):
        rows = [row for row in records if row["problem_id"] == problem_id]
        expected = len({row["reference"]["primary_technique"] for row in rows})
        ready = all(row["prediction"] is not None for row in rows)
        predicted = (
            len({row["prediction"]["primary_technique"] for row in rows})
            if ready else None
        )
        by_problem[problem_id] = {
            "total": len(rows),
            "expected_method_count": expected,
            "predicted_method_count": predicted,
            "method_count_error": predicted - expected if ready else None,
        }
    return {
        "total": len(records),
        "classified": len(completed),
        "missing": len(records) - len(completed),
        "correct": correct,
        "accuracy": correct / len(records) if complete else None,
        "by_case_type": by_case_type,
        "by_problem": by_problem,
        "mean_absolute_method_count_error": (
            sum(abs(row["method_count_error"]) for row in by_problem.values())
            / len(by_problem) if complete else None
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=EVAL_DIR / "pilot_cases.json",
                        help="受測資料檔")
    parser.add_argument("--taxonomy", type=Path, default=EVAL_DIR.parent / "taxonomy.json",
                        help="完整課本方法清單")
    parser.add_argument("--output", type=Path, help="結果 JSON 路徑")
    parser.add_argument("--dry-run", action="store_true",
                        help="只檢查並保存請求，不呼叫 API，也不計分")
    args = parser.parse_args(argv)
    data = read_json(args.data)
    taxonomy = read_json(args.taxonomy)
    labels = taxonomy["primary_techniques"]
    cases = data["cases"]
    if not cases or not 1 <= len(labels) <= 255 or len(set(labels)) != len(labels):
        raise ValueError("案例須非空，方法須為 1 至 255 個不重複選項")
    if data["taxonomy_version"] != taxonomy["version"]:
        raise ValueError("受測資料與方法清單版本不一致")
    if len({case["case_id"] for case in cases}) != len(cases):
        raise ValueError("受測案例編號重複")
    if any(case["reference"]["primary_technique"] not in labels for case in cases):
        raise ValueError("標準方法標籤不在方法清單中")
    records = [
        {
            "case_id": case["case_id"],
            "problem_id": case["problem_id"],
            "reference": case["reference"],
            "request": build_request(case, labels),
            "response": None,
            "prediction": None,
            "correct": None,
            "error": None,
        }
        for case in cases
    ]
    api_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not args.dry_run and not api_key:
        raise ValueError("缺少 OPENROUTER_API_KEY 環境變數；可先使用 --dry-run")
    now = datetime.now(ZoneInfo("Asia/Taipei"))
    suffix = "dry_run" if args.dry_run else "evaluation"
    output = args.output or EVAL_DIR / "results" / f"{now:%Y%m%d_%H%M%S_%f}_{suffix}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    report = {
        "schema_version": 1,
        "status": "dry_run" if args.dry_run else "running",
        "started_at": now.isoformat(),
        "endpoint": API_URL,
        "requested_model": MODEL,
        "dataset_id": data["dataset_id"],
        "dataset_sha256": hashlib.sha256(args.data.read_bytes()).hexdigest(),
        "taxonomy_version": taxonomy["version"],
        "criteria_policy": "完整方法名稱作為選項，不另加個別方法說明。",
        "evaluation_note": "本次為小規模試測，結果只涵蓋受測解答，不代表正式合格判定。",
        "records": records,
        "summary": None,
    }
    exit_code = 0
    with output.open("x", encoding="utf-8") as handle:
        if not args.dry_run:
            for row in records:
                try:
                    row["response"] = call_jev(row["request"], api_key)
                    row["prediction"] = prediction_from_response(row["response"], labels)
                    row["correct"] = (
                        row["prediction"]["primary_technique"]
                        == row["reference"]["primary_technique"]
                    )
                    verdict = "正確" if row["correct"] else "錯誤"
                    print(f"{row['case_id']}：{row['prediction']['primary_technique']}（{verdict}）",
                          flush=True)
                except (KeyError, TypeError, ValueError, OSError) as exc:
                    row["error"] = str(exc)
                    print(f"{row['case_id']}：呼叫或回覆失敗：{exc}", file=sys.stderr)
                    exit_code = 1
                    break
                except KeyboardInterrupt:
                    row["error"] = "使用者中斷執行"
                    exit_code = 130
                    break
            report["status"] = "complete" if exit_code == 0 else "incomplete"
            report["summary"] = summarize(records)
        report["finished_at"] = datetime.now(ZoneInfo("Asia/Taipei")).isoformat()
        json.dump(report, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(f"結果已寫入：{output.resolve()}")
    if args.dry_run:
        print(f"已檢查 {len(cases)} 份請求、{len(labels)} 個方法選項；未呼叫 API。")
    elif exit_code == 0:
        summary = report["summary"]
        print(f"分類正確：{summary['correct']}/{summary['total']}；"
              f"平均絕對方法種類數誤差：{summary['mean_absolute_method_count_error']}")
    else:
        print("執行未完成，完整正確率與整體種類數誤差不計算。", file=sys.stderr)
    return exit_code


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (KeyError, TypeError, ValueError, OSError) as exc:
        print(f"無法執行評估：{exc}", file=sys.stderr)
        raise SystemExit(1)
