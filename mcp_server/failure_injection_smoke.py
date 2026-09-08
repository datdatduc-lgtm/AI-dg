#!/usr/bin/env python3
"""Safe MCP-side failure smoke test.

This test never stops SketchUp and never contacts 9Router.  It points one
in-process client call at an ephemeral unused localhost port to verify the
disconnect/error contract, then verifies that provider model sync remains
blocked without the explicit network opt-in.
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

        provider = json.loads(server.ai_dg_9router_sync_models())
        provider_ok = provider.get("status") == "blocked" and provider.get("request_count") == 0
        report["tests"].append({
            "name": "provider_sync_network_guard",
            "status": "PASS" if provider_ok else "FAIL",
            "error": provider.get("error"),
            "request_count": provider.get("request_count"),
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
