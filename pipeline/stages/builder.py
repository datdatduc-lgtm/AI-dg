"""Semantic Build Planner (M6).

Turns each buildable ModelSpec item into an ordered, typed Build Operation that
the SketchUp bridge can execute with stress-testable parameters:

    BUILD_ITEM   item_code + width/depth/height/mm + materials
    CREATE_PANEL panel_id + dims + role (body/face/edge)
    ATTACH_META  entity + operation_id (always safe metadata, never guessed)

Every operation is emitted only for items whose source_review_status is
APPROVED and whose envelope is fully buildable.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .build_ir import build_from_model_spec

BUILD_OPS = ("CREATE_SEMANTIC_ITEM", "ATTACH_META")
REQUIRED_BUILD_DIMS = ("width_mm", "depth_mm", "height_mm")


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class BuildPlan:
    run_id: str
    schema_version: str = "0.1"
    operations: list[dict[str, Any]] = field(default_factory=list)
    blocked_items: list[dict[str, Any]] = field(default_factory=list)
    generated_utc: str = field(default_factory=utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "run_id": self.run_id,
            "generated_utc": self.generated_utc,
            "operations": self.operations,
            "blocked_items": self.blocked_items,
        }


def _envelope(item: dict[str, Any]) -> dict[str, float | None]:
    dims = item.get("dimensions_mm") or {}
    return {
        "width_mm": (dims.get("width") or {}).get("value_mm"),
        "depth_mm": (dims.get("depth") or {}).get("value_mm"),
        "height_mm": (dims.get("height") or {}).get("value_mm"),
    }


def plan_build(
    spec_items: list[dict[str, Any]],
    run_id: str,
    source_review_status: str = "APPROVED",
) -> BuildPlan:
    """Generate the legacy Build Plan view from the central Build IR.

    Build Plan remains as a compatibility artifact for the existing executor;
    operation identity and semantic payloads now come from Build IR so the
    plan cannot drift from the code-generation source of truth.
    """
    plan = BuildPlan(run_id=run_id)

    spec = {
        "schema_version": "0.1",
        "run_id": run_id,
        "source_review_status": str(source_review_status or "OPEN").upper(),
        "items": spec_items,
    }
    build_ir = build_from_model_spec(spec).to_dict()
    for blocked in build_ir["blocked_items"]:
        reason = str(blocked.get("message") or "")
        if "semantic parts" in reason.lower():
            blocked = {**blocked, "reason": "SEMANTIC_PARTS_REQUIRED"}
        plan.blocked_items.append(blocked)

    for operation in build_ir["operations"]:
        op_id = operation["id"]
        code = operation["item_code"]
        plan.operations.append(
            {
                "op": "CREATE_SEMANTIC_ITEM",
                "execution_tool": operation["tool"],
                "op_id": op_id,
                "item_code": code,
                "name": operation["name"],
                "dimensions_mm": operation["dimensions_mm"],
                "materials": operation["materials"],
                "parts": operation["parts"],
                "source_refs": operation["source_refs"],
                "expected": operation["dimensions_mm"],
            }
        )
        plan.operations.append(
            {
                "op": "ATTACH_META",
                "op_id": f"{op_id}-meta",
                "ref_op": op_id,
                "metadata": {
                    "item_code": code,
                    "pipeline_stage": "M6-build-plan",
                    "provenance": "2d-source-reconciliation",
                },
            }
        )
    return plan


def save_plan(plan: BuildPlan, output_path: Path) -> Path:
    output_path = output_path.expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(plan.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path


def load_plan(path: Path) -> BuildPlan:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return BuildPlan(
        run_id=data.get("run_id", ""),
        schema_version=data.get("schema_version", "0.1"),
        operations=data.get("operations", []),
        blocked_items=data.get("blocked_items", []),
        generated_utc=data.get("generated_utc", utcnow()),
    )
