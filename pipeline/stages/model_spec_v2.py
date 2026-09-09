"""ModelSpec V2: preserves spatial hierarchy and evidence relationships."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .region_graph_v2 import validate_region_graph_v2


SCHEMA_VERSION = 2
BUILDABLE_STATES = {"EXPLICIT", "EXPLICIT_LOCAL_DETAIL", "APPROVED_DERIVED"}


def _complete_bounds(bounds: Any) -> bool:
    return isinstance(bounds, dict) and all(
        isinstance(bounds.get(axis), list) and len(bounds[axis]) == 2 and bounds[axis][1] > bounds[axis][0]
        for axis in ("x", "y", "z")
    )


def generate_model_spec_v2(ledger: dict[str, Any], graph: dict[str, Any]) -> dict[str, Any]:
    errors = validate_region_graph_v2(graph)
    if errors:
        raise ValueError("invalid Region Graph V2: " + "; ".join(errors))
    review_status = str(ledger.get("source_review_status") or "OPEN").upper()
    items = []
    for ledger_item in ledger.get("items", []):
        code = str(ledger_item["item_code"])
        prefix = f"{code}:"
        graph_nodes = [node for node in graph.get("nodes", []) if node.get("item_code") == code]
        regions = [dict(node) for node in graph_nodes if node.get("node_type") in {"REGION", "SUBREGION", "DETAIL_FEATURE", "UNRESOLVED_REGION"}]
        materials = [dict(node) for node in graph_nodes if node.get("node_type") == "MATERIAL_LAYER"]
        relationships = [dict(edge) for edge in graph.get("edges", []) if str(edge.get("from", "")).startswith(prefix)]
        unresolved = [dict(row) for row in graph.get("unresolved", []) if row.get("item_code") == code]
        blockers = [row for row in unresolved if row.get("impact", "BLOCKING") == "BLOCKING"]
        envelope = dict(ledger_item.get("envelope") or {})
        envelope_ready = all(isinstance(envelope.get(axis), (int, float)) and envelope[axis] > 0 for axis in ("x_mm", "y_mm", "z_mm"))
        visible_regions = [region for region in regions if region.get("visibility") == "VISIBLE"]
        regions_ready = bool(visible_regions) and all(
            _complete_bounds(region.get("bounds")) and region.get("state") in BUILDABLE_STATES and region.get("source_refs")
            for region in visible_regions
        )
        material_targets = {edge.get("to") for edge in relationships if edge.get("type") == "MATERIAL_OF"}
        materials_ready = all(region.get("id") in material_targets for region in visible_regions)
        ready = review_status == "APPROVED" and envelope_ready and regions_ready and materials_ready and not blockers
        items.append({
            "item_code": code,
            "coordinate_frame": dict(ledger_item.get("coordinate_frame") or {}),
            "views": [dict(view) for view in ledger_item.get("views", [])],
            "envelope": envelope,
            "dimension_spans": [dict(span) for span in ledger_item.get("dimension_spans", [])],
            "dimension_hierarchy": [dict(row) for row in ledger_item.get("dimension_hierarchy", [])],
            "regions": regions,
            "relationships": relationships,
            "materials": materials,
            "unresolved": unresolved,
            "source_refs": [dict(ref) for ref in ledger_item.get("source_refs", [])],
            "buildable_state": "READY" if ready else "REVIEW_REQUIRED",
            "gate_checks": {
                "source_review_approved": review_status == "APPROVED",
                "envelope_complete": envelope_ready,
                "visible_regions_complete": regions_ready,
                "material_mapping_complete": materials_ready,
                "blocking_ambiguity_absent": not blockers,
            },
        })
    return {"schema_version": SCHEMA_VERSION, "run_id": ledger.get("run_id", ""), "source_review_status": review_status, "items": items}


def save_model_spec_v2(spec: dict[str, Any], path: str | Path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")
    return target
