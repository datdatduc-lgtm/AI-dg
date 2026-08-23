#!/usr/bin/env python3
"""Create OUTPUT/output-manifest.json for an AI-dg project run."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

TYPE_BY_FOLDER = {
    "RUBY": "RUBY",
    "TAKEOFF": "TAKEOFF",
    "EXCEL": "EXCEL",
    "REPORTS": "REPORT",
    "MODEL": "MODEL",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Finalize AI-dg output manifest")
    parser.add_argument("project_root", type=Path)
    parser.add_argument("--status", default="PARTIAL", choices=["PASS", "PARTIAL", "FAIL"])
    return parser.parse_args()


def classify(relative: Path) -> str:
    if relative.parts:
        return TYPE_BY_FOLDER.get(relative.parts[0].upper(), "OTHER")
    return "OTHER"


def main() -> int:
    args = parse_args()
    root = args.project_root.expanduser().resolve()
    output_root = root / "OUTPUT"
    if not output_root.is_dir():
        raise SystemExit(f"OUTPUT directory not found: {output_root}")

    rows = []
    manifest_path = output_root / "output-manifest.json"
    for path in sorted(p for p in output_root.rglob("*") if p.is_file()):
        if path.resolve() == manifest_path.resolve():
            continue
        rel_to_output = path.relative_to(output_root)
        rows.append({
            "relative_path": path.relative_to(root).as_posix(),
            "artifact_type": classify(rel_to_output),
            "size_bytes": path.stat().st_size,
            "sha256": sha256_file(path),
            "status": "GENERATED",
        })

    payload = {
        "schema_version": "0.1",
        "run_status": args.status,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "artifact_count": len(rows),
        "artifacts": rows,
    }
    manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Output manifest: {manifest_path}")
    print(f"Artifacts: {len(rows)} | run_status: {args.status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
