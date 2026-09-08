# Archived migration reference; not imported by the production runtime.
#!/usr/bin/env python3
"""Run one bounded, read-only Codex CLI turn for the SketchUp Control Center.

This adapter is deliberately separate from the 9Router provider adapter.  It
uses the Codex CLI authentication already present on the host, never prints
the CLI environment or credentials, and requires an explicit per-request
``allow_network=true`` flag from the Control Center.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
NETWORK_GATE_ERROR = "CODEX_NETWORK_TEST_REQUIRES_EXPLICIT_ENABLE"
MCP_WRAPPER_PATH = ROOT_DIR / "mcp_server" / "ai_dg_codex_mcp.cmd"


def _candidate_paths() -> list[Path]:
    values: list[str] = []
    configured = os.environ.get("CODEX_CLI_PATH", "").strip()
    if configured:
        values.append(configured)
    values.extend([
        str(Path.home() / "AppData" / "Roaming" / "npm" / "codex.cmd"),
        str(Path.home() / "AppData" / "Roaming" / "npm" / "node_modules" / "@openai" / "codex" / "node_modules" / "@openai" / "codex-win32-x64" / "vendor" / "x86_64-pc-windows-msvc" / "bin" / "codex.exe"),
    ])
    local_bin = Path.home() / "AppData" / "Local" / "OpenAI" / "Codex" / "bin"
    if local_bin.is_dir():
        values.extend(str(path) for path in sorted(local_bin.glob("*/codex.exe")))
    for name in ("codex.exe", "codex.cmd", "codex"):
        found = shutil.which(name)
        if found:
            values.append(found)

    result: list[Path] = []
    seen: set[str] = set()
    for value in values:
        path = Path(value)
        key = str(path).lower()
        if key in seen:
            continue
        seen.add(key)
        if path.is_file():
            result.append(path)
    return result


def _command(executable: Path, args: list[str]) -> list[str]:
    if executable.suffix.lower() in {".cmd", ".bat"}:
        command_line = subprocess.list2cmdline([str(executable), *args])
        return [os.environ.get("COMSPEC", "cmd.exe"), "/d", "/s", "/c", command_line]
    return [str(executable), *args]


def _mcp_config_args() -> list[str]:
    """Inject AI-DG MCP for this Codex turn without mutating global Codex config."""
    if not MCP_WRAPPER_PATH.is_file():
        return []
    command = str(MCP_WRAPPER_PATH).replace('\\', '/')
    cwd = str(ROOT_DIR).replace('\\', '/')
    python_path = f"{cwd}/OUTPUT/mcp_deps;{cwd}/mcp_server;{cwd}"
    return [
        "-c", f'mcp_servers.ai_dg.command="{command}"',
        "-c", f'mcp_servers.ai_dg.cwd="{cwd}"',
        "-c", 'mcp_servers.ai_dg.env.AI_DG_TOOL_PROFILE="minimal"',
        "-c", f'mcp_servers.ai_dg.env.PYTHONPATH="{python_path}"',
    ]


def _agent_message(event: Any) -> str:
    if not isinstance(event, dict):
        return ""
    item = event.get("item") if isinstance(event.get("item"), dict) else {}
    item_type = str(item.get("type") or "").lower()
    if event.get("type") not in {"item.completed", "item.updated"}:
        return ""
    if item_type not in {"agent_message", "message"}:
        return ""
    value = item.get("text")
    if isinstance(value, str):
        return value.strip()
    content = item.get("content")
    if isinstance(content, list):
        parts = [part.get("text", "") for part in content if isinstance(part, dict) and isinstance(part.get("text"), str)]
        return "".join(parts).strip()
    return ""


def _dispatch(request: dict[str, Any]) -> dict[str, Any]:
    action = str(request.get("action") or "agent_ask").strip().lower()
    if action != "agent_ask":
        return {"status": "error", "error": "UNKNOWN_CODEX_ACTION"}
    if not bool(request.get("allow_network", False)):
        return {"status": "blocked", "error": NETWORK_GATE_ERROR, "request_count": 0}

    prompt = str(request.get("prompt") or "").strip()[:4000]
    if not prompt:
        return {"status": "error", "error": "PROMPT_REQUIRED"}
    executable = next(iter(_candidate_paths()), None)
    if executable is None:
        return {"status": "error", "error": "CODEX_CLI_NOT_FOUND"}
    mcp_config = _mcp_config_args()
    if not mcp_config:
        return {"status": "error", "error": "CODEX_MCP_NOT_CONFIGURED"}

    args = [
        "exec",
        "--ephemeral",
        "--sandbox",
        "read-only",
        "--skip-git-repo-check",
        "--json",
        "--color",
        "never",
        "-C",
        str(ROOT_DIR),
        *mcp_config,
        "-",
    ]
    configured_model = os.environ.get("CODEX_MODEL", "").strip()
    if configured_model:
        args[1:1] = ["--model", configured_model[:200]]

    try:
        completed = subprocess.run(
            _command(executable, args),
            input=prompt,
            text=True,
            capture_output=True,
            timeout=60,
            cwd=str(ROOT_DIR),
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {"status": "error", "error": "CODEX_CLI_TIMEOUT", "runtime": executable.name}
    except OSError as exc:
        return {"status": "error", "error": "CODEX_CLI_START_FAILED", "detail": exc.__class__.__name__}

    answer = ""
    thread_id = None
    for line in completed.stdout.splitlines():
        try:
            event = json.loads(line.strip())
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict) and event.get("type") == "thread.started":
            value = event.get("thread_id")
            if isinstance(value, str):
                thread_id = value[:120]
        candidate = _agent_message(event)
        if candidate:
            answer = candidate

    if answer:
        return {
            "status": "ok",
            "provider": "Codex",
            "backend": "codex_cli",
            "mcp_server": "ai-dg",
            "mcp_profile": "minimal",
            "model": configured_model or None,
            "answer": answer[:8000],
            "implementation_state": "REAL",
            "thread_id": thread_id,
        }
    if completed.returncode != 0:
        return {
            "status": "error",
            "error": "CODEX_CLI_PROCESS_FAILED",
            "exit_code": completed.returncode,
            "runtime": executable.name,
            "stdout_bytes": len(completed.stdout.encode("utf-8", errors="replace")),
            "stderr_bytes": len(completed.stderr.encode("utf-8", errors="replace")),
        }
    return {
        "status": "error",
        "error": "CODEX_CLI_INVALID_RESPONSE",
        "runtime": executable.name,
        "stdout_bytes": len(completed.stdout.encode("utf-8", errors="replace")),
        "stderr_bytes": len(completed.stderr.encode("utf-8", errors="replace")),
    }


def main() -> int:
    try:
        request = json.loads(sys.stdin.read(64 * 1024) or "{}")
        if not isinstance(request, dict):
            raise ValueError("REQUEST_MUST_BE_OBJECT")
        result = _dispatch(request)
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        result = {"status": "error", "error": str(exc)}
    except Exception as exc:  # Never expose child output or environment details.
        result = {"status": "error", "error": "CODEX_CLI_HELPER_FAILED", "detail": exc.__class__.__name__}
    sys.stdout.write(json.dumps(result, ensure_ascii=False, separators=(",", ":")) + "\n")
    sys.stdout.flush()
    return 0 if result.get("status") != "error" else 1


if __name__ == "__main__":
    raise SystemExit(main())
