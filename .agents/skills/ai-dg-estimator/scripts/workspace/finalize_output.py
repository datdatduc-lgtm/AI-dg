#!/usr/bin/env python3
"""Create OUTPUT/output-manifest.json and validate mandatory AI-dg deliverables."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

TYPE_BY_FOLDER = {
    "RUBY": "RUBY",
    "IMAGES": "IMAGE",
    "TAKEOFF": "TAKEOFF",
    "EXCEL": "EXCEL",
    "REPORTS": "REPORT",
    "MODEL": "MODEL",
}

MANDATORY_EXCEL = [
    "AI-dg_Tong-hop-vat-lieu.xlsx",
    "AI-dg_Bao-gia.xlsx",
]


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


def slug(value: Any) -> str:
    return re.sub(r"[^A-Z0-9]+", "", str(value or "").upper())


def load_json(path: Path) -> Any:
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def modelable_items(root: Path) -> list[str]:
    payload = load_json(root / "WORK" / "geometry" / "geometry-ledger.json")
    if not isinstance(payload, dict):
        return []
    rows = []
    for key in ("items", "item_ledgers", "geometry_ledgers"):
        if isinstance(payload.get(key), list):
            rows = [row for row in payload[key] if isinstance(row, dict)]
            break
    result = []
    for row in rows:
        readiness = str(
            row.get("component_geometry_readiness")
            or row.get("readiness")
            or row.get("status")
            or ""
        ).upper()
        if readiness not in {"READY", "PARTIAL_READY"}:
            continue
        item_id = row.get("item_code") or row.get("item_id") or row.get("id") or row.get("name")
        if item_id:
            result.append(str(item_id))
    return result


def deliverable_checks(root: Path) -> dict[str, Any]:
    output_root = root / "OUTPUT"
    excel_root = output_root / "EXCEL"
    ruby_root = output_root / "RUBY"

    excel = {
        name: (excel_root / name).is_file()
        for name in MANDATORY_EXCEL
    }

    ruby_files = sorted(ruby_root.glob("*.rb")) if ruby_root.is_dir() else []
    modelable = modelable_items(root)
    ruby_by_item = {}
    for item in modelable:
        token = slug(item)
        ruby_by_item[item] = any(token and token in slug(path.stem) for path in ruby_files)

    return {
        "mandatory_excel": excel,
        "all_mandatory_excel_present": all(excel.values()),
        "modelable_items": modelable,
        "ruby_by_modelable_item": ruby_by_item,
        "all_modelable_items_have_ruby": all(ruby_by_item.values()) if ruby_by_item else True,
        "ruby_file_count": len(ruby_files),
    }


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

    checks = deliverable_checks(root)
    effective_status = args.status
    missing_required = (
        not checks["all_mandatory_excel_present"]
        or not checks["all_modelable_items_have_ruby"]
    )
    if missing_required and effective_status == "PASS":
        effective_status = "PARTIAL"

    payload = {
        "schema_version": "0.2",
        "requested_run_status": args.status,
        "run_status": effective_status,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "artifact_count": len(rows),
        "deliverable_checks": checks,
        "artifacts": rows,
    }
    manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Output manifest: {manifest_path}")
    print(f"Artifacts: {len(rows)} | run_status: {effective_status}")
    if not checks["all_mandatory_excel_present"]:
        print("WARNING: mandatory Excel deliverables are missing.")
    if not checks["all_modelable_items_have_ruby"]:
        missing = [item for item, ok in checks["ruby_by_modelable_item"].items() if not ok]
        print(f"WARNING: modelable items missing Ruby: {missing}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
