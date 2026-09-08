"""Read-only SketchUp file analyzer contract.

The SKP binary format is proprietary.  This adapter intentionally reports
file metadata and `adapter_unavailable` instead of pretending to parse model
geometry outside SketchUp.  Live model structure is obtained through the
official Ruby bridge read tools.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any


def analyze_file(path_value: str) -> dict[str, Any]:
    path = Path(path_value)
    if not path.is_file():
        return {"status": "error", "error": "FILE_NOT_FOUND", "path": str(path)}
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return {
        "status": "partial",
        "path": str(path),
        "file_name": path.name,
        "extension": path.suffix.lower(),
        "size_bytes": path.stat().st_size,
        "sha256": digest.hexdigest(),
        "adapter_status": "adapter_unavailable",
        "geometry": None,
        "notes": "Use the live SketchUp Ruby API read tools for model metadata; this operation never opens, saves or modifies the file.",
    }
