#!/usr/bin/env python3
"""Verify capability-based MCP schema exposure without touching SketchUp."""

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


def parse(result: object) -> dict:
    content = getattr(result, "content", [])
    if not content:
        return {}
    return json.loads(content[0].text)


async def inspect_profile(profile: str) -> tuple[set[str], dict]:
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(
        str(path) for path in (ROOT_DIR / "OUTPUT" / "mcp_deps", ROOT_DIR, ROOT_DIR / "mcp_server")
    )
    env["AI_DG_TOOL_PROFILE"] = profile
    params = StdioServerParameters(
        command=sys.executable,
        args=[str(ROOT_DIR / "mcp_server" / "launcher.py")],
        env=env,
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            names = {tool.name for tool in (await session.list_tools()).tools}
            metadata = parse(await session.call_tool("ai_dg_list_tools", {}))
            return names, metadata


async def main() -> int:
    snapshots: dict[str, dict] = {}
    for profile in ("minimal", "drawing", "build", "full"):
        names, metadata = await inspect_profile(profile)
        exposure = metadata.get("exposure", {})
        snapshots[profile] = {
            "tool_count": len(names),
            "reported_exposed": exposure.get("exposed_tool_count"),
            "reported_all": exposure.get("all_tool_count"),
            "schema_reduction_percent": exposure.get("schema_reduction_percent"),
            "has_build": "sketchup_create_cabinet" in names,
            "has_drawing": "ai_dg_source_ingest" in names,
            "has_legacy_agent_tools": bool(names.intersection({
                "ai_dg_agent_ask",
                "ai_dg_model_status",
                "ai_dg_model_select",
                "ai_dg_9router_sync_models",
                "ai_dg_provider_status",
                "ai_dg_provider_configure",
                "ai_dg_provider_disconnect",
                "ai_dg_9router_test",
            })),
            "has_eval_ruby": "sketchup_eval_ruby" in names,
        }

    minimal = snapshots["minimal"]
    drawing = snapshots["drawing"]
    build = snapshots["build"]
    full = snapshots["full"]
    ok = (
        minimal["tool_count"] < full["tool_count"]
        and minimal["reported_exposed"] == minimal["tool_count"]
        and minimal["reported_all"] == full["tool_count"]
        and not minimal["has_build"]
        and not minimal["has_drawing"]
        and drawing["has_drawing"]
        and not drawing["has_build"]
        and build["has_drawing"]
        and build["has_build"]
        and not build["has_legacy_agent_tools"]
        and full["tool_count"] == full["reported_all"]
        and not full["has_eval_ruby"]
    )
    print(json.dumps({"status": "PASS" if ok else "FAIL", "profiles": snapshots}, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
