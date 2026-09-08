#!/usr/bin/env python3
"""Local contract test for the Codex CLI adapter; never starts Codex or uses network."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from subprocess import CompletedProcess


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR / "mcp_server"))

import codex_cli  # noqa: E402


def main() -> int:
    original_candidates = codex_cli._candidate_paths
    original_run = codex_cli.subprocess.run
    original_mcp_wrapper = codex_cli.MCP_WRAPPER_PATH
    observed: dict[str, object] = {}
    try:
        codex_cli._candidate_paths = lambda: [Path("C:/fake/codex.exe")]

        def fake_run(command, **kwargs):
            observed["command"] = command
            observed.update(kwargs)
            stdout = "\n".join([
                json.dumps({"type": "thread.started", "thread_id": "thread-contract"}),
                json.dumps({"type": "item.completed", "item": {"type": "reasoning", "text": "hidden"}}),
                json.dumps({"type": "item.completed", "item": {"type": "agent_message", "text": "Đã đọc model an toàn."}}),
            ])
            return CompletedProcess(command, 0, stdout=stdout, stderr="")

        codex_cli.subprocess.run = fake_run
        result = codex_cli._dispatch({"action": "agent_ask", "allow_network": True, "prompt": "Đọc model."})
        command = observed.get("command") if isinstance(observed.get("command"), list) else []
        command_text = " ".join(str(value) for value in command)
        ok = (
            result.get("status") == "ok"
            and result.get("provider") == "Codex"
            and result.get("implementation_state") == "REAL"
            and result.get("mcp_server") == "ai-dg"
            and result.get("answer") == "Đã đọc model an toàn."
            and "--ephemeral" in command
            and "--sandbox" in command
            and "read-only" in command
            and "--json" in command
            and "-c" in command
            and any("mcp_servers.ai_dg.command=" in str(value) for value in command)
            and any(str(codex_cli.MCP_WRAPPER_PATH).replace('\\', '/') in str(value) for value in command)
            and observed.get("input") == "Đọc model."
            and observed.get("timeout") == 60
            and "hidden" not in str(result)
        )
        previous_command = observed.get("command")
        codex_cli.MCP_WRAPPER_PATH = Path("C:/missing/ai_dg_codex_mcp.cmd")
        missing_mcp = codex_cli._dispatch({"action": "agent_ask", "allow_network": True, "prompt": "Không được chạy."})
        mcp_guard_ok = missing_mcp.get("error") == "CODEX_MCP_NOT_CONFIGURED" and observed.get("command") == previous_command
        report = {
            "status": "PASS" if ok and mcp_guard_ok else "FAIL",
            "provider": result.get("provider"),
            "answer_parsed": result.get("answer") == "Đã đọc model an toàn.",
            "sandbox_flags": all(flag in command_text for flag in ("--ephemeral", "--sandbox", "read-only", "--json")),
            "ai_dg_mcp_injected": any("mcp_servers.ai_dg.command=" in str(value) for value in command),
            "missing_mcp_guard": mcp_guard_ok,
            "timeout_seconds": observed.get("timeout"),
            "network": "NOT_USED",
        }
    finally:
        codex_cli._candidate_paths = original_candidates
        codex_cli.subprocess.run = original_run
        codex_cli.MCP_WRAPPER_PATH = original_mcp_wrapper

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
