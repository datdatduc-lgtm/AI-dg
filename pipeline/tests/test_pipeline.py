"""Unit tests for the AI-DG 2D->3D pipeline (M2..M7)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pipeline.stages import runner
from pipeline.stages import build_ir, builder, executor, graphs, model_spec, reconciliation, review_queue, verification
from pipeline.stages.source_ingestion import classify_drawing, ingest_excel


def test_classify_drawing_signals() -> None:
    assert classify_drawing("MẶT ĐỨNG VÁCH NGĂN VN-1")["drawing_type"] == "ELEVATION"
    assert classify_drawing("MẶT CẮT ĐIỂN HÌNH")["drawing_type"] == "SECTION"
    assert classify_drawing("CHI TIẾT CT1")["drawing_type"] == "DETAIL"
    assert classify_drawing("GHI CHÚ VẬT LIỆU")["drawing_type"] == "MATERIAL_LEGEND"
    assert classify_drawing("không có gì ở đây")["drawing_type"] == "UNKNOWN"


def test_reconciliation_match_vs_mismatch() -> None:
    facts = [
        {"fact": "overall width", "axis": "X", "span": "front", "value_mm": 8000, "source_id": "SRC-001", "drawing_id": "D01"},
        {"fact": "overall width", "axis": "X", "span": "front", "value_mm": 8000.5, "source_id": "SRC-002", "drawing_id": "D02"},
        {"fact": "overall height", "axis": "Z", "span": "base-top", "value_mm": 1100, "source_id": "SRC-001", "drawing_id": "D01"},
        {"fact": "overall height", "axis": "Z", "span": "base-top", "value_mm": 950, "source_id": "SRC-002", "drawing_id": "D02"},
    ]
    report = reconciliation.reconcile_dimensions(facts, run_id="test")
    statuses = {r["fact"]: r["status"] for r in report.comparisons}
    assert statuses["overall width"] == "MATCH_WITHIN_VIEWS"
    assert statuses["overall height"] == "MISMATCH"
    assert len(report.mismatches) == 1


def test_dimension_graph_conflict_detection() -> None:
    facts = [
        {"item_code": "VN-1", "region": "R1", "dim": "width", "value_mm": 8000, "state": "EXPLICIT", "confidence": 0.9},
        {"item_code": "VN-1", "region": "R1", "dim": "width", "value_mm": 7700, "state": "EXPLICIT", "confidence": 0.9},
        {"item_code": "VN-1", "region": "R1", "dim": "height", "value_mm": 1100, "state": "EXPLICIT", "confidence": 0.9},
    ]
    graph = graphs.build_dimension_graph(facts, run_id="test")
    conflict_facts = [c for c in graph.conflicts if c["dim"] == "width"]
    assert conflict_facts and conflict_facts[0]["span_mm"] == 300.0
    assert not any(c["dim"] == "height" for c in graph.conflicts)


def test_material_graph_roles() -> None:
    facts = [
        {"item_code": "VN-1", "material_code": "MDF18", "role": "body"},
        {"item_code": "VN-1", "material_code": "KINH10", "role": "face"},
    ]
    graph = graphs.build_material_graph(facts, run_id="test")
    assert graph.items["VN-1"]["materials"] == ["KINH10", "MDF18"]
    roles = {m["code"]: m["roles"] for m in graph.materials if m["item_code"] == "VN-1"}
    assert roles["MDF18"] == ["body"]
    assert roles["KINH10"] == ["face"]


def test_model_spec_only_explicit_buildable() -> None:
    facts = [
        {"item_code": "VN-1", "dim": "width", "value_mm": 8000, "state": "EXPLICIT", "confidence": 0.95, "sources": ["SRC-001"]},
        {"item_code": "VN-1", "dim": "depth", "value_mm": 40, "state": "DERIVED", "confidence": 0.6, "sources": ["SRC-001"]},
        {"item_code": "VN-1", "dim": "height", "value_mm": 1100, "state": "EXPLICIT", "confidence": 0.95, "sources": ["SRC-001"]},
    ]
    spec = model_spec.generate_model_spec(facts, run_id="test")
    item = spec.items[0]
    assert item["buildable_state"] == "REVIEW_REQUIRED"
    assert item["dimensions_mm"]["depth"]["buildable"] is False
    assert item["dimensions_mm"]["width"]["buildable"] is True


def test_builder_requires_explicit_semantic_parts() -> None:
    envelope = {
        "item_code": "VN-1",
        "buildable_state": "READY",
        "dimensions_mm": {
            "width": {"value_mm": 800, "buildable": True},
            "depth": {"value_mm": 40, "buildable": True},
            "height": {"value_mm": 1100, "buildable": True},
        },
    }
    blocked = builder.plan_build([envelope], run_id="test", source_review_status="APPROVED")
    assert blocked.operations == []
    assert blocked.blocked_items[0]["reason"] == "SEMANTIC_PARTS_REQUIRED"

    envelope["parts"] = [{
        "part_id": "SIDE-L",
        "role": "body",
        "dimensions_mm": {"width_mm": 1100, "depth_mm": 40, "height_mm": 800},
        "origin_mm": [0, 0, 0],
        "material_code": "MDF18",
        "source_refs": ["SRC-001"],
    }]
    ready = builder.plan_build([envelope], run_id="test", source_review_status="APPROVED")
    assert [op["op"] for op in ready.operations] == ["CREATE_SEMANTIC_ITEM", "ATTACH_META"]
    assert ready.operations[0]["execution_tool"] == "sketchup_create_semantic_item"


def test_build_ir_is_deterministic_and_codegen_is_readable() -> None:
    spec = {
        "run_id": "ir-test",
        "source_review_status": "APPROVED",
        "items": [{
            "item_code": "CAB-A01",
            "name": "CABINET A01",
            "buildable_state": "READY",
            "dimensions_mm": {
                "width": {"value_mm": 1200, "buildable": True},
                "depth": {"value_mm": 600, "buildable": True},
                "height": {"value_mm": 800, "buildable": True},
            },
            "parts": [{
                "part_id": "BODY",
                "role": "carcass",
                "dimensions_mm": {"width_mm": 1200, "depth_mm": 600, "height_mm": 800},
                "origin_mm": [0, 0, 0],
                "material_code": "MDF18",
                "source_refs": ["SRC-001"],
            }],
        }],
    }
    first = build_ir.build_from_model_spec(spec).to_dict()
    second = build_ir.build_from_model_spec({**spec, "items": list(reversed(spec["items"]))}).to_dict()
    assert first["status"] == "READY"
    assert first["operations"] == second["operations"]
    assert build_ir.validate_build_ir(first) == []
    generated = build_ir.generate_codegen(first)
    assert set(generated) == {"json", "python", "ruby"}
    assert "sketchup_create_semantic_item" in generated["ruby"]
    assert "BUILD_IR =" in generated["python"]


def test_excel_explicit_parts_to_ready_pipeline(tmp_path: Path) -> None:
    openpyxl = pytest.importorskip("openpyxl")
    root = tmp_path / "approved-project"
    (root / "INPUT" / "OTHER").mkdir(parents=True)
    (root / "WORK").mkdir()
    marker = root / "project.ai-dg.json"
    marker.write_text(json.dumps({"project_name": "APPROVED", "work_root": "WORK"}), encoding="utf-8")
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.append(["item_code", "part_id", "part_role", "width_mm", "depth_mm", "height_mm", "material"])
    sheet.append(["VN-1", "SIDE-L", "body", 1100, 40, 800, "MDF18"])
    excel_path = root / "INPUT" / "OTHER" / "explicit-parts.xlsx"
    workbook.save(excel_path)
    package = ingest_excel(excel_path)
    assert len(package.dimensions) == 3
    assert package.dimensions[0]["part_id"] == "SIDE-L"

    result = runner.run_pipeline(root, run_id="approved-excel", render_pdf=False, review_status="APPROVED", model_measurements={"VN-1": {"width": 1100, "depth": 40, "height": 800, "materials": ["MDF18"]}})
    assert result.gate_status == "READY"
    assert result.build_plan["operations"][0]["op"] == "CREATE_SEMANTIC_ITEM"
    assert result.build_ir["status"] == "READY"
    assert result.build_ir["operations"][0]["tool"] == "sketchup_create_semantic_item"
    assert result.codegen["status"] == "READY"
    assert set(result.codegen["files"]) == {"json", "python", "ruby"}
    assert result.verification["status"] == "PASS"


def test_review_queue_blocker() -> None:
    queue = review_queue.ReviewQueue(run_id="test")
    queue.add("X", severity="BLOCKER", impact="blocked")
    assert queue.has_blockers()
    queue.items[0]["status"] = "RESOLVED"
    assert not queue.has_blockers()
def test_verification_pass_and_fail() -> None:
    spec_items = [
        {
            "item_code": "VN-1",
            "dimensions_mm": {
                "width": {"value_mm": 8000, "buildable": True},
                "depth": {"value_mm": 40, "buildable": True},
                "height": {"value_mm": 1100, "buildable": True},
            },
        }
    ]
    good = verification.verify_model_vs_spec(spec_items, {"VN-1": {"width": 8000.5, "depth": 40, "height": 1100}}, run_id="t")
    assert good.status == "PASS"
    bad = verification.verify_model_vs_spec(spec_items, {"VN-1": {"width": 7700, "depth": 40, "height": 1100}}, run_id="t")
    assert bad.status == "FAIL"


def test_verification_optional_semantic_fields() -> None:
    spec_items = [{
        "item_code": "VN-1",
        "dimensions_mm": {"width": {"value_mm": 800}, "depth": {"value_mm": 40}, "height": {"value_mm": 1100}},
        "materials": ["MDF18"],
        "tag": "AI_DG_BODY",
        "hierarchy_path": ["AI_DG_ITEM_VN-1", "SIDE-L"],
    }]
    report = verification.verify_model_vs_spec(spec_items, {"VN-1": {
        "width": 800, "depth": 40, "height": 1100, "materials": ["MDF18", "PAINT"],
        "tag": "AI_DG_BODY", "hierarchy_path": ["AI_DG_ITEM_VN-1", "SIDE-L"],
    }}, run_id="t")
    assert report.status == "PASS"
    assert report.tolerance_policy["dimension_mm"] == 2.0


def _approved_build_fixture() -> tuple[dict, list[dict]]:
    spec_item = {
        "item_code": "VN-1",
        "buildable_state": "READY",
        "dimensions_mm": {
            "width": {"value_mm": 800, "buildable": True},
            "depth": {"value_mm": 40, "buildable": True},
            "height": {"value_mm": 1100, "buildable": True},
        },
        "materials": ["MDF18"],
        "parts": [{
            "part_id": "SIDE-L",
            "role": "body",
            "dimensions_mm": {"width_mm": 800, "depth_mm": 40, "height_mm": 1100},
            "origin_mm": [0, 0, 0],
            "material_code": "MDF18",
            "source_refs": ["SRC-001"],
        }],
    }
    plan = builder.plan_build([spec_item], run_id="executor-test", source_review_status="APPROVED").to_dict()
    return plan, [spec_item]


def test_executor_requires_review_write_and_confirmation() -> None:
    plan, spec_items = _approved_build_fixture()
    calls: list[str] = []
    blocked = executor.execute_build_plan(
        plan, spec_items, "executor-test", "OPEN", "write_enabled", True,
        lambda payload: calls.append("dispatch") or {"status": "ok"},
        lambda item_code: calls.append("readback") or {},
    )
    assert blocked["status"] == "BLOCKED"
    assert blocked["reason"] == "REVIEW_APPROVAL_REQUIRED"
    assert calls == []

    readonly = executor.execute_build_plan(
        plan, spec_items, "executor-test", "APPROVED", "read_only", True,
        lambda payload: calls.append("dispatch") or {"status": "ok"},
        lambda item_code: calls.append("readback") or {},
    )
    assert readonly["status"] == "BLOCKED"
    assert readonly["reason"] == "READ_ONLY_MODE"
    assert calls == []


def test_executor_dispatches_then_verifies_official_readback() -> None:
    plan, spec_items = _approved_build_fixture()
    calls: list[str] = []

    def dispatch(payload: dict) -> dict:
        calls.append("dispatch")
        assert payload["item_code"] == "VN-1"
        return {"status": "ok", "operation_id": "ruby-op-1", "root_persistent_id": 123, "verified": True}

    def readback(item_code: str) -> dict:
        calls.append("readback")
        return {"status": "ok", "data": {
            "found": True,
            "root": {"bounds_mm": [800, 40, 1100]},
            "parts": [{"attributes": {"AI_DG": {"material_code": "MDF18"}}}],
        }}

    result = executor.execute_build_plan(plan, spec_items, "executor-test", "APPROVED", "write_enabled", True, dispatch, readback)
    assert result["status"] == "PASS"
    assert calls == ["dispatch", "readback"]
    assert result["verification"]["status"] == "PASS"


def _write_sample_dxf(root: Path) -> Path:
    (root / "INPUT" / "CAD").mkdir(parents=True)
    dxf_path = root / "INPUT" / "CAD" / "sample.dxf"
    dxf_path.write_text(
        "0\nSECTION\n2\nHEADER\n0\nENDSEC\n"
        "0\nSECTION\n2\nENTITIES\n0\nLWPOLYLINE\n8\nCUT_OUTLINE\n90\n4\n70\n1\n"
        "10\n0.0\n20\n0.0\n10\n800\n20\n0.0\n10\n800\n20\n40\n10\n0.0\n20\n40\n"
        "0\nENDSEC\n0\nEOF\n",
        encoding="utf-8",
    )
    return dxf_path


def test_runner_end_to_end(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    (root / "WORK").mkdir(parents=True)
    marker = root / "project.ai-dg.json"
    marker.write_text(json.dumps({"project_name": "TEST", "work_root": "WORK"}, ensure_ascii=False), encoding="utf-8")
    _write_sample_dxf(root)

    result = runner.run_pipeline(root, run_id="e2e-test", render_pdf=False, review_status="OPEN")
    payload = result.to_dict()
    assert result.status == "DONE"
    assert payload["package_count"] == 1
    assert payload["artifacts"]["index"]["entries"]
    assert payload["artifacts"]["reconciliation"]["comparisons"]
    assert payload["artifacts"]["dimension_graph"]["nodes"]
    assert payload["artifacts"]["build_plan"]["operations"] == []  # review OPEN -> no build


def test_runner_artifacts_written_to_work(tmp_path: Path) -> None:
    root = tmp_path / "proj3"
    (root / "WORK").mkdir(parents=True)
    marker = root / "project.ai-dg.json"
    marker.write_text(json.dumps({"project_name": "TEST3", "work_root": "WORK"}, ensure_ascii=False), encoding="utf-8")
    _write_sample_dxf(root)

    result = runner.run_pipeline(root, run_id="e2e-write", render_pdf=False, review_status="OPEN")
    run_dir = root / "WORK" / "pipeline" / "e2e-write"
    assert (run_dir / "index" / "drawing-index.json").is_file()
    assert (run_dir / "reconciliation" / "source-reconciliation.json").is_file()
    assert (run_dir / "graphs" / "dimension-graph.json").is_file()
    assert (run_dir / "review" / "review-queue.json").is_file()
    assert (run_dir / "spec" / "model-spec.json").is_file()
    assert (run_dir / "plan" / "build-plan.json").is_file()
    assert (run_dir / "run-summary.json").is_file()
    assert result.build_plan is not None
