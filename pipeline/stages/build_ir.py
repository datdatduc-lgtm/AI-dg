"""Deterministic Build IR and readable code generation (M8-M9).

Build IR is the portable source of truth between the reviewed ModelSpec and
any executor.  It contains semantic operations only; it never contains raw
SketchUp face/edge code and it never invents dimensions, materials, or parts.

The generated Python and Ruby files are representations for inspection and
integration tests.  Production execution still goes through the controlled
MCP handlers and the official SketchUp Ruby bridge.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


BUILD_IR_SCHEMA_VERSION = 1
_DIMENSIONS = ("width_mm", "depth_mm", "height_mm")


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slug(value: Any) -> str:
    text = re.sub(r"[^A-Za-z0-9_.-]+", "-", str(value or "UNKNOWN")).strip("-")
    return text[:80] or "UNKNOWN"


def _number(value: Any, field_name: str, *, positive: bool = True) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field_name} must be numeric")
    number = float(value)
    if not math.isfinite(number) or (positive and number <= 0):
        raise ValueError(f"{field_name} must be finite and {'positive' if positive else 'valid'}")
    return round(number, 3)


def _origin(value: Any) -> list[float]:
    if value is None:
        return [0.0, 0.0, 0.0]
    if not isinstance(value, list) or len(value) != 3:
        raise ValueError("origin_mm must contain exactly three numbers")
    return [_number(entry, "origin_mm", positive=False) for entry in value]


def _source_refs(value: Any) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError("source_refs must be an array")
    return sorted({str(entry).strip() for entry in value if str(entry).strip()})


def _part(part: Any, item_code: str) -> dict[str, Any]:
    if not isinstance(part, dict):
        raise ValueError(f"{item_code}: every part must be an object")
    part_id = str(part.get("part_id") or "").strip()
    if not part_id:
        raise ValueError(f"{item_code}: every part needs an explicit part_id")
    dims = part.get("dimensions_mm")
    if not isinstance(dims, dict):
        raise ValueError(f"{item_code}/{part_id}: dimensions_mm is required")
    normalized_dims = {
        field: _number(dims.get(field), f"{item_code}/{part_id}.{field}")
        for field in _DIMENSIONS
    }
    material_code = str(part.get("material_code") or "").strip()
    return {
        "part_id": part_id,
        "role": str(part.get("role") or "unspecified").strip() or "unspecified",
        "dimensions_mm": normalized_dims,
        "origin_mm": _origin(part.get("origin_mm")),
        "material_code": material_code,
        "source_refs": _source_refs(part.get("source_refs")),
    }


def _item_operation(item: Any, run_id: str) -> dict[str, Any]:
    if not isinstance(item, dict):
        raise ValueError("ModelSpec items must be objects")
    item_code = str(item.get("item_code") or "").strip()
    if not item_code:
        raise ValueError("ModelSpec item_code is required")
    dimensions = item.get("dimensions_mm")
    if not isinstance(dimensions, dict):
        raise ValueError(f"{item_code}: dimensions_mm is required")
    envelope = {}
    for field in _DIMENSIONS:
        short_field = field.removesuffix("_mm")
        candidate = dimensions.get(field) or dimensions.get(short_field)
        if not isinstance(candidate, dict):
            raise ValueError(f"{item_code}: {field} evidence is required")
        if candidate.get("buildable") is not True:
            raise ValueError(f"{item_code}: {field} is not buildable")
        envelope[field] = _number(candidate.get("value_mm"), f"{item_code}.{field}")

    raw_parts = item.get("parts")
    if not isinstance(raw_parts, list) or not raw_parts:
        raise ValueError(f"{item_code}: explicit semantic parts are required")
    parts = sorted((_part(part, item_code) for part in raw_parts), key=lambda part: part["part_id"])

    raw_materials = item.get("materials")
    if raw_materials is None:
        raw_materials = []
    if not isinstance(raw_materials, list):
        raise ValueError(f"{item_code}: materials must be an array")
    materials = {str(code).strip() for code in raw_materials if str(code).strip()}
    materials.update(part["material_code"] for part in parts if part["material_code"])
    source_refs = set(_source_refs(item.get("source_refs")))
    for part in parts:
        source_refs.update(part["source_refs"])
    if not source_refs:
        raise ValueError(f"{item_code}: source_refs are required for Build IR")

    operation_id = f"build-{_slug(run_id)}-{_slug(item_code)}"
    return {
        "operation": "create_semantic_item",
        "id": operation_id,
        "tool": "sketchup_create_semantic_item",
        "item_id": item_code,
        "item_code": item_code,
        "name": str(item.get("name") or f"ITEM {item_code}"),
        "dimensions_mm": envelope,
        "materials": sorted(materials),
        "parts": parts,
        "source_refs": sorted(source_refs),
        "readback": {
            "tool": "sketchup_get_semantic_item",
            "key": "item_code",
            "value": item_code,
        },
    }


@dataclass
class BuildIR:
    run_id: str
    source_review_status: str
    status: str = "REVIEW_REQUIRED"
    operations: list[dict[str, Any]] = field(default_factory=list)
    blocked_items: list[dict[str, Any]] = field(default_factory=list)
    generated_utc: str = field(default_factory=utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": BUILD_IR_SCHEMA_VERSION,
            "run_id": self.run_id,
            "source": {"type": "ModelSpec", "review_status": self.source_review_status},
            "status": self.status,
            "operations": self.operations,
            "blocked_items": self.blocked_items,
            "generated_utc": self.generated_utc,
        }


def build_from_model_spec(model_spec: dict[str, Any]) -> BuildIR:
    """Convert a ModelSpec into Build IR without inference.

    A rejected item is recorded in ``blocked_items`` rather than being
    silently omitted.  The operation order and IDs are stable for the same
    run_id and source ModelSpec.
    """
    if not isinstance(model_spec, dict):
        raise ValueError("model_spec must be an object")
    run_id = str(model_spec.get("run_id") or "").strip()
    review_status = str(model_spec.get("source_review_status") or "OPEN").strip().upper()
    result = BuildIR(run_id=run_id, source_review_status=review_status)
    items = model_spec.get("items")
    if not isinstance(items, list):
        raise ValueError("ModelSpec items must be an array")

    for item in sorted(items, key=lambda value: str(value.get("item_code") if isinstance(value, dict) else "")):
        item_code = str(item.get("item_code") or "UNKNOWN") if isinstance(item, dict) else "UNKNOWN"
        if review_status != "APPROVED":
            result.blocked_items.append({
                "item_code": item_code,
                "reason": "REVIEW_APPROVAL_REQUIRED",
                "message": "Source Review must be APPROVED before Build IR can execute.",
            })
            continue
        if not isinstance(item, dict) or item.get("buildable_state") != "READY":
            result.blocked_items.append({
                "item_code": item_code,
                "reason": "MODEL_SPEC_NOT_READY",
                "message": "Only READY ModelSpec items may enter Build IR.",
            })
            continue
        try:
            result.operations.append(_item_operation(item, run_id))
        except ValueError as exc:
            result.blocked_items.append({
                "item_code": item_code,
                "reason": "BUILD_IR_VALIDATION_FAILED",
                "message": str(exc),
            })

    if result.blocked_items:
        result.status = "BLOCKED" if review_status == "APPROVED" else "REVIEW_REQUIRED"
    elif result.operations:
        result.status = "READY"
    else:
        result.status = "BLOCKED"
    return result


def validate_build_ir(build_ir: dict[str, Any]) -> list[str]:
    """Return deterministic validation errors for an execution boundary."""
    errors: list[str] = []
    if not isinstance(build_ir, dict):
        return ["Build IR must be an object"]
    if build_ir.get("schema_version") != BUILD_IR_SCHEMA_VERSION:
        errors.append("unsupported Build IR schema_version")
    if build_ir.get("status") != "READY":
        errors.append("Build IR status must be READY")
    operations = build_ir.get("operations")
    if not isinstance(operations, list) or not operations:
        errors.append("Build IR must contain at least one operation")
        return errors
    seen: set[str] = set()
    for operation in operations:
        if not isinstance(operation, dict):
            errors.append("operation must be an object")
            continue
        operation_id = str(operation.get("id") or "")
        if not operation_id or operation_id in seen:
            errors.append(f"duplicate or missing operation id: {operation_id or '<empty>'}")
        seen.add(operation_id)
        if operation.get("operation") != "create_semantic_item":
            errors.append(f"unsupported operation: {operation.get('operation')}")
        if not operation.get("source_refs"):
            errors.append(f"{operation.get('item_code', '<unknown>')}: source_refs required")
    return errors


def save_build_ir(build_ir: BuildIR | dict[str, Any], output_path: Path) -> Path:
    output_path = output_path.expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = build_ir.to_dict() if isinstance(build_ir, BuildIR) else build_ir
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=False), encoding="utf-8")
    return output_path


def load_build_ir(path: Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def codegen_json(build_ir: dict[str, Any]) -> str:
    return json.dumps(build_ir, ensure_ascii=False, indent=2) + "\n"


def codegen_python(build_ir: dict[str, Any]) -> str:
    literal = repr(build_ir)
    return (
        "# Generated from AI-DG Build IR; dispatch through MCP, never eval arbitrary code.\n"
        f"BUILD_IR = {literal}\n\n"
        "def commands(build_ir):\n"
        "    return [(op['tool'], op) for op in build_ir['operations']]\n"
    )


def codegen_ruby(build_ir: dict[str, Any]) -> str:
    payload = json.dumps(build_ir, ensure_ascii=False, indent=2)
    return (
        "# Generated from AI-DG Build IR.\n"
        "# Inspection/integration representation only; use controlled MCP handlers.\n"
        "require 'json'\n\n"
        "AI_DG_BUILD_IR = JSON.parse(<<~'AI_DG_BUILD_IR_JSON')\n"
        f"{payload}\n"
        "AI_DG_BUILD_IR_JSON\n\n"
        "AI_DG_COMMANDS = AI_DG_BUILD_IR.fetch('operations').map do |operation|\n"
        "  { 'tool' => operation.fetch('tool'), 'arguments' => operation }\n"
        "end\n"
    )


def generate_codegen(build_ir: dict[str, Any]) -> dict[str, str]:
    errors = validate_build_ir(build_ir)
    if errors:
        raise ValueError("Build IR is not executable: " + "; ".join(errors))
    return {
        "json": codegen_json(build_ir),
        "python": codegen_python(build_ir),
        "ruby": codegen_ruby(build_ir),
    }
