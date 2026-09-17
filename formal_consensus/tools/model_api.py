"""OpenRouter 與 Ollama 共用的 tool-calling 用戶端。"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable, Sequence, TypeVar

from ..core.config import ApiConfig, ModelConfig


class ApiError(RuntimeError):
    """遠端 API 無法產生可用回覆。"""


@dataclass(frozen=True)
class ChatResult:
    assistant_message: dict[str, Any]
    finish_reason: str | None
    usage: dict[str, Any]
    response_id: str | None
    response_model: str | None
    response_provider: str | None
    attempts: int

    def to_record(self) -> dict[str, Any]:
        return {
            "response_id": self.response_id,
            "response_model": self.response_model,
            "response_provider": self.response_provider,
            "finish_reason": self.finish_reason,
            "usage": self.usage,
            "attempts": self.attempts,
            "assistant_message": self.assistant_message,
        }


Transport = Callable[[urllib.request.Request, int], dict[str, Any]]
ValidatedToolOutput = TypeVar("ValidatedToolOutput")


def _default_transport(
    request: urllib.request.Request, timeout_seconds: int
) -> dict[str, Any]:
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        raw = response.read().decode("utf-8")
    decoded = json.loads(raw)
    if not isinstance(decoded, dict):
        raise ApiError("API 回覆不是 JSON object")
    return decoded


def parse_tool_arguments(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if not isinstance(value, str):
        raise ValueError("tool arguments 必須是 JSON 字串或 object")
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError(f"tool arguments 不是有效 JSON：{exc}") from exc
    if not isinstance(parsed, dict):
        raise ValueError("tool arguments 必須解碼為 JSON object")
    return parsed


def extract_tool_calls(message: dict[str, Any]) -> list[dict[str, Any]]:
    calls = message.get("tool_calls", [])
    if calls is None:
        return []
    if not isinstance(calls, list):
        raise ApiError("assistant.tool_calls 不是陣列")
    normalized: list[dict[str, Any]] = []
    for index, call in enumerate(calls):
        if not isinstance(call, dict):
            raise ApiError(f"tool_calls[{index}] 不是 object")
        function = call.get("function")
        if not isinstance(function, dict):
            raise ApiError(f"tool_calls[{index}].function 不存在")
        call_id = call.get("id")
        name = function.get("name")
        if not isinstance(call_id, str) or not call_id:
            raise ApiError(f"tool_calls[{index}].id 不合法")
        if not isinstance(name, str) or not name:
            raise ApiError(f"tool_calls[{index}].function.name 不合法")
        normalized.append(
            {
                "id": call_id,
                "type": "function",
                "function": {
                    "name": name,
                    "arguments": function.get("arguments", "{}"),
                },
            }
        )
    return normalized


def assistant_message_for_history(message: dict[str, Any]) -> dict[str, Any]:
    """只保留下一個 API turn 所需且可序列化的欄位。"""
    result: dict[str, Any] = {
        "role": "assistant",
        "content": message.get("content"),
    }
    calls = extract_tool_calls(message)
    if calls:
        result["tool_calls"] = calls
    # 部分推理模型可能要求工具呼叫後原樣帶回此欄位，
    # 它只留在該代理的私有 transcript，不會進入共享池。
    if "reasoning_details" in message:
        result["reasoning_details"] = message["reasoning_details"]
    return result


class ApiClient:
    def __init__(
        self,
        api: ApiConfig,
        *,
        timeout_seconds: int,
        max_attempts: int,
        transport: Transport | None = None,
    ):
        self.api = api
        self.timeout_seconds = timeout_seconds
        self.max_attempts = max_attempts
        self.transport = transport or _default_transport

    def chat(
        self,
        model: ModelConfig,
        messages: Sequence[dict[str, Any]],
        tools: Sequence[dict[str, Any]],
        *,
        tool_choice: str | dict[str, Any] = "auto",
    ) -> ChatResult:
        api_key = os.environ.get(self.api.api_key_env)
        if not api_key:
            raise ApiError(
                f"缺少環境變數 {self.api.api_key_env}；系統不會讀取 .env"
            )

        payload: dict[str, Any] = {
            "model": model.model_id,
            "messages": list(messages),
            "tools": list(tools),
            "tool_choice": tool_choice,
            # max_tokens 是目前兩種 API 共同支援的欄位。
            "max_tokens": model.max_completion_tokens,
        }
        if self.api.kind == "openrouter":
            payload["provider"] = {
                "order": list(model.provider_order),
                "allow_fallbacks": model.allow_provider_fallbacks,
                "require_parameters": model.require_parameters,
            }
        if model.temperature is not None:
            payload["temperature"] = model.temperature
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        if self.api.kind == "openrouter":
            headers.update(
                {
                    "HTTP-Referer": "https://localhost/formal-consensus",
                    "X-Title": "Formal Consensus Experiment",
                }
            )
        request = urllib.request.Request(
            self.api.base_url,
            data=body,
            headers=headers,
            method="POST",
        )

        last_error: Exception | None = None
        for attempt in range(1, self.max_attempts + 1):
            try:
                raw = self.transport(request, self.timeout_seconds)
                return self._decode_response(raw, attempt)
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", errors="replace")[-4000:]
                last_error = ApiError(
                    f"{self.api.kind} HTTP {exc.code}：{detail or exc.reason}"
                )
                if exc.code not in {408, 409, 429} and exc.code < 500:
                    break
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                last_error = exc
            except (json.JSONDecodeError, ApiError, ValueError, KeyError) as exc:
                last_error = exc
                # 無法解析的成功回覆可能是暫時性供應商問題，允許重試。

            if attempt < self.max_attempts:
                time.sleep(min(2 ** (attempt - 1), 8))

        raise ApiError(
            f"{self.api.kind} 在 {self.max_attempts} 次嘗試後失敗：{last_error}"
        ) from last_error

    def _decode_response(self, raw: dict[str, Any], attempts: int) -> ChatResult:
        choices = raw.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ApiError(f"{self.api.kind} 回覆缺少 choices")
        choice = choices[0]
        if not isinstance(choice, dict) or not isinstance(choice.get("message"), dict):
            raise ApiError(f"{self.api.kind} 回覆缺少 assistant message")
        message = assistant_message_for_history(choice["message"])
        usage = raw.get("usage")
        if not isinstance(usage, dict):
            usage = {}
        return ChatResult(
            assistant_message=message,
            finish_reason=(
                choice.get("finish_reason")
                if isinstance(choice.get("finish_reason"), str)
                else None
            ),
            usage=usage,
            response_id=raw.get("id") if isinstance(raw.get("id"), str) else None,
            response_model=(
                raw.get("model") if isinstance(raw.get("model"), str) else None
            ),
            response_provider=(
                raw.get("provider")
                if isinstance(raw.get("provider"), str)
                else self.api.kind
            ),
            attempts=attempts,
        )


def call_required_tool(
    client: ApiClient,
    model: ModelConfig,
    *,
    system_prompt: str,
    user_prompt: str,
    tool: dict[str, Any],
    tool_name: str,
    validate: Callable[[dict[str, Any]], ValidatedToolOutput],
    max_turns: int = 3,
) -> tuple[ValidatedToolOutput, list[dict[str, Any]]]:
    """強制單一評審工具，並保留所有 API 回覆供稽核。"""
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    records: list[dict[str, Any]] = []
    forced_choice = {
        "type": "function",
        "function": {"name": tool_name},
    }
    last_error = "沒有工具呼叫"
    for _ in range(max_turns):
        result = client.chat(
            model,
            messages,
            [tool],
            tool_choice=forced_choice,
        )
        records.append(result.to_record())
        assistant = assistant_message_for_history(result.assistant_message)
        messages.append(assistant)
        calls = extract_tool_calls(assistant)
        matching = [call for call in calls if call["function"]["name"] == tool_name]
        if len(matching) != 1:
            last_error = f"預期一個 {tool_name}，實際收到 {len(matching)} 個"
            messages.append(
                {
                    "role": "user",
                    "content": f"Protocol error: {last_error}. Call the required tool.",
                }
            )
            continue
        call = matching[0]
        try:
            arguments = parse_tool_arguments(call["function"]["arguments"])
            validated = validate(arguments)
        except (ValueError, TypeError, KeyError) as exc:
            last_error = str(exc)
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call["id"],
                    "content": json.dumps(
                        {"ok": False, "error": last_error}, ensure_ascii=False
                    ),
                }
            )
            continue
        return validated, records
    raise ApiError(
        f"{model.name} 未產生有效的 {tool_name}：{last_error}"
    )
