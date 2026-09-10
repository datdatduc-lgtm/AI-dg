"""General, evidence-gated multi-view reconstruction workflow.

This module consumes interpreted drawing facts. Extraction/OCR adapters are
separate concerns: no source value is invented here. One physical item may be
linked to views on multiple sheets and may carry several competing 3D
hypotheses until all mandatory view contracts select exactly one.
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Callable


SCHEMA_VERSION = 3
VIEW_TYPES = {
    "FRONT", "BACK", "LEFT", "RIGHT", "PLAN", "SIDE", "SECTION", "DETAIL",
}
FEATURE_TYPES = {
    "SLOT", "GROOVE", "RECESS", "HOLE", "CUTOUT", "CHAMFER", "RADIUS",
    "BEVEL", "LIP", "STEP", "POCKET", "OPENING", "LAYER", "PANEL",
    "GLASS", "HARDWARE_ZONE",
}
BUILDABLE_STATES = {"EXPLICIT", "DERIVED_FROM_VIEWS", "APPROVED_DERIVED"}


def geometry_hash_v3(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _source_refs(value: Any, label: str) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{label}: source_refs required")
    refs = []
    for ref in value:
        if not isinstance(ref, dict) or not ref.get("source_id"):
            raise ValueError(f"{label}: invalid source_ref")
        refs.append(dict(ref))
    return refs


def _normalize_axes(view: dict[str, Any]) -> list[str]:
    axes = [str(axis).upper() for axis in view.get("projection_axes", [])]
    if len(axes) != 2 or len(set(axes)) != 2 or any(axis not in {"X", "Y", "Z"} for axis in axes):
        raise ValueError(f"{view.get('view_id')}: exactly two projection axes required")
    return axes


def build_view_registry_v3(payload: dict[str, Any], run_id: str) -> dict[str, Any]:
    """Normalize sheet regions into a cross-sheet registry of actual views."""
    raw_views = payload.get("views")
    if not isinstance(raw_views, list) or not raw_views:
        raise ValueError("views required")
    views = []
    seen: set[str] = set()
    for raw in raw_views:
        view_id = str(raw.get("view_id") or raw.get("id") or "").strip()
        if not view_id or view_id in seen:
            raise ValueError("view_id missing or duplicated")
        view_type = str(raw.get("view_type") or raw.get("role") or "").upper()
        aliases = {"FRONT_ELEVATION": "FRONT", "SIDE_ELEVATION": "SIDE", "LOCAL_DETAIL": "DETAIL"}
        view_type = aliases.get(view_type, view_type)
        if view_type not in VIEW_TYPES:
            raise ValueError(f"{view_id}: unsupported view_type {view_type}")
        item_refs = [str(value).strip() for value in raw.get("item_refs", []) if str(value).strip()]
        refs = _source_refs(raw.get("source_refs"), view_id)
        views.append({
            "view_id": view_id,
            "sheet_id": str(raw.get("sheet_id") or refs[0].get("sheet_id") or refs[0].get("page") or "UNKNOWN"),
            "view_type": view_type,
            "projection_axes": _normalize_axes(raw),
            "item_refs": item_refs,
            "mandatory": raw.get("mandatory", True) is not False,
            "bbox_on_sheet": raw.get("bbox_on_sheet"),
            "scale": raw.get("scale"),
            "section_marker": raw.get("section_marker"),
            "cut_plane": copy.deepcopy(raw.get("cut_plane")),
            "look_direction": copy.deepcopy(raw.get("look_direction")),
            "refines_view_id": raw.get("refines_view_id"),
            "verification_contract": copy.deepcopy(raw.get("verification_contract") or {}),
            "source_refs": refs,
        })
        seen.add(view_id)
    return {"schema_version": SCHEMA_VERSION, "run_id": run_id, "views": views}


def build_view_link_graph_v3(registry: dict[str, Any], items: list[dict[str, Any]]) -> dict[str, Any]:
    item_ids = {str(item.get("item_id") or item.get("item_code") or "") for item in items}
    view_ids = {view["view_id"] for view in registry["views"]}
    edges = []
    unresolved = []
    for view in registry["views"]:
        if not view["item_refs"]:
            unresolved.append({"type": "VIEW_NOT_LINKED", "view_id": view["view_id"], "impact": "BLOCKING" if view["mandatory"] else "NON_BLOCKING"})
        for item_id in view["item_refs"]:
            if item_id not in item_ids:
                unresolved.append({"type": "VIEW_NOT_LINKED", "view_id": view["view_id"], "item_id": item_id, "impact": "BLOCKING"})
            else:
                edges.append({"type": "PROJECTS_ITEM", "from": view["view_id"], "to": item_id, "source_refs": view["source_refs"]})
        parent = view.get("refines_view_id")
        if parent:
            if parent not in view_ids:
                unresolved.append({"type": "VIEW_NOT_LINKED", "view_id": view["view_id"], "missing_parent": parent, "impact": "BLOCKING"})
            else:
                edges.append({"type": "REFINES_VIEW", "from": view["view_id"], "to": parent, "source_refs": view["source_refs"]})
    return {"schema_version": SCHEMA_VERSION, "run_id": registry["run_id"], "edges": edges, "unresolved": unresolved}


def build_constraint_graph_v3(payload: dict[str, Any], registry: dict[str, Any]) -> dict[str, Any]:
    view_ids = {view["view_id"] for view in registry["views"]}
    nodes = []
    unresolved = []
    for raw in payload.get("constraints", []):
        constraint_id = str(raw.get("constraint_id") or raw.get("id") or "").strip()
        kind = str(raw.get("kind") or "DIMENSION").upper()
        view_id = str(raw.get("view_id") or "")
        state = str(raw.get("state") or "UNKNOWN").upper()
        if not constraint_id or view_id not in view_ids or not raw.get("start_ref") or not raw.get("end_ref"):
            unresolved.append({"type": "AXIS_MAPPING_ERROR", "constraint_id": constraint_id, "impact": "BLOCKING"})
            continue
        node = copy.deepcopy(raw)
        node.update({"constraint_id": constraint_id, "kind": kind, "view_id": view_id, "state": state, "source_refs": _source_refs(raw.get("source_refs"), constraint_id)})
        nodes.append(node)
        if state not in BUILDABLE_STATES:
            unresolved.append({"type": "CONSTRAINT_UNRESOLVED", "constraint_id": constraint_id, "impact": raw.get("impact", "BLOCKING")})
    return {"schema_version": SCHEMA_VERSION, "run_id": registry["run_id"], "nodes": nodes, "unresolved": unresolved}


def build_section_profile_graph_v3(payload: dict[str, Any], registry: dict[str, Any]) -> dict[str, Any]:
    views = {view["view_id"]: view for view in registry["views"]}
    profiles = []
    unresolved = []
    for raw in payload.get("section_profiles", []):
        profile_id = str(raw.get("profile_id") or "").strip()
        view_id = str(raw.get("view_id") or "")
        state = str(raw.get("state") or "UNKNOWN").upper()
        if not profile_id or view_id not in views or views[view_id]["view_type"] not in {"SECTION", "DETAIL"}:
            unresolved.append({"type": "SECTION_PROFILE_MISMATCH", "profile_id": profile_id, "impact": "BLOCKING"})
            continue
        features = []
        for feature in raw.get("features", []):
            feature_type = str(feature.get("type") or "").upper()
            if feature_type not in FEATURE_TYPES:
                unresolved.append({"type": "FEATURE_UNSUPPORTED", "profile_id": profile_id, "feature_type": feature_type, "impact": "BLOCKING"})
                continue
            normalized = copy.deepcopy(feature)
            normalized["type"] = feature_type
            normalized["state"] = str(feature.get("state") or state).upper()
            normalized["source_refs"] = _source_refs(feature.get("source_refs") or raw.get("source_refs"), f"{profile_id}/{feature_type}")
            features.append(normalized)
        profile = copy.deepcopy(raw)
        profile.update({"profile_id": profile_id, "view_id": view_id, "state": state, "features": features, "source_refs": _source_refs(raw.get("source_refs"), profile_id)})
        profiles.append(profile)
        if state not in BUILDABLE_STATES:
            unresolved.append({"type": "SECTION_PROFILE_MISMATCH", "profile_id": profile_id, "impact": "BLOCKING"})
    return {"schema_version": SCHEMA_VERSION, "run_id": registry["run_id"], "profiles": profiles, "unresolved": unresolved}


def _candidate_geometry(item: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    geometry = copy.deepcopy(candidate.get("geometry") or {})
    return {
        "envelope": geometry.get("envelope", item.get("envelope", {})),
        "regions": geometry.get("regions", item.get("regions", [])),
        "features": geometry.get("features", item.get("features", [])),
        "section_profile_ids": geometry.get("section_profile_ids", item.get("section_profile_ids", [])),
        "relationships": geometry.get("relationships", item.get("relationships", [])),
        "materials": geometry.get("materials", item.get("materials", [])),
    }


def build_hypotheses_v3(payload: dict[str, Any], section_graph: dict[str, Any]) -> dict[str, Any]:
    profiles = {row["profile_id"] for row in section_graph["profiles"]}
    hypotheses = []
    for item in payload.get("items", []):
        item_id = str(item.get("item_id") or item.get("item_code") or "").strip()
        if not item_id:
            raise ValueError("item_id required")
        candidates = item.get("hypotheses") or [{"hypothesis_id": f"{item_id}:H1", "state": item.get("state", "EXPLICIT")}]
        for candidate in candidates:
            geometry = _candidate_geometry(item, candidate)
            missing_profiles = sorted(set(geometry["section_profile_ids"]) - profiles)
            hypotheses.append({
                "hypothesis_id": str(candidate.get("hypothesis_id") or f"{item_id}:H{len(hypotheses) + 1}"),
                "item_id": item_id,
                "state": str(candidate.get("state") or "UNKNOWN").upper(),
                "geometry": geometry,
                "geometry_hash": geometry_hash_v3(geometry),
                "source_refs": _source_refs(candidate.get("source_refs") or item.get("source_refs"), item_id),
                "missing_profile_ids": missing_profiles,
            })
    return {"schema_version": SCHEMA_VERSION, "run_id": section_graph["run_id"], "hypotheses": hypotheses}


def generate_model_spec_v3(payload: dict[str, Any], registry: dict[str, Any], links: dict[str, Any], constraints: dict[str, Any], sections: dict[str, Any], hypotheses: dict[str, Any]) -> dict[str, Any]:
    """Select only a uniquely verified hypothesis for each physical item."""
    from .view_verification_v3 import compare_view_back_v3, project_hypothesis_v3

    items = []
    blocking_global = [*links["unresolved"], *constraints["unresolved"], *sections["unresolved"]]
    for raw_item in payload.get("items", []):
        item_id = str(raw_item.get("item_id") or raw_item.get("item_code"))
        linked_views = [view for view in registry["views"] if item_id in view["item_refs"]]
        candidates = [row for row in hypotheses["hypotheses"] if row["item_id"] == item_id and row["state"] in BUILDABLE_STATES and not row["missing_profile_ids"]]
        evaluated = []
        for candidate in candidates:
            view_back = project_hypothesis_v3(candidate, linked_views, sections, model_revision=0)
            comparison = compare_view_back_v3(view_back, linked_views)
            evaluated.append({**candidate, "verification": comparison, "score": comparison["score"]})
        winners = [row for row in evaluated if row["verification"]["status"] == "PASS"]
        unique_hashes = {row["geometry_hash"] for row in winners}
        selected = winners[0] if len(unique_hashes) == 1 and winners else None
        ambiguity = len(unique_hashes) > 1
        blockers = [row for row in blocking_global if row.get("item_id") in {None, item_id}]
        ready = payload.get("source_review_status") == "APPROVED" and selected is not None and not ambiguity and not blockers
        items.append({
            "item_id": item_id,
            "views": linked_views,
            "selected_hypothesis_id": selected["hypothesis_id"] if selected else None,
            "geometry_hash": selected["geometry_hash"] if selected else None,
            "geometry": selected["geometry"] if selected else None,
            "candidate_results": [{"hypothesis_id": row["hypothesis_id"], "geometry_hash": row["geometry_hash"], "score": row["score"], "status": row["verification"]["status"]} for row in evaluated],
            "unresolved": blockers + ([{"type": "HYPOTHESIS_AMBIGUOUS", "impact": "BLOCKING"}] if ambiguity else []),
            "buildable_state": "READY" if ready else "REVIEW_REQUIRED",
            "source_refs": copy.deepcopy(raw_item.get("source_refs", [])),
        })
    return {"schema_version": SCHEMA_VERSION, "run_id": registry["run_id"], "source_review_status": payload.get("source_review_status", "OPEN"), "items": items}


def build_ir_v3(model_spec: dict[str, Any], sections: dict[str, Any]) -> dict[str, Any]:
    profile_lookup = {row["profile_id"]: row for row in sections["profiles"]}
    operations = []
    blocked = []
    for item in model_spec["items"]:
        if item["buildable_state"] != "READY":
            blocked.append({"item_id": item["item_id"], "reason": "MODELSPEC_V3_NOT_READY"})
            continue
        geometry = item["geometry"]
        operations.append({
            "operation": "create_physical_item",
            "item_id": item["item_id"],
            "model_revision": 1,
            "geometry_hash": item["geometry_hash"],
            "envelope": geometry["envelope"],
            "regions": geometry["regions"],
            "features": geometry["features"],
            "section_profiles": [copy.deepcopy(profile_lookup[profile_id]) for profile_id in geometry["section_profile_ids"]],
            "relationships": geometry["relationships"],
            "materials": geometry["materials"],
            "verification_contracts": [{"view_id": view["view_id"], "mandatory": view["mandatory"], "expects": view["verification_contract"]} for view in item["views"]],
            "source_refs": item["source_refs"],
        })
    return {"schema_version": SCHEMA_VERSION, "run_id": model_spec["run_id"], "status": "READY" if operations and not blocked else "BLOCKED", "operations": operations, "blocked_items": blocked}


def run_reconstruction_workflow_v3(payload: dict[str, Any], output_root: str | Path, run_id: str) -> dict[str, Any]:
    """Run generic interpretation-to-Build-IR gates without touching SketchUp."""
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("schema_version 3 required")
    root = Path(output_root)
    items = payload.get("items")
    if not isinstance(items, list) or not items:
        raise ValueError("items required")
    registry = build_view_registry_v3(payload, run_id)
    links = build_view_link_graph_v3(registry, items)
    constraints = build_constraint_graph_v3(payload, registry)
    sections = build_section_profile_graph_v3(payload, registry)
    hypotheses = build_hypotheses_v3(payload, sections)
    spec = generate_model_spec_v3(payload, registry, links, constraints, sections, hypotheses)
    build_ir = build_ir_v3(spec, sections)

    work = root / "WORK" / "reconstruction" / run_id
    model = root / "OUTPUT" / "MODEL" / "reconstruction" / run_id
    for path, artifact in (
        (work / "view-registry-v3.json", registry),
        (work / "view-link-graph-v3.json", links),
        (work / "constraint-graph-v3.json", constraints),
        (work / "section-profile-graph-v3.json", sections),
        (work / "hypotheses-v3.json", hypotheses),
        (model / "model-spec-v3.json", spec),
        (model / "build-ir-v3.json", build_ir),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8")

    checks = {
        "VIEW_REGISTRY": bool(registry["views"]),
        "VIEW_LINK_GRAPH": not any(row["impact"] == "BLOCKING" for row in links["unresolved"]),
        "CONSTRAINT_GRAPH": not any(row["impact"] == "BLOCKING" for row in constraints["unresolved"]),
        "SECTION_PROFILE_GRAPH": not any(row["impact"] == "BLOCKING" for row in sections["unresolved"]),
        "UNIQUE_3D_HYPOTHESIS": all(item["selected_hypothesis_id"] for item in spec["items"]),
        "MODELSPEC_READY": all(item["buildable_state"] == "READY" for item in spec["items"]),
        "BUILD_IR_READY": build_ir["status"] == "READY",
    }
    status = "READY_FOR_PREVIEW" if all(checks.values()) else "REVIEW_REQUIRED"
    summary = {"schema_version": SCHEMA_VERSION, "run_id": run_id, "status": status, "checks": checks, "artifact_root": str(work)}
    (work / "workflow-summary-v3.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def run_raw_reconstruction_workflow_v3(
    source_path: str | Path,
    output_root: str | Path,
    run_id: str,
    *,
    tessdata_dir: str | Path | None = None,
    dpi: int = 240,
) -> dict[str, Any]:
    """Run raw source extraction and all pre-build V3 gates without hand-edited JSON."""
    from .raw_drawing_understanding_v3 import extract_raw_drawing_evidence_v3, interpret_profile_assembly_v3

    evidence = extract_raw_drawing_evidence_v3(source_path, tessdata_dir=tessdata_dir, dpi=dpi)
    payload = interpret_profile_assembly_v3(evidence)
    root = Path(output_root)
    work = root / "WORK" / "reconstruction" / run_id
    work.mkdir(parents=True, exist_ok=True)
    for name, artifact in (("raw-evidence-v3.json", evidence), ("interpreted-payload-v3.json", payload)):
        (work / name).write_text(json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8")
    result = run_reconstruction_workflow_v3(payload, root, run_id)
    return {**result, "source_path": str(Path(source_path).resolve()), "payload": payload}
