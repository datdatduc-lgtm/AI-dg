#!/usr/bin/env python3
"""Create a standard AI-dg project workspace outside the installed skill.

Usage:
  python init_project.py D:/CongTrinh/Villa-A --name "Villa A"
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

DIRS = [
    "INPUT/PDF",
    "INPUT/CAD",
    "INPUT/SKP",
    "INPUT/OTHER",
    "WORK/manifests",
    "WORK/extracted",
    "WORK/geometry",
    "WORK/reconciliation",
    "WORK/logs",
    "OUTPUT/RUBY",
    "OUTPUT/TAKEOFF",
    "OUTPUT/EXCEL",
    "OUTPUT/REPORTS",
    "OUTPUT/MODEL",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Initialize an AI-dg project workspace")
    parser.add_argument("project_root", type=Path)
    parser.add_argument("--name", default=None, help="Human-readable project name")
    parser.add_argument("--force-metadata", action="store_true", help="Replace existing project.ai-dg.json")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = args.project_root.expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)

    for rel in DIRS:
        (root / rel).mkdir(parents=True, exist_ok=True)

    metadata_path = root / "project.ai-dg.json"
    if metadata_path.exists() and not args.force_metadata:
        print(f"Workspace exists: {root}")
        print(f"Metadata preserved: {metadata_path}")
        return 0

    payload = {
        "schema_version": "0.1",
        "project_name": args.name or root.name,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "input_root": "INPUT",
        "work_root": "WORK",
        "output_root": "OUTPUT",
        "rules": {
            "input_read_only": True,
            "reconcile_pdf_cad_skp": True,
            "geometry_first": True,
            "unknowns_must_remain_explicit": True,
        },
    }
    metadata_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"AI-dg workspace created: {root}")
    print("Put source files under INPUT/, then run scan_input.py against the project root.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
