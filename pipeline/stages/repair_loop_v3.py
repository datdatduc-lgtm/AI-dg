"""Bounded upstream repair orchestration for reconstruction V3."""

from __future__ import annotations

import copy
from typing import Any, Callable

from .view_verification_v3 import MISMATCH_STAGE, compare_view_back_v3


MAX_RECONSTRUCTION_ITERATIONS = 5


def plan_repairs_v3(comparison: dict[str, Any], iteration: int) -> dict[str, Any]:
    actions = []
    seen = set()
    for mismatch in comparison.get("mismatches", []):
        key = (mismatch["type"], mismatch["view_id"])
        if key in seen:
            continue
        seen.add(key)
        actions.append({
            "repair_id": f"REPAIR-{iteration:03d}-{len(actions) + 1:03d}",
            "mismatch_type": mismatch["type"],
            "view_id": mismatch["view_id"],
            "patch_stage": MISMATCH_STAGE[mismatch["type"]],
            "expected": mismatch.get("expected"),
            "actual": mismatch.get("actual"),
            "policy": "PATCH_UPSTREAM_AND_REGENERATE",
        })
    return {"schema_version": 3, "iteration": iteration, "status": "READY" if actions else "NO_ACTION", "actions": actions}


def run_repair_loop_v3(
    initial_build_ir: dict[str, Any],
    views: list[dict[str, Any]],
    view_back: Callable[[dict[str, Any], int], dict[str, Any]],
    apply_upstream_repair: Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]] | None = None,
    max_iterations: int = MAX_RECONSTRUCTION_ITERATIONS,
) -> dict[str, Any]:
    """Verify/rebuild until PASS, REVIEW_REQUIRED, STALLED, or iteration cap.

    The callback must patch an upstream representation and regenerate Build IR;
    direct SketchUp edits are intentionally not accepted by this interface.
    """
    if not 1 <= max_iterations <= MAX_RECONSTRUCTION_ITERATIONS:
        raise ValueError(f"max_iterations must be 1..{MAX_RECONSTRUCTION_ITERATIONS}")
    current = copy.deepcopy(initial_build_ir)
    history = []
    best_score = -1.0
    for iteration in range(1, max_iterations + 1):
        snapshot = view_back(current, iteration)
        comparison = compare_view_back_v3(snapshot, views)
        plan = plan_repairs_v3(comparison, iteration)
        history.append({"iteration": iteration, "model_revision": snapshot.get("model_revision"), "geometry_hash": snapshot.get("geometry_hash"), "score": comparison["score"], "status": comparison["status"], "repair_plan": plan})
        if comparison["status"] == "PASS":
            return {"schema_version": 3, "status": "PASS", "iterations": history, "build_ir": current, "comparison": comparison}
        if apply_upstream_repair is None:
            return {"schema_version": 3, "status": "REVIEW_REQUIRED", "reason": "UPSTREAM_REPAIR_CALLBACK_REQUIRED", "iterations": history, "comparison": comparison}
        if comparison["score"] <= best_score:
            return {"schema_version": 3, "status": "STALLED", "reason": "MISMATCH_SCORE_NOT_IMPROVING", "iterations": history, "comparison": comparison}
        best_score = comparison["score"]
        repaired = apply_upstream_repair(copy.deepcopy(current), plan)
        if not isinstance(repaired, dict) or repaired == current:
            return {"schema_version": 3, "status": "STALLED", "reason": "NO_CONSTRAINED_UPSTREAM_CHANGE", "iterations": history, "comparison": comparison}
        current = repaired
    return {"schema_version": 3, "status": "REVIEW_REQUIRED", "reason": "MAX_RECONSTRUCTION_ITERATIONS", "iterations": history, "build_ir": current}
