import json
from pathlib import Path

from pipeline.stages.geometry_ledger_v2 import build_geometry_ledger_v2
from pipeline.stages.region_graph_v2 import build_region_graph_v2, validate_region_graph_v2
from pipeline.stages.model_spec_v2 import generate_model_spec_v2
from pipeline.stages.build_ir_v2 import build_ir_v2, validate_build_ir_v2
from pipeline.stages.projection_verification_v2 import verify_prebuild_projection_v2
from pipeline.stages.executor_v2 import execute_build_ir_v2
from tests.fixtures.vn1.run_fixture import run as run_vn1_fixture


ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests" / "fixtures" / "vn1" / "interpreted-source-v2.json"


def _ledger():
    return build_geometry_ledger_v2(json.loads(FIXTURE.read_text(encoding="utf-8")), "vn1-golden")


def test_vn1_geometry_ledger_preserves_hierarchical_spans():
    item = _ledger()["items"][0]
    spans = {span["id"]: span for span in item["dimension_spans"]}
    assert spans["dim-x-overall"]["value_mm"] == 8000
    assert spans["dim-z-overall"]["value_mm"] == 1100
    assert spans["dim-z-lower"]["value_mm"] + spans["dim-z-upper"]["value_mm"] == 1100
    assert spans["dim-z-lower-section"]["value_mm"] + spans["dim-z-embed"]["value_mm"] == 800
    assert all(row["equation_status"] == "PASS" for row in item["dimension_hierarchy"])
    assert spans["dim-z-embed"]["visibility"] == "SECTION_ONLY"


def test_vn1_source_refs_and_views_are_not_collapsed_to_page():
    item = _ledger()["items"][0]
    assert {view["id"] for view in item["views"]} >= {
        "elevation-main", "side-typical", "section-typical", "detail-ct1"
    }
    assert all(span["source_refs"] for span in item["dimension_spans"])


def test_vn1_region_graph_preserves_spatial_regions_and_section_only_refinement():
    graph = build_region_graph_v2(_ledger())
    nodes = {node["id"]: node for node in graph["nodes"]}
    edges = {(edge["type"], edge["from"], edge["to"]) for edge in graph["edges"]}
    assert validate_region_graph_v2(graph) == []
    assert nodes["VN-1:lower-body"]["bounds"]["z"] == [0, 800]
    assert nodes["VN-1:upper-glass"]["bounds"]["z"] == [800, 1100]
    assert nodes["VN-1:embed-50"]["visibility"] == "SECTION_ONLY"
    assert ("SECTION_ONLY", "VN-1:embed-50", "VN-1:lower-body") in edges
    assert not any(edge[0] == "VISIBLE_IN" and edge[1] == "VN-1:embed-50" for edge in edges)


def test_vn1_model_spec_v2_preserves_hierarchy_and_is_ready_after_review():
    ledger = _ledger()
    spec = generate_model_spec_v2(ledger, build_region_graph_v2(ledger))
    item = spec["items"][0]
    assert item["buildable_state"] == "READY"
    assert {region["id"] for region in item["regions"]} >= {
        "VN-1:lower-body", "VN-1:upper-glass", "VN-1:embed-50"
    }
    assert any(edge["type"] == "SECTION_ONLY" for edge in item["relationships"])
    assert len(item["dimension_hierarchy"]) == 2


def test_model_spec_v2_blocks_ambiguous_geometry():
    ledger = _ledger()
    ledger["source_review_status"] = "OPEN"
    ledger["items"][0]["envelope"]["y_mm"] = None
    graph = build_region_graph_v2(ledger)
    item = generate_model_spec_v2(ledger, graph)["items"][0]
    assert item["buildable_state"] == "REVIEW_REQUIRED"
    assert item["gate_checks"]["source_review_approved"] is False
    assert item["gate_checks"]["envelope_complete"] is False


def test_vn1_build_ir_v2_keeps_semantic_regions_and_relations():
    ledger = _ledger()
    spec = generate_model_spec_v2(ledger, build_region_graph_v2(ledger))
    build_ir = build_ir_v2(spec)
    operation = build_ir["operations"][0]
    assert validate_build_ir_v2(build_ir) == []
    assert operation["operation"] == "create_item_assembly"
    assert {region["id"] for region in operation["regions"]} >= {
        "VN-1:lower-body", "VN-1:upper-glass", "VN-1:embed-50"
    }
    embed = next(region for region in operation["regions"] if region["id"] == "VN-1:embed-50")
    assert embed["build_geometry"] is False
    assert "VN-1:embed-50" in operation["verification_contract"]["forbidden_visible_region_ids"]
    assert any(edge["type"] == "SECTION_ONLY" for edge in operation["relationships"])


def test_vn1_prebuild_projection_is_a_hard_pass_gate():
    ledger = _ledger()
    spec = generate_model_spec_v2(ledger, build_region_graph_v2(ledger))
    build_ir = build_ir_v2(spec)
    report = verify_prebuild_projection_v2(build_ir)
    assert report["status"] == "PASS"
    by_id = {row["region_id"]: row for row in report["projections"]}
    assert by_id["VN-1:lower-body"]["front_xz"]["z"] == [0, 800]
    assert by_id["VN-1:upper-glass"]["front_xz"]["z"] == [800, 1100]
    assert "VN-1:embed-50" not in by_id


def test_prebuild_projection_rejects_visible_section_refinement():
    ledger = _ledger()
    spec = generate_model_spec_v2(ledger, build_region_graph_v2(ledger))
    build_ir = build_ir_v2(spec)
    embed = next(region for region in build_ir["operations"][0]["regions"] if region["id"] == "VN-1:embed-50")
    embed["build_geometry"] = True
    assert verify_prebuild_projection_v2(build_ir)["status"] == "FAIL"


def test_vn1_golden_fixture_a_to_f(tmp_path):
    source = ROOT / "INPUT" / "PDF" / "CHI TIET VACH NGAN VN-1.pdf"
    result = run_vn1_fixture(source, FIXTURE, tmp_path)
    assert result["status"] == "PASS"
    assert all(result["checks"].values())
    index = json.loads((tmp_path / "WORK" / "geometry" / "drawing-index-v2.json").read_text(encoding="utf-8"))
    assert {row["role"] for row in index["entries"]} >= {"front_elevation", "side_elevation", "section", "local_detail"}
    assert (tmp_path / "OUTPUT" / "MODEL" / "model-spec-v2.json").is_file()
    assert (tmp_path / "OUTPUT" / "MODEL" / "build-ir-v2.json").is_file()
    assert (tmp_path / "OUTPUT" / "VERIFICATION" / "projection-prebuild-v2.json").is_file()


def test_v2_executor_blocks_before_dispatch_when_projection_fails():
    ledger = _ledger()
    build_ir = build_ir_v2(generate_model_spec_v2(ledger, build_region_graph_v2(ledger)))
    embed = next(region for region in build_ir["operations"][0]["regions"] if region["id"] == "VN-1:embed-50")
    embed["build_geometry"] = True
    calls = []
    result = execute_build_ir_v2(
        build_ir,
        target={"instance_id": "su-test", "status": "ONLINE"},
        access_mode="write_enabled",
        confirm_write=True,
        dispatch=lambda payload: calls.append(payload) or {"status": "ok"},
        readback=lambda code: {},
    )
    assert result["status"] == "BLOCKED"
    assert result["reason"] == "PREBUILD_PROJECTION_FAILED"
    assert calls == []


def test_v2_executor_uses_only_scoped_preapproval_after_all_gates_pass():
    ledger = _ledger()
    build_ir = build_ir_v2(generate_model_spec_v2(ledger, build_region_graph_v2(ledger)))
    operation = build_ir["operations"][0]
    calls = []

    def readback(_item_code):
        parts = []
        for index, region in enumerate(operation["regions"], start=1):
            if region.get("build_geometry") is not True:
                continue
            bounds = region["bounds"]
            parts.append({
                "persistent_id": index,
                "min_mm": [bounds[axis][0] for axis in ("x", "y", "z")],
                "max_mm": [bounds[axis][1] for axis in ("x", "y", "z")],
                "attributes": {"AI_DG": {
                    "region_id": region["id"],
                    "material_code": region["material_id"],
                    "visibility": region["visibility"],
                }},
            })
        return {"status": "ok", "data": {"item_code": operation["item_code"], "parts": parts}}

    result = execute_build_ir_v2(
        build_ir,
        target={"instance_id": "su-test", "status": "ONLINE"},
        access_mode="write_enabled",
        confirm_write=True,
        dispatch=lambda payload: calls.append(payload) or {"status": "ok", "operation_id": "op-test"},
        readback=readback,
    )
    assert result["status"] == "PASS"
    assert len(calls) == 1
    assert calls[0]["approval_mode"] == "user_preapproved_v2"
    assert calls[0]["confirm_write"] is True
    assert calls[0]["tool_name"] == "ai_dg_execute_build_ir_v2"


def test_ruby_bridge_limits_preapproval_to_v2_semantic_item():
    source = (ROOT / "bridge_sketchup" / "ai_dg_bridge" / "main_safe.rb").read_text(encoding="utf-8")
    assert "def v2_scoped_preapproval?(data)" in source
    assert "data['tool_name'] == 'ai_dg_execute_build_ir_v2'" in source
    assert "def create_semantic_item(model, data)\n        guard_model_write!(data)" in source
    assert source.count("guard_model_write!(data)") == 1


def test_drawing_reconstruction_profile_hides_raw_writes():
    from mcp_server.tool_exposure import PROFILE_GROUPS, visible_tool_ids

    registry = [
        {"id": "ai_dg_execute_build_ir_v2"}, {"id": "sketchup_create_box"},
        {"id": "sketchup_create_semantic_item"}, {"id": "sketchup_set_write_mode"},
    ]
    groups = PROFILE_GROUPS["drawing_reconstruction"]
    visible = visible_tool_ids(registry, "drawing_reconstruction", groups, False)
    assert "ai_dg_execute_build_ir_v2" in visible
    assert "sketchup_set_write_mode" in visible
    assert "sketchup_create_box" not in visible
    assert "sketchup_create_semantic_item" not in visible
