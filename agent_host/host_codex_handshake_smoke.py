#!/usr/bin/env python3
"""Exercise JsonRpcProcess + real Codex without the outer JSONL host loop."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from agent_host.host import AgentHost


async def main() -> int:
    root = ROOT_DIR
    host = AgentHost(root, auto_install_cline=False)
    process = None
    try:
        process = await host._ensure_codex(root)
        initialize = await process.request(
            "initialize",
            {"clientInfo": {"name": "ai_dg_host_probe", "title": "AI-DG Host Probe", "version": "0.1.0"}},
            timeout=20.0,
        )
        await process.notify("initialized")
        try:
            mcp_status = await process.request("mcpServerStatus/list", {}, timeout=20.0)
        except Exception as exc:
            mcp_status = {"error": type(exc).__name__}
        print(json.dumps({
            "status": "PASS",
            "pid": process.pid,
            "initialize": initialize,
            "mcp_status": mcp_status,
            "stderr_tail": process.stderr_tail,
        }, ensure_ascii=False, indent=2))
        return 0
    finally:
        if process is not None:
            await process.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
