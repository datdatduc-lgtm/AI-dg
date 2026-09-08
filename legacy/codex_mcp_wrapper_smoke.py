# Archived migration reference; not imported by the production runtime.
#!/usr/bin/env python3
"""Verify the workspace Codex-to-AI-DG MCP wrapper without a model turn."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR / "mcp_server"))

import codex_cli  # noqa: E402


def main() -> int:
    requests = [
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "ai-dg-codex-wrapper-smoke", "version": "1"},
            },
        },
        {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
    ]
    env = os.environ.copy()
    env["AI_DG_TOOL_PROFILE"] = "minimal"
    command = codex_cli._command(codex_cli.MCP_WRAPPER_PATH, [])
    try:
        completed = subprocess.run(
            command,
            input="\n".join(json.dumps(item, ensure_ascii=False) for item in requests) + "\n",
            text=True,
            capture_output=True,
            timeout=20,
            cwd=str(ROOT_DIR),
            env=env,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        report = {"status": "FAIL", "error": exc.__class__.__name__}
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 1

    responses = []
    for line in completed.stdout.splitlines():
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            responses.append(value)
    listing = next((item for item in responses if item.get("id") == 2), {})
    tools = listing.get("result", {}).get("tools", [])
    names = {item.get("name") for item in tools if isinstance(item, dict)}
    write_names = {name for name in names if isinstance(name, str) and any(token in name for token in ("create", "transform", "apply_material", "set_tag"))}
    ok = (
        completed.returncode == 0
        and any(item.get("id") == 1 and "result" in item for item in responses)
        and isinstance(tools, list)
        and "sketchup_health" in names
        and "sketchup_get_selection" in names
        and not write_names
    )
    report = {
        "status": "PASS" if ok else "FAIL",
        "tool_count": len(tools) if isinstance(tools, list) else 0,
        "has_sketchup_health": "sketchup_health" in names,
        "has_selection": "sketchup_get_selection" in names,
        "has_write_tool": bool(write_names),
        "network": "NOT_USED",
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
