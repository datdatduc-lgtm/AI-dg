"""Deterministic semantic Build IR V2."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 2


def _stable_id(run_id: str, item_code: str) -> str:
    digest = hashlib.sha256(f"{run_id}\0{item_code}".encode("utf-8")).hexdigest()[:16]
    return f"assembly-{digest}"


def build_ir_v2(model_spec: dict[str, Any]) -> dict[str, Any]:
    if model_spec.get("schema_version") != 2:
        raise ValueError("ModelSpec schema_version 2 required")
    run_id = str(model_spec.get("run_id") or "")
    operations = []
    blocked_items = []
    for item in sorted(model_spec.get("items", []), key=lambda row: str(row.get("item_code", ""))):
        code = str(item.get("item_code") or "")
        if item.get("buildable_state") != "READY":
            blocked_items.append({"item_code": code, "reason": "MODELSPEC_V2_NOT_READY"})
            continue
        visible_regions = [region for region in item.get("regions", []) if region.get("visibility") == "VISIBLE"]
        semantic_regions = []
        for region in item.get("regions", []):
            semantic_regions.append({
                **region,
                "build_geometry": region.get("visibility") == "VISIBLE",
            })
        operations.append({
            "operation": "create_item_assembly",
            "id": _stable_id(run_id, code),
            "item_code": code,
            "coordinate_frame": item.get("coordinate_frame", {}),
            "envelope": item.get("envelope", {}),
            "regions": semantic_regions,
            "relationships": item.get("relationships", []),
            "materials": item.get("materials", []),
            "source_refs": item.get("source_refs", []),
            "verification_contract": {
                "views": item.get("views", []),
                "dimension_spans": item.get("dimension_spans", []),
                "dimension_hierarchy": item.get("dimension_hierarchy", []),
                "expected_visible_region_ids": [region["id"] for region in visible_regions],
                "forbidden_visible_region_ids": [
                    region["id"] for region in semantic_regions if region.get("visibility") == "SECTION_ONLY"
                ],
            },
        })
    status = "READY" if operations and not blocked_items else "BLOCKED"
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "source_review_status": model_spec.get("source_review_status", "OPEN"),
        "status": status,
        "operations": operations,
        "blocked_items": blocked_items,
    }


def validate_build_ir_v2(build_ir: dict[str, Any]) -> list[str]:
    errors = []
    if build_ir.get("schema_version") != 2:
        errors.append("schema_version 2 required")
    if build_ir.get("status") != "READY":
        errors.append("Build IR V2 status must be READY")
    for operation in build_ir.get("operations", []):
        if operation.get("operation") != "create_item_assembly":
            errors.append("unsupported operation")
        if not operation.get("regions") or not operation.get("relationships"):
            errors.append(f"{operation.get('item_code')}: semantic regions/relationships required")
        if not operation.get("verification_contract"):
            errors.append(f"{operation.get('item_code')}: verification contract required")
    return errors


def save_build_ir_v2(build_ir: dict[str, Any], path: str | Path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(build_ir, ensure_ascii=False, indent=2), encoding="utf-8")
    return target
