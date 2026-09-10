"""Build semantic V3 view-back snapshots from official SketchUp Ruby read-back."""

from __future__ import annotations

from typing import Any

from .reconstruction_workflow_v3 import geometry_hash_v3
from .view_verification_v3 import project_hypothesis_v3


def view_back_from_sketchup_readback_v3(
    item_id: str,
    response: dict[str, Any],
    views: list[dict[str, Any]],
    section_graph: dict[str, Any],
    model_revision: int,
) -> dict[str, Any]:
    """Normalize read-only Ruby data; never substitute expected section data."""
    if response.get("status") != "ok":
        raise ValueError(f"SKETCHUP_READBACK_FAILED: {response.get('error')}")
    data = response.get("data")
    if not isinstance(data, dict):
        raise ValueError("SKETCHUP_READBACK_DATA_REQUIRED")
    root = data.get("root") or {}
    minimum = root.get("min_mm")
    maximum = root.get("max_mm")
    if not isinstance(minimum, list) or not isinstance(maximum, list) or len(minimum) != 3 or len(maximum) != 3:
        raise ValueError("SKETCHUP_ROOT_BOUNDS_REQUIRED")
    envelope = {
        "x_mm": round(float(maximum[0]) - float(minimum[0]), 3),
        "y_mm": round(float(maximum[1]) - float(minimum[1]), 3),
        "z_mm": round(float(maximum[2]) - float(minimum[2]), 3),
    }
    regions = []
    for child in data.get("parts", []):
        attrs = (child.get("attributes") or {}).get("AI_DG", {})
        child_min = child.get("min_mm")
        child_max = child.get("max_mm")
        if not isinstance(child_min, list) or not isinstance(child_max, list) or len(child_min) != 3 or len(child_max) != 3:
            continue
        regions.append({
            "id": attrs.get("region_id") or attrs.get("part_id"),
            "visibility": attrs.get("visibility", "VISIBLE"),
            "bounds": {axis: [child_min[index], child_max[index]] for index, axis in enumerate(("x", "y", "z"))},
            "material_id": attrs.get("material_id") or attrs.get("material_code"),
            "persistent_id": child.get("persistent_id"),
        })
    actual_profiles = data.get("analysis_section_profiles")
    if not isinstance(actual_profiles, list):
        actual_profiles = []
    expected_profiles = {row.get("profile_id"): row for row in section_graph.get("profiles", [])}
    routed_profiles = []
    for observed in actual_profiles:
        profile_id = observed.get("profile_id")
        expected = expected_profiles.get(profile_id)
        routed_profiles.append({
            **observed,
            # The expected graph supplies only projection identity. Geometry,
            # dimensions and features remain exclusively native observations.
            "view_id": expected.get("view_id") if expected else observed.get("view_id"),
        })
    actual_section_graph = {"profiles": routed_profiles}
    geometry = {
        "envelope": envelope,
        "regions": regions,
        "features": (data.get("analysis_features") or []) + [feature for row in routed_profiles for feature in row.get("features", [])],
        "section_profile_ids": [row.get("profile_id") for row in routed_profiles if row.get("profile_id")],
        "relationships": data.get("analysis_relationships") or [],
        "materials": [],
    }
    observed_revision = int(data.get("model_revision") or model_revision)
    observed_hash = str(data.get("geometry_hash") or geometry_hash_v3(geometry))
    hypothesis = {"item_id": item_id, "geometry": geometry, "geometry_hash": observed_hash}
    snapshot = project_hypothesis_v3(hypothesis, views, actual_section_graph, observed_revision)
    snapshot["readback_source"] = data.get("readback_source") or "official_sketchup_ruby_api"
    snapshot["target"] = response.get("target")
    snapshot["expected_section_profile_ids"] = [row.get("profile_id") for row in section_graph.get("profiles", [])]
    snapshot["observed_section_profile_ids"] = geometry["section_profile_ids"]
    snapshot["native_analysis_views"] = data.get("analysis_views")
    return snapshot
