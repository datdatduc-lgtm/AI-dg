#!/usr/bin/env python3
"""Non-destructive workflow-profile and SKP-analyzer acceptance probe."""

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
    return json.loads(content[0].text) if content else {}


async def main() -> int:
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{ROOT_DIR / 'OUTPUT' / 'mcp_deps'};{ROOT_DIR / 'mcp_server'};{ROOT_DIR}"
    env["AI_DG_TOOL_PROFILE"] = "full"
    params = StdioServerParameters(
        command=sys.executable,
        args=[str(ROOT_DIR / "mcp_server" / "launcher.py")],
        env=env,
    )

    profile_path = ROOT_DIR / "USER_PROFILE" / "sketchup_workflow_profile.json"
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            profile = parse(
                await session.call_tool(
                    "ai_dg_build_workflow_profile",
                    {"output_path": str(profile_path)},
                )
            )
            analyzer = parse(
                await session.call_tool(
                    "aidg_analyze_skp_readonly",
                    {"path": str(ROOT_DIR / "test_empty.skp")},
                )
            )

    saved = json.loads(profile_path.read_text(encoding="utf-8")) if profile_path.is_file() else {}
    ok = (
        profile.get("status") == "ok"
        and profile.get("privacy", {}).get("paths_persisted") is False
        and profile.get("privacy", {}).get("raw_geometry_persisted") is False
        and saved.get("privacy", {}).get("paths_persisted") is False
        and analyzer.get("status") == "partial"
        and analyzer.get("adapter_status") == "adapter_unavailable"
        and analyzer.get("geometry") is None
    )
    print(
        json.dumps(
            {
                "status": "PASS" if ok else "FAIL",
                "profile": {
                    "sample_count": profile.get("sample_count"),
                    "confidence": profile.get("confidence"),
                    "privacy": profile.get("privacy"),
                },
                "skp_analyzer": {
                    "status": analyzer.get("status"),
                    "adapter_status": analyzer.get("adapter_status"),
                    "geometry": analyzer.get("geometry"),
                },
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
