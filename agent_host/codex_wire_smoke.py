#!/usr/bin/env python3
"""Diagnostic wire probe for the installed Codex App Server.

The process stays open while reading the initialize response. This isolates
transport behavior from Agent Host routing and does not start a turn or call a
model.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import threading
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT_DIR))

from agent_host.host import AgentHost


def resolve_codex() -> str:
    local_app = Path(os.environ.get("LOCALAPPDATA", ""))
    native = sorted((local_app / "OpenAI" / "Codex" / "bin").glob("*/codex.exe"), reverse=True)
    if native:
        return str(native[0])
    return shutil.which("codex") or "codex"


def main() -> int:
    command = AgentHost(Path(__file__).resolve().parents[1], auto_install_cline=False).codex_command(resolve_codex())
    process = subprocess.Popen(
        command,
        cwd=str(ROOT_DIR),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )
    assert process.stdin and process.stdout and process.stderr
    process.stdin.write(json.dumps({
        "id": "wire-1",
        "method": "initialize",
        "params": {"clientInfo": {"name": "ai_dg_wire_probe", "title": "AI-DG Wire Probe", "version": "0.1.0"}},
    }) + "\n")
    process.stdin.write(json.dumps({"method": "initialized", "params": {}}) + "\n")
    process.stdin.write(json.dumps({"id": "wire-2", "method": "mcpServerStatus/list", "params": {"limit": 50}}) + "\n")
    process.stdin.flush()
    stdout_lines: list[str] = []
    stderr_lines: list[str] = []

    def read_stdout() -> None:
        for line in process.stdout:
            stdout_lines.append(line[:4000])
            if len(stdout_lines) >= 20:
                break

    def read_stderr() -> None:
        for line in process.stderr:
            stderr_lines.append(line[:1000])
            del stderr_lines[:-20]

    stdout_thread = threading.Thread(target=read_stdout, daemon=True)
    stderr_thread = threading.Thread(target=read_stderr, daemon=True)
    stdout_thread.start()
    stderr_thread.start()
    stdout_thread.join(15.0)
    result = {
        "command": command,
        "response": stdout_lines[0].strip() if stdout_lines else None,
        "alive_after_15s": process.poll() is None,
        "stderr_tail": "".join(stderr_lines)[-4000:],
    }
    if process.poll() is None:
        process.terminate()
    try:
        process.wait(timeout=5.0)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5.0)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["response"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
