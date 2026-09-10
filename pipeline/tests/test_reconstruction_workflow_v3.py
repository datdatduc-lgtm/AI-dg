import copy
import json
from pathlib import Path

from pipeline.stages.reconstruction_workflow_v3 import (
    build_constraint_graph_v3,
    build_hypotheses_v3,
    build_section_profile_graph_v3,
    build_view_link_graph_v3,
    build_view_registry_v3,
    generate_model_spec_v3,
    run_reconstruction_workflow_v3,
)
from pipeline.stages.repair_loop_v3 import run_repair_loop_v3
from pipeline.stages.executor_v3 import run_autonomous_hypothesis_repair_v3
from pipeline.stages.raw_drawing_understanding_v3 import interpret_profile_assembly_v3
from pipeline.stages.sketchup_view_back_v3 import view_back_from_sketchup_readback_v3
from pipeline.stages.view_verification_v3 import compare_view_back_v3, project_hypothesis_v3


ROOT = Path(__file__).resolve().parents[2]


def _ref(view_id, sheet_id="S1"):
    return {"source_id": "drawing-package", "sheet_id": sheet_id, "view_id": view_id}


def _payload():
    lower = {"id": "lower", "visibility": "VISIBLE", "bounds": {"x": [0, 2400], "y": [0, 40], "z": [0, 800]}, "material_id": "body", "state": "EXPLICIT"}
    centered_glass = {"id": "glass", "visibility": "VISIBLE", "bounds": {"x": [0, 2400], "y": [15, 25], "z": [800, 1100]}, "material_id": "glass", "state": "DERIVED_FROM_VIEWS"}
    flush_glass = {**centered_glass, "bounds": {"x": [0, 2400], "y": [0, 10], "z": [800, 1100]}}
    return {
        "schema_version": 3,
        "source_review_status": "APPROVED",
        "views": [
            {
                "view_id": "E-01", "sheet_id": "S1", "view_type": "FRONT", "projection_axes": ["X", "Z"],
                "item_refs": ["PARTITION-A"], "mandatory": True, "source_refs": [_ref("E-01")],
                "verification_contract": {"overall_mm": {"X": 2400, "Z": 1100}, "visible_region_ids": ["lower", "glass"], "region_spans": {"lower": {"Z": [0, 800]}, "glass": {"Z": [800, 1100]}}},
            },
            {
                "view_id": "S-A", "sheet_id": "S2", "view_type": "SECTION", "projection_axes": ["Y", "Z"],
                "item_refs": ["PARTITION-A"], "mandatory": True, "section_marker": "A-A", "source_refs": [_ref("S-A", "S2")],
                "verification_contract": {"overall_mm": {"Y": 40, "Z": 1100}, "region_spans": {"glass": {"Y": [15, 25]}}, "section_features": [{"feature_id": "slot-1", "type": "SLOT", "dimensions_mm": {"width": 12, "depth": 50}}]},
            },
            {
                "view_id": "D-01", "sheet_id": "S3", "view_type": "DETAIL", "projection_axes": ["Y", "Z"],
                "item_refs": ["PARTITION-A"], "mandatory": False, "refines_view_id": "S-A", "source_refs": [_ref("D-01", "S3")],
                "verification_contract": {},
            },
        ],
        "constraints": [
            {"constraint_id": "dim-z", "kind": "DIMENSION", "axis": "Z", "value_mm": 1100, "start_ref": "item.bottom", "end_ref": "item.top", "view_id": "E-01", "state": "EXPLICIT", "source_refs": [_ref("E-01")]},
        ],
        "section_profiles": [
            {"profile_id": "profile-A", "view_id": "S-A", "state": "EXPLICIT", "source_refs": [_ref("S-A", "S2")], "features": [{"feature_id": "slot-1", "type": "SLOT", "dimensions_mm": {"width": 12, "depth": 50}, "state": "EXPLICIT", "source_refs": [_ref("S-A", "S2")]}]},
        ],
        "items": [
            {
                "item_id": "PARTITION-A", "state": "EXPLICIT", "source_refs": [_ref("E-01")],
                "envelope": {"x_mm": 2400, "y_mm": 40, "z_mm": 1100},
                "regions": [lower, centered_glass], "section_profile_ids": ["profile-A"],
                "relationships": [{"type": "ABOVE", "from": "glass", "to": "lower"}],
                "materials": [{"id": "body"}, {"id": "glass"}],
                "hypotheses": [
                    {"hypothesis_id": "H-centered", "state": "DERIVED_FROM_VIEWS", "geometry": {"regions": [lower, centered_glass], "section_profile_ids": ["profile-A"]}, "source_refs": [_ref("E-01"), _ref("S-A", "S2")]},
                    {"hypothesis_id": "H-flush", "state": "DERIVED_FROM_VIEWS", "geometry": {"regions": [lower, flush_glass], "section_profile_ids": ["profile-A"]}, "source_refs": [_ref("E-01"), _ref("S-A", "S2")]},
                ],
            }
        ],
    }


def _stages(payload):
    registry = build_view_registry_v3(payload, "generic-run")
    links = build_view_link_graph_v3(registry, payload["items"])
    constraints = build_constraint_graph_v3(payload, registry)
    sections = build_section_profile_graph_v3(payload, registry)
    hypotheses = build_hypotheses_v3(payload, sections)
    return registry, links, constraints, sections, hypotheses


def test_cross_sheet_views_link_to_one_physical_item_and_detail_refines_section():
    payload = _payload()
    registry, links, *_ = _stages(payload)
    assert {view["sheet_id"] for view in registry["views"]} == {"S1", "S2", "S3"}
    assert len([edge for edge in links["edges"] if edge["type"] == "PROJECTS_ITEM"]) == 3
    assert {"type": "REFINES_VIEW", "from": "D-01", "to": "S-A", "source_refs": [_ref("D-01", "S3")]} in links["edges"]
    assert links["unresolved"] == []


def test_section_profile_uses_generic_feature_taxonomy_with_evidence():
    payload = _payload()
    registry, _, _, sections, _ = _stages(payload)
    profile = sections["profiles"][0]
    assert profile["features"][0]["type"] == "SLOT"
    assert profile["features"][0]["source_refs"]
    assert sections["unresolved"] == []
    assert next(view for view in registry["views"] if view["view_id"] == "S-A")["view_type"] == "SECTION"


def test_all_mandatory_views_select_the_only_consistent_3d_hypothesis():
    payload = _payload()
    registry, links, constraints, sections, hypotheses = _stages(payload)
    spec = generate_model_spec_v3(payload, registry, links, constraints, sections, hypotheses)
    item = spec["items"][0]
    assert item["buildable_state"] == "READY"
    assert item["selected_hypothesis_id"] == "H-centered"
    results = {row["hypothesis_id"]: row["status"] for row in item["candidate_results"]}
    assert results == {"H-centered": "PASS", "H-flush": "FAIL"}


def test_distinct_hypotheses_that_all_fit_available_views_are_ambiguous():
    payload = _payload()
    section = next(view for view in payload["views"] if view["view_id"] == "S-A")
    section["verification_contract"].pop("region_spans")
    registry, links, constraints, sections, hypotheses = _stages(payload)
    spec = generate_model_spec_v3(payload, registry, links, constraints, sections, hypotheses)
    item = spec["items"][0]
    assert item["buildable_state"] == "REVIEW_REQUIRED"
    assert item["selected_hypothesis_id"] is None
    assert item["unresolved"][-1]["type"] == "HYPOTHESIS_AMBIGUOUS"


def test_workflow_writes_general_artifacts_and_reaches_preview_gate(tmp_path):
    result = run_reconstruction_workflow_v3(_payload(), tmp_path, "generic-run")
    assert result["status"] == "READY_FOR_PREVIEW"
    assert all(result["checks"].values())
    work = tmp_path / "WORK" / "reconstruction" / "generic-run"
    assert (work / "view-registry-v3.json").is_file()
    assert (work / "section-profile-graph-v3.json").is_file()
    assert (work / "hypotheses-v3.json").is_file()
    assert (tmp_path / "OUTPUT" / "MODEL" / "reconstruction" / "generic-run" / "build-ir-v3.json").is_file()


def test_one_mandatory_view_failure_blocks_model_pass():
    payload = _payload()
    registry, _, _, sections, hypotheses = _stages(payload)
    centered = next(row for row in hypotheses["hypotheses"] if row["hypothesis_id"] == "H-centered")
    snapshot = project_hypothesis_v3(centered, registry["views"], sections, model_revision=3)
    section = next(row for row in snapshot["views"] if row["view_id"] == "S-A")
    section["overall"]["Y"] = 60
    result = compare_view_back_v3(snapshot, registry["views"])
    assert result["status"] == "FAIL"
    assert any(row["type"] == "OVERALL_DIMENSION_MISMATCH" and row["view_id"] == "S-A" for row in result["mismatches"])


def test_old_view_result_cannot_be_mixed_with_new_model_revision():
    payload = _payload()
    registry, _, _, sections, hypotheses = _stages(payload)
    centered = next(row for row in hypotheses["hypotheses"] if row["hypothesis_id"] == "H-centered")
    snapshot = project_hypothesis_v3(centered, registry["views"], sections, model_revision=4)
    snapshot["views"][0]["model_revision"] = 3
    result = compare_view_back_v3(snapshot, registry["views"])
    assert result["status"] == "FAIL"
    assert any(row["type"] == "STALE_VERIFICATION" for row in result["mismatches"])


def test_repair_loop_patches_upstream_and_rechecks_every_view():
    payload = _payload()
    registry, _, _, sections, hypotheses = _stages(payload)
    wrong = next(row for row in hypotheses["hypotheses"] if row["hypothesis_id"] == "H-flush")
    initial = {"geometry": copy.deepcopy(wrong["geometry"]), "item_id": wrong["item_id"]}

    def view_back(build_ir, revision):
        candidate = {"item_id": build_ir["item_id"], "geometry": build_ir["geometry"]}
        return project_hypothesis_v3(candidate, registry["views"], sections, revision)

    def repair_upstream(build_ir, plan):
        assert any(action["patch_stage"] == "region_graph" for action in plan["actions"])
        glass = next(region for region in build_ir["geometry"]["regions"] if region["id"] == "glass")
        glass["bounds"]["y"] = [15, 25]
        return build_ir

    result = run_repair_loop_v3(initial, registry["views"], view_back, repair_upstream)
    assert result["status"] == "PASS"
    assert [row["status"] for row in result["iterations"]] == ["FAIL", "PASS"]
    assert result["iterations"][0]["geometry_hash"] != result["iterations"][1]["geometry_hash"]


def test_official_sketchup_readback_does_not_fake_missing_section_features():
    payload = _payload()
    registry, _, _, sections, _ = _stages(payload)
    response = {
        "status": "ok",
        "target": {"instance_id": "su-test", "pid": 123},
        "data": {
            "readback_source": "official_sketchup_ruby_api",
            "root": {"min_mm": [0, 0, 0], "max_mm": [2400, 40, 1100]},
            "parts": [
                {"persistent_id": 1, "min_mm": [0, 0, 0], "max_mm": [2400, 40, 800], "attributes": {"AI_DG": {"region_id": "lower", "visibility": "VISIBLE", "material_code": "body"}}},
                {"persistent_id": 2, "min_mm": [0, 15, 800], "max_mm": [2400, 25, 1100], "attributes": {"AI_DG": {"region_id": "glass", "visibility": "VISIBLE", "material_code": "glass"}}},
            ],
        },
    }
    snapshot = view_back_from_sketchup_readback_v3("PARTITION-A", response, registry["views"], sections, 8)
    comparison = compare_view_back_v3(snapshot, registry["views"])
    assert snapshot["readback_source"] == "official_sketchup_ruby_api"
    assert snapshot["observed_section_profile_ids"] == []
    assert comparison["status"] == "FAIL"
    assert any(row["type"] == "FEATURE_MISSING" for row in comparison["mismatches"])


def test_production_workflow_contains_no_fixture_item_branch():
    files = [
        ROOT / "pipeline" / "stages" / "reconstruction_workflow_v3.py",
        ROOT / "pipeline" / "stages" / "view_verification_v3.py",
        ROOT / "pipeline" / "stages" / "repair_loop_v3.py",
        ROOT / "pipeline" / "stages" / "sketchup_view_back_v3.py",
        ROOT / "pipeline" / "stages" / "raw_drawing_understanding_v3.py",
        ROOT / "pipeline" / "stages" / "executor_v3.py",
    ]
    production = "\n".join(path.read_text(encoding="utf-8") for path in files)
    assert "VN-1" not in production
    assert "if item_code" not in production


def test_reconstruction_profile_exposes_only_gated_v3_entrypoints():
    from mcp_server.tool_exposure import PROFILE_GROUPS, visible_tool_ids

    registry = [
        {"id": "ai_dg_reconstruction_workflow_v3"},
        {"id": "ai_dg_compare_views_v3"},
        {"id": "sketchup_create_box"},
    ]
    visible = visible_tool_ids(
        registry,
        "drawing_reconstruction",
        PROFILE_GROUPS["drawing_reconstruction"],
        False,
    )
    assert visible == {"ai_dg_reconstruction_workflow_v3", "ai_dg_compare_views_v3"}


def test_generic_raw_evidence_interpreter_derives_profile_without_fixture_branch():
    def line(text, confidence=95):
        return {"text": text, "normalized": text, "bbox_px": [1, 2, 3, 4], "confidence": confidence}

    def number(value):
        return {"text": str(value), "value": value, "confidence": 95, "bbox_px": [1, 2, 3, 4], "ocr_rotation_deg_ccw": 0}

    views = []
    for index, (kind, text, axes) in enumerate((("FRONT", "FRONT ELEVATION RS-2", ["X", "Z"]), ("SIDE", "SIDE ELEVATION", ["Y", "Z"]), ("SECTION", "SECTION A-A", ["Y", "Z"]), ("DETAIL", "DETAIL D1", ["Y", "Z"])), start=1):
        ref = {"source_id": "fixture.pdf", "sheet_id": "page-0001", "view_id": f"V{index}", "bbox_px": [1, 2, 3, 4], "ocr_text": text, "ocr_confidence": 95}
        views.append({"view_id": f"V{index}", "sheet_id": "page-0001", "view_type": kind, "projection_axes": axes, "item_refs": ["RS-2"], "mandatory": True, "source_refs": [ref], "label_evidence": ref, "verification_contract": {}})
    evidence = {
        "schema_version": 3,
        "source": {"path": "fixture.pdf", "kind": "pdf"},
        "item_codes": ["RS-2"],
        "views": views,
        "sheets": [{
            "sheet_id": "page-0001", "orientation_correction_deg_ccw": 0,
            "ocr_lines": [line("GLASS THICKNESS 12")],
            "numeric_evidence": [number(value) for value in (2400, 1000, 700, 300, 60, 23, 14, 45)],
        }],
    }
    payload = interpret_profile_assembly_v3(evidence)
    assert payload["items"][0]["envelope"] == {"x_mm": 2400.0, "y_mm": 60.0, "z_mm": 1000.0}
    feature = payload["section_profiles"][0]["features"][0]
    assert feature["dimensions_mm"] == {"width": 14.0, "depth": 45.0}
    assert payload["items"][0]["regions"][1]["bounds"]["y"] == [24.0, 36.0]


def test_native_repair_rebuilds_wrong_hypothesis_then_passes_from_observed_geometry():
    payload = _payload()
    writes = []
    current = {}

    def dispatch(operation):
        writes.append(copy.deepcopy(operation))
        current.clear()
        current.update(copy.deepcopy(operation))
        return {"status": "ok", "operation_id": f"op-{len(writes)}"}

    def readback(item_id):
        operation = current
        profile = operation["body"]["profile_yz_mm"]
        ys = [point[0] for point in profile]
        zs = [point[1] for point in profile]
        insert = operation["inserts"][0]
        origin = insert["origin_mm"]
        dimensions = insert["dimensions_mm"]
        features = []
        if len(profile) > 4:
            features = [{"feature_id": "slot-1", "type": "SLOT", "dimensions_mm": {"width": profile[4][0] - profile[5][0], "depth": max(zs) - profile[4][1]}}]
        return {
            "status": "ok",
            "data": {
                "model_revision": operation["model_revision"], "geometry_hash": operation["geometry_hash"],
                "root": {"min_mm": [0, min(ys), 0], "max_mm": [operation["body"]["length_mm"], max(ys), 1100]},
                "parts": [
                    {"min_mm": [0, min(ys), 0], "max_mm": [operation["body"]["length_mm"], max(ys), max(zs)], "attributes": {"AI_DG": {"region_id": "lower", "visibility": "VISIBLE", "material_code": "body"}}},
                    {"min_mm": origin, "max_mm": [origin[0] + dimensions["width_mm"], origin[1] + dimensions["depth_mm"], origin[2] + dimensions["height_mm"]], "attributes": {"AI_DG": {"region_id": "glass", "visibility": "VISIBLE", "material_code": "glass"}}},
                ],
                "analysis_section_profiles": [{"profile_id": "profile-A", "features": features}],
                "readback_source": "official_sketchup_ruby_api",
            },
        }

    result = run_autonomous_hypothesis_repair_v3(
        payload,
        target={"instance_id": "su-test", "status": "ONLINE"}, access_mode="write_enabled", confirm_write=True,
        dispatch=dispatch, readback=readback, initial_hypothesis_id="H-flush",
    )
    assert result["status"] == "PASS"
    assert [row["status"] for row in result["iterations"]] == ["FAIL", "PASS"]
    assert [row["hypothesis_id"] for row in result["iterations"]] == ["H-flush", "H-centered"]
    assert len(writes) == 2
