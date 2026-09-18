"""固定 theorem header 的 Lean 完整證明驗證器。"""

from __future__ import annotations

import json
import queue
import re
import subprocess
import threading
import time
from collections import deque
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from ..core.schemas import Problem, normalize_proof_body


_LEAN_LOCK = threading.Lock()
_BANNED_WORDS = re.compile(r"\b(sorry|admit|axiom|opaque)\b")
_SORRY_WARNING = re.compile(
    r"declaration uses\s+[`'\"]?sorry[`'\"]?",
    re.IGNORECASE,
)
_TOP_LEVEL_DECLARATION = re.compile(
    r"^(?:theorem|lemma|def|example|axiom|opaque|inductive|structure|class|instance|"
    r"namespace|section|end|import|set_option|attribute|macro|syntax|elab)\b",
    re.MULTILINE,
)


@dataclass(frozen=True)
class LeanCheckResult:
    status: str
    verified: bool
    lean_file: str | None
    module_name: str | None
    error: str | None
    elapsed_seconds: float
    command: list[str] | None
    diagnostics: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def validate_proof_body(proof_body: str) -> str:
    proof = normalize_proof_body(proof_body)
    if not proof.startswith("by") or (len(proof) > 2 and not proof[2].isspace()):
        raise ValueError("proof_body 必須是以 by 開頭的完整證明")
    if "```" in proof:
        raise ValueError("proof_body 不得包含 Markdown code fence")
    if "--" in proof or "/-" in proof or "-/" in proof:
        raise ValueError("proof_body 不得包含註解，以免把自然語言帶入共享池")
    if _BANNED_WORDS.search(proof):
        raise ValueError("proof_body 含 sorry、admit、axiom 或 opaque")
    later_lines = "\n".join(proof.splitlines()[1:])
    if _TOP_LEVEL_DECLARATION.search(later_lines):
        raise ValueError("proof_body 不得加入其他頂層宣告或修改環境")
    return proof


# Lean 預設會把陳述裡不認識的名字當成自動產生的型別變數，編譯照樣通過。
# theorem header 是人手寫的，打錯一個沒有點號的名字（ℝ 寫成 R）就會證到別的
# 命題上而毫無警訊，所以每次驗證都關掉這個行為。用 `in` 是為了只管接下來那
# 一個宣告，不改動常駐 REPL 的環境設定。
AUTO_IMPLICIT_OFF = "set_option autoImplicit false in\n"


def compose_lean_source(problem: Problem, proof_body: str) -> str:
    proof = validate_proof_body(proof_body)
    return (
        "\n".join(problem.lean_imports)
        + "\n\n"
        + AUTO_IMPLICIT_OFF
        + problem.lean_theorem_header.rstrip()
        + "\n"
        + proof
        + "\n"
    )


def _bounded_diagnostics(output: str, limit: int = 12000) -> str | None:
    if not output:
        return None
    if len(output) <= limit:
        return output
    half = limit // 2
    return (
        output[:half]
        + "\n... Lean diagnostics truncated ...\n"
        + output[-half:]
    )


def _safe_module_component(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_]", "_", value)
    if not cleaned or cleaned[0].isdigit():
        cleaned = f"C_{cleaned}"
    return cleaned[:180]


class LakeLeanRunner:
    def __init__(self, project_dir: Path, timeout_seconds: int):
        self.project_dir = project_dir.resolve()
        self.timeout_seconds = timeout_seconds
        self.generated_dir = self.project_dir / "ProofPool" / "Generated"

    def check(
        self,
        problem: Problem,
        proof_body: str,
        check_id: str,
    ) -> LeanCheckResult:
        started = time.monotonic()
        try:
            source = compose_lean_source(problem, proof_body)
        except ValueError as exc:
            return LeanCheckResult(
                status="invalid_output",
                verified=False,
                lean_file=None,
                module_name=None,
                error=str(exc),
                elapsed_seconds=time.monotonic() - started,
                command=None,
            )

        component = _safe_module_component(check_id)
        module_name = f"ProofPool.Generated.{component}"
        lean_file = self.generated_dir / f"{component}.lean"
        command = ["lake", "build", module_name]

        try:
            self.generated_dir.mkdir(parents=True, exist_ok=True)
            temporary = lean_file.with_suffix(".lean.tmp")
            temporary.write_text(source, encoding="utf-8")
            temporary.replace(lean_file)
            with _LEAN_LOCK:
                completed = subprocess.run(
                    command,
                    cwd=self.project_dir,
                    text=True,
                    capture_output=True,
                    timeout=self.timeout_seconds,
                    check=False,
                )
        except FileNotFoundError as exc:
            return LeanCheckResult(
                status="tool_failed",
                verified=False,
                lean_file=str(lean_file),
                module_name=module_name,
                error=f"找不到 Lean 工具：{exc}",
                elapsed_seconds=time.monotonic() - started,
                command=command,
            )
        except subprocess.TimeoutExpired:
            return LeanCheckResult(
                status="tool_failed",
                verified=False,
                lean_file=str(lean_file),
                module_name=module_name,
                error=f"Lean 驗證超過 {self.timeout_seconds} 秒",
                elapsed_seconds=time.monotonic() - started,
                command=command,
            )
        except OSError as exc:
            return LeanCheckResult(
                status="tool_failed",
                verified=False,
                lean_file=str(lean_file),
                module_name=module_name,
                error=f"Lean 工具層錯誤：{exc}",
                elapsed_seconds=time.monotonic() - started,
                command=command,
            )

        combined = "\n".join(
            part.strip() for part in (completed.stdout, completed.stderr) if part.strip()
        )
        diagnostics = _bounded_diagnostics(combined)
        if completed.returncode == 0 and not _SORRY_WARNING.search(combined):
            return LeanCheckResult(
                status="verified",
                verified=True,
                lean_file=str(lean_file),
                module_name=module_name,
                error=None,
                elapsed_seconds=time.monotonic() - started,
                command=command,
                diagnostics=diagnostics,
            )
        return LeanCheckResult(
            status="proof_failed",
            verified=False,
            lean_file=str(lean_file),
            module_name=module_name,
            error=diagnostics or f"lake build 結束碼 {completed.returncode}",
            elapsed_seconds=time.monotonic() - started,
            command=command,
            diagnostics=diagnostics,
        )


class ReplError(RuntimeError):
    """常駐 REPL 無法正確處理請求。"""


class ReplLeanRunner:
    """共用同一個 Mathlib 環境的常駐 Lean REPL 驗證器。"""

    def __init__(
        self,
        project_dir: Path,
        timeout_seconds: int,
        repl_path: Path,
    ):
        self.project_dir = project_dir.resolve()
        self.timeout_seconds = timeout_seconds
        self.repl_path = repl_path.resolve()
        self.command = ["lake", "env", str(self.repl_path)]
        self._process: subprocess.Popen[str] | None = None
        self._responses: queue.Queue[str | None] = queue.Queue()
        self._stderr: deque[str] = deque(maxlen=200)
        self._base_envs: dict[tuple[str, ...], int] = {}

    def _read_stdout(self, stream: Any) -> None:
        block: list[str] = []
        try:
            for line in stream:
                if line.strip():
                    block.append(line)
                elif block:
                    self._responses.put("".join(block))
                    block = []
            if block:
                self._responses.put("".join(block))
        finally:
            self._responses.put(None)

    def _read_stderr(self, stream: Any) -> None:
        for line in stream:
            self._stderr.append(line.rstrip())

    def _start(self) -> None:
        if self._process is not None and self._process.poll() is None:
            return
        if not self.repl_path.is_file():
            raise ReplError(f"找不到 REPL 執行檔：{self.repl_path}")

        self._responses = queue.Queue()
        self._stderr.clear()
        self._base_envs.clear()
        try:
            process = subprocess.Popen(
                self.command,
                cwd=self.project_dir,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )
        except OSError as exc:
            raise ReplError(f"無法啟動 Lean REPL：{exc}") from exc
        if process.stdin is None or process.stdout is None or process.stderr is None:
            process.kill()
            raise ReplError("Lean REPL 未建立完整的標準輸入輸出管線")

        self._process = process
        threading.Thread(
            target=self._read_stdout,
            args=(process.stdout,),
            daemon=True,
        ).start()
        threading.Thread(
            target=self._read_stderr,
            args=(process.stderr,),
            daemon=True,
        ).start()

    def _stderr_text(self) -> str:
        return "\n".join(self._stderr)

    def _request(self, payload: dict[str, Any]) -> dict[str, Any]:
        self._start()
        process = self._process
        if process is None or process.stdin is None:
            raise ReplError("Lean REPL 尚未啟動")
        try:
            process.stdin.write(json.dumps(payload, ensure_ascii=False) + "\n\n")
            process.stdin.flush()
        except (BrokenPipeError, OSError) as exc:
            stderr = self._stderr_text()
            self.close()
            raise ReplError(f"Lean REPL 輸入失敗：{exc}\n{stderr}".strip()) from exc

        try:
            block = self._responses.get(timeout=self.timeout_seconds)
        except queue.Empty as exc:
            self.close()
            raise TimeoutError(
                f"Lean REPL 驗證超過 {self.timeout_seconds} 秒"
            ) from exc
        if block is None:
            return_code = process.poll()
            stderr = self._stderr_text()
            self.close()
            raise ReplError(
                f"Lean REPL 提前結束（結束碼 {return_code}）\n{stderr}".strip()
            )
        try:
            response = json.loads(block)
        except json.JSONDecodeError as exc:
            self.close()
            raise ReplError(f"Lean REPL 回傳非 JSON 內容：{block[:1000]}") from exc
        if not isinstance(response, dict):
            raise ReplError("Lean REPL 回傳內容不是 JSON object")
        if isinstance(response.get("message"), str):
            raise ReplError(f"Lean REPL protocol error：{response['message']}")
        return response

    @staticmethod
    def _has_error(response: dict[str, Any]) -> bool:
        messages = response.get("messages", [])
        return isinstance(messages, list) and any(
            isinstance(message, dict) and message.get("severity") == "error"
            for message in messages
        )

    @staticmethod
    def _response_error(response: dict[str, Any]) -> str | None:
        env = response.get("env")
        if isinstance(env, bool) or not isinstance(env, int) or env < 0:
            return "Lean REPL 回覆缺少合法的 env"
        messages = response.get("messages", [])
        if not isinstance(messages, list) or any(
            not isinstance(message, dict)
            or message.get("severity") not in {"trace", "info", "warning", "error"}
            or not isinstance(message.get("data"), str)
            for message in messages
        ):
            return "Lean REPL 回覆的 messages 格式不合法"
        sorries = response.get("sorries", [])
        if not isinstance(sorries, list) or any(
            not isinstance(sorry, dict) for sorry in sorries
        ):
            return "Lean REPL 回覆的 sorries 格式不合法"
        return None

    def _base_env(self, imports: tuple[str, ...]) -> int:
        existing = self._base_envs.get(imports)
        if existing is not None:
            return existing
        response = self._request({"cmd": "\n".join(imports)})
        response_error = self._response_error(response)
        if response_error is not None:
            raise ReplError(response_error)
        if self._has_error(response) or response.get("sorries"):
            raise ReplError(
                "Lean REPL 無法載入題目 imports："
                + json.dumps(response, ensure_ascii=False)
            )
        env = response["env"]
        self._base_envs[imports] = env
        return env

    def check(
        self,
        problem: Problem,
        proof_body: str,
        check_id: str,
    ) -> LeanCheckResult:
        del check_id  # REPL 從固定基礎環境分支，不建立檔案或全域宣告名稱。
        started = time.monotonic()
        try:
            proof = validate_proof_body(proof_body)
        except ValueError as exc:
            return LeanCheckResult(
                status="invalid_output",
                verified=False,
                lean_file=None,
                module_name=None,
                error=str(exc),
                elapsed_seconds=time.monotonic() - started,
                command=None,
            )

        declaration = (
            AUTO_IMPLICIT_OFF + problem.lean_theorem_header.rstrip() + "\n" + proof
        )
        try:
            with _LEAN_LOCK:
                base_env = self._base_env(problem.lean_imports)
                response = self._request({"cmd": declaration, "env": base_env})
        except TimeoutError as exc:
            return LeanCheckResult(
                status="tool_failed",
                verified=False,
                lean_file=None,
                module_name=None,
                error=str(exc),
                elapsed_seconds=time.monotonic() - started,
                command=self.command,
            )
        except ReplError as exc:
            return LeanCheckResult(
                status="tool_failed",
                verified=False,
                lean_file=None,
                module_name=None,
                error=str(exc),
                elapsed_seconds=time.monotonic() - started,
                command=self.command,
            )

        raw_diagnostics = json.dumps(response, ensure_ascii=False, indent=2)
        diagnostics = _bounded_diagnostics(raw_diagnostics)
        response_error = self._response_error(response)
        if response_error is not None:
            return LeanCheckResult(
                status="tool_failed",
                verified=False,
                lean_file=None,
                module_name=None,
                error=response_error,
                elapsed_seconds=time.monotonic() - started,
                command=self.command,
                diagnostics=diagnostics,
            )
        has_sorry = bool(response.get("sorries")) or bool(
            _SORRY_WARNING.search(raw_diagnostics)
        )
        if not self._has_error(response) and not has_sorry:
            return LeanCheckResult(
                status="verified",
                verified=True,
                lean_file=None,
                module_name=None,
                error=None,
                elapsed_seconds=time.monotonic() - started,
                command=self.command,
                diagnostics=diagnostics,
            )
        return LeanCheckResult(
            status="proof_failed",
            verified=False,
            lean_file=None,
            module_name=None,
            error=diagnostics,
            elapsed_seconds=time.monotonic() - started,
            command=self.command,
            diagnostics=diagnostics,
        )

    def close(self) -> None:
        process = self._process
        self._process = None
        self._base_envs.clear()
        if process is None or process.poll() is not None:
            return
        try:
            if process.stdin is not None:
                process.stdin.close()
            process.terminate()
            process.wait(timeout=2)
        except (OSError, subprocess.TimeoutExpired):
            process.kill()
            try:
                process.wait(timeout=2)
            except (OSError, subprocess.TimeoutExpired):
                pass

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass


class LeanRunner:
    """依設定選用常駐 REPL；未指定 REPL 時保留 lake build 後端。"""

    def __init__(
        self,
        project_dir: Path,
        timeout_seconds: int,
        repl_path: Path | None = None,
    ):
        self._backend: LakeLeanRunner | ReplLeanRunner
        if repl_path is None:
            self._backend = LakeLeanRunner(project_dir, timeout_seconds)
        else:
            self._backend = ReplLeanRunner(
                project_dir,
                timeout_seconds,
                repl_path,
            )

    def check(
        self,
        problem: Problem,
        proof_body: str,
        check_id: str,
    ) -> LeanCheckResult:
        return self._backend.check(problem, proof_body, check_id)

    def close(self) -> None:
        close = getattr(self._backend, "close", None)
        if close is not None:
            close()
