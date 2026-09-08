# Archived migration reference; not imported by the production runtime.
"""E: local session persistence with no provider-secret fields."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PRIMARY_SESSION_ROOT = Path("E:/AI-DG/.codex/sessions")
FALLBACK_SESSION_ROOT = Path("E:/AI-DG/OUTPUT/sessions")
SESSION_ROOT = PRIMARY_SESSION_ROOT
SESSION_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,80}$")


def _path(session_id: str, root: Path = SESSION_ROOT) -> Path:
    if not SESSION_ID_RE.match(session_id):
        raise ValueError("INVALID_SESSION_ID")
    return root / f"{session_id}.json"


def save_session(session_id: str, messages: list[dict[str, Any]]) -> dict[str, Any]:
    payload = {
        "schema_version": "0.1",
        "session_id": session_id,
        "updated_utc": datetime.now(timezone.utc).isoformat(),
        "messages": messages[-200:],
    }
    serialized = json.dumps(payload, ensure_ascii=False, indent=2)
    errors = []
    for root in (PRIMARY_SESSION_ROOT, FALLBACK_SESSION_ROOT):
        target = _path(session_id, root)
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(serialized, encoding="utf-8")
            return {
                "status": "ok",
                "session_id": session_id,
                "path": str(target),
                "message_count": len(payload["messages"]),
            }
        except OSError as exc:
            errors.append(f"{root}: {exc}")
    return {
        "status": "error",
        "error": "SESSION_WRITE_FAILED",
        "session_id": session_id,
        "details": errors,
    }


def load_session(session_id: str) -> dict[str, Any]:
    for root in (FALLBACK_SESSION_ROOT, PRIMARY_SESSION_ROOT):
        target = _path(session_id, root)
        if not target.is_file():
            continue
        return json.loads(target.read_text(encoding="utf-8")) | {"found": True}
    return {"status": "ok", "session_id": session_id, "messages": [], "found": False}
