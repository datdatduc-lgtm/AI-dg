#!/usr/bin/env python3
"""One-shot local drawing-pipeline helper for external clients.

The helper is intentionally separate from the MCP stdio server. It never
enables provider traffic and never calls the SketchUp API.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

RUN_ID_RE = re.compile(r"[A-Za-z0-9._-]{1,120}\Z")


def _project_root(value: str) -> Path:
    root = Path(value or ROOT_DIR).expanduser().resolve()
    if root.drive.upper() == "D:":
        raise PermissionError("PROTECTED_DRIVE_WRITE_DENIED")
    try:
        inside_workspace = root == ROOT_DIR or root.is_relative_to(ROOT_DIR)
    except AttributeError:  # pragma: no cover - Python 3.8 fallback
        inside_workspace = str(root).lower().startswith(str(ROOT_DIR).lower() + "\\")
    if not inside_workspace:
        raise PermissionError("PROJECT_OUTSIDE_WORKSPACE_DENIED")
    if not (root / "INPUT").is_dir():
        raise ValueError("INPUT_DIRECTORY_NOT_FOUND")
    return root


def _run(request: dict[str, Any]) -> dict[str, Any]:
    root = _project_root(str(request.get("project_path") or ROOT_DIR))
    run_id = str(request.get("run_id") or "")
    if run_id and not RUN_ID_RE.fullmatch(run_id):
        raise ValueError("INVALID_RUN_ID")
    review_status = str(request.get("review_status") or "OPEN").upper()
    if review_status not in {"OPEN", "APPROVED"}:
        raise ValueError("INVALID_REVIEW_STATUS")

    from pipeline.stages.runner import run_pipeline

    result = run_pipeline(
        root,
        run_id=run_id,
        render_pdf=bool(request.get("render_pdf", True)),
        review_status=review_status,
    )
    return {
        "status": "ok",
        "action": "pipeline_run",
        "data": result.to_dict(),
    }


def main() -> int:
    try:
        request = json.loads(sys.stdin.read() or "{}")
        if not isinstance(request, dict):
            raise ValueError("REQUEST_MUST_BE_OBJECT")
        action = str(request.get("action") or "run")
        if action != "run":
            raise ValueError("UNKNOWN_PIPELINE_ACTION")
        response = _run(request)
        print(json.dumps(response, ensure_ascii=False))
        return 0
    except (OSError, PermissionError, ValueError, RuntimeError, ImportError) as exc:
        print(json.dumps({"status": "error", "action": "pipeline_run", "error": str(exc)}, ensure_ascii=False))
        return 0
    except Exception:
        print(json.dumps({"status": "error", "action": "pipeline_run", "error": "PIPELINE_HELPER_FAILED"}, ensure_ascii=False))
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
