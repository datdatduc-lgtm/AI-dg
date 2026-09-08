"""Small local JSONL logger for the AI-DG runtime.

Only sanitized event metadata is written. Callers must never pass
credentials, full prompts, or model geometry into this helper.
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


LOG_ROOT = Path("E:/AI-DG/OUTPUT/logs")
_LOCK = threading.Lock()


def ensure_log_files() -> None:
    LOG_ROOT.mkdir(parents=True, exist_ok=True)
    for name in ("bridge", "mcp", "agent", "tools", "runtime", "errors"):
        path = LOG_ROOT / f"{name}.log"
        if not path.exists():
            path.touch()


def log_event(name: str, event: str, **fields: Any) -> None:
    if name not in {"bridge", "mcp", "agent", "tools", "runtime", "errors"}:
        raise ValueError("INVALID_LOG_NAME")
    ensure_log_files()
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": event,
        **{key: value for key, value in fields.items() if key not in {"secret", "api_key", "token", "prompt", "content"}},
    }
    with _LOCK:
        with (LOG_ROOT / f"{name}.log").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n")
