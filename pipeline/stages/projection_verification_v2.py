"""Pre/post-build orthographic projection verification for Build IR V2."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 2


def _check(name: str, passed: bool, expected: Any = None, actual: Any = None) -> dict[str, Any]:
    return {"check": name, "status": "PASS" if passed else "FAIL", "expected": expected, "actual": actual}


def verify_prebuild_projection_v2(build_ir: dict[str, Any]) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    projections: list[dict[str, Any]] = []
    if build_ir.get("schema_version") != 2 or build_ir.get("status") != "READY":
        return {"schema_version": 2, "stage": "prebuild", "status": "FAIL", "checks": [_check("build_ir_ready", False, "READY", build_ir.get("status"))], "projections": []}

    for operation in build_ir.get("operations", []):
        code = operation.get("item_code")
        envelope = operation.get("envelope", {})
        regions = operation.get("regions", [])
        visible = [region for region in regions if region.get("build_geometry") is True]
        contract = operation.get("verification_contract", {})
        views = contract.get("views", [])
        checks.append(_check(f"{code}.front.overall", envelope.get("x_mm") > 0 and envelope.get("z_mm") > 0, {"axes": ["X", "Z"]}, {"x_mm": envelope.get("x_mm"), "z_mm": envelope.get("z_mm")}))

        forbidden = set(contract.get("forbidden_visible_region_ids", []))
        accidentally_visible = sorted(forbidden.intersection(region.get("id") for region in visible))
        checks.append(_check(f"{code}.forbidden_visible_regions", not accidentally_visible, [], accidentally_visible))

        for region in visible:
            bounds = region.get("bounds", {})
            xyz_ok = all(isinstance(bounds.get(axis), list) and len(bounds[axis]) == 2 for axis in ("x", "y", "z"))
            checks.append(_check(f"{code}.{region.get('id')}.bounds", xyz_ok, "X/Y/Z bounds", bounds))
            projections.append({
                "item_code": code,
                "region_id": region.get("id"),
                "front_xz": {"x": bounds.get("x"), "z": bounds.get("z")},
                "side_yz": {"y": bounds.get("y"), "z": bounds.get("z")},
                "material_id": region.get("material_id"),
            })

        expected_visible = set(contract.get("expected_visible_region_ids", []))
        actual_visible = {region.get("id") for region in visible}
        checks.append(_check(f"{code}.visible_region_set", actual_visible == expected_visible, sorted(expected_visible), sorted(actual_visible)))

        material_targets = {edge.get("to") for edge in operation.get("relationships", []) if edge.get("type") == "MATERIAL_OF"}
        checks.append(_check(f"{code}.material_regions", actual_visible.issubset(material_targets), sorted(actual_visible), sorted(material_targets)))

        for hierarchy in contract.get("dimension_hierarchy", []):
            checks.append(_check(f"{code}.hierarchy.{hierarchy.get('parent_span_id')}", hierarchy.get("equation_status") == "PASS", "PASS", hierarchy.get("equation_status")))

        for view in views:
            refs = view.get("source_refs", [])
            checks.append(_check(f"{code}.view_evidence.{view.get('id')}", bool(refs), "source refs", refs))

        front_regions = sorted((row for row in projections if row["item_code"] == code), key=lambda row: row["front_xz"]["z"][0])
        if front_regions:
            z_ranges = [row["front_xz"]["z"] for row in front_regions]
            contiguous = z_ranges[0][0] == 0 and z_ranges[-1][1] == envelope.get("z_mm") and all(a[1] == b[0] for a, b in zip(z_ranges, z_ranges[1:]))
            checks.append(_check(f"{code}.front.vertical_coverage", contiguous, [0, envelope.get("z_mm")], z_ranges))

    status = "PASS" if checks and all(row["status"] == "PASS" for row in checks) else "FAIL"
    return {"schema_version": SCHEMA_VERSION, "stage": "prebuild", "run_id": build_ir.get("run_id", ""), "status": status, "checks": checks, "projections": projections}


def verify_postbuild_projection_v2(build_ir: dict[str, Any], readback: dict[str, Any], tolerance_mm: float = 1.0) -> dict[str, Any]:
    """Compare official Ruby region read-back with the pre-build contract."""
    pre = verify_prebuild_projection_v2(build_ir)
    checks = [_check("prebuild_projection", pre.get("status") == "PASS", "PASS", pre.get("status"))]
    expected = {row["region_id"]: row for row in pre.get("projections", [])}
    actual_regions = {row.get("region_id"): row for row in readback.get("regions", [])}
    for region_id, projection in expected.items():
        actual = actual_regions.get(region_id, {})
        expected_bounds = {"x": projection["front_xz"]["x"], "y": projection["side_yz"]["y"], "z": projection["front_xz"]["z"]}
        actual_bounds = actual.get("bounds", {})
        deviations = []
        for axis in ("x", "y", "z"):
            if not isinstance(actual_bounds.get(axis), list):
                deviations.append(float("inf"))
            else:
                deviations.extend(abs(float(a) - float(b)) for a, b in zip(actual_bounds[axis], expected_bounds[axis]))
        checks.append(_check(f"postbuild.{region_id}.bounds", max(deviations, default=float("inf")) <= tolerance_mm, expected_bounds, actual_bounds))
        checks.append(_check(f"postbuild.{region_id}.material", actual.get("material_id") == projection.get("material_id"), projection.get("material_id"), actual.get("material_id")))
    forbidden = {
        region_id for operation in build_ir.get("operations", [])
        for region_id in operation.get("verification_contract", {}).get("forbidden_visible_region_ids", [])
    }
    actual_visible = {row.get("region_id") for row in readback.get("regions", []) if row.get("visible") is True}
    checks.append(_check("postbuild.forbidden_visible_regions", not forbidden.intersection(actual_visible), [], sorted(forbidden.intersection(actual_visible))))
    status = "PASS" if checks and all(row["status"] == "PASS" for row in checks) else "FAIL"
    return {"schema_version": SCHEMA_VERSION, "stage": "postbuild", "run_id": build_ir.get("run_id", ""), "status": status, "checks": checks}


def save_projection_report_v2(report: dict[str, Any], path: str | Path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return target
