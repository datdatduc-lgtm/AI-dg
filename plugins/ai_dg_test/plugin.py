"""Small read-only plugin used by the AI-DG plugin registry acceptance test."""

from __future__ import annotations

from datetime import datetime, timezone


def read_tool() -> dict[str, str]:
    return {
        "status": "ok",
        "plugin_id": "ai-dg-test",
        "message": "AI-DG test read tool is loaded",
        "checked_utc": datetime.now(timezone.utc).isoformat(),
    }
