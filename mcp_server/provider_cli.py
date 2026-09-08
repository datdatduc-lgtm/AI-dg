#!/usr/bin/env python3
"""One-shot local provider manager used by the SketchUp Control Center.

The helper communicates over stdin/stdout only and binds no socket.  It is
intended for local UI actions that are not MCP calls (configure/status/chat).
Network access is enabled only when the request explicitly carries
``allow_network=true``; the flag is applied to this one child process only.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
for _path in (ROOT_DIR / "OUTPUT" / "mcp_deps", ROOT_DIR / "OUTPUT" / "pipeline_deps", ROOT_DIR, ROOT_DIR / "mcp_server"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))


def _request() -> dict[str, Any]:
    raw = sys.stdin.read(64 * 1024)
    value = json.loads(raw or "{}")
    if not isinstance(value, dict):
        raise ValueError("REQUEST_MUST_BE_OBJECT")
    return value


def _dispatch(request: dict[str, Any]) -> dict[str, Any]:
    if sys.version_info < (3, 10):
        return {
            "status": "error",
            "error": "PROVIDER_RUNTIME_UNSUPPORTED",
            "python": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "required": ">=3.10",
        }
    action = str(request.get("action") or "status").strip().lower()
    allow_network = bool(request.get("allow_network", False))
    if action in {"test", "sync", "agent_ask", "codex_ask"}:
        if not allow_network:
            return {
                "status": "blocked",
                "error": "CODEX_NETWORK_TEST_REQUIRES_EXPLICIT_ENABLE" if action == "codex_ask" else "PROVIDER_NETWORK_TEST_REQUIRES_EXPLICIT_ENABLE",
                "request_count": 0,
            }
        if action != "codex_ask":
            os.environ["AI_DG_ALLOW_PROVIDER_TEST"] = "1"

    import provider

    if action == "status":
        return {"status": "ok", "provider": provider.status(), "model": provider.model_status()}
    if action == "configure":
        return provider.configure_provider(
            provider_name=str(request.get("provider_name") or ""),
            provider_type=str(request.get("provider_type") or "custom_compatible"),
            base_url=str(request.get("base_url") or ""),
            model_id=str(request.get("model_id") or ""),
            api_key=str(request.get("api_key") or ""),
            enabled=bool(request.get("enabled", True)),
        )
    if action in {"disconnect", "clear"}:
        return provider.disconnect_provider()
    if action == "test":
        model = str(request.get("model") or provider.model_status().get("configured_model") or "")
        return provider.test_chat(model=model, prompt=str(request.get("prompt") or "Trả lời duy nhất: OK"))
    if action == "sync":
        return provider.sync_models()
    if action == "agent_ask":
        os.environ["AI_DG_ENABLE_PROVIDER_AGENT"] = "1"
        import server

        return server._provider_agent_ask(str(request.get("prompt") or ""))
    if action == "codex_ask":
        import codex_cli

        return codex_cli._dispatch({
            "action": "agent_ask",
            "allow_network": True,
            "prompt": str(request.get("prompt") or ""),
        })
    return {"status": "error", "error": "UNKNOWN_PROVIDER_ACTION"}


def main() -> int:
    try:
        result = _dispatch(_request())
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        result = {"status": "error", "error": str(exc)}
    except Exception as exc:  # never expose a secret-bearing exception payload
        result = {"status": "error", "error": "PROVIDER_HELPER_FAILED", "detail": exc.__class__.__name__}
    sys.stdout.write(json.dumps(result, ensure_ascii=False, separators=(",", ":")) + "\n")
    sys.stdout.flush()
    return 0 if result.get("status") not in {"error"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
