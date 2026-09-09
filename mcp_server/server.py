#!/usr/bin/env python3
import os
import sys
import json
import socket
import subprocess
import time
import uuid
from pathlib import Path
from typing import Optional, Dict, Any, List
from mcp.server.fastmcp import FastMCP

from policy import delete_guard, write_guard
from registries import list_plugins, list_skills, load_skill, plugin_diagnostics, reload_plugin, set_plugin_enabled
from sketchup_analyzer import analyze_file
from logging_utils import ensure_log_files, log_event
from workflow_profile import build_profile
from tool_exposure import TOOL_TO_GROUP, apply_profile
from instance_router import RouterFailure, SketchUpInstanceRouter

mcp = FastMCP("AI-DG Universal Bridge")

ROOT_DIR = Path(os.environ.get("AI_DG_ROOT", str(Path(__file__).resolve().parents[1]))).resolve()
DEVELOPER_MODE = os.environ.get("AI_DG_DEVELOPER_MODE", "0") == "1"
SESSION_ID = os.environ.get("AI_DG_SESSION_ID", f"mcp-session-{uuid.uuid4()}")
DEFAULT_BRIDGE_TIMEOUT = 15.0
INSTANCE_ROUTER = SketchUpInstanceRouter(ROOT_DIR)
MODEL_WRITE_ACTIONS = frozenset(
    {
        "create_primitive_box",
        "create_semantic_item",
        "create_group",
        "create_component",
        "transform_entity",
        "apply_material",
        "set_tag",
        "undo",
        "set_write_mode",
    }
)
TOOL_REGISTRY = [
    {"id": "sketchup_list_instances", "permission": "sketchup.read", "risk": "LOW"},
    {"id": "sketchup_select_instance", "permission": "sketchup.target", "risk": "LOW"},
    {"id": "sketchup_get_active_instance", "permission": "sketchup.read", "risk": "LOW"},
    {"id": "sketchup_clear_instance", "permission": "sketchup.target", "risk": "LOW"},
    {"id": "sketchup_ping", "permission": "sketchup.read", "risk": "LOW"},
    {"id": "sketchup_health", "permission": "sketchup.read", "risk": "LOW"},
    {"id": "sketchup_get_runtime_state", "permission": "runtime.read", "risk": "LOW"},
    {"id": "sketchup_get_model_summary", "permission": "sketchup.read", "risk": "LOW"},
    {"id": "sketchup_get_selection", "permission": "sketchup.read", "risk": "LOW"},
    {"id": "sketchup_get_entity", "permission": "sketchup.read", "risk": "LOW"},
    {"id": "sketchup_get_hierarchy", "permission": "sketchup.read", "risk": "LOW"},
    {"id": "sketchup_list_components", "permission": "sketchup.read", "risk": "LOW"},
    {"id": "sketchup_list_materials", "permission": "sketchup.read", "risk": "LOW"},
    {"id": "sketchup_list_tags", "permission": "sketchup.read", "risk": "LOW"},
    {"id": "sketchup_list_scenes", "permission": "sketchup.read", "risk": "LOW"},
    {"id": "sketchup_get_camera", "permission": "sketchup.read", "risk": "LOW"},
    {"id": "sketchup_get_bounds", "permission": "sketchup.read", "risk": "LOW"},
    {"id": "sketchup_get_trace", "permission": "runtime.read", "risk": "LOW"},
    {"id": "sketchup_reload_runtime", "permission": "runtime.reload", "risk": "MEDIUM"},
    {"id": "sketchup_write_mode_status", "permission": "sketchup.read", "risk": "LOW"},
    {"id": "sketchup_set_write_mode", "permission": "sketchup.write_mode", "risk": "HIGH"},
    {"id": "sketchup_list_runtime_tools", "permission": "runtime.read", "risk": "LOW"},
    {"id": "ai_dg_runtime_status", "permission": "runtime.read", "risk": "LOW"},
    {"id": "ai_dg_build_workflow_profile", "permission": "filesystem.write", "risk": "MEDIUM"},
    {"id": "ai_dg_source_ingest", "permission": "filesystem.write", "risk": "MEDIUM"},
    {"id": "ai_dg_pipeline_run", "permission": "filesystem.write", "risk": "MEDIUM"},
    {"id": "ai_dg_pipeline_artifacts", "permission": "filesystem.read", "risk": "LOW"},
    {"id": "ai_dg_review_queue", "permission": "filesystem.read", "risk": "LOW"},
    {"id": "ai_dg_model_spec", "permission": "filesystem.read", "risk": "LOW"},
    {"id": "ai_dg_build_plan", "permission": "filesystem.read", "risk": "LOW"},
    {"id": "ai_dg_build_ir", "permission": "filesystem.read", "risk": "LOW"},
    {"id": "ai_dg_codegen", "permission": "filesystem.read", "risk": "LOW"},
    {"id": "ai_dg_execute_build_plan", "permission": "sketchup.write", "risk": "HIGH"},
    {"id": "ai_dg_execute_build_ir_v2", "permission": "sketchup.write", "risk": "HIGH"},
    {"id": "ai_dg_verification", "permission": "filesystem.read", "risk": "LOW"},
    {"id": "ai_dg_verify_sketchup_build_v2", "permission": "sketchup.read", "risk": "LOW"},
    {"id": "ai_dg_list_tools", "permission": "runtime.read", "risk": "LOW"},
    {"id": "sketchup_capture_viewport", "permission": "filesystem.write", "risk": "MEDIUM"},
    {"id": "sketchup_create_box", "permission": "sketchup.write", "risk": "MEDIUM"},
    {"id": "sketchup_get_semantic_item", "permission": "sketchup.read", "risk": "LOW"},
    {"id": "sketchup_create_semantic_item", "permission": "sketchup.write", "risk": "MEDIUM"},
    {"id": "sketchup_create_group", "permission": "sketchup.write", "risk": "MEDIUM"},
    {"id": "sketchup_create_component", "permission": "sketchup.write", "risk": "MEDIUM"},
    {"id": "sketchup_create_cabinet", "permission": "sketchup.write", "risk": "MEDIUM"},
    {"id": "sketchup_create_panel", "permission": "sketchup.write", "risk": "MEDIUM"},
    {"id": "sketchup_create_partition", "permission": "sketchup.write", "risk": "MEDIUM"},
    {"id": "sketchup_create_shelf", "permission": "sketchup.write", "risk": "MEDIUM"},
    {"id": "sketchup_create_door", "permission": "sketchup.write", "risk": "MEDIUM"},
    {"id": "sketchup_create_drawer", "permission": "sketchup.write", "risk": "MEDIUM"},
    {"id": "sketchup_create_countertop", "permission": "sketchup.write", "risk": "MEDIUM"},
    {"id": "sketchup_create_component_from_spec", "permission": "sketchup.write", "risk": "MEDIUM"},
    {"id": "sketchup_transform_entity", "permission": "sketchup.write", "risk": "MEDIUM"},
    {"id": "sketchup_apply_material", "permission": "sketchup.write", "risk": "MEDIUM"},
    {"id": "sketchup_set_tag", "permission": "sketchup.write", "risk": "MEDIUM"},
    {"id": "sketchup_undo", "permission": "sketchup.write", "risk": "HIGH"},
    {"id": "sketchup_eval_ruby", "permission": "developer.only", "risk": "HIGH"},
    {"id": "ai_dg_list_skills", "permission": "filesystem.read", "risk": "LOW"},
    {"id": "ai_dg_load_skill", "permission": "filesystem.read", "risk": "LOW"},
    {"id": "ai_dg_list_plugins", "permission": "filesystem.read", "risk": "LOW"},
    {"id": "ai_dg_plugin_set_enabled", "permission": "filesystem.write", "risk": "MEDIUM"},
    {"id": "ai_dg_plugin_reload", "permission": "plugin.reload", "risk": "MEDIUM"},
    {"id": "ai_dg_plugin_diagnostics", "permission": "filesystem.read", "risk": "LOW"},
    {"id": "ai_dg_test_read_tool", "permission": "sketchup.read", "risk": "LOW"},
    {"id": "aidg_analyze_skp_readonly", "permission": "filesystem.read", "risk": "LOW"},
    {"id": "aidg_write_text_guarded", "permission": "filesystem.write", "risk": "MEDIUM"},
    {"id": "aidg_delete_file_guarded", "permission": "filesystem.delete", "risk": "HIGH"},
    {"id": "aidg_prepare_run", "permission": "filesystem.write", "risk": "MEDIUM"},
    {"id": "aidg_analyze_drawing_pdf", "permission": "filesystem.write", "risk": "MEDIUM"},
    {"id": "aidg_read_cad_dxf", "permission": "filesystem.read", "risk": "LOW"},
    {"id": "aidg_calculate_bom", "permission": "filesystem.write", "risk": "MEDIUM"},
    {"id": "aidg_export_project_excel", "permission": "filesystem.write", "risk": "MEDIUM"},
    {"id": "aidg_export_dxf_netting", "permission": "filesystem.write", "risk": "MEDIUM"},
]
if not DEVELOPER_MODE:
    TOOL_REGISTRY = [row for row in TOOL_REGISTRY if row["id"] != "sketchup_eval_ruby"]

ACTIVE_TOOL_IDS = frozenset()
ACTIVE_TOOL_EXPOSURE: dict[str, Any] = {
    "profile": "uninitialised",
    "groups": [],
    "all_tool_count": len(TOOL_REGISTRY),
    "exposed_tool_count": 0,
    "hidden_tool_count": len(TOOL_REGISTRY),
    "hidden_tool_ids": [row["id"] for row in TOOL_REGISTRY],
    "schema_reduction_percent": 100.0,
}

def _target_identity(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "instance_id": record["instance_id"],
        "pid": record["pid"],
        "boot_id": record.get("boot_id"),
        "port": record["port"],
    }


def send_sketchup_cmd(action: str, data: Optional[Dict[str, Any]] = None, timeout: float = DEFAULT_BRIDGE_TIMEOUT) -> Dict[str, Any]:
    request_id = f"mcp-{uuid.uuid4()}"
    started = time.perf_counter()
    target_record: dict[str, Any] | None = None
    target: dict[str, Any] | None = None
    ensure_log_files()
    log_event("mcp", "request_started", request_id=request_id, session_id=SESSION_ID, action=action)
    try:
        target_record = INSTANCE_ROUTER.resolve(require_explicit=action in MODEL_WRITE_ACTIONS)
        target = INSTANCE_ROUTER.public_target(target_record)
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            s.connect((str(target_record["host"]), int(target_record["port"])))
            payload = json.dumps({
                "action": action,
                "data": data or {},
                "request_id": request_id,
                "session_id": SESSION_ID,
                "mcp_started_at": time.time(),
                "target": _target_identity(target_record),
            }) + "\n"
            s.sendall(payload.encode("utf-8"))
            response_bytes = bytearray()
            deadline = time.monotonic() + timeout
            while b"\n" not in response_bytes:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise socket.timeout()
                s.settimeout(remaining)
                chunk = s.recv(64 * 1024)
                if not chunk:
                    break
                response_bytes.extend(chunk)
                if len(response_bytes) > 1024 * 1024:
                    raise ValueError("BRIDGE_RESPONSE_TOO_LARGE")
            line = bytes(response_bytes).split(b"\n", 1)[0]
            if not line:
                raise ConnectionError("BRIDGE_EMPTY_RESPONSE")
            response = json.loads(line.decode("utf-8"))
            response_target = response.get("target") if isinstance(response.get("target"), dict) else {}
            expected = _target_identity(target_record)
            if any(str(response_target.get(key)) != str(value) for key, value in expected.items()):
                raise RouterFailure(
                    "TARGET_IDENTITY_MISMATCH",
                    "SketchUp bridge identity did not match the selected target",
                    {"expected": expected, "received": response_target},
                )
            response["target"] = target
            response.setdefault("request_id", request_id)
            response.setdefault("session_id", SESSION_ID)
            response.setdefault("mcp_latency_ms", round((time.perf_counter() - started) * 1000, 2))
            log_event("mcp", "request_finished", request_id=request_id, session_id=SESSION_ID, action=action, status=response.get("status"), latency_ms=response.get("mcp_latency_ms"))
            log_event("tools", "tool_finished", request_id=request_id, action=action, status=response.get("status"), latency_ms=response.get("mcp_latency_ms"))
            return response
    except RouterFailure as exc:
        result = exc.as_result()
        result.update({"action": action, "request_id": request_id, "session_id": SESSION_ID})
        if target:
            result["target"] = target
        log_event("mcp", "request_finished", request_id=request_id, session_id=SESSION_ID, action=action, status="BLOCKED", error=exc.code)
        return result
    except ConnectionRefusedError:
        result = {
            "status": "error",
            "error_code": "TARGET_OFFLINE",
            "error": "TARGET_OFFLINE: selected SketchUp bridge did not accept the connection",
            "target": target,
        }
        log_event("mcp", "request_finished", request_id=request_id, session_id=SESSION_ID, action=action, status="ERROR", error="TARGET_OFFLINE")
        log_event("errors", "bridge_unavailable", request_id=request_id, action=action, instance_id=target_record.get("instance_id") if target_record else None)
        return result
    except (ConnectionResetError, BrokenPipeError, ConnectionAbortedError, ConnectionError) as e:
        result = {
            "status": "error",
            "error_code": "TARGET_OFFLINE",
            "error": f"TARGET_OFFLINE: {e.__class__.__name__}",
            "action": action,
            "request_id": request_id,
            "session_id": SESSION_ID,
            "target": target,
        }
        log_event("mcp", "request_finished", request_id=request_id, session_id=SESSION_ID, action=action, status="ERROR", error="TARGET_OFFLINE")
        log_event("errors", "bridge_disconnected", request_id=request_id, action=action, instance_id=target_record.get("instance_id") if target_record else None)
        return result
    except socket.timeout:
        result = {"status": "error", "error_code": "READ_TIMEOUT", "error": "BRIDGE_TIMEOUT", "action": action, "request_id": request_id, "session_id": SESSION_ID, "target": target}
        log_event("mcp", "request_finished", request_id=request_id, session_id=SESSION_ID, action=action, status="TIMEOUT", error="BRIDGE_TIMEOUT")
        log_event("errors", "bridge_timeout", request_id=request_id, action=action, timeout=timeout)
        return result
    except Exception as e:
        result = {"status": "error", "error_code": "INTERNAL_ERROR", "error": str(e), "request_id": request_id, "session_id": SESSION_ID, "target": target}
        log_event("mcp", "request_finished", request_id=request_id, session_id=SESSION_ID, action=action, status="ERROR", error=e.__class__.__name__)
        log_event("errors", "mcp_error", request_id=request_id, action=action, error=e.__class__.__name__)
        return result

@mcp.tool()
def sketchup_list_instances() -> str:
    """List independently registered SketchUp processes and their target identity."""
    rows = [INSTANCE_ROUTER.public_target(row) | {"age_seconds": row.get("age_seconds")} for row in INSTANCE_ROUTER.list_instances()]
    return json.dumps({"status": "ok", "count": len(rows), "instances": rows}, indent=2, ensure_ascii=False)


@mcp.tool()
def sketchup_select_instance(instance_id: str) -> str:
    """Select the exact SketchUp process used by subsequent tools in this MCP session."""
    try:
        target = INSTANCE_ROUTER.select(instance_id)
        return json.dumps({"status": "ok", "target": INSTANCE_ROUTER.public_target(target)}, indent=2, ensure_ascii=False)
    except RouterFailure as exc:
        return json.dumps(exc.as_result(), indent=2, ensure_ascii=False)


@mcp.tool()
def sketchup_get_active_instance() -> str:
    """Read the sticky target for this MCP process without choosing a fallback."""
    target = INSTANCE_ROUTER.selected()
    if not INSTANCE_ROUTER.selected_instance_id:
        return json.dumps({"status": "ok", "target": None}, indent=2, ensure_ascii=False)
    if not target or target.get("status") != "ONLINE":
        return json.dumps({"status": "error", "error_code": "TARGET_OFFLINE", "error": "Selected SketchUp target is offline", "instance_id": INSTANCE_ROUTER.selected_instance_id}, indent=2, ensure_ascii=False)
    return json.dumps({"status": "ok", "target": INSTANCE_ROUTER.public_target(target)}, indent=2, ensure_ascii=False)


@mcp.tool()
def sketchup_clear_instance() -> str:
    """Clear the MCP session's target; this does not stop or modify SketchUp."""
    previous = INSTANCE_ROUTER.clear()
    return json.dumps({"status": "ok", "cleared_instance_id": previous, "target": None}, indent=2, ensure_ascii=False)


@mcp.tool()
def sketchup_ping() -> str:
    res = send_sketchup_cmd("ping")
    return json.dumps(res, indent=2, ensure_ascii=False)

if DEVELOPER_MODE:
    @mcp.tool()
    def sketchup_eval_ruby(ruby_code: str) -> str:
        res = send_sketchup_cmd("eval_ruby", {"code": ruby_code})
        if res.get("status") == "ok":
            return f"Thuc thi Ruby thanh cong: {res.get('result')}"
        return f"Loi Ruby: {res.get('error')}"

@mcp.tool()
def sketchup_get_model_summary() -> str:
    res = send_sketchup_cmd("get_model_info")
    return json.dumps(res, indent=2, ensure_ascii=False)


@mcp.tool()
def sketchup_health() -> str:
    """Read bridge/runtime health without changing the model."""
    res = send_sketchup_cmd("health")
    return json.dumps(res, indent=2, ensure_ascii=False)


@mcp.tool()
def sketchup_get_runtime_state() -> str:
    res = send_sketchup_cmd("get_runtime_state")
    return json.dumps(res, indent=2, ensure_ascii=False)


@mcp.tool()
def sketchup_get_selection() -> str:
    res = send_sketchup_cmd("get_selection")
    return json.dumps(res, indent=2, ensure_ascii=False)


@mcp.tool()
def sketchup_get_entity(persistent_id: int) -> str:
    res = send_sketchup_cmd("get_entity", {"persistent_id": int(persistent_id)})
    if res.get("status") == "ok" and res.get("data", {}).get("found") is False:
        res["status"] = "error"
        res["error_code"] = "ENTITY_NOT_FOUND"
        res["error"] = "ENTITY_NOT_FOUND"
    return json.dumps(res, indent=2, ensure_ascii=False)


@mcp.tool()
def sketchup_get_semantic_item(item_code: str) -> str:
    """Read one AI-DG semantic item through the official SketchUp Ruby API."""
    if not item_code.strip():
        return json.dumps({"status": "error", "error": "SEMANTIC_ITEM_CODE_REQUIRED"}, ensure_ascii=False)
    res = send_sketchup_cmd("get_semantic_item", {"item_code": item_code.strip()})
    if res.get("status") == "ok" and res.get("data", {}).get("found") is False:
        res["status"] = "error"
        res["error_code"] = "SEMANTIC_ITEM_NOT_FOUND"
        res["error"] = "SEMANTIC_ITEM_NOT_FOUND"
    return json.dumps(res, indent=2, ensure_ascii=False)


@mcp.tool()
def sketchup_get_hierarchy(max_depth: int = 3, max_items: int = 200) -> str:
    res = send_sketchup_cmd("get_hierarchy", {"max_depth": max_depth, "max_items": max_items}, timeout=4.0)
    return json.dumps(res, indent=2, ensure_ascii=False)


@mcp.tool()
def sketchup_list_components() -> str:
    res = send_sketchup_cmd("list_components")
    return json.dumps(res, indent=2, ensure_ascii=False)


@mcp.tool()
def sketchup_list_materials() -> str:
    res = send_sketchup_cmd("list_materials")
    return json.dumps(res, indent=2, ensure_ascii=False)


@mcp.tool()
def sketchup_list_tags() -> str:
    res = send_sketchup_cmd("list_tags")
    return json.dumps(res, indent=2, ensure_ascii=False)


@mcp.tool()
def sketchup_list_scenes() -> str:
    res = send_sketchup_cmd("list_scenes")
    return json.dumps(res, indent=2, ensure_ascii=False)


@mcp.tool()
def sketchup_get_camera() -> str:
    res = send_sketchup_cmd("get_camera")
    return json.dumps(res, indent=2, ensure_ascii=False)


@mcp.tool()
def sketchup_get_bounds() -> str:
    res = send_sketchup_cmd("get_bounds")
    return json.dumps(res, indent=2, ensure_ascii=False)


@mcp.tool()
def sketchup_get_trace(limit: int = 100) -> str:
    res = send_sketchup_cmd("get_trace", {"limit": limit})
    return json.dumps(res, indent=2, ensure_ascii=False)


@mcp.tool()
def sketchup_reload_runtime() -> str:
    """Reload the deployed Ruby bridge in-place without restarting SketchUp."""
    res = send_sketchup_cmd("reload_runtime")
    return json.dumps(res, indent=2, ensure_ascii=False)


@mcp.tool()
def sketchup_list_runtime_tools() -> str:
    """Read the bridge-side tool catalog and last-run status."""
    res = send_sketchup_cmd("list_tools")
    return json.dumps(res, indent=2, ensure_ascii=False)


@mcp.tool()
def ai_dg_runtime_status() -> str:
    """Perform one bounded bridge ping and report local runtime status."""
    started = time.perf_counter()
    result = send_sketchup_cmd("ping", timeout=3.0)
    result = {
        "status": "ok" if result.get("status") == "ok" else "error",
        "bridge": "ONLINE" if result.get("status") == "ok" else "DISCONNECTED",
        "mcp": "CONNECTED" if result.get("status") == "ok" else "DISCONNECTED",
        "session_id": SESSION_ID,
        "latency_ms": round((time.perf_counter() - started) * 1000, 2),
        "target": result.get("target"),
        "error_code": result.get("error_code"),
        "error": result.get("error"),
    }
    return json.dumps(result, ensure_ascii=False)


@mcp.tool()
def ai_dg_build_workflow_profile(output_path: str = "E:/AI-DG/USER_PROFILE/sketchup_workflow_profile.json") -> str:
    """Aggregate current live model metadata into a privacy-aware E: profile."""
    denied = write_guard(output_path)
    if denied:
        return json.dumps(denied, ensure_ascii=False)
    reads: dict[str, Any] = {}
    for key, action, timeout in (
        ("model", "get_model_info", 4.0),
        ("components", "list_components", 4.0),
        ("materials", "list_materials", 4.0),
        ("tags", "list_tags", 4.0),
        ("scenes", "list_scenes", 4.0),
    ):
        result = send_sketchup_cmd(action, timeout=timeout)
        if result.get("status") != "ok":
            return json.dumps({"status": "error", "error": "PROFILE_SOURCE_READ_FAILED", "source": action, "detail": result.get("error")}, ensure_ascii=False)
        reads[key] = result.get("data", {})
    hierarchy = send_sketchup_cmd("get_hierarchy", {"max_depth": 2, "max_items": 200}, timeout=4.0)
    reads["hierarchy"] = hierarchy.get("data", {}) if hierarchy.get("status") == "ok" else {"items": [], "status": "unavailable", "error": hierarchy.get("error")}
    return json.dumps(build_profile([reads], output_path), ensure_ascii=False)


def _pipeline_root(project_path: str | Path) -> tuple[Path | None, dict[str, Any] | None]:
    """Resolve an E: workspace project and reject protected/system targets."""
    root = Path(project_path).expanduser().resolve()
    denied = write_guard(root / "WORK" / "pipeline")
    if denied:
        return None, denied
    try:
        inside_workspace = root == ROOT_DIR or root.is_relative_to(ROOT_DIR)
    except AttributeError:  # pragma: no cover - Python 3.8 fallback
        inside_workspace = str(root).lower().startswith(str(ROOT_DIR).lower() + os.sep)
    if not inside_workspace:
        return None, {"status": "error", "error": "PROJECT_OUTSIDE_WORKSPACE_DENIED", "path": str(root)}
    return root, None


def _pipeline_read_path(project_path: str | Path, run_id: str, artifact: str) -> tuple[Path | None, dict[str, Any] | None]:
    root, denied = _pipeline_root(project_path)
    if denied:
        return None, denied
    if not __import__("re").fullmatch(r"[A-Za-z0-9._-]{1,120}", str(run_id)):
        return None, {"status": "error", "error": "INVALID_RUN_ID"}
    allowed = {
        "summary": "run-summary.json",
        "index": "index/drawing-index.json",
        "reconciliation": "reconciliation/source-reconciliation.json",
        "dimension_graph": "graphs/dimension-graph.json",
        "material_graph": "graphs/material-graph.json",
        "review": "review/review-queue.json",
        "spec": "spec/model-spec.json",
        "plan": "plan/build-plan.json",
        "build_ir": "build/build-ir.json",
        "verification": "verification/verification.json",
        "execution": "execution/build-execution.json",
    }
    relative = allowed.get(artifact)
    if relative is None:
        return None, {"status": "error", "error": "UNKNOWN_PIPELINE_ARTIFACT", "artifact": artifact}
    path = root / "WORK" / "pipeline" / str(run_id) / relative
    if not path.is_file():
        return None, {"status": "error", "error": "PIPELINE_ARTIFACT_NOT_FOUND", "path": str(path), "artifact": artifact}
    return path, None


@mcp.tool()
def ai_dg_source_ingest(source_path: str, render: bool = False) -> str:
    """Ingest one PDF/DXF/DWG/Excel/image/SKP source into a safe E: artifact."""
    try:
        source = Path(source_path).expanduser().resolve()
        if not source.is_file():
            return json.dumps({"status": "error", "error": "SOURCE_NOT_FOUND", "path": source_path}, ensure_ascii=False)
        if str(ROOT_DIR) not in sys.path:
            sys.path.insert(0, str(ROOT_DIR))
        from pipeline.stages.source_ingestion import ingest_source, new_source_id, save_package

        output_dir = ROOT_DIR / "WORK" / "pipeline" / "source-ingestion"
        denied = write_guard(output_dir)
        if denied:
            return json.dumps(denied, ensure_ascii=False)
        package = ingest_source(source, render=bool(render), work_dir=output_dir)
        package.source_id = new_source_id(1)
        output = output_dir / f"{package.source_id}-{source.stem}.json"
        save_package(package, output)
        return json.dumps({"status": "ok", "source_id": package.source_id, "source_type": package.source_type, "package_path": str(output), "pages": len(package.pages), "dimensions": len(package.dimensions), "materials": len(package.materials)}, ensure_ascii=False)
    except (OSError, ValueError, RuntimeError, ImportError) as exc:
        return json.dumps({"status": "error", "error": "SOURCE_INGEST_FAILED", "detail": str(exc)}, ensure_ascii=False)


@mcp.tool()
def ai_dg_pipeline_run(project_path: str = "E:/AI-DG", run_id: str = "", render_pdf: bool = False, review_status: str = "OPEN", model_measurements_json: str = "") -> str:
    """Run the real M2-M7 drawing pipeline; build remains gated by review status."""
    root, denied = _pipeline_root(project_path)
    if denied:
        return json.dumps(denied, ensure_ascii=False)
    review_status = str(review_status or "OPEN").upper()
    if review_status not in {"OPEN", "APPROVED"}:
        return json.dumps({"status": "error", "error": "INVALID_REVIEW_STATUS"}, ensure_ascii=False)
    measurements = None
    if model_measurements_json.strip():
        try:
            measurements = json.loads(model_measurements_json)
            if not isinstance(measurements, dict):
                raise ValueError("model_measurements_json must be an object")
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            return json.dumps({"status": "error", "error": "INVALID_MODEL_MEASUREMENTS", "detail": str(exc)}, ensure_ascii=False)
    try:
        if str(ROOT_DIR) not in sys.path:
            sys.path.insert(0, str(ROOT_DIR))
        from pipeline.stages.runner import run_pipeline

        result = run_pipeline(root, run_id=run_id, render_pdf=bool(render_pdf), review_status=review_status, model_measurements=measurements)
        return json.dumps(result.to_dict(), ensure_ascii=False)
    except (OSError, ValueError, PermissionError, RuntimeError, ImportError) as exc:
        return json.dumps({"status": "error", "error": "PIPELINE_RUN_FAILED", "detail": str(exc)}, ensure_ascii=False)


@mcp.tool()
def ai_dg_pipeline_artifacts(run_id: str, artifact: str = "summary", project_path: str = "E:/AI-DG") -> str:
    """Read one persisted pipeline artifact without running or mutating the pipeline."""
    path, denied = _pipeline_read_path(project_path, run_id, artifact)
    if denied:
        return json.dumps(denied, ensure_ascii=False)
    try:
        return json.dumps({"status": "ok", "artifact": artifact, "path": str(path), "data": json.loads(path.read_text(encoding="utf-8"))}, ensure_ascii=False)
    except (OSError, json.JSONDecodeError) as exc:
        return json.dumps({"status": "error", "error": "PIPELINE_ARTIFACT_READ_FAILED", "detail": str(exc)}, ensure_ascii=False)


@mcp.tool()
def ai_dg_review_queue(run_id: str, project_path: str = "E:/AI-DG") -> str:
    return ai_dg_pipeline_artifacts(run_id, "review", project_path)


@mcp.tool()
def ai_dg_model_spec(run_id: str, project_path: str = "E:/AI-DG") -> str:
    return ai_dg_pipeline_artifacts(run_id, "spec", project_path)


@mcp.tool()
def ai_dg_build_plan(run_id: str, project_path: str = "E:/AI-DG") -> str:
    return ai_dg_pipeline_artifacts(run_id, "plan", project_path)


@mcp.tool()
def ai_dg_build_ir(run_id: str, project_path: str = "E:/AI-DG") -> str:
    """Read the central Build IR produced from the reviewed ModelSpec."""
    return ai_dg_pipeline_artifacts(run_id, "build_ir", project_path)


@mcp.tool()
def ai_dg_codegen(run_id: str, language: str = "json", project_path: str = "E:/AI-DG") -> str:
    """Read a generated JSON/Python/Ruby Build IR representation."""
    root, denied = _pipeline_root(project_path)
    if denied:
        return json.dumps(denied, ensure_ascii=False)
    if not __import__("re").fullmatch(r"(?:json|python|ruby)", str(language or "").lower()):
        return json.dumps({"status": "error", "error": "INVALID_CODEGEN_LANGUAGE"}, ensure_ascii=False)
    if not __import__("re").fullmatch(r"[A-Za-z0-9._-]{1,120}", str(run_id)):
        return json.dumps({"status": "error", "error": "INVALID_RUN_ID"}, ensure_ascii=False)
    extension = str(language).lower()
    path = root / "WORK" / "pipeline" / str(run_id) / "build" / "codegen" / f"build-ir.{extension}"
    if not path.is_file():
        return json.dumps({"status": "error", "error": "PIPELINE_CODEGEN_NOT_FOUND", "language": extension, "path": str(path)}, ensure_ascii=False)
    try:
        return json.dumps({"status": "ok", "artifact": f"codegen_{extension}", "path": str(path), "content": path.read_text(encoding="utf-8")}, ensure_ascii=False)
    except OSError as exc:
        return json.dumps({"status": "error", "error": "PIPELINE_CODEGEN_READ_FAILED", "detail": str(exc)}, ensure_ascii=False)


@mcp.tool()
def ai_dg_execute_build_plan(run_id: str, project_path: str = "E:/AI-DG", review_status: str = "OPEN", confirm_write: bool = False) -> str:
    """Execute an approved Build Plan through official Ruby and verify by read-back.

    The default is non-mutating.  A model write requires all of: an APPROVED
    source review, SketchUp Write mode, and ``confirm_write=true`` for this
    call.  The bridge still performs its own transaction/verify/abort guard.
    """
    root, denied = _pipeline_root(project_path)
    if denied:
        return json.dumps(denied, ensure_ascii=False)
    normalized_review = str(review_status or "OPEN").upper()
    if normalized_review not in {"OPEN", "APPROVED"}:
        return json.dumps({"status": "error", "error": "INVALID_REVIEW_STATUS"}, ensure_ascii=False)
    if confirm_write:
        try:
            INSTANCE_ROUTER.resolve(require_explicit=True)
        except RouterFailure as exc:
            return json.dumps(exc.as_result(), ensure_ascii=False)
    plan_path, denied = _pipeline_read_path(root, run_id, "plan")
    if denied:
        return json.dumps(denied, ensure_ascii=False)
    spec_path, denied = _pipeline_read_path(root, run_id, "spec")
    if denied:
        return json.dumps(denied, ensure_ascii=False)
    execution_path = root / "WORK" / "pipeline" / str(run_id) / "execution" / "build-execution.json"
    try:
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
        spec_items = spec.get("items", []) if isinstance(spec, dict) else []
        if not isinstance(spec_items, list):
            raise ValueError("model-spec items must be an array")
        mode_res = send_sketchup_cmd("get_runtime_state")
        mode_data = mode_res.get("data", {}) if isinstance(mode_res, dict) else {}
        if mode_res.get("status") != "ok":
            return json.dumps(mode_res, ensure_ascii=False)

        from pipeline.stages.executor import execute_build_plan

        def dispatch(payload: dict[str, Any]) -> dict[str, Any]:
            return send_sketchup_cmd("create_semantic_item", payload, timeout=30.0)

        def readback(item_code: str) -> dict[str, Any]:
            return send_sketchup_cmd("get_semantic_item", {"item_code": item_code}, timeout=15.0)

        execution = execute_build_plan(
            build_plan=plan,
            spec_items=spec_items,
            run_id=str(run_id),
            review_status=normalized_review,
            access_mode=str(mode_data.get("access_mode") or "read_only"),
            confirm_write=bool(confirm_write),
            dispatch=dispatch,
            readback=readback,
        )
        execution_path.parent.mkdir(parents=True, exist_ok=True)
        execution_path.write_text(json.dumps(execution, ensure_ascii=False, indent=2), encoding="utf-8")

        summary_path, summary_denied = _pipeline_read_path(root, run_id, "summary")
        if not summary_denied and summary_path:
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            summary["execution"] = execution
            if isinstance(execution.get("verification"), dict):
                summary["verification"] = execution["verification"]
            if execution.get("status") == "PASS":
                summary["gate_status"] = "PASS"
            elif execution.get("status") == "FAIL":
                summary["gate_status"] = "BUILD_FAILED"
            summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        return json.dumps({"status": "ok", "artifact": "execution", "path": str(execution_path), "data": execution}, ensure_ascii=False)
    except (OSError, ValueError, TypeError, json.JSONDecodeError, ImportError) as exc:
        return json.dumps({"status": "error", "error": "BUILD_EXECUTION_FAILED", "detail": str(exc)}, ensure_ascii=False)


@mcp.tool()
def ai_dg_verification(run_id: str, project_path: str = "E:/AI-DG") -> str:
    return ai_dg_pipeline_artifacts(run_id, "verification", project_path)


@mcp.tool()
def ai_dg_execute_build_ir_v2(project_path: str = "E:/AI-DG", confirm_write: bool = False) -> str:
    """Execute only a READY, APPROVED, projection-PASS Build IR V2."""
    root, denied = _pipeline_root(project_path)
    if denied:
        return json.dumps(denied, ensure_ascii=False)
    build_path = root / "OUTPUT" / "MODEL" / "build-ir-v2.json"
    if not build_path.is_file():
        return json.dumps({"status": "error", "error": "BUILD_IR_V2_NOT_FOUND", "path": str(build_path)}, ensure_ascii=False)
    try:
        target_record = INSTANCE_ROUTER.resolve(require_explicit=True)
        target = INSTANCE_ROUTER.public_target(target_record)
        mode_res = send_sketchup_cmd("get_runtime_state")
        if mode_res.get("status") != "ok":
            return json.dumps(mode_res, ensure_ascii=False)
        build_ir = json.loads(build_path.read_text(encoding="utf-8"))
        if str(ROOT_DIR) not in sys.path:
            sys.path.insert(0, str(ROOT_DIR))
        from pipeline.stages.executor_v2 import execute_build_ir_v2

        result = execute_build_ir_v2(
            build_ir,
            target=target,
            access_mode=str(mode_res.get("data", {}).get("access_mode") or "read_only"),
            confirm_write=bool(confirm_write),
            dispatch=lambda payload: send_sketchup_cmd("create_semantic_item", payload, timeout=50.0),
            readback=lambda code: send_sketchup_cmd("get_semantic_item", {"item_code": code}, timeout=15.0),
        )
        verification_dir = root / "OUTPUT" / "VERIFICATION"
        verification_dir.mkdir(parents=True, exist_ok=True)
        if result.get("readback"):
            (verification_dir / "sketchup-readback-v2.json").write_text(json.dumps(result["readback"], ensure_ascii=False, indent=2), encoding="utf-8")
        if result.get("postbuild"):
            (verification_dir / "projection-postbuild-v2.json").write_text(json.dumps(result["postbuild"], ensure_ascii=False, indent=2), encoding="utf-8")
        return json.dumps(result, ensure_ascii=False)
    except RouterFailure as exc:
        return json.dumps(exc.as_result(), ensure_ascii=False)
    except (OSError, ValueError, TypeError, json.JSONDecodeError, ImportError) as exc:
        return json.dumps({"status": "error", "error": "BUILD_IR_V2_EXECUTION_FAILED", "detail": str(exc)}, ensure_ascii=False)


@mcp.tool()
def ai_dg_verify_sketchup_build_v2(project_path: str = "E:/AI-DG") -> str:
    """Read back V2 items via official Ruby and run post-build projection only."""
    root, denied = _pipeline_root(project_path)
    if denied:
        return json.dumps(denied, ensure_ascii=False)
    build_path = root / "OUTPUT" / "MODEL" / "build-ir-v2.json"
    if not build_path.is_file():
        return json.dumps({"status": "error", "error": "BUILD_IR_V2_NOT_FOUND"}, ensure_ascii=False)
    try:
        target_record = INSTANCE_ROUTER.resolve(require_explicit=True)
        target = INSTANCE_ROUTER.public_target(target_record)
        build_ir = json.loads(build_path.read_text(encoding="utf-8"))
        if str(ROOT_DIR) not in sys.path:
            sys.path.insert(0, str(ROOT_DIR))
        from pipeline.stages.executor_v2 import normalize_sketchup_readback_v2
        from pipeline.stages.projection_verification_v2 import verify_postbuild_projection_v2

        regions = []
        roots = []
        for operation in build_ir.get("operations", []):
            response = send_sketchup_cmd("get_semantic_item", {"item_code": operation.get("item_code")}, timeout=15.0)
            if response.get("status") != "ok":
                return json.dumps(response, ensure_ascii=False)
            normalized = normalize_sketchup_readback_v2(response)
            regions.extend(normalized["regions"])
            roots.append(normalized["root"])
        readback = {"schema_version": 2, "target": target, "roots": roots, "regions": regions, "readback_source": "official_sketchup_ruby_api"}
        post = verify_postbuild_projection_v2(build_ir, readback)
        verification_dir = root / "OUTPUT" / "VERIFICATION"
        verification_dir.mkdir(parents=True, exist_ok=True)
        (verification_dir / "sketchup-readback-v2.json").write_text(json.dumps(readback, ensure_ascii=False, indent=2), encoding="utf-8")
        (verification_dir / "projection-postbuild-v2.json").write_text(json.dumps(post, ensure_ascii=False, indent=2), encoding="utf-8")
        return json.dumps({"status": post["status"], "target": target, "readback": readback, "postbuild": post}, ensure_ascii=False)
    except RouterFailure as exc:
        return json.dumps(exc.as_result(), ensure_ascii=False)
    except (OSError, ValueError, TypeError, json.JSONDecodeError, ImportError) as exc:
        return json.dumps({"status": "error", "error": "POSTBUILD_V2_FAILED", "detail": str(exc)}, ensure_ascii=False)


@mcp.tool()
def ai_dg_list_tools() -> str:
    tools = [
        dict(
            row,
            capability=TOOL_TO_GROUP.get(row["id"], "UNMAPPED"),
            enabled=row["id"] in ACTIVE_TOOL_IDS,
        )
        for row in TOOL_REGISTRY
    ]
    return json.dumps(
        {
            "status": "ok",
            "developer_mode": DEVELOPER_MODE,
            "tool_count": len(ACTIVE_TOOL_IDS),
            "all_tool_count": len(TOOL_REGISTRY),
            "exposure": ACTIVE_TOOL_EXPOSURE,
            "tools": tools,
        },
        indent=2,
        ensure_ascii=False,
    )


@mcp.tool()
def ai_dg_list_skills() -> str:
    """List skill metadata only; SKILL.md bodies are loaded on demand."""
    return json.dumps({"status": "ok", "lazy": True, "skills": list_skills()}, indent=2, ensure_ascii=False)


@mcp.tool()
def ai_dg_load_skill(skill_id: str, max_chars: int = 20000) -> str:
    return json.dumps(load_skill(skill_id, max_chars=max_chars), indent=2, ensure_ascii=False)


@mcp.tool()
def ai_dg_list_plugins() -> str:
    return json.dumps({"status": "ok", "plugins": list_plugins()}, indent=2, ensure_ascii=False)


@mcp.tool()
def ai_dg_plugin_diagnostics() -> str:
    return json.dumps(plugin_diagnostics(), indent=2, ensure_ascii=False)


@mcp.tool()
def ai_dg_plugin_set_enabled(plugin_id: str, enabled: bool) -> str:
    return json.dumps(set_plugin_enabled(plugin_id, enabled), indent=2, ensure_ascii=False)


@mcp.tool()
def ai_dg_plugin_reload(plugin_id: str) -> str:
    return json.dumps(reload_plugin(plugin_id), indent=2, ensure_ascii=False)


@mcp.tool()
def ai_dg_test_read_tool() -> str:
    plugin = next((row for row in list_plugins() if row.get("id") == "ai-dg-test"), None)
    if not plugin or plugin.get("status") != "ENABLED":
        return json.dumps({"status": "error", "error": "PLUGIN_DISABLED", "plugin_id": "ai-dg-test"}, ensure_ascii=False)
    from plugins.ai_dg_test.plugin import read_tool

    return json.dumps(read_tool(), indent=2, ensure_ascii=False)


@mcp.tool()
def aidg_analyze_skp_readonly(path: str) -> str:
    return json.dumps(analyze_file(path), indent=2, ensure_ascii=False)


@mcp.tool()
def sketchup_capture_viewport(output_image_path: str, view_mode: str = "iso") -> str:
    denied = write_guard(output_image_path)
    if denied:
        return json.dumps(denied, ensure_ascii=False)
    res = send_sketchup_cmd("capture_viewport", {"path": output_image_path, "view_mode": view_mode})
    if res.get("status") == "ok":
        return f"Da chup anh man hinh: {res.get('image_path')}"
    return f"Loi: {res.get('error')}"

@mcp.tool()
def sketchup_create_box(width_mm: float, depth_mm: float, height_mm: float, name: str = "AI_DG_BOX", origin_x: float = 0.0, origin_y: float = 0.0, origin_z: float = 0.0) -> str:
    denied = _write_mode_error()
    if denied:
        return denied
    payload = {
        "width_mm": width_mm,
        "depth_mm": depth_mm,
        "height_mm": height_mm,
        "name": name,
        "origin": [origin_x, origin_y, origin_z]
    }
    res = send_sketchup_cmd("create_primitive_box", payload)
    return json.dumps(res, ensure_ascii=False)


def _write_mode_error() -> str | None:
    """Return a structured write-mode error before any model action is dispatched."""
    try:
        INSTANCE_ROUTER.resolve(require_explicit=True)
    except RouterFailure as exc:
        return json.dumps(exc.as_result(), ensure_ascii=False)
    mode_res = send_sketchup_cmd("get_runtime_state")
    mode_data = mode_res.get("data", {}) if isinstance(mode_res, dict) else {}
    if mode_res.get("status") != "ok":
        return json.dumps(mode_res, ensure_ascii=False)
    if mode_data.get("access_mode") != "write_enabled":
        return json.dumps({"status": "error", "error": "READ_ONLY_MODE: call sketchup_set_write_mode for the selected instance first", "access_mode": mode_data.get("access_mode", "read_only"), "target": mode_res.get("target")}, ensure_ascii=False)
    return None


def _dispatch_semantic_item(
    item_code: str,
    parts: list[dict[str, Any]],
    name: str = "",
    source_refs: list[str] | None = None,
    builder_type: str = "component_from_spec",
    tool_name: str = "sketchup_create_semantic_item",
) -> str:
    denied = _write_mode_error()
    if denied:
        return denied
    if not item_code.strip():
        return json.dumps({"status": "error", "error": "SEMANTIC_ITEM_CODE_REQUIRED"}, ensure_ascii=False)
    if not isinstance(parts, list) or not parts:
        return json.dumps({"status": "error", "error": "SEMANTIC_PARTS_REQUIRED"}, ensure_ascii=False)
    payload = {
        "item_code": item_code.strip(),
        "name": name.strip(),
        "parts": parts[:500],
        "source_refs": [str(value)[:200] for value in (source_refs or [])[:100]],
        "schema_version": "0.1",
        "pipeline_stage": "M6-BUILD",
        "builder_type": builder_type,
        "tool_name": tool_name,
    }
    res = send_sketchup_cmd("create_semantic_item", payload, timeout=30.0)
    return json.dumps(res, ensure_ascii=False)


def _single_builder(
    tool_name: str,
    builder_type: str,
    item_code: str,
    width_mm: float,
    depth_mm: float,
    height_mm: float,
    material_code: str = "",
    name: str = "",
    origin_x: float = 0.0,
    origin_y: float = 0.0,
    origin_z: float = 0.0,
    source_ref: str = "",
) -> str:
    try:
        dimensions = {"width_mm": float(width_mm), "depth_mm": float(depth_mm), "height_mm": float(height_mm)}
        origin = [float(origin_x), float(origin_y), float(origin_z)]
    except (TypeError, ValueError):
        return json.dumps({"status": "error", "error": "SEMANTIC_PART_DIMENSIONS_INVALID"}, ensure_ascii=False)
    part = {
        "part_id": f"{item_code.strip()}-{builder_type}",
        "role": builder_type,
        "material_code": material_code.strip(),
        "dimensions_mm": dimensions,
        "origin_mm": origin,
        "source_refs": [source_ref.strip()] if source_ref.strip() else [],
    }
    return _dispatch_semantic_item(
        item_code=item_code,
        parts=[part],
        name=name,
        source_refs=[source_ref] if source_ref.strip() else [],
        builder_type=builder_type,
        tool_name=tool_name,
    )


@mcp.tool()
def sketchup_create_semantic_item(item_code: str, parts_json: str, name: str = "", source_refs_json: str = "") -> str:
    """Build explicit semantic parts in one transaction; no envelope guessing or primitive fallback."""
    try:
        parts = json.loads(parts_json)
        source_refs = json.loads(source_refs_json) if source_refs_json.strip() else []
        if not isinstance(parts, list) or not parts:
            raise ValueError("parts_json must be a non-empty array")
        if not isinstance(source_refs, list):
            raise ValueError("source_refs_json must be an array")
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        return json.dumps({"status": "error", "error": "INVALID_SEMANTIC_ITEM", "detail": str(exc)}, ensure_ascii=False)
    return _dispatch_semantic_item(item_code, parts, name=name, source_refs=source_refs, builder_type="component_from_spec", tool_name="sketchup_create_semantic_item")


@mcp.tool()
def sketchup_create_group(name: str, item_id: str = "", source_spec_id: str = "") -> str:
    """Create an empty named group with AI-DG provenance metadata."""
    denied = _write_mode_error()
    if denied:
        return denied
    res = send_sketchup_cmd("create_group", {"name": name, "item_id": item_id, "source_spec_id": source_spec_id}, timeout=30.0)
    return json.dumps(res, ensure_ascii=False)


@mcp.tool()
def sketchup_create_component(name: str, parts_json: str, item_id: str = "", source_spec_id: str = "", source_refs_json: str = "") -> str:
    """Create a real SketchUp component from explicit part boxes in one transaction."""
    denied = _write_mode_error()
    if denied:
        return denied
    try:
        parts = json.loads(parts_json)
        source_refs = json.loads(source_refs_json) if source_refs_json.strip() else []
        if not isinstance(parts, list) or not parts:
            raise ValueError("parts_json must be a non-empty array")
        if not isinstance(source_refs, list):
            raise ValueError("source_refs_json must be an array")
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        return json.dumps({"status": "error", "error": "INVALID_COMPONENT", "detail": str(exc)}, ensure_ascii=False)
    res = send_sketchup_cmd("create_component", {"name": name.strip(), "parts": parts[:500], "item_id": item_id, "source_spec_id": source_spec_id, "source_refs": source_refs[:100]}, timeout=30.0)
    return json.dumps(res, ensure_ascii=False)


@mcp.tool()
def sketchup_create_cabinet(item_code: str, parts_json: str, name: str = "", source_refs_json: str = "") -> str:
    """Create a cabinet from an explicit carcass/door/shelf part list; never infer missing parts."""
    try:
        parts = json.loads(parts_json)
        source_refs = json.loads(source_refs_json) if source_refs_json.strip() else []
        if not isinstance(parts, list) or not isinstance(source_refs, list):
            raise ValueError("parts_json and source_refs_json must be arrays")
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        return json.dumps({"status": "error", "error": "INVALID_CABINET_SPEC", "detail": str(exc)}, ensure_ascii=False)
    return _dispatch_semantic_item(item_code, parts, name=name, source_refs=source_refs, builder_type="cabinet", tool_name="sketchup_create_cabinet")


@mcp.tool()
def sketchup_create_panel(item_code: str, width_mm: float, depth_mm: float, height_mm: float, material_code: str = "", name: str = "", origin_x: float = 0.0, origin_y: float = 0.0, origin_z: float = 0.0, source_ref: str = "") -> str:
    return _single_builder("sketchup_create_panel", "panel", item_code, width_mm, depth_mm, height_mm, material_code, name, origin_x, origin_y, origin_z, source_ref)


@mcp.tool()
def sketchup_create_partition(item_code: str, width_mm: float, depth_mm: float, height_mm: float, material_code: str = "", name: str = "", origin_x: float = 0.0, origin_y: float = 0.0, origin_z: float = 0.0, source_ref: str = "") -> str:
    return _single_builder("sketchup_create_partition", "partition", item_code, width_mm, depth_mm, height_mm, material_code, name, origin_x, origin_y, origin_z, source_ref)


@mcp.tool()
def sketchup_create_shelf(item_code: str, width_mm: float, depth_mm: float, height_mm: float, material_code: str = "", name: str = "", origin_x: float = 0.0, origin_y: float = 0.0, origin_z: float = 0.0, source_ref: str = "") -> str:
    return _single_builder("sketchup_create_shelf", "shelf", item_code, width_mm, depth_mm, height_mm, material_code, name, origin_x, origin_y, origin_z, source_ref)


@mcp.tool()
def sketchup_create_door(item_code: str, width_mm: float, depth_mm: float, height_mm: float, material_code: str = "", name: str = "", origin_x: float = 0.0, origin_y: float = 0.0, origin_z: float = 0.0, source_ref: str = "") -> str:
    return _single_builder("sketchup_create_door", "door", item_code, width_mm, depth_mm, height_mm, material_code, name, origin_x, origin_y, origin_z, source_ref)


@mcp.tool()
def sketchup_create_drawer(item_code: str, width_mm: float, depth_mm: float, height_mm: float, material_code: str = "", name: str = "", origin_x: float = 0.0, origin_y: float = 0.0, origin_z: float = 0.0, source_ref: str = "") -> str:
    return _single_builder("sketchup_create_drawer", "drawer", item_code, width_mm, depth_mm, height_mm, material_code, name, origin_x, origin_y, origin_z, source_ref)


@mcp.tool()
def sketchup_create_countertop(item_code: str, width_mm: float, depth_mm: float, height_mm: float, material_code: str = "", name: str = "", origin_x: float = 0.0, origin_y: float = 0.0, origin_z: float = 0.0, source_ref: str = "") -> str:
    return _single_builder("sketchup_create_countertop", "countertop", item_code, width_mm, depth_mm, height_mm, material_code, name, origin_x, origin_y, origin_z, source_ref)


@mcp.tool()
def sketchup_create_component_from_spec(item_code: str, parts_json: str, name: str = "", source_refs_json: str = "") -> str:
    """Create the semantic component represented by an approved ModelSpec."""
    return sketchup_create_semantic_item(item_code, parts_json, name, source_refs_json)


@mcp.tool()
def sketchup_transform_entity(persistent_id: int, translation_x_mm: float = 0.0, translation_y_mm: float = 0.0, translation_z_mm: float = 0.0) -> str:
    denied = _write_mode_error()
    if denied:
        return denied
    res = send_sketchup_cmd("transform_entity", {"persistent_id": int(persistent_id), "translation_mm": [translation_x_mm, translation_y_mm, translation_z_mm]}, timeout=30.0)
    return json.dumps(res, ensure_ascii=False)


@mcp.tool()
def sketchup_apply_material(persistent_id: int, material_code: str, material_role: str = "") -> str:
    denied = _write_mode_error()
    if denied:
        return denied
    res = send_sketchup_cmd("apply_material", {"persistent_id": int(persistent_id), "material_code": material_code, "material_role": material_role}, timeout=30.0)
    return json.dumps(res, ensure_ascii=False)


@mcp.tool()
def sketchup_set_tag(persistent_id: int, tag: str) -> str:
    denied = _write_mode_error()
    if denied:
        return denied
    res = send_sketchup_cmd("set_tag", {"persistent_id": int(persistent_id), "tag": tag}, timeout=30.0)
    return json.dumps(res, ensure_ascii=False)


@mcp.tool()
def sketchup_undo(confirm: bool = False) -> str:
    """Undo exactly one SketchUp operation only after explicit confirmation."""
    denied = _write_mode_error()
    if denied:
        return denied
    if not confirm:
        return json.dumps({"status": "error", "error": "UNDO_CONFIRMATION_REQUIRED"}, ensure_ascii=False)
    res = send_sketchup_cmd("undo", {"confirm": True}, timeout=30.0)
    return json.dumps(res, ensure_ascii=False)


@mcp.tool()
def sketchup_write_mode_status() -> str:
    """Return the SketchUp-side access mode; Normal Mode is read-only by default."""
    res = send_sketchup_cmd("get_runtime_state")
    return json.dumps(res, indent=2, ensure_ascii=False)


@mcp.tool()
def sketchup_set_write_mode(mode: str = "read_only", confirm: bool = False) -> str:
    """Change write mode for the selected SketchUp process.

    Enabling writes requires ``confirm=true`` and a native confirmation in
    that exact SketchUp process. Disabling writes never prompts.
    """
    normalized = str(mode).strip().lower()
    if normalized not in {"read_only", "write_enabled"}:
        return json.dumps({"status": "error", "error": "INVALID_WRITE_MODE"}, ensure_ascii=False)
    if normalized == "write_enabled" and not confirm:
        return json.dumps({"status": "error", "error": "WRITE_MODE_CONFIRMATION_REQUIRED"}, ensure_ascii=False)
    res = send_sketchup_cmd("set_write_mode", {"mode": normalized, "confirm": bool(confirm)}, timeout=30.0)
    return json.dumps(res, indent=2, ensure_ascii=False)


@mcp.tool()
def aidg_write_text_guarded(path: str, content: str = "AI-DG safety probe") -> str:
    """Write only outside D:, with the D: guard evaluated before touching disk."""
    denied = write_guard(path)
    if denied:
        return json.dumps(denied, ensure_ascii=False)
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return json.dumps({"status": "ok", "path": str(target), "bytes": target.stat().st_size}, ensure_ascii=False)


@mcp.tool()
def aidg_delete_file_guarded(path: str) -> str:
    """Guarded delete entrypoint; user SketchUp files are never deleted."""
    denied = delete_guard(path)
    if denied:
        return json.dumps(denied, ensure_ascii=False)
    return json.dumps({"status": "error", "error": "DELETE_DISABLED_BY_DEFAULT", "path": str(path)}, ensure_ascii=False)

@mcp.tool()
def aidg_prepare_run(project_path: str) -> str:
    denied = write_guard(project_path)
    if denied:
        return json.dumps(denied, ensure_ascii=False)
    script = ROOT_DIR / ".agents" / "skills" / "ai-dg-estimator" / "scripts" / "workspace" / "prepare_run.py"
    res = subprocess.run([sys.executable, str(script), project_path], capture_output=True, text=True)
    return res.stdout if res.returncode == 0 else f"Loi: {res.stderr}"

@mcp.tool()
def aidg_analyze_drawing_pdf(pdf_path: str, project_work_path: str, render_pages: bool = True) -> str:
    denied = write_guard(project_work_path)
    if denied:
        return json.dumps(denied, ensure_ascii=False)
    script = ROOT_DIR / ".agents" / "skills" / "ai-dg-estimator" / "scripts" / "analyze_pdf.py"
    cmd = [sys.executable, str(script), pdf_path, "--project", project_work_path]
    if render_pages:
        cmd.append("--render")
    res = subprocess.run(cmd, capture_output=True, text=True)
    return res.stdout if res.returncode == 0 else f"Loi: {res.stderr}"

@mcp.tool()
def aidg_read_cad_dxf(dxf_path: str) -> str:
    try:
        import ezdxf
        doc = ezdxf.readfile(dxf_path)
        msp = doc.modelspace()
        layers = [layer.dxf.name for layer in doc.layers]
        entity_summary = {}
        for e in msp:
            t = e.dxftype()
            entity_summary[t] = entity_summary.get(t, 0) + 1
        return json.dumps({"status": "ok", "dxf_path": dxf_path, "layers": layers, "entities_count": entity_summary}, indent=2, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"status": "error", "error": str(e)}, ensure_ascii=False)

@mcp.tool()
def aidg_calculate_bom(items_json_path: str, output_bom_json: str, materials_json: Optional[str] = None) -> str:
    denied = write_guard(output_bom_json)
    if denied:
        return json.dumps(denied, ensure_ascii=False)
    script = ROOT_DIR / ".agents" / "skills" / "ai-dg-estimator" / "scripts" / "calculate_bom.py"
    cmd = [sys.executable, str(script), items_json_path, "--output", output_bom_json]
    if materials_json:
        cmd.extend(["--materials", materials_json])
    res = subprocess.run(cmd, capture_output=True, text=True)
    return res.stdout if res.returncode == 0 else f"Loi: {res.stderr}"

@mcp.tool()
def aidg_export_project_excel(project_path: str) -> str:
    denied = write_guard(project_path)
    if denied:
        return json.dumps(denied, ensure_ascii=False)
    script = ROOT_DIR / ".agents" / "skills" / "ai-dg-estimator" / "scripts" / "workspace" / "export_project_excel.py"
    res = subprocess.run([sys.executable, str(script), project_path], capture_output=True, text=True)
    return res.stdout if res.returncode == 0 else f"Loi: {res.stderr}"

@mcp.tool()
def aidg_export_dxf_netting(items_json_path: str, output_dxf_dir: str) -> str:
    denied = write_guard(output_dxf_dir)
    if denied:
        return json.dumps(denied, ensure_ascii=False)
    out_dir = Path(output_dxf_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(items_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    items = data.get("items", [])
    exported_count = 0
    for item in items:
        item_id = item.get("id", "ITEM")
        part_name = item.get("part_name", "PART").replace(" ", "_")
        l = item.get("length_mm", 0)
        w = item.get("width_mm", 0)
        th = item.get("thickness_mm", 0)
        mat = item.get("material_code", "MAT").replace(" ", "_")
        if l and w:
            dxf_filename = out_dir / f"{item_id}_{part_name}_{mat}_{l}x{w}x{th}.dxf"
            dxf_content = (
                "0\nSECTION\n2\nENTITIES\n0\nLWPOLYLINE\n100\nAcDbEntity\n8\nCUT_OUTLINE\n"
                "100\nAcDbPolyline\n90\n4\n70\n1\n"
                f"10\n0.0\n20\n0.0\n10\n{l}\n20\n0.0\n10\n{l}\n20\n{w}\n10\n0.0\n20\n{w}\n"
                "0\nENDSEC\n0\nEOF\n"
            )
            dxf_filename.write_text(dxf_content, encoding="utf-8")
            exported_count += 1
    return f"Da xuat {exported_count} file DXF Netting vao: {output_dxf_dir}"


# FastMCP has registered every handler by this point.  Apply the explicit
# capability profile immediately before serving so normal clients do not
# receive the full schema set, while acceptance/developer clients can opt in
# to ``AI_DG_TOOL_PROFILE=full``.
ACTIVE_TOOL_EXPOSURE = apply_profile(mcp, TOOL_REGISTRY, DEVELOPER_MODE)
ACTIVE_TOOL_IDS = frozenset(
    row["id"]
    for row in TOOL_REGISTRY
    if row["id"] not in set(ACTIVE_TOOL_EXPOSURE["hidden_tool_ids"])
)


if __name__ == "__main__":
    mcp.run()
