"""Ordered, non-mutating A-F reconstruction pipeline for schema V2."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .build_ir_v2 import build_ir_v2, save_build_ir_v2, validate_build_ir_v2
from .geometry_ledger_v2 import build_geometry_ledger_v2, save_geometry_ledger_v2
from .model_spec_v2 import generate_model_spec_v2, save_model_spec_v2
from .projection_verification_v2 import save_projection_report_v2, verify_prebuild_projection_v2
from .region_graph_v2 import build_region_graph_v2, save_region_graph_v2, validate_region_graph_v2


def _drawing_index_v2(ledger: dict[str, Any]) -> dict[str, Any]:
    entries = []
    for item in ledger.get("items", []):
        for view in item.get("views", []):
            entries.append({
                "id": view["id"],
                "item_code": item["item_code"],
                "role": view["role"],
                "projection_axes": view.get("projection_axes", []),
                "source_refs": view.get("source_refs", []),
            })
    links = []
    by_item: dict[str, list[dict[str, Any]]] = {}
    for entry in entries:
        by_item.setdefault(entry["item_code"], []).append(entry)
    for code, views in by_item.items():
        if views:
            anchor = views[0]["id"]
            links.extend({"item_code": code, "from": anchor, "to": view["id"], "type": "SAME_PHYSICAL_ITEM"} for view in views[1:])
    return {"schema_version": 2, "run_id": ledger.get("run_id", ""), "entries": entries, "view_links": links}


def run_reconstruction_v2(interpreted_payload: dict[str, Any], output_root: str | Path, run_id: str) -> dict[str, Any]:
    """Run phases A-F only. This function has no SketchUp transport."""
    root = Path(output_root)
    ledger = build_geometry_ledger_v2(interpreted_payload, run_id)
    drawing_index = _drawing_index_v2(ledger)
    graph = build_region_graph_v2(ledger)
    graph_errors = validate_region_graph_v2(graph)
    if graph_errors:
        raise ValueError("Region Graph V2 failed: " + "; ".join(graph_errors))
    spec = generate_model_spec_v2(ledger, graph)
    build_ir = build_ir_v2(spec)
    build_errors = validate_build_ir_v2(build_ir)
    projection = verify_prebuild_projection_v2(build_ir)

    geometry_dir = root / "WORK" / "geometry"
    model_dir = root / "OUTPUT" / "MODEL"
    verification_dir = root / "OUTPUT" / "VERIFICATION"
    geometry_dir.mkdir(parents=True, exist_ok=True)
    (geometry_dir / "drawing-index-v2.json").write_text(json.dumps(drawing_index, ensure_ascii=False, indent=2), encoding="utf-8")
    save_geometry_ledger_v2(ledger, geometry_dir / "geometry-ledger-v2.json")
    save_region_graph_v2(graph, geometry_dir / "region-graph-v2.json")
    save_model_spec_v2(spec, model_dir / "model-spec-v2.json")
    save_build_ir_v2(build_ir, model_dir / "build-ir-v2.json")
    save_projection_report_v2(projection, verification_dir / "projection-prebuild-v2.json")

    checks = {
        "A_INTERPRETATION": bool(drawing_index["entries"]) and len(drawing_index["view_links"]) >= 3,
        "B_GEOMETRY_LEDGER": all(row.get("equation_status") == "PASS" for item in ledger["items"] for row in item.get("dimension_hierarchy", [])),
        "C_REGION_GRAPH": not graph_errors,
        "D_MODELSPEC": bool(spec["items"]) and all(item["buildable_state"] == "READY" for item in spec["items"]),
        "E_BUILD_IR": not build_errors,
        "F_PREBUILD_PROJECTION": projection["status"] == "PASS",
    }
    return {"schema_version": 2, "run_id": run_id, "status": "PASS" if all(checks.values()) else "FAIL", "checks": checks}
