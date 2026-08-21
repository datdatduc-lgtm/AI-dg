#!/usr/bin/env python3
"""Deterministically calculate BOM quantities from verified AI-dg item records."""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Calculate BOM from AI-dg items.json")
    parser.add_argument("items", type=Path)
    parser.add_argument("--materials", type=Path, default=None)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def load_materials(path: Path | None) -> dict[str, dict[str, Any]]:
    if path is None:
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {str(row["code"]): row for row in payload.get("materials", [])}


def main() -> int:
    args = parse_args()
    payload = json.loads(args.items.read_text(encoding="utf-8"))
    material_library = load_materials(args.materials)

    groups: dict[tuple[str, float | None], dict[str, Any]] = defaultdict(
        lambda: {
            "material_code": None,
            "thickness_mm": None,
            "net_area_m2": 0.0,
            "net_volume_m3": 0.0,
            "required_area_m2": 0.0,
            "waste_factor": 0.0,
            "sheet_length_mm": None,
            "sheet_width_mm": None,
            "theoretical_sheet_count": None,
            "item_ids": [],
            "sources": [],
        }
    )
    review: list[dict[str, Any]] = []

    for item in payload.get("items", []):
        material_code = item.get("material_code") or item.get("source_material_code") or "UNSPECIFIED"
        thickness = item.get("thickness_mm")
        key = (material_code, thickness)
        row = groups[key]
        row["material_code"] = material_code
        row["thickness_mm"] = thickness
        row["item_ids"].append(item["id"])
        row["sources"].append(item["source"])

        quantity = int(item["quantity"])
        length = item.get("length_mm")
        width = item.get("width_mm")

        reasons: list[str] = []
        if item.get("review_required"):
            reasons.append("source record marked review_required")
        if item.get("confidence", 0) < 0.90:
            reasons.append("confidence below 0.90")
        if material_code == "UNSPECIFIED":
            reasons.append("material code missing")

        if length is not None and width is not None:
            area_m2 = (float(length) * float(width) * quantity) / 1_000_000.0
            row["net_area_m2"] += area_m2
            if thickness is not None:
                row["net_volume_m3"] += (
                    float(length) * float(width) * float(thickness) * quantity
                ) / 1_000_000_000.0
        else:
            reasons.append("length/width missing; area not calculated")

        if reasons:
            review.append({"item_id": item["id"], "reasons": reasons, "source": item["source"]})

    bom: list[dict[str, Any]] = []
    for (material_code, _), row in sorted(groups.items(), key=lambda pair: (pair[0][0], pair[0][1] or 0)):
        lib = material_library.get(material_code, {})
        waste_factor = float(lib.get("waste_factor", 0.0) or 0.0)
        if waste_factor < 0:
            raise SystemExit(f"Invalid negative waste_factor for {material_code}")

        row["waste_factor"] = waste_factor
        row["required_area_m2"] = row["net_area_m2"] * (1.0 + waste_factor)
        row["sheet_length_mm"] = lib.get("sheet_length_mm")
        row["sheet_width_mm"] = lib.get("sheet_width_mm")

        if row["sheet_length_mm"] and row["sheet_width_mm"]:
            sheet_area_m2 = (
                float(row["sheet_length_mm"]) * float(row["sheet_width_mm"])
            ) / 1_000_000.0
            if sheet_area_m2 > 0:
                row["theoretical_sheet_count"] = math.ceil(row["required_area_m2"] / sheet_area_m2)

        row["net_area_m2"] = round(row["net_area_m2"], 6)
        row["required_area_m2"] = round(row["required_area_m2"], 6)
        row["net_volume_m3"] = round(row["net_volume_m3"], 9)
        bom.append(row)

    result = {
        "schema_version": "0.1",
        "calculation_basis": {
            "dimensions": "millimetres",
            "area": "length_mm * width_mm * quantity / 1,000,000",
            "volume": "length_mm * width_mm * thickness_mm * quantity / 1,000,000,000",
            "sheet_count": "theoretical only; not nesting optimization",
            "default_waste_factor": 0.0,
        },
        "bom": bom,
        "review": review,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"BOM rows: {len(bom)}; review records: {len(review)} -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
