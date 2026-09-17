"""題目、代理輸出與候選紀錄的固定資料規格。"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .io_utils import read_json


class SchemaError(ValueError):
    """輸入或模型輸出不符合固定資料規格。"""


FIDELITY_STATUSES = {"confirmed", "unresolved", "formal_benchmark"}
ACTIONS = {"new", "derived"}


@dataclass(frozen=True)
class Problem:
    problem_id: str
    problem_text: str
    lean_imports: tuple[str, ...]
    lean_theorem_header: str
    taxonomy_version: str
    statement_fidelity_status: str
    problem_image: Path | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "problem_id": self.problem_id,
            "problem_text": self.problem_text,
            "lean_imports": list(self.lean_imports),
            "lean_theorem_header": self.lean_theorem_header,
            "taxonomy_version": self.taxonomy_version,
            "statement_fidelity_status": self.statement_fidelity_status,
        }
        if self.problem_image is not None:
            payload["problem_image"] = str(self.problem_image)
        return payload


@dataclass(frozen=True)
class SubmittedCandidate:
    action: str
    derived_from: tuple[str, ...]
    primary_technique: str
    proof_body: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "derived_from": list(self.derived_from),
            "primary_technique": self.primary_technique,
            "proof_body": self.proof_body,
        }


@dataclass(frozen=True)
class AgentSubmission:
    stop: bool
    candidates: tuple[SubmittedCandidate, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "stop": self.stop,
            "candidates": [candidate.to_dict() for candidate in self.candidates],
        }


def _nonempty_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SchemaError(f"{field} 必須是非空字串")
    return value.strip()


def _validate_problem_id(value: Any) -> str:
    problem_id = _nonempty_string(value, "problem_id")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", problem_id):
        raise SchemaError(
            "problem_id 只能包含英文字母、數字、底線、句點與連字號"
        )
    return problem_id


def load_problem_bank(path: str | Path) -> dict[str, Problem]:
    source_path = Path(path).expanduser().resolve()
    raw = read_json(source_path)
    if not isinstance(raw, dict) or raw.get("schema_version") != 1:
        raise SchemaError("題庫 schema_version 目前只支援 1")
    rows = raw.get("problems")
    if not isinstance(rows, list) or not rows:
        raise SchemaError("題庫 problems 必須是非空陣列")

    problems: dict[str, Problem] = {}
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise SchemaError(f"problems[{index}] 必須是 JSON object")
        problem_id = _validate_problem_id(row.get("problem_id"))
        if problem_id in problems:
            raise SchemaError(f"problem_id 重複：{problem_id}")

        imports_raw = row.get("lean_imports")
        if not isinstance(imports_raw, list) or not imports_raw:
            raise SchemaError(f"{problem_id}.lean_imports 必須是非空陣列")
        imports = tuple(
            _nonempty_string(value, f"{problem_id}.lean_imports[{item_index}]")
            for item_index, value in enumerate(imports_raw)
        )
        if any(not item.startswith("import ") for item in imports):
            raise SchemaError(f"{problem_id}.lean_imports 每一列都必須以 import 開頭")

        header = _nonempty_string(
            row.get("lean_theorem_header"), f"{problem_id}.lean_theorem_header"
        )
        if not header.rstrip().endswith(":="):
            raise SchemaError(f"{problem_id}.lean_theorem_header 必須以 := 結尾")
        if re.search(r"\b(sorry|admit|axiom|opaque)\b", header):
            raise SchemaError(f"{problem_id}.lean_theorem_header 含禁止內容")

        fidelity = _nonempty_string(
            row.get("statement_fidelity_status"),
            f"{problem_id}.statement_fidelity_status",
        )
        if fidelity not in FIDELITY_STATUSES:
            raise SchemaError(
                f"{problem_id}.statement_fidelity_status 必須是 "
                f"{sorted(FIDELITY_STATUSES)}"
            )

        image: Path | None = None
        if row.get("problem_image") is not None:
            image = Path(_nonempty_string(row["problem_image"], "problem_image"))
            if not image.is_absolute():
                image = (source_path.parent / image).resolve()

        problems[problem_id] = Problem(
            problem_id=problem_id,
            problem_text=_nonempty_string(
                row.get("problem_text"), f"{problem_id}.problem_text"
            ),
            lean_imports=imports,
            lean_theorem_header=header,
            taxonomy_version=_nonempty_string(
                row.get("taxonomy_version"), f"{problem_id}.taxonomy_version"
            ),
            statement_fidelity_status=fidelity,
            problem_image=image,
        )
    return problems


def normalize_proof_body(proof_body: str) -> str:
    normalized = proof_body.replace("\r\n", "\n").replace("\r", "\n").strip()
    return "\n".join(line.rstrip() for line in normalized.splitlines())


def compute_proof_hash(proof_body: str) -> str:
    return hashlib.sha256(normalize_proof_body(proof_body).encode("utf-8")).hexdigest()


def validate_agent_submission(
    raw: Any,
    *,
    primary_techniques: Iterable[str],
    visible_candidate_ids: Iterable[str],
    max_candidates: int,
) -> AgentSubmission:
    if not isinstance(raw, dict):
        raise SchemaError("submission 必須是 JSON object")
    if not isinstance(raw.get("stop"), bool):
        raise SchemaError("stop 必須是 boolean")
    rows = raw.get("candidates")
    if not isinstance(rows, list):
        raise SchemaError("candidates 必須是陣列")
    if len(rows) > max_candidates:
        raise SchemaError(f"candidates 不得超過 {max_candidates} 筆")

    labels = set(primary_techniques)
    visible = set(visible_candidate_ids)
    candidates: list[SubmittedCandidate] = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise SchemaError(f"candidates[{index}] 必須是 JSON object")
        action = _nonempty_string(row.get("action"), f"candidates[{index}].action")
        if action not in ACTIONS:
            raise SchemaError(f"candidates[{index}].action 必須是 new 或 derived")

        derived_raw = row.get("derived_from")
        if not isinstance(derived_raw, list) or any(
            not isinstance(item, str) or not item for item in derived_raw
        ):
            raise SchemaError(f"candidates[{index}].derived_from 必須是字串陣列")
        derived_from = tuple(dict.fromkeys(derived_raw))
        if action == "new" and derived_from:
            raise SchemaError(f"candidates[{index}] 為 new 時 derived_from 必須為空")
        if action == "derived":
            if not derived_from:
                raise SchemaError(
                    f"candidates[{index}] 為 derived 時必須提供 derived_from"
                )
            unknown = [candidate_id for candidate_id in derived_from if candidate_id not in visible]
            if unknown:
                raise SchemaError(
                    f"candidates[{index}].derived_from 引用不可見候選：{unknown}"
                )

        technique = _nonempty_string(
            row.get("primary_technique"),
            f"candidates[{index}].primary_technique",
        )
        if technique not in labels:
            raise SchemaError(
                f"candidates[{index}].primary_technique 不在固定分類中"
            )

        proof_body = normalize_proof_body(
            _nonempty_string(row.get("proof_body"), f"candidates[{index}].proof_body")
        )
        candidates.append(
            SubmittedCandidate(
                action=action,
                derived_from=derived_from,
                primary_technique=technique,
                proof_body=proof_body,
            )
        )

    return AgentSubmission(stop=raw["stop"], candidates=tuple(candidates))


def public_pool_entry(candidate: dict[str, Any]) -> dict[str, Any]:
    """只回傳下一輪允許看見的欄位。

    方法標籤刻意公開：最終產出是每個課本方法一份 proof，同方法的其他寫法
    沒有價值，所以下一輪必須看得出哪些方法已經有人做過。模型名稱與輪次以外
    的身分資訊仍然不外洩。
    """
    return {
        "candidate_id": candidate["candidate_id"],
        "round": candidate["round"],
        "derived_from": list(candidate.get("derived_from", [])),
        "primary_technique": candidate["primary_technique_claim"],
        "proof_body": candidate["proof_body"],
    }
