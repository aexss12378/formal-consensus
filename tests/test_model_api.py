"""兩種模型 API 共用用戶端的測試。"""

from __future__ import annotations

import json
import os
import unittest
from unittest.mock import patch

from formal_consensus.core.config import ApiConfig, ModelConfig
from formal_consensus.tools.model_api import (
    ApiClient,
    extract_tool_calls,
    parse_tool_arguments,
)


class ModelApiTests(unittest.TestCase):
    def test_parse_tool_arguments_accepts_string_or_mapping(self) -> None:
        self.assertEqual(parse_tool_arguments('{"x": 1}'), {"x": 1})
        self.assertEqual(parse_tool_arguments({"x": 1}), {"x": 1})
        with self.assertRaises(ValueError):
            parse_tool_arguments("[]")

    def test_client_sends_only_common_tool_parameters(self) -> None:
        observed: dict[str, object] = {}

        def transport(request, timeout):
            observed["timeout"] = timeout
            observed["payload"] = json.loads(request.data.decode("utf-8"))
            self.assertEqual(request.get_header("Authorization"), "Bearer token")
            return {
                "id": "response-1",
                "model": "provider/model",
                "provider": "provider-endpoint",
                "choices": [
                    {
                        "finish_reason": "tool_calls",
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "reasoning_details": [
                                {"type": "reasoning.text", "text": "private"}
                            ],
                            "tool_calls": [
                                {
                                    "id": "call-1",
                                    "type": "function",
                                    "function": {
                                        "name": "submit",
                                        "arguments": '{"ok": true}',
                                    },
                                }
                            ],
                        },
                    }
                ],
                "usage": {"prompt_tokens": 10},
            }

        client = ApiClient(
            ApiConfig("https://example.invalid", "TEST_OPENROUTER_KEY"),
            timeout_seconds=7,
            max_attempts=1,
            transport=transport,
        )
        model = ModelConfig("m", "provider/model", 0.0, 100)
        with patch.dict(os.environ, {"TEST_OPENROUTER_KEY": "token"}):
            result = client.chat(
                model,
                [{"role": "user", "content": "test"}],
                [{"type": "function", "function": {"name": "submit"}}],
            )
        self.assertNotIn("parallel_tool_calls", observed["payload"])
        self.assertEqual(
            observed["payload"]["provider"],
            {
                "order": [],
                "allow_fallbacks": True,
                "require_parameters": True,
            },
        )
        self.assertEqual(observed["timeout"], 7)
        self.assertEqual(result.response_provider, "provider-endpoint")
        calls = extract_tool_calls(result.assistant_message)
        self.assertEqual(calls[0]["function"]["name"], "submit")
        self.assertEqual(
            result.assistant_message["reasoning_details"][0]["text"], "private"
        )

    def test_ollama_omits_openrouter_fields(self) -> None:
        observed: dict[str, object] = {}

        def transport(request, timeout):
            observed["payload"] = json.loads(request.data.decode("utf-8"))
            observed["referer"] = request.get_header("HTTP-referer")
            observed["title"] = request.get_header("X-title")
            return {
                "id": "response-2",
                "model": "qwen3-coder:480b",
                "choices": [
                    {
                        "finish_reason": "tool_calls",
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "call-2",
                                    "type": "function",
                                    "function": {
                                        "name": "submit",
                                        "arguments": '{"ok": true}',
                                    },
                                }
                            ],
                        },
                    }
                ],
                "usage": {"prompt_tokens": 12},
            }

        client = ApiClient(
            ApiConfig(
                "https://ollama.com/v1/chat/completions",
                "TEST_OLLAMA_KEY",
                kind="ollama",
            ),
            timeout_seconds=7,
            max_attempts=1,
            transport=transport,
        )
        model = ModelConfig(
            "qwen", "qwen3-coder:480b", 0.0, 100, api="ollama"
        )
        with patch.dict(os.environ, {"TEST_OLLAMA_KEY": "token"}):
            result = client.chat(
                model,
                [{"role": "user", "content": "test"}],
                [{"type": "function", "function": {"name": "submit"}}],
            )

        self.assertNotIn("provider", observed["payload"])
        self.assertNotIn("reasoning_effort", observed["payload"])
        self.assertIsNone(observed["referer"])
        self.assertIsNone(observed["title"])
        self.assertEqual(result.response_provider, "ollama")

        low_thinking = ModelConfig(
            "qwen", "qwen3-coder:480b", 0.0, 100, api="ollama", reasoning_effort="low"
        )
        with patch.dict(os.environ, {"TEST_OLLAMA_KEY": "token"}):
            client.chat(
                low_thinking,
                [{"role": "user", "content": "test"}],
                [{"type": "function", "function": {"name": "submit"}}],
            )
        self.assertEqual(observed["payload"]["reasoning_effort"], "low")


if __name__ == "__main__":
    unittest.main()
