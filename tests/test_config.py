from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from formal_consensus.core.config import load_config


def base_config() -> dict:
    return {
        "schema_version": 1,
        "models": [
            {
                "name": "deepseek",
                "model_id": "deepseek/model",
                "api": "openrouter",
                "temperature": 0.0,
                "max_completion_tokens": 100,
            },
            {
                "name": "qwen",
                "model_id": "qwen/model",
                "api": "ollama",
                "temperature": 0.0,
                "max_completion_tokens": 100,
            },
            {
                "name": "gemini",
                "model_id": "gemini/model",
                "api": "openrouter",
                "temperature": 0.0,
                "max_completion_tokens": 100,
            },
        ],
        "max_rounds": 1,
        "max_candidates_per_agent_per_round": 5,
        "max_searches_per_agent_per_round": 40,
        "max_api_attempts": 1,
        "api_timeout_seconds": 10,
        "lean_timeout_seconds": 10,
        "apis": {
            "openrouter": {
                "type": "openrouter",
                "base_url": "https://openrouter.invalid/chat",
                "api_key_env": "OPENROUTER_KEY",
            },
            "ollama": {
                "type": "ollama",
                "base_url": "https://ollama.invalid/chat",
                "api_key_env": "OLLAMA_KEY",
            },
        },
        "lean_project_dir": "lean",
        "runs_dir": "runs",
        "taxonomy_path": "taxonomy.json",
    }


class ConfigTests(unittest.TestCase):
    def test_each_model_resolves_its_api(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "config.json"
            path.write_text(
                json.dumps(base_config(), ensure_ascii=False), encoding="utf-8"
            )
            config = load_config(path)

        self.assertEqual(config.api_for(config.models[0]).kind, "openrouter")
        self.assertEqual(config.api_for(config.models[1]).kind, "ollama")
        self.assertEqual(config.api_for(config.models[2]).kind, "openrouter")

    def test_legacy_single_api_config_remains_readable(self) -> None:
        raw = base_config()
        for model in raw["models"]:
            model.pop("api")
        raw.pop("apis")
        raw["api"] = {
            "base_url": "https://openrouter.invalid/chat",
            "api_key_env": "OPENROUTER_KEY",
        }
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "config.json"
            path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
            config = load_config(path)

        self.assertTrue(all(model.api == "openrouter" for model in config.models))
        self.assertEqual(set(config.apis), {"openrouter"})


if __name__ == "__main__":
    unittest.main()
