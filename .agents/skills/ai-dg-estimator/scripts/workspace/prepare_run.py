#!/usr/bin/env python3
"""Prepare a fresh AI-dg project run without touching INPUT.

This is the mandatory first command for a new analysis/deployment run.
It removes generated state from WORK/ and OUTPUT/, recreates the canonical
folder tree, records a fresh run marker, then scans INPUT into a new manifest.

Safety rules:
- project.ai-dg.json must exist at project root;
- INPUT is never deleted or modified;
- project.ai-dg.json is preserved;
- only project-root/WORK and project-root/OUTPUT are reset;
- symlink/junction WORK or OUTPUT roots are refused.

Usage:
  python prepare_run.py D:/AI-dg/Villa-A
  python prepare_run.py D:/AI-dg/Villa-A --dry-run
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

WORK_DIRS = [
    "manifests",
    "extracted",
    "geometry",
    "reconciliation",
    "logs",
]

OUTPUT_DIRS = [
    "RUBY",
    "IMAGES",
    "TAKEOFF",
    "EXCEL",
    "REPORTS",
    "MODEL",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Reset AI-dg generated WORK/OUTPUT and rescan INPUT for a fresh run"
    )
    parser.add_argument("project_root", type=Path)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and report what would be reset without deleting anything",
    )
    return parser.parse_args()


def is_link_or_junction(path: Path) -> bool:
    if path.is_symlink():
        return True
    is_junction = getattr(path, "is_junction", None)
    return bool(is_junction and is_junction())


def validate_project(root: Path) -> dict:
    marker = root / "project.ai-dg.json"
    input_root = root / "INPUT"

    if not root.is_dir():
        raise SystemExit(f"Project root not found: {root}")
    if not marker.is_file():
        raise SystemExit(
            f"Refusing cleanup: AI-dg project marker not found: {marker}"
        )
    if not input_root.is_dir():
        raise SystemExit(f"INPUT directory not found: {input_root}")

    try:
        metadata = json.loads(marker.read_text(encoding="utf-8"))
    except Exception as exc:
        raise SystemExit(f"Invalid project.ai-dg.json: {exc}") from exc

    for name in ("WORK", "OUTPUT"):
        path = root / name
        if path.exists() and is_link_or_junction(path):
            raise SystemExit(
                f"Refusing cleanup: {name} is a symlink/junction: {path}"
            )
        if path.parent != root:
            raise SystemExit(f"Unsafe generated path: {path}")

    return metadata


def count_input_files(root: Path) -> int:
    return sum(1 for path in (root / "INPUT").rglob("*") if path.is_file())


def reset_tree(root: Path) -> None:
    work_root = root / "WORK"
    output_root = root / "OUTPUT"

    if work_root.exists():
        shutil.rmtree(work_root)
    if output_root.exists():
        shutil.rmtree(output_root)

    for rel in WORK_DIRS:
        (work_root / rel).mkdir(parents=True, exist_ok=True)
    for rel in OUTPUT_DIRS:
        (output_root / rel).mkdir(parents=True, exist_ok=True)


def write_run_start(root: Path, input_count: int) -> Path:
    run_id = str(uuid.uuid4())
    payload = {
        "schema_version": "0.1",
        "run_id": run_id,
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "project_root": str(root),
        "input_file_count_before_scan": input_count,
        "fresh_run_policy": {
            "input_preserved": True,
            "project_metadata_preserved": True,
            "work_previous_deleted": True,
            "output_previous_deleted": True,
            "cross_run_output_merge_forbidden": True,
        },
    }
    path = root / "WORK" / "logs" / "run-start.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def rescan_input(root: Path) -> None:
    scanner = Path(__file__).with_name("scan_input.py")
    if not scanner.is_file():
        raise SystemExit(f"Input scanner missing: {scanner}")

    completed = subprocess.run(
        [sys.executable, str(scanner), str(root)],
        check=False,
    )
    if completed.returncode != 0:
        raise SystemExit(
            f"Fresh workspace created, but INPUT scan failed with code {completed.returncode}"
        )


def main() -> int:
    args = parse_args()
    root = args.project_root.expanduser().resolve()
    validate_project(root)
    input_count = count_input_files(root)

    print(f"AI-dg project: {root}")
    print(f"INPUT preserved: {root / 'INPUT'} ({input_count} files)")
    print(f"Generated state to reset: {root / 'WORK'}")
    print(f"Deliverables to reset: {root / 'OUTPUT'}")

    if args.dry_run:
        print("DRY RUN: nothing deleted.")
        return 0

    reset_tree(root)
    run_start = write_run_start(root, input_count)
    rescan_input(root)

    print("Fresh-run reset complete.")
    print(f"Run marker: {run_start}")
    print(f"Fresh input manifest: {root / 'WORK' / 'manifests' / 'input-manifest.json'}")
    print("Previous WORK/OUTPUT data must not be merged into this run.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
