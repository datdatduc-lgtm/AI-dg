"""Evidence-preserving Geometry Ledger V2.

The ledger is deliberately independent from OCR.  Extractors must supply
view-scoped facts with source references; this stage normalizes and validates
them without collapsing regions or reconciling dimensions by numeric value.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 2
BUILDABLE_STATES = {"EXPLICIT", "EXPLICIT_LOCAL_DETAIL", "APPROVED_DERIVED"}


def _number(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be numeric")
    result = float(value)
    if not math.isfinite(result) or result <= 0:
        raise ValueError(f"{field} must be finite and positive")
    return round(result, 3)


def _refs(value: Any, field: str) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{field} requires source_refs")
    refs = []
    for ref in value:
        if not isinstance(ref, dict) or not ref.get("source_id") or not ref.get("view_id"):
            raise ValueError(f"{field} source_ref requires source_id and view_id")
        refs.append(dict(ref))
    return refs


def build_geometry_ledger_v2(payload: dict[str, Any], run_id: str = "") -> dict[str, Any]:
    """Normalize interpreted, evidence-bearing source facts into schema v2."""
    if not isinstance(payload, dict):
        raise ValueError("ledger payload must be an object")
    raw_items = payload.get("items")
    if not isinstance(raw_items, list) or not raw_items:
        raise ValueError("ledger requires at least one item")
    items = []
    for raw in raw_items:
        code = str(raw.get("item_code") or "").strip()
        if not code:
            raise ValueError("item_code is required")
        frame = raw.get("coordinate_frame")
        if not isinstance(frame, dict) or set(frame) < {"x_role", "y_role", "z_role"}:
            raise ValueError(f"{code}: complete coordinate_frame required")
        views = raw.get("views")
        if not isinstance(views, list) or not views:
            raise ValueError(f"{code}: views required")
        view_ids = {str(view.get("id")) for view in views if isinstance(view, dict) and view.get("id")}

        spans = []
        span_ids: set[str] = set()
        for span in raw.get("dimension_spans", []):
            span_id = str(span.get("id") or "").strip()
            if not span_id or span_id in span_ids:
                raise ValueError(f"{code}: dimension span id missing or duplicated")
            if str(span.get("axis")) not in {"X", "Y", "Z"}:
                raise ValueError(f"{code}/{span_id}: invalid axis")
            if not span.get("start_ref") or not span.get("end_ref") or not span.get("span_kind"):
                raise ValueError(f"{code}/{span_id}: semantic span endpoints required")
            if str(span.get("view_id")) not in view_ids:
                raise ValueError(f"{code}/{span_id}: unknown view_id")
            normalized = dict(span)
            normalized["value_mm"] = _number(span.get("value_mm"), f"{code}/{span_id}.value_mm")
            normalized["source_refs"] = _refs(span.get("source_refs"), f"{code}/{span_id}")
            spans.append(normalized)
            span_ids.add(span_id)

        hierarchy = []
        for relation in raw.get("dimension_hierarchy", []):
            parent = str(relation.get("parent_span_id") or "")
            children = [str(value) for value in relation.get("child_span_ids", [])]
            if parent not in span_ids or not children or any(child not in span_ids for child in children):
                raise ValueError(f"{code}: hierarchy references unknown span")
            parent_span = next(span for span in spans if span["id"] == parent)
            child_spans = [next(span for span in spans if span["id"] == child) for child in children]
            if any(child["axis"] != parent_span["axis"] for child in child_spans):
                raise ValueError(f"{code}/{parent}: hierarchy axes differ")
            delta = abs(sum(child["value_mm"] for child in child_spans) - parent_span["value_mm"])
            if delta > float(relation.get("tolerance_mm", 0.1)):
                raise ValueError(f"{code}/{parent}: child spans do not refine parent")
            hierarchy.append({**relation, "equation_status": "PASS", "deviation_mm": round(delta, 3)})

        item_refs = _refs(raw.get("source_refs"), code)
        items.append({
            "item_code": code,
            "coordinate_frame": dict(frame),
            "views": [dict(view) for view in views],
            "envelope": dict(raw.get("envelope") or {}),
            "dimension_spans": spans,
            "dimension_hierarchy": hierarchy,
            "regions": [dict(region) for region in raw.get("regions", [])],
            "subregions": [dict(region) for region in raw.get("subregions", [])],
            "unresolved_geometry": list(raw.get("unresolved_geometry") or []),
            "source_refs": item_refs,
        })
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id or str(payload.get("run_id") or ""),
        "source_review_status": str(payload.get("source_review_status") or "OPEN").upper(),
        "items": items,
    }


def save_geometry_ledger_v2(ledger: dict[str, Any], path: str | Path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(ledger, ensure_ascii=False, indent=2), encoding="utf-8")
    return target
