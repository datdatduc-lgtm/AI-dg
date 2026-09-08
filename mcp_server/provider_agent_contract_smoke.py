#!/usr/bin/env python3
"""Exercise the bounded provider-agent router without contacting 9Router."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR / "OUTPUT" / "mcp_deps"))
sys.path.insert(0, str(ROOT_DIR / "mcp_server"))

import server  # noqa: E402


def main() -> int:
    original_flags = (server.ENABLE_PROVIDER_AGENT, server.ALLOW_PROVIDER_TEST)
    original_model_status = server.provider_model_status
    original_completion = server.provider_chat_completion
    original_selection = server.sketchup_get_selection
    calls: list[dict] = []
    try:
        server.ENABLE_PROVIDER_AGENT = True
        server.ALLOW_PROVIDER_TEST = True
        server.provider_model_status = lambda: {"configured_model": "9router/fake-agent-model"}

        def fake_completion(**kwargs):
            calls.append(kwargs)
            if len(calls) == 1:
                return {
                    "status": "ok",
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [{
                            "id": "call-1",
                            "type": "function",
                            "function": {"name": "sketchup_get_selection", "arguments": "{}"},
                        }],
                    },
                    "usage": {"total_tokens": 5},
                    "request_count": 1,
                }
            return {
                "status": "ok",
                "message": {"role": "assistant", "content": "Đã đọc selection an toàn."},
                "usage": {"total_tokens": 4},
                "request_count": 1,
            }

        server.provider_chat_completion = fake_completion
        server.sketchup_get_selection = lambda: json.dumps({
            "status": "ok",
            "data": {"items": [{"name": "AI_DG_MCP_TEST_BOX", "persistent_id": 469337}]},
        }, ensure_ascii=False)
        result = json.loads(server.ai_dg_agent_ask("Đọc đối tượng đang chọn."))
        ok = (
            result.get("status") == "ok"
            and result.get("agent") == "provider-bounded"
            and result.get("tool") == "sketchup_get_selection"
            and result.get("request_count") == 2
            and len(result.get("steps", [])) == 2
            and len(calls) == 2
            and calls[0].get("tools")
        )
        report = {
            "status": "PASS" if ok else "FAIL",
            "agent": result.get("agent"),
            "tool": result.get("tool"),
            "request_count": result.get("request_count"),
            "steps": result.get("steps"),
            "provider_calls": len(calls),
            "model": result.get("model"),
        }
    finally:
        server.ENABLE_PROVIDER_AGENT, server.ALLOW_PROVIDER_TEST = original_flags
        server.provider_model_status = original_model_status
        server.provider_chat_completion = original_completion
        server.sketchup_get_selection = original_selection

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
