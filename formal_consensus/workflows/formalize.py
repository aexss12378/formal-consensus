"""把老師的自然語言題目起草成 Lean 命題，輸出草稿給人確認。

這一步刻意停在草稿：命題寫錯時 Lean 照樣會通過，後面的證明與教學步驟都會
建立在錯的題目上，所以一定要有人比對過、把狀態改成 confirmed 才能證明。
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any, Callable

from ..agents.prompts import (
    BACK_TRANSLATION_SYSTEM_PROMPT,
    BACK_TRANSLATION_TOOL,
    FORMALIZATION_SYSTEM_PROMPT,
    FORMALIZATION_TOOL,
    back_translation_prompt,
    formalization_prompt,
)
from ..core.config import load_config, load_taxonomy
from ..core.io_utils import read_json, utc_now_iso, write_json_atomic
from ..core.schemas import Problem, SchemaError, _validate_problem_id
from ..tools.lean_runner import _TOP_LEVEL_DECLARATION, LeanRunner
from ..tools.model_api import ApiClient, call_required_tool

LEAN_IMPORTS = ("import Mathlib",)
_BANNED_WORDS = re.compile(r"\b(sorry|admit|axiom|opaque)\b")


def load_teacher_problems(path: Path) -> dict[str, str]:
    """老師的輸入只需要 problem_id 與 problem_text。"""
    raw = read_json(path)
    if not isinstance(raw, dict) or raw.get("schema_version") != 1:
        raise SchemaError("題目檔 schema_version 目前只支援 1")
    rows = raw.get("problems")
    if not isinstance(rows, list) or not rows:
        raise SchemaError("題目檔 problems 必須是非空陣列")
    problems: dict[str, str] = {}
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise SchemaError(f"problems[{index}] 必須是 JSON object")
        problem_id = _validate_problem_id(row.get("problem_id"))
        if problem_id in problems:
            raise SchemaError(f"problem_id 重複：{problem_id}")
        text = row.get("problem_text")
        if not isinstance(text, str) or not text.strip():
            raise SchemaError(f"{problem_id}.problem_text 必須是非空字串")
        problems[problem_id] = text.strip()
    return problems


def statement_validator(
    problem_id: str, lean_runner: LeanRunner
) -> Callable[[dict[str, Any]], dict[str, str]]:
    def validate(raw: dict[str, Any]) -> dict[str, str]:
        header = raw.get("lean_theorem_header")
        if not isinstance(header, str) or not header.strip():
            raise ValueError("lean_theorem_header 必須是非空字串")
        header = header.strip()
        if not header.startswith("theorem "):
            raise ValueError("lean_theorem_header 必須以 theorem 開頭，不要加 code fence")
        if not header.endswith(":="):
            raise ValueError("lean_theorem_header 必須以 := 結尾，不要附上 proof")
        if _BANNED_WORDS.search(header):
            raise ValueError("lean_theorem_header 不得含 sorry、admit、axiom 或 opaque")
        if _TOP_LEVEL_DECLARATION.search("\n".join(header.splitlines()[1:])):
            raise ValueError("lean_theorem_header 只能有一個 theorem 宣告")
        problem = Problem(
            problem_id=problem_id,
            problem_text="",
            lean_imports=LEAN_IMPORTS,
            lean_theorem_header=header,
            taxonomy_version="",
            statement_fidelity_status="unresolved",
        )
        error = lean_runner.check_statement(problem)
        if error is not None:
            raise ValueError(f"Lean 無法編譯這個命題：{error}")
        return {"lean_theorem_header": header}

    return validate


def validate_explanation(raw: dict[str, Any]) -> dict[str, str]:
    explanation = raw.get("explanation")
    if not isinstance(explanation, str) or not explanation.strip():
        raise ValueError("explanation 必須是非空字串")
    return {"explanation": explanation.strip()}


def _review_markdown(rows: list[dict[str, Any]], draft_name: str) -> str:
    lines = [
        "# Lean 命題確認",
        "",
        f"請逐題比對「原題」與「這個命題在說什麼」。一致的話，把 `{draft_name}` 裡該題的"
        " `statement_fidelity_status` 從 `unresolved` 改成 `confirmed`；不一致就修改"
        " `lean_theorem_header`，或刪掉該題。只有 `confirmed` 的題目會進入證明。",
        "",
        "「這個命題在說什麼」是另一次模型呼叫只看 Lean 命題寫出的說明，它沒有看過原題，"
        "但它本身也可能寫錯。可以把每一題整段貼給你慣用的 AI，請它檢查 Lean 命題是否"
        "與原題完全一致。",
        "",
    ]
    for row in rows:
        lines += [
            f"## {row['problem_id']}",
            "",
            "**原題**",
            "",
            row["problem_text"],
            "",
            "**Lean 命題**",
            "",
            "```lean",
            row["lean_theorem_header"],
            "```",
            "",
            "**這個命題在說什麼**",
            "",
            row["explanation"],
            "",
        ]
    return "\n".join(lines)


def run_formalization(
    input_path: Path, output_path: Path, config_path: Path
) -> tuple[Path, Path]:
    draft_path = output_path.expanduser().resolve()
    review_path = draft_path.with_name(draft_path.stem + ".review.md")
    records_path = draft_path.with_name(draft_path.stem + ".records.json")
    existing = [str(path) for path in (draft_path, review_path, records_path) if path.exists()]
    if existing:
        raise ValueError(f"輸出檔已存在，為避免蓋掉人工修改，請換檔名或先移走：{existing}")

    teacher_problems = load_teacher_problems(input_path)
    config = load_config(config_path)
    model = config.translation_model
    if model is None:
        raise ValueError(f"{config_path} 沒有設定 translation_model")
    taxonomy_version, _ = load_taxonomy(config.taxonomy_path)
    client = ApiClient(
        config.api_for(model),
        timeout_seconds=config.api_timeout_seconds,
        max_attempts=config.max_api_attempts,
    )
    lean_runner = LeanRunner(
        config.lean_project_dir, config.lean_timeout_seconds, config.repl_path
    )

    rows: list[dict[str, Any]] = []
    records: dict[str, Any] = {}
    errors: list[str] = []
    try:
        for problem_id, problem_text in teacher_problems.items():
            try:
                statement, draft_responses = call_required_tool(
                    client,
                    model,
                    system_prompt=FORMALIZATION_SYSTEM_PROMPT,
                    user_prompt=formalization_prompt(problem_id, problem_text),
                    tool=FORMALIZATION_TOOL,
                    tool_name="submit_statement",
                    validate=statement_validator(problem_id, lean_runner),
                )
                # 說明只看 Lean 命題、不給原題，才會寫出命題實際的意思而不是原意。
                explained, explain_responses = call_required_tool(
                    client,
                    model,
                    system_prompt=BACK_TRANSLATION_SYSTEM_PROMPT,
                    user_prompt=back_translation_prompt(statement["lean_theorem_header"]),
                    tool=BACK_TRANSLATION_TOOL,
                    tool_name="explain_statement",
                    validate=validate_explanation,
                )
            except Exception as exc:
                errors.append(f"{problem_id}：{exc}")
                continue
            rows.append(
                {
                    "problem_id": problem_id,
                    "problem_text": problem_text,
                    "lean_theorem_header": statement["lean_theorem_header"],
                    "explanation": explained["explanation"],
                }
            )
            records[problem_id] = {
                "formalization_responses": draft_responses,
                "explanation_responses": explain_responses,
            }
    finally:
        lean_runner.close()

    if errors:
        raise RuntimeError(f"有 {len(errors)} 題起草失敗，未寫出任何草稿：{errors}")

    write_json_atomic(
        draft_path,
        {
            "schema_version": 1,
            "problems": [
                {
                    "problem_id": row["problem_id"],
                    "problem_text": row["problem_text"],
                    "lean_imports": list(LEAN_IMPORTS),
                    "lean_theorem_header": row["lean_theorem_header"],
                    "taxonomy_version": taxonomy_version,
                    "statement_fidelity_status": "unresolved",
                }
                for row in rows
            ],
        },
    )
    review_path.write_text(_review_markdown(rows, draft_path.name), encoding="utf-8")
    write_json_atomic(
        records_path,
        {
            "schema_version": 1,
            "model": model.to_dict(),
            "problems": records,
            "completed_at": utc_now_iso(),
        },
    )
    return draft_path, review_path


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="python -m formal_consensus formalize", description=__doc__
    )
    parser.add_argument("--input", type=Path, required=True, help="老師的題目檔")
    parser.add_argument(
        "--output", type=Path, help="草稿檔路徑；預設是題目檔旁的 <檔名>.draft.json"
    )
    parser.add_argument(
        "--config", type=Path, default=Path("config.json"), help="預設 config.json"
    )
    args = parser.parse_args(argv)
    output = args.output or args.input.with_name(args.input.stem + ".draft.json")
    try:
        draft_path, review_path = run_formalization(args.input, output, args.config)
    except (ValueError, RuntimeError, OSError) as exc:
        raise SystemExit(f"起草失敗：{exc}") from exc
    print(f"草稿：{draft_path}")
    print(f"確認說明：{review_path}")
    print("請依確認說明逐題比對，確認後把 statement_fidelity_status 改成 confirmed，再執行：")
    print(f"uv run python -m formal_consensus --input {draft_path}")


if __name__ == "__main__":
    main()
