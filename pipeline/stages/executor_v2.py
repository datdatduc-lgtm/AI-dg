"""Transport-agnostic, projection-gated Build IR V2 executor."""

from __future__ import annotations

from typing import Any, Callable

from .build_ir_v2 import validate_build_ir_v2
from .projection_verification_v2 import verify_postbuild_projection_v2, verify_prebuild_projection_v2


def _region_part(region: dict[str, Any]) -> dict[str, Any]:
    bounds = region["bounds"]
    return {
        "part_id": region["id"],
        "region_id": region["id"],
        "role": "region",
        "visibility": region.get("visibility", "VISIBLE"),
        "material_code": region.get("material_id", ""),
        "dimensions_mm": {name: round(float(bounds[axis][1]) - float(bounds[axis][0]), 3) for axis, name in (("x", "width_mm"), ("y", "depth_mm"), ("z", "height_mm"))},
        "origin_mm": [float(bounds[axis][0]) for axis in ("x", "y", "z")],
        "source_refs": region.get("source_refs", []),
    }


def normalize_sketchup_readback_v2(response: dict[str, Any]) -> dict[str, Any]:
    data = response.get("data", response)
    regions = []
    for child in data.get("parts", []) if isinstance(data, dict) else []:
        attrs = child.get("attributes", {}).get("AI_DG", {})
        minimum = child.get("min_mm", [None, None, None])
        maximum = child.get("max_mm", [None, None, None])
        regions.append({
            "region_id": attrs.get("region_id") or attrs.get("part_id"),
            "bounds": {axis: [minimum[index], maximum[index]] for index, axis in enumerate(("x", "y", "z"))},
            "material_id": attrs.get("material_id") or attrs.get("material_code"),
            "visible": attrs.get("visibility", "VISIBLE") == "VISIBLE",
            "persistent_id": child.get("persistent_id"),
            "transform": child.get("transformation"),
        })
    return {"item_code": data.get("item_code") if isinstance(data, dict) else None, "root": data.get("root", {}) if isinstance(data, dict) else {}, "regions": regions, "readback_source": data.get("readback_source") if isinstance(data, dict) else None}


def execute_build_ir_v2(build_ir: dict[str, Any], *, target: dict[str, Any] | None, access_mode: str, confirm_write: bool, dispatch: Callable[[dict[str, Any]], dict[str, Any]], readback: Callable[[str], dict[str, Any]]) -> dict[str, Any]:
    errors = validate_build_ir_v2(build_ir)
    if errors:
        return {"status": "BLOCKED", "reason": "BUILD_IR_V2_INVALID", "errors": errors}
    if build_ir.get("source_review_status") != "APPROVED":
        return {"status": "BLOCKED", "reason": "SOURCE_REVIEW_NOT_APPROVED"}
    pre = verify_prebuild_projection_v2(build_ir)
    if pre.get("status") != "PASS":
        return {"status": "BLOCKED", "reason": "PREBUILD_PROJECTION_FAILED", "prebuild": pre}
    if not target or not target.get("instance_id") or target.get("status") not in {None, "ONLINE"}:
        return {"status": "BLOCKED", "reason": "EXPLICIT_ONLINE_TARGET_REQUIRED"}
    if access_mode != "write_enabled":
        return {"status": "BLOCKED", "reason": "READ_ONLY_MODE", "target": target}
    if confirm_write is not True:
        return {"status": "BLOCKED", "reason": "WRITE_CONFIRMATION_REQUIRED", "target": target}

    operation_results = []
    all_regions = []
    for operation in build_ir["operations"]:
        parts = [_region_part(region) for region in operation["regions"] if region.get("build_geometry") is True]
        result = dispatch({"item_code": operation["item_code"], "name": f"AI_DG_V2_{operation['item_code']}", "parts": parts, "source_refs": operation.get("source_refs", []), "schema_version": 2, "pipeline_stage": "2D3D-V2", "builder_type": "region_assembly_v2", "tool_name": "ai_dg_execute_build_ir_v2", "approval_mode": "user_preapproved_v2", "confirm_write": True})
        operation_results.append({"item_code": operation["item_code"], "status": result.get("status"), "operation_id": result.get("operation_id")})
        if result.get("status") != "ok":
            return {"status": "FAIL", "reason": "SKETCHUP_DISPATCH_FAILED", "target": target, "operations": operation_results, "error": result.get("error")}
        all_regions.extend(normalize_sketchup_readback_v2(readback(operation["item_code"]))["regions"])

    official = {"target": target, "regions": all_regions, "readback_source": "official_sketchup_ruby_api"}
    post = verify_postbuild_projection_v2(build_ir, official)
    return {"status": "PASS" if post["status"] == "PASS" else "FAIL", "target": target, "operations": operation_results, "readback": official, "postbuild": post}
