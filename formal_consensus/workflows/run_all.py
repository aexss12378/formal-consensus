"""一次跑完候選產生、方法審查、代表解選擇、報告與教學步驟翻譯。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ..core.io_utils import create_unique_directory
from ..core.schemas import SchemaError
from .method_review import run_method_review
from .pipeline import PipelineError, build_pipeline
from .report import build_report
from .representative_selection import run_representative_selection
from .translate import run_translation


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m formal_consensus", description=__doc__)
    parser.add_argument(
        "--config", type=Path, default=Path("config.json"), help="預設 config.json"
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--unit", help="只執行指定 problem_id；省略時依輸入順序執行全部題目")
    parser.add_argument(
        "--run-dir",
        type=Path,
        help="指定新批次資料夾，或續跑既有批次",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    try:
        pipeline = build_pipeline(args.config, args.input)
    except (SchemaError, ValueError, OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"設定或題目讀取失敗：{exc}") from exc
    problem_ids = list(pipeline.problems) if args.unit is None else [args.unit]
    # 建資料夾前先檢查題號與命題確認狀態，被擋下時不留空的批次資料夾。
    try:
        pipeline.select_problems(problem_ids)
    except PipelineError as exc:
        raise SystemExit(str(exc)) from exc

    # 先建好資料夾並印出路徑，中途失敗時使用者才知道要續跑哪個批次。
    run_dir = (
        args.run_dir.expanduser().resolve()
        if args.run_dir is not None
        else create_unique_directory(pipeline.config.runs_dir)
    )
    print(f"批次資料夾：{run_dir}", flush=True)
    resume_hint = f"原指令加上 --run-dir {run_dir} 即可續跑，已完成的部分不會重新呼叫"

    try:
        pipeline.run(problem_ids, run_dir)
    except (PipelineError, SchemaError, ValueError, OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"候選產生失敗：{exc}\n{resume_hint}") from exc
    finally:
        pipeline.lean_runner.close()

    steps = [
        ("方法審查", run_method_review),
        ("代表解選擇", run_representative_selection),
        ("報告建立", build_report),
        ("教學步驟翻譯", lambda path: run_translation(path, args.config)),
    ]
    for label, step in steps:
        try:
            output = step(run_dir)
        except (ValueError, RuntimeError, OSError) as exc:
            raise SystemExit(f"{label}失敗：{exc}\n{resume_hint}") from exc
        paths = output if isinstance(output, tuple) else (output,)
        for path in paths:
            print(f"{label}完成：{path}", flush=True)


if __name__ == "__main__":
    main()
