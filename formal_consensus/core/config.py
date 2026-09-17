"""讀取並驗證實驗設定。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .io_utils import read_json


class ConfigError(ValueError):
    """設定內容不完整或互相矛盾。"""


@dataclass(frozen=True)
class ModelConfig:
    name: str
    model_id: str
    temperature: float | None
    max_completion_tokens: int
    provider_order: tuple[str, ...] = ()
    allow_provider_fallbacks: bool = True
    require_parameters: bool = True
    api: str = "openrouter"

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "model_id": self.model_id,
            "api": self.api,
            "temperature": self.temperature,
            "max_completion_tokens": self.max_completion_tokens,
            "provider_routing": {
                "order": list(self.provider_order),
                "allow_fallbacks": self.allow_provider_fallbacks,
                "require_parameters": self.require_parameters,
            },
        }


@dataclass(frozen=True)
class ApiConfig:
    base_url: str
    api_key_env: str
    kind: str = "openrouter"

    def to_dict(self) -> dict[str, str]:
        return {
            "type": self.kind,
            "base_url": self.base_url,
            "api_key_env": self.api_key_env,
        }


@dataclass(frozen=True)
class ExperimentConfig:
    schema_version: int
    models: tuple[ModelConfig, ...]
    max_rounds: int
    max_candidates_per_agent_per_round: int
    max_api_attempts: int
    api_timeout_seconds: int
    lean_timeout_seconds: int
    apis: dict[str, ApiConfig]
    lean_project_dir: Path
    runs_dir: Path
    taxonomy_path: Path
    source_path: Path
    repl_path: Path | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "models": [model.to_dict() for model in self.models],
            "max_rounds": self.max_rounds,
            "max_candidates_per_agent_per_round": (
                self.max_candidates_per_agent_per_round
            ),
            "max_api_attempts": self.max_api_attempts,
            "api_timeout_seconds": self.api_timeout_seconds,
            "lean_timeout_seconds": self.lean_timeout_seconds,
            "apis": {
                name: api.to_dict() for name, api in self.apis.items()
            },
            # 執行批次中的凍結設定會放在另一個資料夾，故保存解析後的
            # 絕對路徑，避免續跑時相對路徑改指向 run directory。
            "lean_project_dir": str(self.lean_project_dir),
            "runs_dir": str(self.runs_dir),
            "taxonomy_path": str(self.taxonomy_path),
            "repl_path": (
                str(self.repl_path) if self.repl_path is not None else None
            ),
        }

    def api_for(self, model: ModelConfig) -> ApiConfig:
        try:
            return self.apis[model.api]
        except KeyError as exc:
            raise ConfigError(
                f"模型 {model.name} 指定不存在的 API：{model.api}"
            ) from exc


def _require_mapping(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ConfigError(f"{field} 必須是 JSON object")
    return value


def _require_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"{field} 必須是非空字串")
    return value.strip()


def _require_positive_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ConfigError(f"{field} 必須是正整數")
    return value


def _resolve_path(base: Path, raw: Any, field: str) -> Path:
    text = _require_string(raw, field)
    path = Path(text).expanduser()
    return path.resolve() if path.is_absolute() else (base / path).resolve()


def _resolve_optional_path(base: Path, raw: Any, field: str) -> Path | None:
    if raw is None:
        return None
    return _resolve_path(base, raw, field)


def load_config(path: str | Path) -> ExperimentConfig:
    source_path = Path(path).expanduser().resolve()
    raw = _require_mapping(read_json(source_path), "config")
    if raw.get("schema_version") != 1:
        raise ConfigError("config.schema_version 目前只支援 1")

    apis_raw_value = raw.get("apis")
    if apis_raw_value is None:
        # 相容既有批次的單一 OpenRouter 設定。
        legacy_api = _require_mapping(raw.get("api"), "api")
        apis_raw: dict[str, Any] = {
            "openrouter": {
                "type": "openrouter",
                "base_url": legacy_api.get("base_url"),
                "api_key_env": legacy_api.get("api_key_env"),
            }
        }
    else:
        apis_raw = _require_mapping(apis_raw_value, "apis")
        if not apis_raw:
            raise ConfigError("apis 至少要包含一個 API")

    apis: dict[str, ApiConfig] = {}
    for api_name, api_value in apis_raw.items():
        if not isinstance(api_name, str) or not api_name.strip():
            raise ConfigError("apis 的名稱必須是非空字串")
        normalized_name = api_name.strip()
        if normalized_name != api_name:
            raise ConfigError(f"apis 名稱前後不得有空白：{api_name!r}")
        api_row = _require_mapping(api_value, f"apis.{normalized_name}")
        kind = _require_string(
            api_row.get("type", "openrouter"),
            f"apis.{normalized_name}.type",
        )
        if kind not in {"openrouter", "ollama"}:
            raise ConfigError(
                f"apis.{normalized_name}.type 只支援 openrouter 或 ollama"
            )
        apis[normalized_name] = ApiConfig(
            base_url=_require_string(
                api_row.get("base_url"), f"apis.{normalized_name}.base_url"
            ),
            api_key_env=_require_string(
                api_row.get("api_key_env"),
                f"apis.{normalized_name}.api_key_env",
            ),
            kind=kind,
        )

    model_rows = raw.get("models")
    if not isinstance(model_rows, list) or len(model_rows) != 3:
        raise ConfigError("models 必須剛好包含三個模型")

    models: list[ModelConfig] = []
    for index, row_value in enumerate(model_rows):
        row = _require_mapping(row_value, f"models[{index}]")
        api_name = _require_string(
            row.get("api", "openrouter"), f"models[{index}].api"
        )
        if api_name not in apis:
            raise ConfigError(
                f"models[{index}].api 指定不存在的 API：{api_name}"
            )
        routing = _require_mapping(
            row.get("provider_routing", {}),
            f"models[{index}].provider_routing",
        )
        order_raw = routing.get("order", [])
        if not isinstance(order_raw, list) or any(
            not isinstance(item, str) or not item.strip() for item in order_raw
        ):
            raise ConfigError(
                f"models[{index}].provider_routing.order 必須是字串陣列"
            )
        allow_fallbacks = routing.get("allow_fallbacks", True)
        require_parameters = routing.get("require_parameters", True)
        if not isinstance(allow_fallbacks, bool):
            raise ConfigError(
                f"models[{index}].provider_routing.allow_fallbacks 必須是 boolean"
            )
        if not isinstance(require_parameters, bool):
            raise ConfigError(
                f"models[{index}].provider_routing.require_parameters 必須是 boolean"
            )
        normalized_order = tuple(item.strip() for item in order_raw)
        if len(set(normalized_order)) != len(normalized_order):
            raise ConfigError(
                f"models[{index}].provider_routing.order 不得重複"
            )
        if (
            apis[api_name].kind == "openrouter"
            and not allow_fallbacks
            and not normalized_order
        ):
            raise ConfigError(
                f"models[{index}] 關閉 provider fallback 時必須明列 order"
            )
        if apis[api_name].kind == "ollama" and normalized_order:
            raise ConfigError(
                f"models[{index}] 使用 Ollama 時不得設定 provider_routing.order"
            )
        temperature = row.get("temperature")
        if temperature is not None and (
            isinstance(temperature, bool)
            or not isinstance(temperature, (int, float))
        ):
            raise ConfigError(f"models[{index}].temperature 必須是數字或 null")
        models.append(
            ModelConfig(
                name=_require_string(row.get("name"), f"models[{index}].name"),
                model_id=_require_string(
                    row.get("model_id"), f"models[{index}].model_id"
                ),
                temperature=(float(temperature) if temperature is not None else None),
                max_completion_tokens=_require_positive_int(
                    row.get("max_completion_tokens"),
                    f"models[{index}].max_completion_tokens",
                ),
                provider_order=normalized_order,
                allow_provider_fallbacks=allow_fallbacks,
                require_parameters=require_parameters,
                api=api_name,
            )
        )

    names = [model.name for model in models]
    model_ids = [model.model_id for model in models]
    if len(set(names)) != 3:
        raise ConfigError("三個 models.name 必須互不相同")
    if len(set(model_ids)) != 3:
        raise ConfigError("三個 models.model_id 必須互不相同")

    base = source_path.parent
    return ExperimentConfig(
        schema_version=1,
        models=tuple(models),
        max_rounds=_require_positive_int(raw.get("max_rounds"), "max_rounds"),
        max_candidates_per_agent_per_round=_require_positive_int(
            raw.get("max_candidates_per_agent_per_round"),
            "max_candidates_per_agent_per_round",
        ),
        max_api_attempts=_require_positive_int(
            raw.get("max_api_attempts"), "max_api_attempts"
        ),
        api_timeout_seconds=_require_positive_int(
            raw.get("api_timeout_seconds"), "api_timeout_seconds"
        ),
        lean_timeout_seconds=_require_positive_int(
            raw.get("lean_timeout_seconds"), "lean_timeout_seconds"
        ),
        apis=apis,
        lean_project_dir=_resolve_path(
            base, raw.get("lean_project_dir"), "lean_project_dir"
        ),
        runs_dir=_resolve_path(base, raw.get("runs_dir"), "runs_dir"),
        taxonomy_path=_resolve_path(
            base, raw.get("taxonomy_path"), "taxonomy_path"
        ),
        source_path=source_path,
        repl_path=_resolve_optional_path(base, raw.get("repl_path"), "repl_path"),
    )


def load_taxonomy(path: Path) -> tuple[str, tuple[str, ...]]:
    raw = _require_mapping(read_json(path), "taxonomy")
    version = _require_string(raw.get("version"), "taxonomy.version")
    labels = raw.get("primary_techniques")
    if not isinstance(labels, list) or not labels:
        raise ConfigError("taxonomy.primary_techniques 必須是非空陣列")
    normalized = tuple(
        _require_string(label, f"taxonomy.primary_techniques[{index}]")
        for index, label in enumerate(labels)
    )
    if len(set(normalized)) != len(normalized):
        raise ConfigError("taxonomy.primary_techniques 不得重複")
    return version, normalized
