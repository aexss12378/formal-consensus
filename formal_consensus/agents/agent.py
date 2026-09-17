"""單一證明代理的私有 Lean 工具迴圈。"""

from __future__ import annotations

import base64
import json
import mimetypes
from dataclasses import dataclass
from typing import Any, Protocol, Sequence

from ..core.config import ExperimentConfig, ModelConfig
from ..core.io_utils import utc_now_iso
from ..core.schemas import Problem, SchemaError, validate_agent_submission
from ..tools.lean_runner import LeanRunner
from ..tools.model_api import (
    ApiClient,
    ChatResult,
    assistant_message_for_history,
    extract_tool_calls,
    parse_tool_arguments,
)
from .prompts import (
    GENERATION_SYSTEM_PROMPT,
    generation_tools,
    generation_user_prompt,
)


# 模型連續這麼多次沒送出合法的單一工具呼叫就中止該輪，避免無上限重試。
MAX_PROTOCOL_VIOLATIONS = 3


class ChatClient(Protocol):
    def chat(
        self,
        model: ModelConfig,
        messages: Sequence[dict[str, Any]],
        tools: Sequence[dict[str, Any]],
        *,
        tool_choice: str | dict[str, Any] = "auto",
    ) -> ChatResult: ...


class RoundAgent(Protocol):
    model: ModelConfig

    def run_round(
        self,
        problem: Problem,
        shared_pool: Sequence[dict[str, Any]],
        round_number: int,
        primary_techniques: Sequence[str],
    ) -> dict[str, Any]: ...


def _user_message(problem: Problem, text: str) -> dict[str, Any]:
    if problem.problem_image is None:
        return {"role": "user", "content": text}
    if not problem.problem_image.is_file():
        raise FileNotFoundError(f"找不到題目圖片：{problem.problem_image}")
    mime = mimetypes.guess_type(problem.problem_image.name)[0] or "image/png"
    encoded = base64.b64encode(problem.problem_image.read_bytes()).decode("ascii")
    return {
        "role": "user",
        "content": [
            {"type": "text", "text": text},
            {
                "type": "image_url",
                "image_url": {"url": f"data:{mime};base64,{encoded}"},
            },
        ],
    }


def _tool_result_message(tool_call_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "role": "tool",
        "tool_call_id": tool_call_id,
        "content": json.dumps(payload, ensure_ascii=False),
    }


@dataclass
class ToolCallingProofAgent:
    model: ModelConfig
    config: ExperimentConfig
    client: ChatClient
    lean_runner: LeanRunner

    def run_round(
        self,
        problem: Problem,
        shared_pool: Sequence[dict[str, Any]],
        round_number: int,
        primary_techniques: Sequence[str],
    ) -> dict[str, Any]:
        started_at = utc_now_iso()
        visible_ids = [item["candidate_id"] for item in shared_pool]
        user_prompt = generation_user_prompt(
            problem,
            shared_pool,
            round_number,
            primary_techniques,
            self.config.max_candidates_per_agent_per_round,
        )
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": GENERATION_SYSTEM_PROMPT},
            _user_message(problem, user_prompt),
        ]
        tools = generation_tools(
            primary_techniques,
            self.config.max_candidates_per_agent_per_round,
        )
        private_searches: list[dict[str, Any]] = []
        private_verifications: list[dict[str, Any]] = []
        api_responses: list[dict[str, Any]] = []
        staged_candidates: list[dict[str, Any]] = []

        turn = 0
        violations = 0
        while True:
            turn += 1
            if violations >= MAX_PROTOCOL_VIOLATIONS:
                raise RuntimeError(
                    f"{self.model.name} 連續 {violations} 次沒有送出合法的單一工具"
                    "呼叫；中止本輪，不再繼續請求"
                )
            result = self.client.chat(self.model, messages, tools, tool_choice="auto")
            api_responses.append(result.to_record())
            assistant_message = assistant_message_for_history(result.assistant_message)
            messages.append(assistant_message)
            calls = extract_tool_calls(assistant_message)
            if not calls:
                violations += 1
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            "Protocol error: call lean_search, lean_verify, or stop. "
                            "Do not answer with prose."
                        ),
                    }
                )
                continue
            if len(calls) > 1:
                violations += 1
                for call in calls:
                    messages.append(
                        _tool_result_message(
                            call["id"],
                            {
                                "ok": False,
                                "error": (
                                    "call exactly one tool per response; retry with "
                                    "one tool only"
                                ),
                            },
                        )
                    )
                continue

            lean_ran = False
            for call_index, call in enumerate(calls, start=1):
                name = call["function"]["name"]
                call_id = call["id"]
                try:
                    arguments = parse_tool_arguments(call["function"]["arguments"])
                except ValueError as exc:
                    messages.append(
                        _tool_result_message(call_id, {"ok": False, "error": str(exc)})
                    )
                    continue

                if name == "lean_search":
                    proof_body = arguments.get("probe_body")
                    if not isinstance(proof_body, str):
                        messages.append(
                            _tool_result_message(
                                call_id,
                                {
                                    "ok": False,
                                    "error": "probe_body must be a string",
                                },
                            )
                        )
                        continue
                    check_id = (
                        f"private_search_{problem.problem_id}_r{round_number:03d}_"
                        f"{self.model.name}_t{turn:02d}_{call_index:02d}"
                    )
                    checked = self.lean_runner.check(problem, proof_body, check_id)
                    lean_ran = True
                    record = {
                        "turn": turn,
                        "tool_call_id": call_id,
                        "proof_body": proof_body,
                        "result": checked.to_dict(),
                    }
                    private_searches.append(record)
                    tool_ok = checked.status not in {
                        "tool_failed",
                        "invalid_output",
                    }
                    messages.append(
                        _tool_result_message(
                            call_id,
                            {
                                "ok": tool_ok,
                                "proof_closed": checked.verified,
                                "lean_status": checked.status,
                                "diagnostics": checked.diagnostics or checked.error,
                            },
                        )
                    )
                    continue

                if name == "lean_verify":
                    if (
                        len(staged_candidates)
                        >= self.config.max_candidates_per_agent_per_round
                    ):
                        messages.append(
                            _tool_result_message(
                                call_id,
                                {
                                    "ok": False,
                                    "error": "candidate limit reached; call stop",
                                },
                            )
                        )
                        continue
                    try:
                        candidate_submission = validate_agent_submission(
                            {"stop": False, "candidates": [arguments]},
                            primary_techniques=primary_techniques,
                            visible_candidate_ids=visible_ids,
                            max_candidates=1,
                        )
                    except SchemaError as exc:
                        messages.append(
                            _tool_result_message(
                                call_id,
                                {"ok": False, "error": str(exc)},
                            )
                        )
                        continue
                    candidate = candidate_submission.candidates[0]
                    if any(
                        existing["proof_body"] == candidate.proof_body
                        for existing in staged_candidates
                    ):
                        messages.append(
                            _tool_result_message(
                                call_id,
                                {
                                    "ok": False,
                                    "error": "this proof is already saved in this round",
                                },
                            )
                        )
                        continue

                    check_id = (
                        f"private_verify_{problem.problem_id}_r{round_number:03d}_"
                        f"{self.model.name}_t{turn:02d}_{call_index:02d}"
                    )
                    checked = self.lean_runner.check(
                        problem,
                        candidate.proof_body,
                        check_id,
                    )
                    lean_ran = True
                    saved = checked.verified
                    if saved:
                        staged_candidates.append(candidate.to_dict())
                    private_verifications.append(
                        {
                            "turn": turn,
                            "tool_call_id": call_id,
                            "candidate": candidate.to_dict(),
                            "candidate_saved": saved,
                            "result": checked.to_dict(),
                        }
                    )
                    messages.append(
                        _tool_result_message(
                            call_id,
                            {
                                "ok": saved,
                                "candidate_saved": saved,
                                "saved_candidate_count": len(staged_candidates),
                                "status": checked.status,
                                "error": checked.error,
                                "diagnostics": checked.diagnostics,
                            },
                        )
                    )
                    continue

                if name == "stop":
                    if arguments:
                        messages.append(
                            _tool_result_message(
                                call_id,
                                {"ok": False, "error": "stop takes no arguments"},
                            )
                        )
                        continue
                    submission = validate_agent_submission(
                        {"stop": True, "candidates": staged_candidates},
                        primary_techniques=primary_techniques,
                        visible_candidate_ids=visible_ids,
                        max_candidates=self.config.max_candidates_per_agent_per_round,
                    )
                    return {
                        "schema_version": 1,
                        "model_name": self.model.name,
                        "model_id": self.model.model_id,
                        "round": round_number,
                        "frozen_pool_candidate_ids": visible_ids,
                        "started_at": started_at,
                        "finished_at": utc_now_iso(),
                        "submission": submission.to_dict(),
                        "private_lean_searches": private_searches,
                        "private_lean_verifications": private_verifications,
                        "api_responses": api_responses,
                    }

                messages.append(
                    _tool_result_message(
                        call_id,
                        {"ok": False, "error": f"unknown tool: {name}"},
                    )
                )

            violations = 0 if lean_ran else violations + 1


def build_default_agents(
    config: ExperimentConfig, lean_runner: LeanRunner
) -> list[ToolCallingProofAgent]:
    return [
        ToolCallingProofAgent(
            model,
            config,
            ApiClient(
                config.api_for(model),
                timeout_seconds=config.api_timeout_seconds,
                max_attempts=config.max_api_attempts,
            ),
            lean_runner,
        )
        for model in config.models
    ]
