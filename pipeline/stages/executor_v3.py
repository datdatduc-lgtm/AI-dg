"""Native SketchUp executor and hypothesis-repair loop for reconstruction V3."""

from __future__ import annotations

import copy
from typing import Any, Callable

from .reconstruction_workflow_v3 import geometry_hash_v3
from .repair_loop_v3 import plan_repairs_v3
from .sketchup_view_back_v3 import view_back_from_sketchup_readback_v3
from .view_verification_v3 import compare_view_back_v3, project_hypothesis_v3


def _span(region: dict[str, Any], axis: str) -> float:
    values = region["bounds"][axis]
    return float(values[1]) - float(values[0])


def build_native_operation_v3(
    item_id: str,
    geometry: dict[str, Any],
    section_graph: dict[str, Any],
    *,
    model_revision: int,
) -> dict[str, Any]:
    regions = {row["id"]: row for row in geometry.get("regions", [])}
    if not regions:
        raise ValueError("V3_REGIONS_REQUIRED")
    body = regions.get("body") or max(regions.values(), key=lambda row: _span(row, "y") * _span(row, "z"))
    length = _span(body, "x")
    depth = _span(body, "y")
    height = _span(body, "z")
    profiles = {row["profile_id"]: row for row in section_graph.get("profiles", [])}
    selected_profiles = [profiles[key] for key in geometry.get("section_profile_ids", []) if key in profiles]
    slots = [feature for profile in selected_profiles for feature in profile.get("features", []) if feature.get("type") == "SLOT"]
    if slots:
        slot = slots[0]
        slot_width = float(slot["dimensions_mm"]["width"])
        slot_depth = float(slot["dimensions_mm"]["depth"])
        side = (depth - slot_width) / 2.0
        if side <= 0 or slot_depth <= 0 or slot_depth >= height:
            raise ValueError("V3_SLOT_GEOMETRY_INVALID")
        profile = [[0, 0], [depth, 0], [depth, height], [depth - side, height], [depth - side, height - slot_depth], [side, height - slot_depth], [side, height], [0, height]]
        profile_id = selected_profiles[0]["profile_id"]
    else:
        profile = [[0, 0], [depth, 0], [depth, height], [0, height]]
        profile_id = "profile-main"

    inserts = []
    radius_features = [feature for feature in geometry.get("features", []) if feature.get("type") == "RADIUS"]
    top_radius = float(radius_features[0]["dimensions_mm"]["radius"]) if radius_features else None
    for region in regions.values():
        if region is body:
            continue
        bounds = region["bounds"]
        inserts.append({
            "part_id": region["id"], "region_id": region["id"],
            "material_code": region.get("material_id") or "insert",
            "dimensions_mm": {"width_mm": _span(region, "x"), "depth_mm": _span(region, "y"), "height_mm": _span(region, "z")},
            "origin_mm": [float(bounds[axis][0]) for axis in ("x", "y", "z")],
            "top_corner_radius_mm": top_radius,
        })
    if not inserts:
        raise ValueError("V3_INSERT_REGION_REQUIRED")
    return {
        "item_code": item_id,
        "name": f"AI_DG_V3_{item_id}",
        "model_revision": model_revision,
        "geometry_hash": geometry_hash_v3(geometry),
        "body": {"part_id": body["id"], "region_id": body["id"], "profile_id": profile_id, "length_mm": length, "profile_yz_mm": profile, "material_code": body.get("material_id") or "body"},
        "inserts": inserts,
        "schema_version": 3,
        "pipeline_stage": "RECONSTRUCTION-V3",
        "tool_name": "ai_dg_execute_build_ir_v3",
        "approval_mode": "user_preapproved_v3",
        "confirm_write": True,
    }


def execute_hypothesis_v3(
    item_id: str,
    geometry: dict[str, Any],
    section_graph: dict[str, Any],
    views: list[dict[str, Any]],
    *,
    model_revision: int,
    target: dict[str, Any],
    access_mode: str,
    confirm_write: bool,
    dispatch: Callable[[dict[str, Any]], dict[str, Any]],
    readback: Callable[[str], dict[str, Any]],
) -> dict[str, Any]:
    if not target or not target.get("instance_id") or target.get("status") not in {None, "ONLINE"}:
        return {"status": "BLOCKED", "reason": "EXPLICIT_ONLINE_TARGET_REQUIRED"}
    if access_mode != "write_enabled":
        return {"status": "BLOCKED", "reason": "READ_ONLY_MODE"}
    if confirm_write is not True:
        return {"status": "BLOCKED", "reason": "WRITE_CONFIRMATION_REQUIRED"}
    operation = build_native_operation_v3(item_id, geometry, section_graph, model_revision=model_revision)
    write_result = dispatch(operation)
    if write_result.get("status") != "ok":
        return {"status": "FAIL", "reason": "SKETCHUP_DISPATCH_FAILED", "operation": operation, "write": write_result}
    response = readback(item_id)
    snapshot = view_back_from_sketchup_readback_v3(item_id, response, views, section_graph, model_revision)
    comparison = compare_view_back_v3(snapshot, views)
    return {"status": comparison["status"], "operation": operation, "write": write_result, "view_back": snapshot, "comparison": comparison}


def run_autonomous_hypothesis_repair_v3(
    payload: dict[str, Any],
    *,
    target: dict[str, Any],
    access_mode: str,
    confirm_write: bool,
    dispatch: Callable[[dict[str, Any]], dict[str, Any]],
    readback: Callable[[str], dict[str, Any]],
    initial_hypothesis_id: str | None = None,
    max_iterations: int = 5,
) -> dict[str, Any]:
    """Build, observe and replace the full item using only viable hypotheses."""
    from .reconstruction_workflow_v3 import build_section_profile_graph_v3, build_view_registry_v3

    registry = build_view_registry_v3(payload, "live-repair")
    sections = build_section_profile_graph_v3(payload, registry)
    item = payload["items"][0]
    item_id = item["item_id"]
    candidates = item.get("hypotheses") or []
    if not candidates:
        raise ValueError("V3_HYPOTHESES_REQUIRED")
    ordered = list(candidates)
    if initial_hypothesis_id:
        ordered.sort(key=lambda row: row.get("hypothesis_id") != initial_hypothesis_id)
    attempted_hashes: set[str] = set()
    history = []
    for revision, candidate in enumerate(ordered[:max_iterations], start=1):
        geometry = copy.deepcopy(item)
        geometry.update(copy.deepcopy(candidate.get("geometry") or {}))
        geometry = {key: geometry.get(key, default) for key, default in (("envelope", {}), ("regions", []), ("features", []), ("section_profile_ids", []), ("relationships", []), ("materials", []))}
        geometry_hash = geometry_hash_v3(geometry)
        if geometry_hash in attempted_hashes:
            continue
        attempted_hashes.add(geometry_hash)
        result = execute_hypothesis_v3(
            item_id, geometry, sections, registry["views"], model_revision=revision,
            target=target, access_mode=access_mode, confirm_write=confirm_write,
            dispatch=dispatch, readback=readback,
        )
        plan = plan_repairs_v3(result.get("comparison", {}), revision) if result.get("comparison") else {"status": "NO_ACTION", "actions": []}
        history.append({"iteration": revision, "hypothesis_id": candidate.get("hypothesis_id"), "geometry_hash": geometry_hash, "status": result["status"], "comparison": result.get("comparison"), "repair_plan": plan, "write": result.get("write")})
        if result["status"] == "PASS":
            return {"schema_version": 3, "status": "PASS", "item_id": item_id, "selected_hypothesis_id": candidate.get("hypothesis_id"), "iterations": history, "target": target}
    return {"schema_version": 3, "status": "REVIEW_REQUIRED", "reason": "NO_HYPOTHESIS_PASSED_NATIVE_VIEW_BACK", "item_id": item_id, "iterations": history, "target": target}
