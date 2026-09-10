"""Semantic view-back and cross-view comparison for reconstruction V3."""

from __future__ import annotations

import copy
import hashlib
import json
from typing import Any


MISMATCH_STAGE = {
    "VIEW_NOT_LINKED": "view_link_graph",
    "AXIS_MAPPING_ERROR": "view_registry",
    "OVERALL_DIMENSION_MISMATCH": "geometry_constraints",
    "REGION_BOUNDARY_MISMATCH": "region_graph",
    "SECTION_PROFILE_MISMATCH": "section_profile_graph",
    "FEATURE_MISSING": "section_profile_graph",
    "FEATURE_EXTRA": "section_profile_graph",
    "FEATURE_WRONG_DEPTH": "section_profile_graph",
    "FEATURE_WRONG_POSITION": "section_profile_graph",
    "VISIBLE_EDGE_EXTRA": "region_graph",
    "VISIBLE_EDGE_MISSING": "region_graph",
    "MATERIAL_REGION_MISMATCH": "material_spatial_graph",
    "THICKNESS_MISMATCH": "section_profile_graph",
    "RELATIONSHIP_MISMATCH": "region_graph",
    "PLACEMENT_MISMATCH": "model_spec",
    "ROTATION_MISMATCH": "model_spec",
    "STALE_VERIFICATION": "view_back",
}


def _geometry_hash(geometry: Any) -> str:
    return hashlib.sha256(json.dumps(geometry, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _project_bounds(bounds: dict[str, Any], axes: list[str]) -> dict[str, Any]:
    return {axis: copy.deepcopy(bounds.get(axis.lower())) for axis in axes}


def project_hypothesis_v3(hypothesis: dict[str, Any], views: list[dict[str, Any]], section_graph: dict[str, Any], model_revision: int) -> dict[str, Any]:
    geometry = hypothesis["geometry"]
    profile_lookup = {row["profile_id"]: row for row in section_graph.get("profiles", [])}
    projected_views = []
    for view in views:
        axes = view["projection_axes"]
        is_cut = view["view_type"] in {"SECTION", "DETAIL"}
        regions = []
        for region in geometry.get("regions", []):
            visibility = region.get("visibility", "VISIBLE")
            if visibility == "SECTION_ONLY" and not is_cut:
                continue
            regions.append({
                "region_id": region.get("id"),
                "bounds": _project_bounds(region.get("bounds", {}), axes),
                "material_id": region.get("material_id"),
                "visibility": visibility,
            })
        profiles = []
        if is_cut:
            accepted_view_ids = {view["view_id"]}
            if view.get("refines_view_id"):
                accepted_view_ids.add(view["refines_view_id"])
            profiles = [
                copy.deepcopy(profile_lookup[profile_id])
                for profile_id in geometry.get("section_profile_ids", [])
                if profile_id in profile_lookup and profile_lookup[profile_id]["view_id"] in accepted_view_ids
            ]
        projected_views.append({
            "view_id": view["view_id"],
            "view_type": view["view_type"],
            "projection_axes": axes,
            "model_revision": model_revision,
            "geometry_hash": hypothesis.get("geometry_hash") or _geometry_hash(geometry),
            "overall": {axis: geometry.get("envelope", {}).get(f"{axis.lower()}_mm") for axis in axes},
            "regions": regions,
            "section_profiles": profiles,
            "features": [
                copy.deepcopy(feature)
                for feature in geometry.get("features", [])
                if not feature.get("view_types") or view["view_type"] in feature.get("view_types", [])
            ],
        })
    return {"schema_version": 3, "item_id": hypothesis["item_id"], "model_revision": model_revision, "geometry_hash": hypothesis.get("geometry_hash") or _geometry_hash(geometry), "views": projected_views}


def _equal_number(actual: Any, expected: Any, tolerance: float) -> bool:
    return isinstance(actual, (int, float)) and isinstance(expected, (int, float)) and abs(float(actual) - float(expected)) <= tolerance


def compare_view_back_v3(view_back: dict[str, Any], views: list[dict[str, Any]], tolerance_mm: float = 1.0) -> dict[str, Any]:
    actual_by_id = {row["view_id"]: row for row in view_back.get("views", [])}
    checks = []
    mismatches = []
    expected_revision = view_back.get("model_revision")
    expected_hash = view_back.get("geometry_hash")

    def record(view_id: str, check: str, passed: bool, mismatch_type: str, expected: Any, actual: Any) -> None:
        checks.append({"view_id": view_id, "check": check, "status": "PASS" if passed else "FAIL", "expected": expected, "actual": actual})
        if not passed:
            mismatches.append({"view_id": view_id, "type": mismatch_type, "source_stage": MISMATCH_STAGE[mismatch_type], "expected": expected, "actual": actual})

    for view in views:
        view_id = view["view_id"]
        actual = actual_by_id.get(view_id)
        if not actual:
            record(view_id, "view_exists", not view["mandatory"], "VIEW_NOT_LINKED", "projected view", None)
            continue
        fresh = actual.get("model_revision") == expected_revision and actual.get("geometry_hash") == expected_hash
        record(view_id, "revision_fresh", fresh, "STALE_VERIFICATION", {"model_revision": expected_revision, "geometry_hash": expected_hash}, {"model_revision": actual.get("model_revision"), "geometry_hash": actual.get("geometry_hash")})
        expects = view.get("verification_contract") or {}
        for axis, expected in (expects.get("overall_mm") or {}).items():
            observed = actual.get("overall", {}).get(str(axis).upper())
            record(view_id, f"overall.{str(axis).upper()}", _equal_number(observed, expected, tolerance_mm), "OVERALL_DIMENSION_MISMATCH", expected, observed)
        actual_regions = {row.get("region_id"): row for row in actual.get("regions", [])}
        expected_visible = set(expects.get("visible_region_ids", []))
        if expected_visible:
            observed = {key for key, row in actual_regions.items() if row.get("visibility") != "SECTION_ONLY"}
            record(view_id, "visible_regions", expected_visible == observed, "VISIBLE_EDGE_MISSING" if expected_visible - observed else "VISIBLE_EDGE_EXTRA", sorted(expected_visible), sorted(observed))
        forbidden = set(expects.get("forbidden_visible_region_ids", []))
        observed_forbidden = sorted(forbidden.intersection(actual_regions))
        record(view_id, "forbidden_regions", not observed_forbidden, "VISIBLE_EDGE_EXTRA", [], observed_forbidden)
        for region_id, expected_axes in (expects.get("region_spans") or {}).items():
            observed_region = actual_regions.get(region_id)
            if not observed_region:
                record(view_id, f"region.{region_id}", False, "REGION_BOUNDARY_MISMATCH", expected_axes, None)
                continue
            for axis, expected_span in expected_axes.items():
                observed_span = observed_region.get("bounds", {}).get(str(axis).upper())
                passed = isinstance(observed_span, list) and len(observed_span) == len(expected_span) and all(_equal_number(a, b, tolerance_mm) for a, b in zip(observed_span, expected_span))
                record(view_id, f"region.{region_id}.{str(axis).upper()}", passed, "REGION_BOUNDARY_MISMATCH", expected_span, observed_span)
        actual_features = {feature.get("feature_id") or feature.get("id"): feature for profile in actual.get("section_profiles", []) for feature in profile.get("features", [])}
        expected_features = {feature.get("feature_id") or feature.get("id"): feature for feature in expects.get("section_features", [])}
        for feature_id, expected_feature in expected_features.items():
            observed = actual_features.get(feature_id)
            record(view_id, f"feature.{feature_id}.exists", observed is not None, "FEATURE_MISSING", expected_feature, observed)
            if observed is None:
                continue
            record(view_id, f"feature.{feature_id}.type", observed.get("type") == expected_feature.get("type"), "SECTION_PROFILE_MISMATCH", expected_feature.get("type"), observed.get("type"))
            for key, expected in (expected_feature.get("dimensions_mm") or {}).items():
                value = (observed.get("dimensions_mm") or {}).get(key)
                mismatch = "FEATURE_WRONG_DEPTH" if "depth" in key else "THICKNESS_MISMATCH" if "thickness" in key else "SECTION_PROFILE_MISMATCH"
                record(view_id, f"feature.{feature_id}.{key}", _equal_number(value, expected, tolerance_mm), mismatch, expected, value)
        extra_features = sorted(set(actual_features) - set(expected_features)) if expected_features else []
        record(view_id, "extra_features", not extra_features, "FEATURE_EXTRA", [], extra_features)
        actual_view_features = {feature.get("feature_id") or feature.get("id"): feature for feature in actual.get("features", [])}
        for feature in expects.get("features", []):
            feature_id = feature.get("feature_id") or feature.get("id")
            observed = actual_view_features.get(feature_id)
            record(view_id, f"view_feature.{feature_id}.exists", observed is not None, "FEATURE_MISSING", feature, observed)
            if observed is None:
                continue
            record(view_id, f"view_feature.{feature_id}.type", observed.get("type") == feature.get("type"), "SECTION_PROFILE_MISMATCH", feature.get("type"), observed.get("type"))
            for key, expected in (feature.get("dimensions_mm") or {}).items():
                value = (observed.get("dimensions_mm") or {}).get(key)
                record(view_id, f"view_feature.{feature_id}.{key}", _equal_number(value, expected, tolerance_mm), "SECTION_PROFILE_MISMATCH", expected, value)

    mandatory_ids = {view["view_id"] for view in views if view["mandatory"]}
    mandatory_failures = [row for row in checks if row["view_id"] in mandatory_ids and row["status"] == "FAIL"]
    passed = sum(row["status"] == "PASS" for row in checks)
    score = round(passed / len(checks), 6) if checks else 0.0
    return {"schema_version": 3, "status": "PASS" if checks and not mandatory_failures else "FAIL", "model_revision": expected_revision, "geometry_hash": expected_hash, "score": score, "checks": checks, "mismatches": mismatches}
