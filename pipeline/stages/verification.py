"""Verification Engine (M7).

Compares a built 3D model measurement set against the ModelSpec derived from
the reconciled 2D drawings.  A PASS requires every buildable envelope dimension
within tolerance; anything else is FAIL or PARTIAL with the offending
dimensions listed so the autonomous loop can re-plan.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_TOLERANCE_MM = 2.0
DEFAULT_POSITION_TOLERANCE_MM = 2.0
DEFAULT_ANGLE_TOLERANCE_DEG = 0.5
REQUIRED_DIMS = ("width", "depth", "height")


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class VerificationReport:
    run_id: str
    schema_version: str = "0.1"
    status: str = "PASS"
    items: list[dict[str, Any]] = field(default_factory=list)
    tolerance_policy: dict[str, float] = field(default_factory=lambda: {
        "dimension_mm": DEFAULT_TOLERANCE_MM,
        "position_mm": DEFAULT_POSITION_TOLERANCE_MM,
        "angle_deg": DEFAULT_ANGLE_TOLERANCE_DEG,
    })
    generated_utc: str = field(default_factory=utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "run_id": self.run_id,
            "generated_utc": self.generated_utc,
            "status": self.status,
            "tolerance_policy": self.tolerance_policy,
            "items": self.items,
        }


def verify_model_vs_spec(
    spec_items: list[dict[str, Any]],
    model_measurements: dict[str, dict[str, Any]],
    run_id: str = "",
    tolerance_mm: float = DEFAULT_TOLERANCE_MM,
    position_tolerance_mm: float = DEFAULT_POSITION_TOLERANCE_MM,
    angle_tolerance_deg: float = DEFAULT_ANGLE_TOLERANCE_DEG,
) -> VerificationReport:
    """Compare dimensions and optional position/angle/material/hierarchy evidence."""
    report = VerificationReport(
        run_id=run_id,
        tolerance_policy={
            "dimension_mm": float(tolerance_mm),
            "position_mm": float(position_tolerance_mm),
            "angle_deg": float(angle_tolerance_deg),
        },
    )
    all_pass = True

    for item in spec_items:
        code = str(item.get("item_code") or "UNKNOWN")
        expected = item.get("dimensions_mm") or {}
        measured = model_measurements.get(code) or {}
        checks = []
        item_pass = True

        for dim in REQUIRED_DIMS:
            expected_entry = expected.get(dim) or {}
            expected_value = expected_entry.get("value_mm")
            if expected_value is None:
                checks.append(
                    {
                        "dimension": dim,
                        "expected_mm": None,
                        "actual_mm": measured.get(dim),
                        "state": "SKIP_NO_EXPECTATION",
                        "pass": None,
                    }
                )
                continue
            actual = measured.get(dim)
            if actual is None:
                checks.append(
                    {
                        "dimension": dim,
                        "expected_mm": expected_value,
                        "actual_mm": None,
                        "state": "MISSING_MEASUREMENT",
                        "pass": False,
                    }
                )
                item_pass = False
                continue
            deviation = abs(float(actual) - float(expected_value))
            ok = deviation <= tolerance_mm
            item_pass = item_pass and ok
            checks.append(
                {
                    "dimension": dim,
                    "expected_mm": float(expected_value),
                    "actual_mm": round(float(actual), 3),
                    "deviation_mm": round(deviation, 3),
                    "tolerance_mm": tolerance_mm,
                    "state": "PASS" if ok else "FAIL",
                    "pass": ok,
                }
            )

        expected_position = expected.get("position_mm")
        actual_position = measured.get("position_mm")
        if isinstance(expected_position, (list, tuple)):
            if not isinstance(actual_position, (list, tuple)) or len(actual_position) != len(expected_position):
                checks.append({"field": "position_mm", "expected": expected_position, "actual": actual_position, "state": "MISSING_MEASUREMENT", "pass": False})
                item_pass = False
            else:
                deviations = [abs(float(actual) - float(target)) for actual, target in zip(actual_position, expected_position)]
                ok = max(deviations, default=0.0) <= position_tolerance_mm
                checks.append({"field": "position_mm", "expected": list(expected_position), "actual": list(actual_position), "max_deviation_mm": round(max(deviations, default=0.0), 3), "tolerance_mm": position_tolerance_mm, "state": "PASS" if ok else "FAIL", "pass": ok})
                item_pass = item_pass and ok

        expected_angles = expected.get("angles_deg")
        actual_angles = measured.get("angles_deg")
        if isinstance(expected_angles, (list, tuple)):
            if not isinstance(actual_angles, (list, tuple)) or len(actual_angles) != len(expected_angles):
                checks.append({"field": "angles_deg", "expected": expected_angles, "actual": actual_angles, "state": "MISSING_MEASUREMENT", "pass": False})
                item_pass = False
            else:
                deviations = [abs(float(actual) - float(target)) for actual, target in zip(actual_angles, expected_angles)]
                ok = max(deviations, default=0.0) <= angle_tolerance_deg
                checks.append({"field": "angles_deg", "expected": list(expected_angles), "actual": list(actual_angles), "max_deviation_deg": round(max(deviations, default=0.0), 3), "tolerance_deg": angle_tolerance_deg, "state": "PASS" if ok else "FAIL", "pass": ok})
                item_pass = item_pass and ok

        expected_materials = sorted(str(value) for value in (item.get("materials") or []))
        if expected_materials:
            actual_materials = sorted(str(value) for value in (measured.get("materials") or []))
            ok = set(expected_materials).issubset(set(actual_materials))
            checks.append({"field": "materials", "expected": expected_materials, "actual": actual_materials, "state": "PASS" if ok else "FAIL", "pass": ok})
            item_pass = item_pass and ok

        expected_tag = item.get("tag")
        if expected_tag:
            actual_tag = measured.get("tag")
            ok = str(actual_tag) == str(expected_tag)
            checks.append({"field": "tag", "expected": expected_tag, "actual": actual_tag, "state": "PASS" if ok else "FAIL", "pass": ok})
            item_pass = item_pass and ok

        expected_hierarchy = item.get("hierarchy_path")
        if expected_hierarchy:
            actual_hierarchy = measured.get("hierarchy_path")
            ok = actual_hierarchy == expected_hierarchy
            checks.append({"field": "hierarchy_path", "expected": expected_hierarchy, "actual": actual_hierarchy, "state": "PASS" if ok else "FAIL", "pass": ok})
            item_pass = item_pass and ok

        all_pass = all_pass and item_pass
        report.items.append(
            {
                "item_code": code,
                "status": "PASS" if item_pass else "FAIL",
                "checks": checks,
            }
        )

    report.status = "PASS" if all_pass else "FAIL"
    return report


def save_report(report: VerificationReport, output_path: Path) -> Path:
    output_path = output_path.expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path
