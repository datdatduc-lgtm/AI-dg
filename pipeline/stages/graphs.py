"""Dimension and material graphs (M4).

The graph layer is deliberately deterministic and provenance-first.  It keeps
every source observation as a node/fact and records conflicts instead of
choosing a value silently.  A later review step may resolve a conflict; this
module never approves or invents dimensions/materials.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_part(value: Any) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "-", str(value or "UNKNOWN").strip())
    return cleaned.strip("-") or "UNKNOWN"


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if result == result and abs(result) != float("inf") else None


@dataclass
class DimensionGraph:
    run_id: str
    schema_version: str = "0.1"
    nodes: list[dict[str, Any]] = field(default_factory=list)
    edges: list[dict[str, Any]] = field(default_factory=list)
    conflicts: list[dict[str, Any]] = field(default_factory=list)
    generated_utc: str = field(default_factory=utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "run_id": self.run_id,
            "generated_utc": self.generated_utc,
            "nodes": self.nodes,
            "edges": self.edges,
            "conflicts": self.conflicts,
        }


@dataclass
class MaterialGraph:
    run_id: str
    schema_version: str = "0.1"
    items: dict[str, dict[str, Any]] = field(default_factory=dict)
    materials: list[dict[str, Any]] = field(default_factory=list)
    edges: list[dict[str, Any]] = field(default_factory=list)
    generated_utc: str = field(default_factory=utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "run_id": self.run_id,
            "generated_utc": self.generated_utc,
            "items": self.items,
            "materials": self.materials,
            "edges": self.edges,
        }


def build_dimension_graph(facts: list[dict[str, Any]], run_id: str = "") -> DimensionGraph:
    """Build a graph keyed by item/region/dimension.

    Equal values from multiple sources are retained as provenance.  Different
    values become a review conflict; no representative value is promoted to a
    buildable value here.
    """
    graph = DimensionGraph(run_id=run_id)
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for fact in facts:
        value = _number(fact.get("value_mm"))
        if value is None:
            continue
        item = str(fact.get("item_code") or fact.get("item") or "UNKNOWN")
        region = str(fact.get("region") or fact.get("span") or "default")
        dim = str(fact.get("dim") or fact.get("role") or "candidate")
        grouped.setdefault((item, region, dim), []).append(fact)

    for (item, region, dim), group in sorted(grouped.items()):
        values = sorted({_number(fact.get("value_mm")) for fact in group if _number(fact.get("value_mm")) is not None})
        node_id = "DIM-{}-{}-{}".format(_safe_part(item), _safe_part(region), _safe_part(dim))
        sources = sorted({str(fact.get("source_id") or "UNKNOWN") for fact in group})
        confidences = [float(fact.get("confidence", 0.0) or 0.0) for fact in group]
        states = sorted({str(fact.get("state") or "OBSERVED").upper() for fact in group})
        graph.nodes.append({
            "id": node_id,
            "kind": "dimension",
            "item": item,
            "region": region,
            "dim": dim,
            "unit": "mm",
            "values_mm": [round(value, 3) for value in values],
            "sources": sources,
            "states": states,
            "confidence": round(min(confidences) if confidences else 0.0, 3),
        })
        for fact in group:
            source = str(fact.get("source_id") or "UNKNOWN")
            graph.edges.append({
                "from": node_id,
                "to": source,
                "relation": "observed_from",
                "provenance": fact.get("provenance") or {
                    "source_id": source,
                    "drawing_id": fact.get("drawing_id"),
                },
            })
        if len(values) > 1:
            graph.conflicts.append({
                "node": node_id,
                "item": item,
                "region": region,
                "dim": dim,
                "values": [round(value, 3) for value in values],
                "span_mm": round(max(values) - min(values), 3),
                "sources": sources,
                "severity": "HIGH",
                "status": "REVIEW_REQUIRED",
                "reason": "Multiple source values disagree; no value selected automatically.",
            })
    return graph


def build_material_graph(facts: list[dict[str, Any]], run_id: str = "") -> MaterialGraph:
    """Build item/material relationships while retaining material roles."""
    graph = MaterialGraph(run_id=run_id)
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for fact in facts:
        code = str(fact.get("material_code") or fact.get("code") or "").strip()
        if not code:
            continue
        item = str(fact.get("item_code") or fact.get("item") or "UNKNOWN")
        grouped.setdefault((item, code), []).append(fact)

    for (item, code), group in sorted(grouped.items()):
        roles = sorted({str(fact.get("role") or "unspecified") for fact in group})
        sources = sorted({str(fact.get("source_id") or "UNKNOWN") for fact in group})
        row = {
            "id": "MAT-{}-{}".format(_safe_part(item), _safe_part(code)),
            "item_code": item,
            "code": code,
            "roles": roles,
            "sources": sources,
            "confidence": round(min(float(fact.get("confidence", 0.0) or 0.0) for fact in group), 3),
            "status": "OBSERVED",
        }
        graph.materials.append(row)
        item_row = graph.items.setdefault(item, {"item_code": item, "materials": [], "roles": {}})
        if code not in item_row["materials"]:
            item_row["materials"].append(code)
        for role in roles:
            item_row["roles"].setdefault(role, []).append(code)
        graph.edges.append({"from": item, "to": row["id"], "relation": "uses_material", "roles": roles, "sources": sources})

    for item_row in graph.items.values():
        item_row["materials"] = sorted(item_row["materials"])
        item_row["roles"] = {key: sorted(value) for key, value in sorted(item_row["roles"].items())}
    return graph


def save_graph(output_path: Path, payload: dict[str, Any]) -> Path:
    output_path = output_path.expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path
