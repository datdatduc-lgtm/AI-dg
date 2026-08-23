#!/usr/bin/env python3
"""Inventory AI-dg project INPUT files into a reproducible manifest.

Usage:
  python scan_input.py D:/CongTrinh/Villa-A
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

TYPE_BY_EXT = {
    ".pdf": "PDF",
    ".dwg": "CAD",
    ".dxf": "CAD",
    ".dwt": "CAD",
    ".skp": "SKP",
    ".xlsx": "SPREADSHEET",
    ".xls": "SPREADSHEET",
    ".csv": "SPREADSHEET",
    ".docx": "DOCUMENT",
    ".txt": "DOCUMENT",
    ".md": "DOCUMENT",
    ".png": "IMAGE",
    ".jpg": "IMAGE",
    ".jpeg": "IMAGE",
    ".tif": "IMAGE",
    ".tiff": "IMAGE",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scan an AI-dg project INPUT directory")
    parser.add_argument("project_root", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = args.project_root.expanduser().resolve()
    input_root = root / "INPUT"
    manifest_dir = root / "WORK" / "manifests"
    manifest_path = manifest_dir / "input-manifest.json"

    if not input_root.is_dir():
        raise SystemExit(f"INPUT directory not found: {input_root}")

    manifest_dir.mkdir(parents=True, exist_ok=True)
    rows = []

    for path in sorted(p for p in input_root.rglob("*") if p.is_file()):
        stat = path.stat()
        ext = path.suffix.lower()
        source_type = TYPE_BY_EXT.get(ext, "OTHER")
        rows.append({
            "relative_path": path.relative_to(root).as_posix(),
            "source_type": source_type,
            "extension": ext,
            "size_bytes": stat.st_size,
            "sha256": sha256_file(path),
            "modified_time_utc": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
            "analysis_status": "PENDING",
            "notes": None if source_type != "OTHER" else "Unclassified extension; inspect manually if relevant.",
        })

    counts = {}
    for row in rows:
        counts[row["source_type"]] = counts.get(row["source_type"], 0) + 1

    payload = {
        "schema_version": "0.1",
        "project_root": str(root),
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "file_count": len(rows),
        "counts_by_type": counts,
        "files": rows,
    }
    manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Input manifest: {manifest_path}")
    print(f"Files: {len(rows)} | types: {counts}")
    if not rows:
        print("WARNING: INPUT contains no files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
