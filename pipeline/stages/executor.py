"""Build-plan executor and official SketchUp read-back contract (M6-M7).

The executor is deliberately transport-agnostic.  The MCP layer supplies a
dispatch callback backed by the official Ruby bridge and a read-back callback
backed by ``get_semantic_item``.  No operation is dispatched unless all three
gates are explicit: APPROVED source review, WRITE ENABLED runtime state, and a
per-call confirmation.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable

from .verification import verify_model_vs_spec


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _measurement_from_readback(item_code: str, readback: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(readback, dict) or readback.get("status") != "ok":
        return None
    data = readback.get("data") if isinstance(readback.get("data"), dict) else {}
    if data.get("found") is not True:
        return None
    root = data.get("root") if isinstance(data.get("root"), dict) else {}
    bounds = root.get("bounds_mm")
    if not isinstance(bounds, list) or len(bounds) != 3:
        return None
    materials: set[str] = set()
    for part in data.get("parts", []) if isinstance(data.get("parts"), list) else []:
        attributes = part.get("attributes") if isinstance(part, dict) and isinstance(part.get("attributes"), dict) else {}
        ai_dg = attributes.get("AI_DG") if isinstance(attributes.get("AI_DG"), dict) else {}
        material_code = str(ai_dg.get("material_code") or "").strip()
        if material_code:
            materials.add(material_code)
    measurement = {
        "width": float(bounds[0]),
        "depth": float(bounds[1]),
        "height": float(bounds[2]),
        "materials": sorted(materials),
        "readback_source": "official_sketchup_ruby_api",
        "item_code": item_code,
    }
    return measurement


def execute_build_plan(
    build_plan: dict[str, Any],
    spec_items: list[dict[str, Any]],
    run_id: str,
    review_status: str,
    access_mode: str,
    confirm_write: bool,
    dispatch: Callable[[dict[str, Any]], dict[str, Any]],
    readback: Callable[[str], dict[str, Any]],
) -> dict[str, Any]:
    """Execute approved semantic operations and verify each item by read-back."""
    generated = utcnow()
    normalized_review = str(review_status or "OPEN").upper()
    if normalized_review != "APPROVED":
        return {
            "status": "BLOCKED",
            "run_id": run_id,
            "reason": "REVIEW_APPROVAL_REQUIRED",
            "review_status": normalized_review,
            "generated_utc": generated,
            "operations": [],
            "measurements": {},
        }
    if access_mode != "write_enabled":
        return {
            "status": "BLOCKED",
            "run_id": run_id,
            "reason": "READ_ONLY_MODE",
            "access_mode": access_mode,
            "generated_utc": generated,
            "operations": [],
            "measurements": {},
        }
    if not confirm_write:
        return {
            "status": "BLOCKED",
            "run_id": run_id,
            "reason": "WRITE_CONFIRMATION_REQUIRED",
            "access_mode": access_mode,
            "generated_utc": generated,
            "operations": [],
            "measurements": {},
        }

    operations = build_plan.get("operations") if isinstance(build_plan, dict) else []
    blocked_items = build_plan.get("blocked_items") if isinstance(build_plan, dict) else []
    if isinstance(blocked_items, list) and blocked_items:
        return {
            "status": "BLOCKED",
            "run_id": run_id,
            "reason": "PLAN_HAS_BLOCKED_ITEMS",
            "generated_utc": generated,
            "operations": [],
            "blocked_items": blocked_items,
            "measurements": {},
        }
    if not isinstance(operations, list) or not operations:
        return {
            "status": "BLOCKED",
            "run_id": run_id,
            "reason": "NO_BUILD_OPERATIONS",
            "generated_utc": generated,
            "operations": [],
            "measurements": {},
        }

    spec_by_code = {
        str(item.get("item_code")): item
        for item in spec_items
        if isinstance(item, dict) and item.get("item_code")
    }
    operation_results: list[dict[str, Any]] = []
    measurements: dict[str, dict[str, Any]] = {}
    failed = False

    for operation in operations:
        if not isinstance(operation, dict):
            operation_results.append({"status": "FAIL", "reason": "INVALID_BUILD_OPERATION"})
            failed = True
            break
        op_type = str(operation.get("op") or "")
        if op_type == "ATTACH_META":
            # create_semantic_item attaches provenance inside the same
            # transaction, so a second write would be redundant and unsafe.
            operation_results.append({
                "op": op_type,
                "op_id": operation.get("op_id"),
                "status": "PASS",
                "execution": "included_in_create_semantic_item_transaction",
            })
            continue
        if op_type != "CREATE_SEMANTIC_ITEM":
            operation_results.append({"op": op_type, "op_id": operation.get("op_id"), "status": "FAIL", "reason": "UNSUPPORTED_BUILD_OPERATION"})
            failed = True
            break

        item_code = str(operation.get("item_code") or "").strip()
        if not item_code or item_code not in spec_by_code:
            operation_results.append({"op": op_type, "op_id": operation.get("op_id"), "status": "FAIL", "reason": "SPEC_ITEM_NOT_FOUND", "item_code": item_code})
            failed = True
            break
        payload = {
            "item_code": item_code,
            "name": operation.get("name") or f"ITEM {item_code}",
            "parts": operation.get("parts"),
            "source_refs": operation.get("source_refs") or [],
            "schema_version": "0.1",
            "pipeline_stage": "M6-BUILD",
            "builder_type": "component_from_spec",
            "tool_name": "sketchup_create_semantic_item",
        }
        result = dispatch(payload)
        result_row = {
            "op": op_type,
            "op_id": operation.get("op_id"),
            "item_code": item_code,
            "status": "PASS" if result.get("status") == "ok" else "FAIL",
            "operation_id": result.get("operation_id"),
            "root_persistent_id": result.get("root_persistent_id"),
            "verified_by_bridge": result.get("verified"),
            "error": result.get("error"),
        }
        operation_results.append(result_row)
        if result.get("status") != "ok":
            failed = True
            break

        readback_result = readback(item_code)
        measurement = _measurement_from_readback(item_code, readback_result)
        result_row["readback"] = "PASS" if measurement else "FAIL"
        if measurement:
            measurements[item_code] = measurement
        else:
            result_row["readback_error"] = readback_result.get("error")
            failed = True
            break

    verification = verify_model_vs_spec(spec_items, measurements, run_id=run_id)
    execution_status = "PASS" if not failed and verification.status == "PASS" else "FAIL"
    return {
        "status": execution_status,
        "run_id": run_id,
        "review_status": normalized_review,
        "access_mode": access_mode,
        "generated_utc": generated,
        "operations": operation_results,
        "measurements": measurements,
        "verification": verification.to_dict(),
    }
