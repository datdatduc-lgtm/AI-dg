#!/usr/bin/env python3
"""Safe Cline-compatible stdio acceptance probe.

This mirrors the command shape stored in Cline's ``cline_mcp_settings.json``:
the Cline-side MCP client starts ``server.py`` over stdio, performs the MCP
initialize/list-tools handshake, and then reads live SketchUp health and
selection metadata.  It never calls a provider, enables write mode, or
changes the model.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR / "OUTPUT" / "mcp_deps"))

from mcp import ClientSession, StdioServerParameters  # noqa: E402
from mcp.client.stdio import stdio_client  # noqa: E402


CLINE_PYTHON = Path(
    os.environ.get(
        "AI_DG_CLINE_PYTHON",
        r"C:\Users\Admin\AppData\Local\Programs\Python\Python312\python.exe",
    )
)


def parse(result: object) -> dict:
    content = getattr(result, "content", [])
    if not content:
        return {}
    return json.loads(content[0].text)


async def main() -> int:
    if not CLINE_PYTHON.exists():
        print(json.dumps({"status": "BLOCKED", "error": "CLINE_PYTHON_NOT_FOUND", "command": str(CLINE_PYTHON)}))
        return 2

    env = os.environ.copy()
    # Match the Cline config's local workspace path; no credential variables
    # are added and the server does not contact the provider in this probe.
    env["PYTHONPATH"] = os.pathsep.join(
        str(path) for path in (ROOT_DIR / "OUTPUT" / "mcp_deps", ROOT_DIR, ROOT_DIR / "mcp_server")
    )
    env["AI_DG_TOOL_PROFILE"] = "minimal"
    params = StdioServerParameters(
        command=str(CLINE_PYTHON),
        args=[str(ROOT_DIR / "mcp_server" / "server.py")],
        env=env,
    )

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = {tool.name for tool in (await session.list_tools()).tools}
            required = {
                "sketchup_health",
                "sketchup_get_selection",
                "sketchup_get_model_summary",
            }
            exposure = parse(await session.call_tool("ai_dg_list_tools", {}))
            exposure_state = exposure.get("exposure", {})
            minimal_exposure_ok = (
                exposure_state.get("profile") == "minimal"
                and exposure_state.get("exposed_tool_count") == len(tools)
                and exposure_state.get("all_tool_count", 0) > len(tools)
                and "sketchup_create_cabinet" not in tools
                and "ai_dg_provider_configure" not in tools
            )
            health = parse(await session.call_tool("sketchup_health", {}))
            selection = parse(await session.call_tool("sketchup_get_selection", {}))
            items = selection.get("data", {}).get("items")
            item = (items or [None])[0]
            ok = (
                required <= tools
                and minimal_exposure_ok
                and health.get("status") == "ok"
                and health.get("data", {}).get("bridge_status") == "ONLINE"
                and selection.get("status") == "ok"
                and isinstance(selection.get("data", {}).get("count"), int)
                and isinstance(items, list)
            )
            print(
                json.dumps(
                    {
                        "status": "PASS" if ok else "FAIL",
                        "client_contract": "CLINE_STDIO",
                        "command": str(CLINE_PYTHON),
                        "server": str(ROOT_DIR / "mcp_server" / "server.py"),
                        "tool_count": len(tools),
                        "all_tool_count": exposure_state.get("all_tool_count"),
                        "profile": exposure_state.get("profile"),
                        "schema_reduction_percent": exposure_state.get("schema_reduction_percent"),
                        "health": {
                            "bridge": health.get("data", {}).get("bridge_status"),
                            "sketchup_version": health.get("data", {}).get("sketchup_version"),
                        },
                        "selection": {
                            "name": item.get("name") if item else None,
                            "persistent_id": item.get("persistent_id") if item else None,
                            "count": selection.get("data", {}).get("count"),
                        },
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
