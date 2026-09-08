#!/usr/bin/env python3
"""Safe MCP-side failure smoke test.

This test never stops SketchUp or contacts a model service. It points one
in-process client call at an ephemeral unused localhost port to verify the
disconnect/error contract, then verifies that legacy agent tools are absent.
"""

from __future__ import annotations

import json
import socket
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR / "OUTPUT" / "mcp_deps"))
sys.path.insert(0, str(ROOT_DIR / "mcp_server"))

import server  # noqa: E402


def main() -> int:
    original_host = server.SKETCHUP_HOST
    original_port = server.SKETCHUP_PORT
    report = {"status": "PASS", "tests": []}
    try:
        probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        probe.bind(("127.0.0.1", 0))
        unused_port = probe.getsockname()[1]
        probe.close()

        server.SKETCHUP_HOST = "127.0.0.1"
        server.SKETCHUP_PORT = unused_port
        failed = server.send_sketchup_cmd("ping", timeout=0.25)
        failure_ok = failed.get("error_code") in {"BRIDGE_NOT_READY", "BRIDGE_DISCONNECTED", "READ_TIMEOUT"} and failed.get("status") == "error"
        report["tests"].append({
            "name": "mcp_disconnect_error_mapping",
            "status": "PASS" if failure_ok else "FAIL",
            "error_code": failed.get("error_code"),
            "error": failed.get("error"),
        })

        runtime = json.loads(server.ai_dg_runtime_status())
        runtime_ok = runtime.get("bridge") == "DISCONNECTED" and runtime.get("mcp") == "DISCONNECTED"
        report["tests"].append({
            "name": "runtime_disconnected_status",
            "status": "PASS" if runtime_ok else "FAIL",
            "bridge": runtime.get("bridge"),
            "mcp": runtime.get("mcp"),
        })

        legacy_ids = {
            "ai_dg_agent_ask",
            "ai_dg_model_status",
            "ai_dg_model_select",
            "ai_dg_9router_sync_models",
            "ai_dg_provider_status",
            "ai_dg_provider_configure",
            "ai_dg_provider_disconnect",
            "ai_dg_9router_test",
        }
        legacy_ok = not legacy_ids.intersection({row["id"] for row in server.TOOL_REGISTRY})
        report["tests"].append({
            "name": "legacy_agent_tools_removed",
            "status": "PASS" if legacy_ok else "FAIL",
            "legacy_tools": sorted(legacy_ids.intersection({row["id"] for row in server.TOOL_REGISTRY})),
        })
    finally:
        server.SKETCHUP_HOST = original_host
        server.SKETCHUP_PORT = original_port

    if any(test["status"] == "FAIL" for test in report["tests"]):
        report["status"] = "FAIL"
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
