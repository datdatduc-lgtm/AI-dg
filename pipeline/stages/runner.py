"""Pipeline Orchestrator (M2..M9 end-to-end).

Runs the full 2D->3D pipeline against a project root:

    M2 ingest       scan INPUT -> Source Packages
    M3 index        build Drawing Index + view links
    M3 reconcile    reconcile dimension facts (PDF/CAD/Excel)
    M4 graph        Dimension + Material graphs with conflict detection
    M5 review       source review queue (never auto-approves conflicts)
    M5 spec         ModelSpec (only explicit facts are buildable)
    M6 plan         Build Plan for approved items
    M7 verify       VerificationReport vs measured model data
    M8/M9 build     Build IR plus readable JSON/Python/Ruby codegen

Outputs land under `WORK/pipeline/<run_id>/` and follow the schema_version 0.1
JSON contract used by the estimator skill (provenance + run_id preserved).
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .source_ingestion import (
    SourcePackage,
    IMAGE_EXTENSIONS,
    ingest_source,
    new_source_id,
    save_package,
)
from .drawing_index import build_drawing_index, save_index
from .reconciliation import reconcile_dimensions, save_report as save_recon_report
from .graphs import build_dimension_graph, build_material_graph, save_graph
from .review_queue import queue_from_conflicts, save_queue
from .model_spec import generate_model_spec, save_spec
from .builder import plan_build, save_plan
from .build_ir import build_from_model_spec, generate_codegen, save_build_ir, validate_build_ir
from .verification import verify_model_vs_spec, save_report as save_verify_report

SUPPORTED_EXT = {
    ".pdf": "pdf",
    ".dxf": "dxf",
    ".dwg": "dxf",
    ".xlsx": "excel",
    ".xls": "excel",
    ".skp": "skp",
    **{extension: "image" for extension in IMAGE_EXTENSIONS},
}


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class PipelineRun:
    run_id: str
    project_root: str
    status: str = "DONE"
    generated_utc: str = field(default_factory=utcnow)
    packages: list[dict[str, Any]] = field(default_factory=list)
    index: dict[str, Any] | None = None
    reconciliation: dict[str, Any] | None = None
    dimension_graph: dict[str, Any] | None = None
    material_graph: dict[str, Any] | None = None
    review_queue: dict[str, Any] | None = None
    model_spec: dict[str, Any] | None = None
    build_plan: dict[str, Any] | None = None
    build_ir: dict[str, Any] | None = None
    codegen: dict[str, Any] | None = None
    verification: dict[str, Any] | None = None
    gate_status: str = "REVIEW_REQUIRED"

    def to_dict(self) -> dict[str, Any]:
        artifacts = {
            "index": self.index,
            "reconciliation": self.reconciliation,
            "dimension_graph": self.dimension_graph,
            "material_graph": self.material_graph,
            "review_queue": self.review_queue,
            "model_spec": self.model_spec,
            "build_plan": self.build_plan,
            "build_ir": self.build_ir,
            "codegen": self.codegen,
            "verification": self.verification,
        }
        return {
            "schema_version": "0.1",
            "run_id": self.run_id,
            "project_root": self.project_root,
            "status": self.status,
            "gate_status": self.gate_status,
            "generated_utc": self.generated_utc,
            "package_count": len(self.packages),
            "artifacts": {key: value for key, value in artifacts.items() if value is not None},
        }


def _resolve_inputs(project_root: Path) -> list[Path]:
    input_dir = project_root / "INPUT"
    if not input_dir.is_dir():
        raise ValueError(f"INPUT directory not found under {project_root}")
    files = [p for p in sorted(input_dir.rglob("*")) if p.is_file() and p.suffix.lower() in SUPPORTED_EXT]
    if not files:
        raise ValueError(f"No supported 2D source files under {input_dir}")
    return files


def _dimension_facts_from_package(package: SourcePackage) -> list[dict[str, Any]]:
    facts = []
    for dim in package.dimensions:
        values = dim.get("values_mm")
        if not isinstance(values, list):
            values = [dim.get("value_mm")] if dim.get("value_mm") is not None else [dim.get(key) for key in ("a_mm", "b_mm", "c_mm")]
        for ordinal, value in enumerate(values):
            if not isinstance(value, (int, float)):
                continue
            facts.append(
                {
                    "fact": str(dim.get("fact") or "dimension candidate"),
                    "axis": str(dim.get("axis") or "-"),
                    "span": str(dim.get("span") or f"page-{dim.get('page', '?')}"),
                    "value_mm": float(value),
                    "item_code": dim.get("item_code") or "UNKNOWN",
                    "dim": dim.get("dim") or f"candidate_{ordinal + 1}",
                    "source_id": package.source_id,
                    "source_type": package.source_type,
                    "drawing_id": dim.get("drawing_id"),
                    "part_id": dim.get("part_id"),
                    "part_role": dim.get("part_role") or dim.get("role"),
                    "origin_mm": dim.get("origin_mm"),
                    "material_code": dim.get("material_code"),
                    "provenance": dim.get("provenance") or {"source_id": package.source_id, "page": dim.get("page")},
                    "confidence": float(dim.get("confidence", 0.9)),
                }
            )
    return facts


def _material_facts_from_package(package: SourcePackage) -> list[dict[str, Any]]:
    return [
        {
            "item_code": mat.get("item_code") or "UNKNOWN",
            "material_code": mat.get("code"),
            "role": mat.get("role") or "body",
            "provenance": mat.get("provenance"),
            "source_id": package.source_id,
            "source_type": package.source_type,
            "confidence": float(mat.get("confidence", 0.7)),
        }
        for mat in package.materials
        if mat.get("code")
    ]
def _assign_dimension_roles(facts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Assign a semantic role (width/depth/height) using axis + span heuristics.

    This is deliberately conservative: only facts with explicit axis labels are
    given a role; the rest remain 'candidate' and require source review before
    they can be part of a buildable ModelSpec.
    """
    axis_role = {"X": "width", "Y": "depth", "Z": "height", "-": None}
    roles_by_span: dict[str, dict[str, int]] = {}
    for fact in facts:
        span = str(fact.get("span") or "?")
        role = axis_role.get(str(fact.get("axis") or "-"))
        if role is None:
            continue
        bucket = roles_by_span.setdefault(span, {})
        bucket[role] = bucket.get(role, 0) + 1
        fact["dim"] = role
        fact["state"] = "EXPLICIT" if fact.get("confidence", 0) >= 0.8 else "DERIVED"
    return facts


def run_pipeline(
    project_root: str | Path,
    run_id: str = "",
    render_pdf: bool = True,
    review_status: str = "OPEN",
    model_measurements: dict[str, dict[str, float]] | None = None,
) -> PipelineRun:
    """Execute the full 2D->3D pipeline and return a PipelineRun summary.

    `review_status` is informational: the queue itself is never auto-approved,
    but a caller can pass APPROVED after a human review to demonstrate the
    build-plan path in tests.
    """
    root = Path(project_root).expanduser().resolve()
    if root.drive.upper() == "D:":
        raise PermissionError("PROTECTED_DRIVE_WRITE_DENIED: pipeline outputs must not be written under D:")
    run_id = run_id or str(uuid.uuid4())
    work_dir = root / "WORK" / "pipeline" / run_id
    if not work_dir.is_relative_to(root / "WORK"):
        raise ValueError(f"Unsafe run work directory: {work_dir}")
    work_dir.mkdir(parents=True, exist_ok=True)

    sources = _resolve_inputs(root)
    packages: list[SourcePackage] = []
    for index, source_path in enumerate(sources):
        package = ingest_source(source_path, render=render_pdf, work_dir=work_dir)
        package.source_id = new_source_id(index + 1)
        save_package(package, work_dir / "packages" / f"{package.source_id}-{source_path.stem}.json")
        packages.append(package)

    if not packages:
        raise ValueError("No package could be ingested")

    package_dicts = [p.to_dict() for p in packages]
    index = build_drawing_index(packages, run_id=run_id)
    save_index(index, work_dir / "index" / "drawing-index.json")

    drawing_lookup = {(entry["source_id"], entry["page"]): entry["id"] for entry in index.entries}
    for package in packages:
        for dimension in package.dimensions:
            page = dimension.get("page", 1)
            dimension["drawing_id"] = drawing_lookup.get((package.source_id, page))
    for package, source_path in zip(packages, sources):
        save_package(package, work_dir / "packages" / f"{package.source_id}-{source_path.stem}.json")
    package_dicts = [p.to_dict() for p in packages]

    facts: list[dict[str, Any]] = []
    mat_facts: list[dict[str, Any]] = []
    for package in packages:
        facts.extend(_dimension_facts_from_package(package))
        mat_facts.extend(_material_facts_from_package(package))

    _assign_dimension_roles(facts)

    reconciliation = reconcile_dimensions(facts, run_id=run_id)
    save_recon_report(reconciliation, work_dir / "reconciliation" / "source-reconciliation.json")

    dimension_graph = build_dimension_graph(facts, run_id=run_id)
    material_graph = build_material_graph(mat_facts, run_id=run_id)
    save_graph(work_dir / "graphs" / "dimension-graph.json", dimension_graph.to_dict())
    save_graph(work_dir / "graphs" / "material-graph.json", material_graph.to_dict())

    review = queue_from_conflicts(dimension_graph.conflicts, run_id=run_id)
    if not facts:
        review.add(
            "No dimension facts recovered from any source",
            severity="BLOCKER",
            impact="A ModelSpec cannot be built without measured source dimensions",
            category="dimensions",
        )
    if not mat_facts:
        review.add(
            "No material facts recovered from any source",
            severity="BLOCKER",
            impact="Materials cannot be assigned",
            category="materials",
        )
    spec = generate_model_spec(facts, run_id=run_id, mat_graph=material_graph)
    spec.source_review_status = review_status
    for item in spec.items:
        if item.get("buildable_state") != "READY":
            review.add(
                f"ModelSpec {item.get('item_code', 'UNKNOWN')} has missing, inferred or unresolved dimensions",
                severity="HIGH",
                impact="Build is blocked until source facts are reviewed",
                category="dimensions",
            )
    review.status = "BLOCKED" if review.has_blockers() else "OPEN"
    effective_review_status = review_status if not review.items else "BLOCKED"
    spec.source_review_status = effective_review_status
    save_queue(review, work_dir / "review" / "review-queue.json")
    save_spec(spec, work_dir / "spec" / "model-spec.json")

    build_ir_obj = build_from_model_spec(spec.to_dict())
    build_ir_data = build_ir_obj.to_dict()
    save_build_ir(build_ir_obj, work_dir / "build" / "build-ir.json")
    codegen_meta: dict[str, Any]
    codegen_errors = validate_build_ir(build_ir_data)
    if codegen_errors:
        codegen_meta = {"status": "BLOCKED", "errors": codegen_errors, "files": {}}
    else:
        generated = generate_codegen(build_ir_data)
        codegen_meta = {"status": "READY", "errors": [], "files": {}}
        for language, content in generated.items():
            extension = "json" if language == "json" else language
            output_path = work_dir / "build" / "codegen" / f"build-ir.{extension}"
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(content, encoding="utf-8")
            codegen_meta["files"][language] = {"path": str(output_path), "bytes": len(content.encode("utf-8"))}

    plan = plan_build(spec.items, run_id=run_id, source_review_status=effective_review_status)
    save_plan(plan, work_dir / "plan" / "build-plan.json")

    gate_status = "BLOCKED" if review.has_blockers() else "REVIEW_REQUIRED" if review.items or review_status != "APPROVED" else "READY"

    verification = None
    if model_measurements:
        report = verify_model_vs_spec(spec.items, model_measurements, run_id=run_id)
        verification = report.to_dict()
        save_verify_report(report, work_dir / "verification" / "verification.json")

    result = PipelineRun(
        run_id=run_id,
        project_root=str(root),
        packages=package_dicts,
        index=index.to_dict(),
        reconciliation=reconciliation.to_dict(),
        dimension_graph=dimension_graph.to_dict(),
        material_graph=material_graph.to_dict(),
        review_queue=review.to_dict(),
        model_spec=spec.to_dict(),
        build_plan=plan.to_dict(),
        build_ir=build_ir_data,
        codegen=codegen_meta,
        verification=verification,
        gate_status=gate_status,
    )
    summary_path = work_dir / "run-summary.json"
    summary_path.write_text(json.dumps(result.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return result
