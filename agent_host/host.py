#!/usr/bin/env python3
"""AI-DG persistent agent host.

This process is the only component that starts Codex and Cline.  SketchUp's
Ruby thread never waits on either runtime; it exchanges bounded JSONL
messages with this host instead.  The host deliberately speaks the native
Codex App Server and ACP protocols and never pretends that a local response is
Codex or Cline output.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Awaitable, Callable


MAX_LINE_BYTES = 1_048_576
MAX_NATIVE_LINE_BYTES = 16 * MAX_LINE_BYTES
MAX_EVENT_QUEUE = 500
REQUEST_TIMEOUT = 60.0
TURN_TIMEOUT = 30 * 60.0
PROTOCOL_VERSION = 1


def now_ms() -> int:
    return int(time.time() * 1000)


def json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def redact(value: Any) -> Any:
    """Remove obvious secret fields from diagnostic payloads."""

    secret_words = ("api_key", "apikey", "token", "secret", "password", "authorization")
    if isinstance(value, dict):
        return {
            str(key): "[REDACTED]" if any(word in str(key).lower() for word in secret_words) else redact(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact(item) for item in value[:100]]
    if isinstance(value, str):
        return value[:4000]
    return value


class RpcFailure(RuntimeError):
    def __init__(self, code: str, message: str, detail: Any = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.detail = detail


def windows_command(command: list[str]) -> list[str]:
    """Run .cmd/.bat files without a shell for arbitrary user input."""

    if os.name != "nt" or not command:
        return command
    suffix = Path(command[0]).suffix.lower()
    if suffix not in {".cmd", ".bat"}:
        return command
    command_line = subprocess.list2cmdline(command)
    return [os.environ.get("COMSPEC", "cmd.exe"), "/d", "/s", "/c", command_line]


class JsonRpcProcess:
    """Bounded JSONL JSON-RPC subprocess with request correlation."""

    def __init__(
        self,
        name: str,
        command: list[str],
        cwd: Path,
        env: dict[str, str],
        jsonrpc_header: bool,
        on_message: Callable[[dict[str, Any]], Awaitable[None]],
        on_exit: Callable[[str, int | None], Awaitable[None]],
    ):
        self.name = name
        self.command = command
        self.cwd = cwd
        self.env = env
        self.jsonrpc_header = jsonrpc_header
        self.on_message = on_message
        self.on_exit = on_exit
        self.process: asyncio.subprocess.Process | None = None
        self._write_lock = asyncio.Lock()
        self._pending: dict[str, asyncio.Future[dict[str, Any]]] = {}
        self._sequence = 0
        self._reader_task: asyncio.Task[None] | None = None
        self._stderr_task: asyncio.Task[None] | None = None
        self.stderr_tail: list[str] = []
        self.last_error: str | None = None

    @property
    def pid(self) -> int | None:
        return self.process.pid if self.process else None

    @property
    def alive(self) -> bool:
        return bool(self.process and self.process.returncode is None)

    async def start(self) -> None:
        if self.alive:
            return
        command = windows_command(self.command)
        try:
            self.process = await asyncio.create_subprocess_exec(
                *command,
                cwd=str(self.cwd),
                env=self.env,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                limit=MAX_NATIVE_LINE_BYTES,
            )
        except OSError as exc:
            raise RpcFailure("PROCESS_START_FAILED", f"{self.name} không khởi chạy được", type(exc).__name__) from exc

        self._reader_task = asyncio.create_task(self._read_stdout())
        self._stderr_task = asyncio.create_task(self._read_stderr())

    async def send(self, message: dict[str, Any]) -> None:
        if not self.process or not self.process.stdin or not self.alive:
            raise RpcFailure("PROCESS_NOT_RUNNING", f"{self.name} chưa chạy")
        payload = dict(message)
        if self.jsonrpc_header:
            payload.setdefault("jsonrpc", "2.0")
        raw = (json_dumps(payload) + "\n").encode("utf-8")
        if len(raw) > MAX_LINE_BYTES:
            raise RpcFailure("PROTOCOL_LINE_TOO_LARGE", f"Request {self.name} vượt giới hạn")
        async with self._write_lock:
            self.process.stdin.write(raw)
            await self.process.stdin.drain()

    async def notify(self, method: str, params: dict[str, Any] | None = None) -> None:
        message: dict[str, Any] = {"method": method}
        if params is not None:
            message["params"] = params
        await self.send(message)

    async def request(self, method: str, params: dict[str, Any] | None = None, timeout: float = REQUEST_TIMEOUT) -> dict[str, Any]:
        self._sequence += 1
        request_id = f"{self.name}-{self._sequence}"
        loop = asyncio.get_running_loop()
        future: asyncio.Future[dict[str, Any]] = loop.create_future()
        self._pending[request_id] = future
        message: dict[str, Any] = {"id": request_id, "method": method}
        if params is not None:
            message["params"] = params
        try:
            await self.send(message)
            response = await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError as exc:
            raise RpcFailure("PROTOCOL_TIMEOUT", f"{self.name}: {method} timeout") from exc
        finally:
            self._pending.pop(request_id, None)
        if "error" in response:
            error = response.get("error") or {}
            raise RpcFailure(
                str(error.get("code", "REMOTE_ERROR")),
                str(error.get("message", f"{self.name}: {method} failed")),
                redact(error.get("data")),
            )
        return response.get("result") if isinstance(response.get("result"), dict) else response

    async def respond(self, request_id: Any, result: Any = None, error: Any = None) -> None:
        message: dict[str, Any] = {"id": request_id}
        if error is not None:
            message["error"] = error
        else:
            message["result"] = result if result is not None else {}
        await self.send(message)

    async def _read_stdout(self) -> None:
        assert self.process and self.process.stdout
        exit_code: int | None = None
        try:
            while True:
                raw = await self.process.stdout.readline()
                if not raw:
                    break
                if len(raw) > MAX_NATIVE_LINE_BYTES:
                    self.last_error = "PROTOCOL_LINE_TOO_LARGE"
                    continue
                try:
                    message = json.loads(raw.decode("utf-8", errors="replace"))
                except json.JSONDecodeError:
                    self.last_error = "PROTOCOL_INVALID_JSON"
                    continue
                if not isinstance(message, dict):
                    self.last_error = "PROTOCOL_INVALID_MESSAGE"
                    continue
                response_id = message.get("id")
                if response_id is not None and "method" not in message:
                    future = self._pending.get(str(response_id))
                    if future and not future.done():
                        future.set_result(message)
                    continue
                await self.on_message(message)
        except asyncio.CancelledError:
            raise
        except (BrokenPipeError, ConnectionError, OSError, ValueError) as exc:
            self.last_error = str(exc)[:200] if isinstance(exc, ValueError) else type(exc).__name__
            if self.process:
                await terminate_process_tree(self.process)
        finally:
            if self.process:
                try:
                    exit_code = await self.process.wait()
                except OSError:
                    exit_code = self.process.returncode
            failure = RpcFailure("PROCESS_EXITED", f"{self.name} đã dừng", self.last_error)
            for future in list(self._pending.values()):
                if not future.done():
                    future.set_exception(failure)
            await self.on_exit(self.name, exit_code)

    async def _read_stderr(self) -> None:
        assert self.process and self.process.stderr
        try:
            while True:
                raw = await self.process.stderr.readline()
                if not raw:
                    break
                line = raw.decode("utf-8", errors="replace").strip()
                if line:
                    self.stderr_tail.append(line[:1000])
                    self.stderr_tail = self.stderr_tail[-20:]
        except (asyncio.CancelledError, OSError):
            return

    async def close(self) -> None:
        process = self.process
        if not process:
            return
        if process.returncode is None:
            try:
                if process.stdin:
                    process.stdin.close()
                    await process.stdin.wait_closed()
            except (OSError, RuntimeError):
                pass
            try:
                await asyncio.wait_for(process.wait(), timeout=2.0)
            except asyncio.TimeoutError:
                await terminate_process_tree(process)
        tasks = tuple(task for task in (self._reader_task, self._stderr_task) if task)
        if tasks:
            try:
                # Let EOF close the subprocess pipe transports normally.  A
                # forced kill or a broken child can still require cancellation
                # after the bounded grace period.
                await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), timeout=5.0)
            except asyncio.TimeoutError:
                for task in tasks:
                    if not task.done():
                        task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
        self._reader_task = None
        self._stderr_task = None
        # asyncio.subprocess.Process does not expose a public transport close
        # method.  Close its owned transport while the loop is still alive so
        # Proactor pipe destructors do not run after asyncio.run() has closed
        # the event loop.
        transport = getattr(process, "_transport", None)
        if transport is not None:
            try:
                transport.close()
            except (OSError, RuntimeError):
                pass
        self.process = None


async def terminate_process_tree(process: asyncio.subprocess.Process) -> None:
    if process.returncode is not None:
        return
    try:
        if os.name == "nt":
            killer = await asyncio.create_subprocess_exec(
                os.environ.get("COMSPEC", "cmd.exe"),
                "/d",
                "/c",
                "taskkill",
                "/PID",
                str(process.pid),
                "/T",
                "/F",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await asyncio.wait_for(killer.wait(), timeout=3.0)
        else:
            process.terminate()
        await asyncio.wait_for(process.wait(), timeout=3.0)
    except (asyncio.TimeoutError, OSError):
        try:
            process.kill()
        except OSError:
            pass


class AgentHost:
    def __init__(self, root: Path, auto_install_cline: bool = True):
        self.root = root.resolve()
        self.auto_install_cline = auto_install_cline
        self.runtime_dir = self.root / "OUTPUT" / "runtime" / "agent-host"
        self.mapping_path = self.root / "OUTPUT" / "runtime" / "agent-sessions.json"
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.runtimes: dict[str, JsonRpcProcess] = {}
        self.sessions: dict[str, dict[str, Any]] = self._load_mapping()
        self.pending_child_requests: dict[str, tuple[str, Any]] = {}
        self.pending_request_details: dict[str, dict[str, Any]] = {}
        self.active_turns: dict[str, str] = {}
        self.turn_started = {backend: asyncio.Event() for backend in ("codex", "cline")}
        self.loaded_sessions: dict[tuple[str, str], dict[str, Any]] = {}
        self.backend_locks = {name: asyncio.Lock() for name in ("codex", "cline")}
        self.request_context: dict[Any, dict[str, Any]] = {}
        self.cline_install_task: asyncio.Task[None] | None = None
        self.background_tasks: set[asyncio.Task[Any]] = set()
        self.cline_install_state = "NOT_CHECKED"
        self._output_lock = asyncio.Lock()
        self._shutdown = False
        self._shutdown_event: asyncio.Event | None = None

    def _load_mapping(self) -> dict[str, dict[str, Any]]:
        if not self.mapping_path.is_file():
            return {}
        try:
            payload = json.loads(self.mapping_path.read_text(encoding="utf-8"))
            if isinstance(payload, dict) and isinstance(payload.get("documents"), dict):
                return {str(key): value for key, value in payload["documents"].items() if isinstance(value, dict)}
        except (OSError, json.JSONDecodeError):
            pass
        return {}

    def _save_mapping(self) -> None:
        payload = {"schema_version": 1, "documents": self.sessions, "updated_utc_ms": now_ms()}
        self.mapping_path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(prefix="agent-sessions-", suffix=".json", dir=str(self.mapping_path.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
            os.replace(temp_name, self.mapping_path)
        finally:
            try:
                os.unlink(temp_name)
            except FileNotFoundError:
                pass

    async def emit(self, message: dict[str, Any]) -> None:
        if self._shutdown:
            return
        async with self._output_lock:
            raw = (json_dumps(message) + "\n").encode("utf-8")
            if len(raw) > MAX_LINE_BYTES:
                raw = (json_dumps({"type": "agent/event", "event": "host/error", "data": {"error": "OUTPUT_TOO_LARGE"}}) + "\n").encode("utf-8")
            sys.stdout.buffer.write(raw)
            sys.stdout.buffer.flush()

    async def response(self, request_id: Any, result: Any = None, error: str | None = None, detail: Any = None) -> None:
        if error:
            payload: dict[str, Any] = {"id": request_id, "status": "error", "error": error}
            if detail is not None:
                payload["detail"] = redact(detail)
        else:
            payload = {"id": request_id, "status": "ok", "data": result if result is not None else {}}
        payload.update(self.request_context.pop(request_id, {}))
        await self.emit(payload)

    def python_command(self) -> str:
        configured = os.environ.get("AI_DG_PYTHON", "").strip()
        candidates = [
            configured,
            str(Path(os.environ.get("LOCALAPPDATA", "")) / "Programs/Python/Python312/python.exe"),
            str(Path(os.environ.get("USERPROFILE", "")) / ".cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe"),
            "python.exe",
        ]
        for candidate in candidates:
            if not candidate:
                continue
            if Path(candidate).is_file() or shutil.which(candidate):
                return candidate
        return sys.executable

    def mcp_definition(self) -> dict[str, Any]:
        config_path = self.root / "mcp_config.json"
        try:
            config = json.loads(config_path.read_text(encoding="utf-8"))
            definition = config.get("mcpServers", {}).get("ai-dg", {})
            if isinstance(definition, dict) and definition.get("command"):
                return definition
        except (OSError, json.JSONDecodeError):
            pass
        python = self.python_command()
        return {
            "command": python,
            "args": [str(self.root / "mcp_server" / "launcher.py")],
            "env": {"PYTHONPATH": str(self.root), "AI_DG_TOOL_PROFILE": "minimal"},
        }

    def codex_path(self) -> str | None:
        configured = os.environ.get("CODEX_CLI_PATH", "").strip()
        user_root = Path(os.environ.get("USERPROFILE", ""))
        local_app = Path(os.environ.get("LOCALAPPDATA", ""))
        native_candidates = sorted(
            (local_app / "OpenAI" / "Codex" / "bin").glob("*/codex.exe"),
            reverse=True,
        )
        resolved = shutil.which("codex")
        candidates = [
            configured,
            *(str(path) for path in native_candidates),
            resolved,
            str(user_root / "AppData/Roaming/npm/codex.cmd"),
            str(user_root / "AppData/Local/Microsoft/WinGet/Links/codex.exe"),
        ]
        for candidate in candidates:
            if candidate and (Path(candidate).is_file() or shutil.which(candidate)):
                return candidate
        return None

    def cline_path(self) -> str | None:
        user_root = Path(os.environ.get("USERPROFILE", ""))
        local_app = Path(os.environ.get("LOCALAPPDATA", ""))
        candidates = [
            os.environ.get("CLINE_CLI_PATH", "").strip(),
            shutil.which("cline"),
            str(user_root / "AppData/Roaming/npm/cline.cmd"),
            str(local_app / "npm/cline.cmd"),
            str(local_app / "AI-DG/npm/node_modules/.bin/cline.cmd"),
        ]
        for candidate in candidates:
            if candidate and (Path(candidate).is_file() or shutil.which(candidate)):
                return candidate
        return None

    def _base_env(self) -> dict[str, str]:
        env = os.environ.copy()
        env["AI_DG_ROOT"] = str(self.root)
        env["PYTHONPATH"] = os.pathsep.join(
            [str(self.root / "OUTPUT" / "mcp_deps"), str(self.root), str(self.root / "mcp_server")]
            + ([env["PYTHONPATH"]] if env.get("PYTHONPATH") else [])
        )
        return env

    async def _process_message(self, backend: str, message: dict[str, Any], source: JsonRpcProcess | None = None) -> None:
        process = self.runtimes.get(backend)
        if process is None or (source is not None and process is not source):
            return
        if message.get("id") is not None and message.get("method"):
            child_id = message.get("id")
            key = f"{backend}:{child_id}"
            self.pending_child_requests[key] = (backend, child_id)
            self.pending_request_details[key] = message
            await self.emit({
                "type": "agent/event",
                "backend": backend,
                "event": "server/request",
                "data": {"request_id": child_id, "method": message.get("method"), "params": redact(message.get("params", {}))},
            })
            return

        params = message.get("params", {})
        if not isinstance(params, dict):
            params = {"value": params}
        event_name = str(message.get("method", "notification"))
        if event_name == "turn/started":
            self.turn_started[backend].set()
        session_id = self._session_id_for_backend(backend, params)
        if event_name in {"turn/completed", "turn/failed", "turn/interrupted", "turn/aborted"}:
            self.active_turns.pop(backend, None)
        await self.emit({
            "type": "agent/event",
            "backend": backend,
            "event": event_name,
            "session_id": session_id,
            "data": redact(params),
        })

    async def _process_exit(self, backend: str, exit_code: int | None) -> None:
        self.loaded_sessions = {key: value for key, value in self.loaded_sessions.items() if key[0] != backend}
        await self.emit({
            "type": "agent/event",
            "backend": backend,
            "event": "runtime/exited",
            "data": {"exit_code": exit_code, "protocol_error": self.runtimes[backend].last_error if backend in self.runtimes else None},
        })
        self.active_turns.pop(backend, None)

    def _session_id_for_backend(self, backend: str, params: dict[str, Any]) -> str | None:
        for value in (params.get("sessionId"), params.get("session_id"), params.get("threadId"), params.get("thread_id")):
            if value:
                return str(value)
        thread = params.get("thread", {})
        if isinstance(thread, dict) and thread.get("id"):
            return str(thread["id"])
        return None

    async def _ensure_codex(self, cwd: Path) -> JsonRpcProcess:
        existing = self.runtimes.get("codex")
        if existing and existing.alive:
            return existing
        path = self.codex_path()
        if not path:
            raise RpcFailure("CODEX_NOT_FOUND", "Không tìm thấy Codex CLI")
        command = self.codex_command(path)
        process = JsonRpcProcess(
            "codex",
            command,
            cwd,
            self._base_env(),
            jsonrpc_header=False,
            on_message=lambda message: self._process_message("codex", message, process),
            on_exit=self._process_exit,
        )
        await process.start()
        self.runtimes["codex"] = process
        try:
            await process.request(
                "initialize",
                {
                    "clientInfo": {"name": "ai_dg_sketchup", "title": "AI-DG SketchUp", "version": "0.1.0"},
                    "capabilities": {},
                },
                timeout=20.0,
            )
            await process.notify("initialized")
        except Exception:
            await process.close()
            self.runtimes.pop("codex", None)
            raise
        await self.emit({"type": "agent/event", "backend": "codex", "event": "runtime/ready", "data": {"pid": process.pid, "command": "codex app-server --stdio"}})
        task = asyncio.create_task(self._check_codex_mcp_status(process))
        self.background_tasks.add(task)
        task.add_done_callback(self.background_tasks.discard)
        return process

    async def _check_codex_mcp_status(self, process: JsonRpcProcess) -> None:
        """Run the diagnostic after readiness so MCP discovery cannot block startup."""

        try:
            result = await process.request(
                "mcpServerStatus/list",
                {"limit": 50, "detail": "toolsAndAuthOnly"},
                timeout=10.0,
            )
            servers = result.get("data", [])
            summary = [{"name": server.get("name"), "authStatus": server.get("authStatus"),
                        "tools": list(server.get("tools", {}))[:100]} for server in servers if server.get("name") == "ai-dg"]
            await self.emit({
                "type": "agent/event",
                "backend": "codex",
                "event": "mcp/status",
                "data": {"servers": summary, "ai_dg_found": bool(summary)},
            })
        except RpcFailure as exc:
            await self.emit({
                "type": "agent/event",
                "backend": "codex",
                "event": "mcp/status_failed",
                "data": {"error": exc.code, "detail": exc.message},
            })

    def codex_command(self, path: str | None = None) -> list[str]:
        """Build the isolated app-server command without touching global config."""

        executable = path or self.codex_path()
        if not executable:
            raise RpcFailure("CODEX_NOT_FOUND", "Không tìm thấy Codex CLI")
        mcp = self.mcp_definition()
        command = [executable, "app-server", "--stdio"]
        command.extend(["-c", f"mcp_servers.ai-dg.command={json.dumps(str(mcp.get('command', self.python_command())))}"])
        command.extend(["-c", f"mcp_servers.ai-dg.args={json.dumps(list(mcp.get('args', [])))}"])
        command.extend(["-c", 'mcp_servers.ai-dg.env.AI_DG_TOOL_PROFILE="minimal"'])
        return command

    def cline_mcp_path(self) -> Path:
        configured = os.environ.get("CLINE_MCP_CONFIG_PATH", "").strip()
        user_root = Path(os.environ.get("USERPROFILE", str(Path.home())))
        app_data = Path(os.environ.get("APPDATA", str(user_root / "AppData" / "Roaming")))
        candidates = [
            Path(configured) if configured else None,
            app_data / "Code" / "User" / "globalStorage" / "saoudrizwan.claude-dev" / "settings" / "cline_mcp_settings.json",
            app_data / "Cursor" / "User" / "globalStorage" / "saoudrizwan.claude-dev" / "settings" / "cline_mcp_settings.json",
            user_root / ".cline" / "mcp.json",
        ]
        for candidate in candidates:
            if candidate and candidate.is_file():
                return candidate
        return user_root / ".cline" / "mcp.json"

    def ensure_cline_mcp_config(self) -> Path:
        path = self.cline_mcp_path()
        payload: dict[str, Any] = {}
        if path.is_file():
            try:
                loaded = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    payload = loaded
            except (OSError, json.JSONDecodeError) as exc:
                raise RpcFailure("CLINE_MCP_CONFIG_INVALID", "Cấu hình MCP hiện tại không đọc được; đã giữ nguyên file") from exc
        servers = payload.get("mcpServers")
        if not isinstance(servers, dict):
            servers = {}
            payload["mcpServers"] = servers
        mcp = self.mcp_definition()
        servers["ai-dg"] = {
            "command": str(mcp.get("command", self.python_command())),
            "args": list(mcp.get("args", [])),
            "env": {**dict(mcp.get("env", {})), "AI_DG_TOOL_PROFILE": "minimal"},
            "disabled": False,
            "autoApprove": [],
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(prefix="mcp-", suffix=".json", dir=str(path.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
            os.replace(temp_name, path)
        finally:
            try:
                os.unlink(temp_name)
            except FileNotFoundError:
                pass
        return path

    async def _install_cline(self) -> None:
        if self.cline_path():
            self.cline_install_state = "READY"
            return
        npm = shutil.which("npm") or shutil.which("npm.cmd")
        if not npm:
            self.cline_install_state = "NPM_NOT_FOUND"
            await self.emit({"type": "agent/event", "backend": "cline", "event": "install/failed", "data": {"error": "NPM_NOT_FOUND"}})
            return
        self.cline_install_state = "INSTALLING"
        await self.emit({"type": "agent/event", "backend": "cline", "event": "install/started", "data": {"package": "cline"}})
        env = self._base_env()
        command = windows_command([npm, "install", "-g", "cline"])
        process = None
        fallback_process = None
        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                cwd=str(self.root),
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=300.0)
            if process.returncode != 0:
                local_prefix = Path(os.environ.get("LOCALAPPDATA", str(self.root / "OUTPUT"))) / "AI-DG" / "npm"
                fallback = windows_command([npm, "install", "--prefix", str(local_prefix), "cline"])
                fallback_process = await asyncio.create_subprocess_exec(
                    *fallback,
                    cwd=str(self.root),
                    env=env,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                fallback_stdout, fallback_stderr = await asyncio.wait_for(fallback_process.communicate(), timeout=300.0)
                if fallback_process.returncode != 0:
                    self.cline_install_state = "INSTALL_FAILED"
                    await self.emit({"type": "agent/event", "backend": "cline", "event": "install/failed", "data": {"error": "INSTALL_FAILED", "exit_code": fallback_process.returncode, "stdout_bytes": len(fallback_stdout), "stderr_bytes": len(fallback_stderr)}})
                    return
            self.cline_install_state = "READY" if self.cline_path() else "INSTALL_VERIFY_FAILED"
            event = "install/completed" if self.cline_install_state == "READY" else "install/failed"
            await self.emit({"type": "agent/event", "backend": "cline", "event": event, "data": {"state": self.cline_install_state}})
        except asyncio.TimeoutError:
            self.cline_install_state = "INSTALL_TIMEOUT"
            await self.emit({"type": "agent/event", "backend": "cline", "event": "install/failed", "data": {"error": self.cline_install_state}})
        except OSError as exc:
            self.cline_install_state = "INSTALL_FAILED"
            await self.emit({"type": "agent/event", "backend": "cline", "event": "install/failed", "data": {"error": self.cline_install_state, "detail": type(exc).__name__}})
        finally:
            for owned in (process, fallback_process):
                if owned is not None and owned.returncode is None:
                    await terminate_process_tree(owned)

    async def _ensure_cline(self, cwd: Path) -> JsonRpcProcess:
        existing = self.runtimes.get("cline")
        if existing and existing.alive:
            return existing
        path = self.cline_path()
        if not path:
            if self.cline_install_task and not self.cline_install_task.done():
                raise RpcFailure("CLINE_INSTALLING", "Cline đang được cài đặt")
            if self.auto_install_cline and self.cline_install_state in {"NOT_CHECKED", "INSTALL_FAILED", "INSTALL_VERIFY_FAILED", "NPM_NOT_FOUND"}:
                self.cline_install_task = asyncio.create_task(self._install_cline())
                raise RpcFailure("CLINE_INSTALLING", "Cline đang được cài đặt")
            raise RpcFailure("CLINE_NOT_FOUND", "Không tìm thấy Cline CLI")
        self.ensure_cline_mcp_config()
        process = JsonRpcProcess(
            "cline",
            [path, "--acp", "--cwd", str(cwd)],
            cwd,
            self._base_env(),
            jsonrpc_header=True,
            on_message=lambda message: self._process_message("cline", message, process),
            on_exit=self._process_exit,
        )
        await process.start()
        self.runtimes["cline"] = process
        try:
            await process.request(
                "initialize",
                {
                    "protocolVersion": PROTOCOL_VERSION,
                    "clientCapabilities": {},
                    "clientInfo": {"name": "ai_dg_sketchup", "title": "AI-DG SketchUp", "version": "0.1.0"},
                },
                timeout=20.0,
            )
        except Exception:
            await process.close()
            self.runtimes.pop("cline", None)
            raise
        await self.emit({"type": "agent/event", "backend": "cline", "event": "runtime/ready", "data": {"pid": process.pid, "command": "cline --acp"}})
        return process

    async def ensure_backend(self, backend: str, cwd: Path) -> JsonRpcProcess:
        if backend not in self.backend_locks:
            raise RpcFailure("INVALID_BACKEND", "Backend phải là codex hoặc cline")
        async with self.backend_locks[backend]:
            return await (self._ensure_codex(cwd) if backend == "codex" else self._ensure_cline(cwd))

    def _document(self, key: str) -> dict[str, Any]:
        return self.sessions.setdefault(key, {})

    @staticmethod
    def _codex_thread_id(result: dict[str, Any]) -> str | None:
        thread = result.get("thread") if isinstance(result.get("thread"), dict) else result
        for key in ("id", "threadId", "thread_id"):
            if isinstance(thread, dict) and thread.get(key):
                return str(thread[key])
        return None

    @staticmethod
    def _cline_session_id(result: dict[str, Any]) -> str | None:
        for key in ("sessionId", "session_id", "id"):
            if result.get(key):
                return str(result[key])
        return None

    def acp_mcp_servers(self) -> list[dict[str, Any]]:
        mcp = self.mcp_definition()
        env = {**dict(mcp.get("env", {})), "AI_DG_TOOL_PROFILE": "minimal"}
        return [{"name": "ai-dg", "command": str(mcp.get("command", self.python_command())),
                 "args": list(mcp.get("args", [])),
                 "env": [{"name": key, "value": str(value)} for key, value in env.items()]}]

    async def open_session(self, backend: str, document_key: str, cwd: Path, force_resume: bool = False) -> dict[str, Any]:
        process = await self.ensure_backend(backend, cwd)
        loaded = self.loaded_sessions.get((backend, document_key))
        if not force_resume and loaded and loaded.get("cwd") == str(cwd):
            return loaded
        document = self._document(document_key)
        saved = document.get(backend) if isinstance(document.get(backend), dict) else {}
        if backend == "codex":
            thread_id = str(saved.get("thread_id")) if saved.get("thread_id") else None
            result: dict[str, Any]
            if thread_id and (force_resume or saved.get("cwd") == str(cwd)):
                try:
                    result = await process.request("thread/resume", {"threadId": thread_id, "cwd": str(cwd), "approvalPolicy": "on-request", "sandbox": "read-only"}, timeout=30.0)
                except RpcFailure as exc:
                    await self.emit({"type": "agent/event", "backend": backend, "event": "session/resume_failed", "data": {"error": exc.code, "detail": exc.message}})
                    raise RpcFailure("SESSION_RESUME_FAILED", "Codex không resume được thread đã lưu", {"runtime_error": exc.code, "detail": exc.message}) from exc
            else:
                result = await process.request("thread/start", {"cwd": str(cwd), "approvalPolicy": "on-request", "sandbox": "read-only"}, timeout=30.0)
            thread_id = self._codex_thread_id(result)
            if not thread_id:
                raise RpcFailure("CODEX_THREAD_ID_MISSING", "Codex không trả về thread ID")
            session_id = None
            thread = result.get("thread") if isinstance(result.get("thread"), dict) else result
            if isinstance(thread, dict):
                session_id = thread.get("sessionId") or thread.get("session_id")
            document[backend] = {"thread_id": thread_id, "session_id": str(session_id) if session_id else None, "cwd": str(cwd)}
            self._save_mapping()
            opened = {"backend": backend, "thread_id": thread_id, "session_id": session_id, "cwd": str(cwd), "runtime_pid": process.pid}
            self.loaded_sessions[(backend, document_key)] = opened
            return opened

        session_id = str(saved.get("session_id")) if saved.get("session_id") else None
        result = {}
        if session_id and (force_resume or saved.get("cwd") == str(cwd)):
            try:
                result = await process.request("session/load", {"sessionId": session_id, "cwd": str(cwd), "mcpServers": self.acp_mcp_servers()}, timeout=30.0)
            except RpcFailure as exc:
                await self.emit({"type": "agent/event", "backend": backend, "event": "session/resume_failed", "data": {"error": exc.code, "detail": exc.message}})
                raise RpcFailure("SESSION_RESUME_FAILED", "Cline không resume được session đã lưu", {"runtime_error": exc.code, "detail": exc.message}) from exc
        if not session_id:
            mcp = self.mcp_definition()
            result = await process.request(
                "session/new",
                {
                    "cwd": str(cwd),
                    "mcpServers": self.acp_mcp_servers(),
                },
                timeout=45.0,
            )
            session_id = self._cline_session_id(result)
        if not session_id:
            raise RpcFailure("CLINE_SESSION_ID_MISSING", "Cline không trả về session ID")
        if not saved.get("session_id"):
            await process.request("session/set_mode", {"sessionId": session_id, "modeId": "plan"}, timeout=10.0)
        document[backend] = {"session_id": session_id, "cwd": str(cwd)}
        self._save_mapping()
        opened = {"backend": backend, "session_id": session_id, "cwd": str(cwd), "runtime_pid": process.pid, "models": redact(result.get("models")), "modes": redact(result.get("modes"))}
        self.loaded_sessions[(backend, document_key)] = opened
        return opened

    async def handle(self, request: dict[str, Any]) -> None:
        request_id = request.get("id")
        method = str(request.get("method", ""))
        data = request.get("data") if isinstance(request.get("data"), dict) else request
        backend = str(request.get("backend") or data.get("backend") or "").lower()
        self.request_context[request_id] = {"backend": backend, "method": method}
        document_key = str(request.get("document_key") or data.get("document_key") or "untitled")
        cwd = Path(str(request.get("cwd") or data.get("cwd") or self.root)).resolve()
        if not cwd.is_dir():
            cwd = self.root
        try:
            if method in {"host/status", "runtime/status"}:
                await self.response(request_id, self.status())
                return
            if method == "host/shutdown":
                await self.response(request_id, {"stopping": True})
                # Let the stdin loop own the final cleanup.  Closing the child
                # from a detached task races with run(), which can leave the
                # host waiting for an already-closing pipe.
                if self._shutdown_event is not None:
                    self._shutdown_event.set()
                else:
                    self._shutdown = True
                return
            if method == "agent/open":
                process = await self.ensure_backend(backend, cwd)
                await self.response(request_id, {"backend": backend, "pid": process.pid, "command": " ".join(process.command[:3])})
                return
            if method in {"session/open", "session/resume"}:
                result = await self.open_session(backend, document_key, cwd, force_resume=method == "session/resume")
                await self.response(request_id, result)
                return
            if method == "turn/start":
                if backend not in {"codex", "cline"}:
                    raise RpcFailure("INVALID_BACKEND", "Backend phải là codex hoặc cline")
                if backend in self.active_turns:
                    raise RpcFailure("TURN_BUSY", f"{backend} đang xử lý một turn")
                self.active_turns[backend] = str(request_id)
                self.turn_started[backend].clear()
                session = await self.open_session(backend, document_key, cwd)
                text = str(request.get("text") or data.get("text") or "").strip()
                if not text:
                    raise RpcFailure("EMPTY_PROMPT", "Tin nhắn trống")
                process = self.runtimes[backend]
                if backend == "codex":
                    native = await process.request(
                        "turn/start",
                        {"threadId": session["thread_id"], "input": [{"type": "text", "text": text}], "cwd": str(cwd), "approvalPolicy": "on-request", "sandboxPolicy": {"type": "readOnly"}},
                        timeout=30.0,
                    )
                    native_turn = native.get("turn") if isinstance(native.get("turn"), dict) else native
                    turn_id = str(native_turn.get("id") or native_turn.get("turnId") or "") if isinstance(native_turn, dict) else ""
                else:
                    self.active_turns[backend] = str(request_id)
                    native = await process.request(
                        "session/prompt",
                        {"sessionId": session["session_id"], "prompt": [{"type": "text", "text": text}]},
                        timeout=TURN_TIMEOUT,
                    )
                    turn_id = str(native.get("turnId") or native.get("id") or "") if isinstance(native, dict) else ""
                self.active_turns[backend] = turn_id or str(request_id)
                await self.response(request_id, {**session, "turn_id": turn_id, "native": redact(native)})
                if backend == "cline":
                    self.active_turns.pop(backend, None)
                return
            if method == "turn/cancel":
                process = self.runtimes.get(backend)
                if not process or not process.alive:
                    raise RpcFailure("PROCESS_NOT_RUNNING", f"{backend} chưa chạy")
                session = self._document(document_key).get(backend, {})
                if backend == "codex":
                    if backend in self.active_turns and not self.turn_started[backend].is_set():
                        await asyncio.wait_for(self.turn_started[backend].wait(), timeout=10.0)
                    await process.request("turn/interrupt", {"threadId": session.get("thread_id"), "turnId": data.get("turn_id") or self.active_turns.get(backend)}, timeout=10.0)
                else:
                    await process.notify("session/cancel", {"sessionId": session.get("session_id")})
                self.active_turns.pop(backend, None)
                await self.response(request_id, {"backend": backend, "cancelled": True})
                return
            if method == "approval/respond":
                child_request_id = data.get("request_id")
                key = f"{backend}:{child_request_id}"
                pending = self.pending_child_requests.pop(key, None)
                if not pending:
                    raise RpcFailure("APPROVAL_NOT_FOUND", "Yêu cầu approval không còn chờ")
                process = self.runtimes.get(backend)
                if not process:
                    raise RpcFailure("PROCESS_NOT_RUNNING", f"{backend} chưa chạy")
                original = self.pending_request_details.pop(key, {})
                native_method = str(original.get("method") or data.get("method") or "")
                if backend == "cline" and "request_permission" in native_method:
                    kind = "allow_once" if data.get("approved") is True else "reject_once"
                    options = original.get("params", {}).get("options", [])
                    chosen = next((option for option in options if option.get("kind") == kind), None)
                    outcome = {"outcome": "selected", "optionId": chosen["optionId"]} if chosen else {"outcome": "cancelled"}
                    await process.respond(child_request_id, result={"outcome": outcome})
                elif "elicitation" in native_method:
                    action = "accept" if data.get("approved") is True else "decline"
                    await process.respond(child_request_id, result={"action": action, "content": {}})
                elif data.get("approved") is True:
                    await process.respond(child_request_id, result=data.get("result") or {"decision": "accept"})
                else:
                    await process.respond(child_request_id, result={"decision": "decline"})
                await self.response(request_id, {"responded": True})
                return
            if method == "model/list":
                process = await self.ensure_backend(backend, cwd)
                if backend == "codex":
                    result = await process.request("model/list", {}, timeout=30.0)
                else:
                    result = self.loaded_sessions.get((backend, document_key), {}).get("models", {})
                await self.response(request_id, redact(result))
                return
            if method == "session/set_mode":
                if backend != "cline" or data.get("mode_id") not in {"plan", "act"}:
                    raise RpcFailure("INVALID_MODE", "Chọn Plan hoặc Act cho Cline")
                session = await self.open_session(backend, document_key, cwd)
                result = await self.runtimes[backend].request("session/set_mode", {"sessionId": session["session_id"], "modeId": data["mode_id"]})
                await self.response(request_id, {"backend": backend, "mode_id": data["mode_id"], "native": result})
                return
            if method == "session/close":
                self.active_turns.pop(backend, None)
                await self.response(request_id, {"backend": backend, "closed": True})
                return
            raise RpcFailure("UNKNOWN_METHOD", f"Method không được hỗ trợ: {method}")
        except RpcFailure as exc:
            if method == "turn/start" and exc.code != "TURN_BUSY":
                self.active_turns.pop(backend, None)
            await self.response(request_id, error=exc.code, detail={"message": exc.message, "runtime": exc.detail})
        except Exception as exc:  # pragma: no cover - defensive boundary
            await self.response(request_id, error="HOST_INTERNAL_ERROR", detail=type(exc).__name__)

    def status(self) -> dict[str, Any]:
        return {
            "host": "READY" if not self._shutdown else "STOPPING",
            "pid": os.getpid(),
            "root": str(self.root),
            "codex": {"available": bool(self.codex_path()), "pid": self.runtimes.get("codex").pid if self.runtimes.get("codex") else None, "alive": self.runtimes.get("codex").alive if self.runtimes.get("codex") else False},
            "cline": {"available": bool(self.cline_path()), "pid": self.runtimes.get("cline").pid if self.runtimes.get("cline") else None, "alive": self.runtimes.get("cline").alive if self.runtimes.get("cline") else False, "install_state": self.cline_install_state},
            "sessions_path": str(self.mapping_path),
        }

    async def startup(self) -> None:
        await self.emit({"type": "agent/event", "event": "host/ready", "data": self.status()})
        if self.auto_install_cline and not self.cline_path():
            self.cline_install_task = asyncio.create_task(self._install_cline())
            self.cline_install_state = "INSTALLING"

    async def shutdown(self) -> None:
        if self._shutdown:
            return
        self._shutdown = True
        if self._shutdown_event is not None:
            self._shutdown_event.set()
        if self.cline_install_task and not self.cline_install_task.done():
            self.cline_install_task.cancel()
            await asyncio.gather(self.cline_install_task, return_exceptions=True)
        for task in list(self.background_tasks):
            task.cancel()
        await asyncio.gather(*self.background_tasks, return_exceptions=True)
        for process in list(self.runtimes.values()):
            await process.close()
        self.runtimes.clear()

    async def run(self) -> int:
        self._shutdown_event = asyncio.Event()
        await self.startup()
        loop = asyncio.get_running_loop()
        stdin_queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=MAX_EVENT_QUEUE)
        # Open3 gives the host a blocking pipe on Windows.  Keep that one
        # blocking call outside asyncio, but use os.read rather than the
        # buffered TextIO object so interpreter shutdown cannot deadlock on an
        # I/O lock.  This thread never owns protocol or runtime state.
        def enqueue(raw_line: bytes) -> None:
            try:
                stdin_queue.put_nowait(raw_line)
            except asyncio.QueueFull:
                self._shutdown_event.set()

        def read_stdin() -> None:
            pending = bytearray()
            while True:
                try:
                    chunk = os.read(0, 65536)
                except (OSError, ValueError):
                    chunk = b""
                if not chunk:
                    if pending:
                        try:
                            loop.call_soon_threadsafe(enqueue, bytes(pending))
                        except RuntimeError:
                            return
                    try:
                        loop.call_soon_threadsafe(enqueue, b"")
                    except RuntimeError:
                        pass
                    return
                pending.extend(chunk)
                if len(pending) > MAX_LINE_BYTES:
                    loop.call_soon_threadsafe(self._shutdown_event.set)
                    return
                while b"\n" in pending:
                    raw_line, _, pending = pending.partition(b"\n")
                    try:
                        loop.call_soon_threadsafe(enqueue, bytes(raw_line) + b"\n")
                    except RuntimeError:
                        return

        stdin_thread = threading.Thread(target=read_stdin, name="ai-dg-agent-host-stdin", daemon=True)
        stdin_thread.start()

        try:
            while not self._shutdown:
                read_task = asyncio.create_task(stdin_queue.get())
                stop_task = asyncio.create_task(self._shutdown_event.wait())
                done, pending = await asyncio.wait({read_task, stop_task}, return_when=asyncio.FIRST_COMPLETED)
                for task in pending:
                    task.cancel()
                if stop_task in done:
                    break
                raw = read_task.result()
                if not raw:
                    break
                if len(raw) > MAX_LINE_BYTES:
                    await self.emit({"type": "agent/event", "event": "host/error", "data": {"error": "INPUT_TOO_LARGE"}})
                    continue
                try:
                    request = json.loads(raw.decode("utf-8", errors="replace"))
                except json.JSONDecodeError:
                    await self.emit({"type": "agent/event", "event": "host/error", "data": {"error": "INVALID_JSON"}})
                    continue
                if isinstance(request, dict):
                    asyncio.create_task(self.handle(request))
        finally:
            await self.shutdown()
        return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AI-DG Codex/Cline persistent host")
    parser.add_argument("--root", default=os.environ.get("AI_DG_ROOT", str(Path(__file__).resolve().parents[1])))
    parser.add_argument("--no-auto-install-cline", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    host = AgentHost(Path(args.root), auto_install_cline=not args.no_auto_install_cline)
    try:
        return asyncio.run(host.run())
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
