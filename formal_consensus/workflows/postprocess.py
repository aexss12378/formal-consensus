"""方法審查與代表解選擇共用的批次讀取工具。"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from ..core.config import ExperimentConfig, load_config, load_taxonomy
from ..core.io_utils import read_json
from ..core.schemas import Problem, load_problem_bank


def load_frozen_run(
    run_dir: Path,
) -> tuple[ExperimentConfig, dict[str, Problem], str, tuple[str, ...]]:
    root = run_dir.expanduser().resolve()
    required = [root / "config.json", root / "input.json", root / "taxonomy.json"]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise ValueError(f"批次缺少凍結檔案：{missing}")
    config = load_config(root / "config.json")
    problems = load_problem_bank(root / "input.json")
    version, techniques = load_taxonomy(root / "taxonomy.json")
    return config, problems, version, techniques


def load_complete_problem_state(run_dir: Path, problem_id: str) -> dict[str, Any]:
    path = run_dir / "problems" / problem_id / "state.json"
    state = read_json(path)
    if state.get("status") != "complete":
        raise ValueError(f"{problem_id} 尚未完成候選產生，不能進行後處理")
    return state


def safe_component(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]", "_", value)
    return cleaned[:180] or "item"
