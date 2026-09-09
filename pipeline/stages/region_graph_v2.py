"""Spatial Region Graph V2 built from Geometry Ledger V2."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 2
NODE_TYPES = {
    "ITEM_ENVELOPE", "REGION", "SUBREGION", "MATERIAL_LAYER", "SURFACE",
    "DETAIL_FEATURE", "UNRESOLVED_REGION",
}
EDGE_TYPES = {
    "CONTAINS", "WITHIN", "ABOVE", "BELOW", "ADJACENT_TO", "ALIGNED_WITH",
    "OVERLAPS", "REFINES", "VISIBLE_IN", "SECTION_ONLY", "MATERIAL_OF",
    "EMBEDDED_IN", "RECESSED_IN", "SLOTTED_IN", "OFFSET_FROM",
}
EVIDENCE_REQUIRED_EDGES = {"EMBEDDED_IN", "RECESSED_IN", "SLOTTED_IN", "OFFSET_FROM"}


def build_region_graph_v2(ledger: dict[str, Any]) -> dict[str, Any]:
    if ledger.get("schema_version") != 2:
        raise ValueError("Geometry Ledger schema_version 2 required")
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []

    for item in ledger.get("items", []):
        code = str(item["item_code"])
        envelope_id = f"{code}:envelope"
        nodes.append({
            "id": envelope_id, "node_type": "ITEM_ENVELOPE", "item_code": code,
            "bounds": item.get("envelope", {}), "state": "EXPLICIT",
            "source_refs": item.get("source_refs", []),
        })
        item_nodes: dict[str, dict[str, Any]] = {envelope_id: nodes[-1]}
        for raw in [*item.get("regions", []), *item.get("subregions", []), *item.get("materials", [])]:
            node = {**raw, "id": f"{code}:{raw['id']}", "item_code": code}
            if node.get("node_type") not in NODE_TYPES:
                raise ValueError(f"{node['id']}: unsupported node_type")
            if not node.get("source_refs"):
                raise ValueError(f"{node['id']}: source_refs required")
            nodes.append(node)
            item_nodes[node["id"]] = node

        for raw in item.get("regions", []):
            region_id = f"{code}:{raw['id']}"
            edges.append({"type": "CONTAINS", "from": envelope_id, "to": region_id, "state": raw.get("state", "EXPLICIT"), "source_refs": raw.get("source_refs", [])})
            if raw.get("material_id"):
                edges.append({"type": "MATERIAL_OF", "from": f"{code}:{raw['material_id']}", "to": region_id, "state": raw.get("state", "EXPLICIT"), "source_refs": raw.get("source_refs", [])})
            if raw.get("visibility") == "VISIBLE":
                for ref in raw.get("source_refs", []):
                    edges.append({"type": "VISIBLE_IN", "from": region_id, "to": f"view:{ref['view_id']}", "state": raw.get("state", "EXPLICIT"), "source_refs": [ref]})

        for raw in item.get("subregions", []):
            child_id = f"{code}:{raw['id']}"
            parent_id = f"{code}:{raw.get('parent_region_id')}"
            if parent_id not in item_nodes:
                raise ValueError(f"{child_id}: parent region not found")
            edges.append({"type": "WITHIN", "from": child_id, "to": parent_id, "state": raw.get("state", "REVIEW_REQUIRED"), "source_refs": raw.get("source_refs", [])})
            edge_type = "SECTION_ONLY" if raw.get("visibility") == "SECTION_ONLY" else "REFINES"
            edges.append({"type": edge_type, "from": child_id, "to": parent_id, "state": raw.get("state", "REVIEW_REQUIRED"), "source_refs": raw.get("source_refs", [])})

        visible = [raw for raw in item.get("regions", []) if raw.get("visibility") == "VISIBLE"]
        for lower in visible:
            lower_z = (lower.get("bounds") or {}).get("z")
            for upper in visible:
                upper_z = (upper.get("bounds") or {}).get("z")
                if lower is not upper and isinstance(lower_z, list) and isinstance(upper_z, list) and lower_z[1] == upper_z[0]:
                    refs = [*lower.get("source_refs", []), *upper.get("source_refs", [])]
                    edges.append({"type": "BELOW", "from": f"{code}:{lower['id']}", "to": f"{code}:{upper['id']}", "state": "EXPLICIT", "source_refs": refs})
                    edges.append({"type": "ADJACENT_TO", "from": f"{code}:{lower['id']}", "to": f"{code}:{upper['id']}", "state": "EXPLICIT", "source_refs": refs})

        for relation in item.get("relationships", []):
            edge_type = str(relation.get("type") or "")
            if edge_type not in EDGE_TYPES:
                raise ValueError(f"{code}: unsupported relationship {edge_type}")
            if edge_type in EVIDENCE_REQUIRED_EDGES and (not relation.get("source_refs") or relation.get("state") not in {"EXPLICIT", "APPROVED_DERIVED"}):
                unresolved.append({"item_code": code, "relationship": relation, "reason": "RELATIONSHIP_EVIDENCE_REQUIRED"})
                continue
            edges.append(dict(relation))

        for entry in item.get("unresolved_geometry", []):
            detail = dict(entry) if isinstance(entry, dict) else {"description": str(entry)}
            unresolved.append({"item_code": code, "state": "REVIEW_REQUIRED", "impact": "BLOCKING", **detail})

    return {"schema_version": SCHEMA_VERSION, "run_id": ledger.get("run_id", ""), "source_review_status": ledger.get("source_review_status", "OPEN"), "nodes": nodes, "edges": edges, "unresolved": unresolved}


def validate_region_graph_v2(graph: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    ids = {node.get("id") for node in graph.get("nodes", [])}
    for node in graph.get("nodes", []):
        if node.get("node_type") not in NODE_TYPES:
            errors.append(f"{node.get('id')}: invalid node type")
        if not node.get("source_refs"):
            errors.append(f"{node.get('id')}: source refs missing")
    for edge in graph.get("edges", []):
        if edge.get("type") not in EDGE_TYPES:
            errors.append(f"invalid edge {edge.get('type')}")
        if edge.get("type") in EVIDENCE_REQUIRED_EDGES and not edge.get("source_refs"):
            errors.append(f"{edge.get('type')}: evidence missing")
        if not str(edge.get("to", "")).startswith("view:") and edge.get("to") not in ids:
            errors.append(f"edge target missing: {edge.get('to')}")
    return errors


def save_region_graph_v2(graph: dict[str, Any], path: str | Path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(graph, ensure_ascii=False, indent=2), encoding="utf-8")
    return target
