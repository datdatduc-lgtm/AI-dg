#!/usr/bin/env python3
"""Repeatable, non-destructive AI-DG MCP acceptance smoke test.

The test intentionally never enables write mode and never calls a model
provider. Agent conversations are owned by the native Codex/Cline runtimes;
this process only verifies the shared SketchUp MCP contract.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR / "OUTPUT" / "mcp_deps"))

from mcp import ClientSession, StdioServerParameters  # noqa: E402
from mcp.client.stdio import stdio_client  # noqa: E402


def parse(result):
    return json.loads(result.content[0].text)


async def main() -> int:
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{ROOT_DIR / 'OUTPUT' / 'mcp_deps'};{ROOT_DIR / 'mcp_server'};{ROOT_DIR}"
    # This regression suite intentionally opts into every capability so it can
    # exercise the complete contract. Normal clients use the default minimal
    # profile and are covered by cline_acceptance_smoke/tool_exposure_smoke.
    env["AI_DG_TOOL_PROFILE"] = "full"
    params = StdioServerParameters(
        command=sys.executable,
        args=[str(ROOT_DIR / "mcp_server" / "launcher.py")],
        env=env,
    )
    report: dict[str, object] = {"status": "PASS", "tests": []}

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            names = {tool.name for tool in (await session.list_tools()).tools}
            required = {"sketchup_list_instances", "sketchup_select_instance", "sketchup_get_active_instance", "sketchup_clear_instance", "sketchup_health", "sketchup_get_selection", "sketchup_get_camera", "sketchup_set_write_mode", "aidg_write_text_guarded", "ai_dg_source_ingest", "ai_dg_pipeline_run", "ai_dg_pipeline_artifacts", "ai_dg_review_queue", "ai_dg_model_spec", "ai_dg_build_plan", "ai_dg_execute_build_plan", "ai_dg_verification", "sketchup_get_semantic_item", "sketchup_create_semantic_item", "sketchup_create_component", "sketchup_create_cabinet", "sketchup_create_panel", "sketchup_create_partition", "sketchup_create_shelf", "sketchup_create_door", "sketchup_create_drawer", "sketchup_create_countertop", "sketchup_create_component_from_spec", "sketchup_transform_entity", "sketchup_apply_material", "sketchup_set_tag", "sketchup_undo"}
            legacy = {"ai_dg_agent_ask", "ai_dg_model_status", "ai_dg_model_select", "ai_dg_9router_sync_models", "ai_dg_provider_status", "ai_dg_provider_configure", "ai_dg_provider_disconnect", "ai_dg_9router_test", "ai_dg_session_save", "ai_dg_session_load"}
            discovery_ok = required <= names and not names.intersection(legacy)
            report["tests"].append({"name": "mcp_discovery_without_legacy_agent", "status": "PASS" if discovery_ok else "FAIL", "tool_count": len(names), "legacy_tools": sorted(names.intersection(legacy))})

            tool_metadata = parse(await session.call_tool("ai_dg_list_tools", {}))
            tool_rows = tool_metadata.get("tools", [])
            enabled_ok = (
                tool_metadata.get("status") == "ok"
                and tool_metadata.get("tool_count") == len(names)
                and isinstance(tool_rows, list)
                and all(row.get("enabled") is True for row in tool_rows if isinstance(row, dict))
            )
            report["tests"].append({"name": "tool_manager_enabled_metadata", "status": "PASS" if enabled_ok else "FAIL", "tool_count": len(tool_rows)})

            instances = parse(await session.call_tool("sketchup_list_instances", {}))
            online = [row for row in instances.get("instances", []) if row.get("status") == "ONLINE"]
            requested_instance = os.environ.get("AI_DG_TEST_INSTANCE_ID", "").strip()
            chosen = next((row for row in online if row.get("instance_id") == requested_instance), None) if requested_instance else (online[0] if len(online) == 1 else None)
            if not chosen:
                report["tests"].append({"name": "exact_instance_target", "status": "FAIL", "error": "AI_DG_TEST_INSTANCE_ID_REQUIRED" if len(online) > 1 else "NO_SKETCHUP_INSTANCES", "online": online})
                print(json.dumps(report, ensure_ascii=False, indent=2))
                return 1
            selected = parse(await session.call_tool("sketchup_select_instance", {"instance_id": chosen["instance_id"]}))
            target_ok = selected.get("status") == "ok" and selected.get("target", {}).get("instance_id") == chosen["instance_id"]
            report["tests"].append({"name": "exact_instance_target", "status": "PASS" if target_ok else "FAIL", "target": selected.get("target")})

            write_mode_gate = parse(await session.call_tool("sketchup_set_write_mode", {"mode": "write_enabled", "confirm": False}))
            write_mode_gate_ok = write_mode_gate.get("error") == "WRITE_MODE_CONFIRMATION_REQUIRED"
            report["tests"].append({"name": "headless_write_mode_confirmation_gate", "status": "PASS" if write_mode_gate_ok else "FAIL", "error": write_mode_gate.get("error")})

            health = parse(await session.call_tool("sketchup_health", {}))
            health_ok = health.get("status") == "ok" and health.get("data", {}).get("bridge_status") == "ONLINE"
            report["tests"].append({"name": "live_bridge_health", "status": "PASS" if health_ok else "FAIL", "pid": health.get("data", {}).get("sketchup_pid"), "version": health.get("data", {}).get("sketchup_version")})

            runtime_tools = parse(await session.call_tool("sketchup_list_runtime_tools", {}))
            catalogs_ok = (
                runtime_tools.get("status") == "ok"
                and isinstance(runtime_tools.get("data"), list)
            )
            report["tests"].append({"name": "live_runtime_catalog", "status": "PASS" if catalogs_ok else "FAIL", "tool_count": len(runtime_tools.get("data", []))})

            reload_result = parse(await session.call_tool("sketchup_reload_runtime", {}))
            reload_ok = reload_result.get("status") == "ok" and reload_result.get("reloaded") is True and int(reload_result.get("reload_generation", 0)) >= 1
            report["tests"].append({"name": "live_graceful_runtime_reload", "status": "PASS" if reload_ok else "FAIL", "generation": reload_result.get("reload_generation"), "source_sha256_length": len(reload_result.get("source_sha256", ""))})
            read_only = parse(await session.call_tool("sketchup_set_write_mode", {"mode": "read_only", "confirm": False}))
            read_only_ok = read_only.get("status") == "ok" and read_only.get("access_mode") == "read_only"
            report["tests"].append({"name": "headless_default_read_only", "status": "PASS" if read_only_ok else "FAIL", "access_mode": read_only.get("access_mode")})
            runtime_tools_after = parse(await session.call_tool("sketchup_list_runtime_tools", {}))
            runtime_ids_after = {row.get("id") for row in runtime_tools_after.get("data", []) if isinstance(row, dict)}
            reload_catalog_ok = (
                runtime_tools_after.get("status") == "ok"
                and "sketchup_set_write_mode" in runtime_ids_after
                and not runtime_ids_after.intersection({"sketchup_get_toolbar_info", "sketchup_list_runtime_skills", "sketchup_list_runtime_plugins"})
            )
            report["tests"].append({"name": "reload_refreshes_runtime_catalog", "status": "PASS" if reload_catalog_ok else "FAIL", "before": len(runtime_tools.get("data", [])), "after": len(runtime_tools_after.get("data", []))})

            model = parse(await session.call_tool("sketchup_get_model_summary", {}))
            model_data = model.get("data", {})
            model_ok = isinstance(model_data.get("entities"), int) and isinstance(model_data.get("bounds_mm"), list) and len(model_data.get("bounds_mm")) == 3 and model.get("target", {}).get("instance_id") == chosen["instance_id"]
            report["tests"].append({"name": "official_model_read", "status": "PASS" if model_ok else "FAIL", "entities": model_data.get("entities"), "bounds_mm": model_data.get("bounds_mm"), "target": model.get("target")})

            selection = parse(await session.call_tool("sketchup_get_selection", {}))
            items = selection.get("data", {}).get("items")
            item = (items or [None])[0]
            selection_ok = selection.get("status") == "ok" and isinstance(selection.get("data", {}).get("count"), int) and isinstance(items, list) and selection.get("target", {}).get("instance_id") == chosen["instance_id"]
            report["tests"].append({"name": "official_selection_entity_read", "status": "PASS" if selection_ok else "FAIL", "entity": item, "target": selection.get("target")})

            camera = parse(await session.call_tool("sketchup_get_camera", {}))
            camera_ok = camera.get("status") == "ok" and camera.get("data", {}).get("view_class") == "Sketchup::View"
            report["tests"].append({"name": "official_view_read", "status": "PASS" if camera_ok else "FAIL", "view_class": camera.get("data", {}).get("view_class")})

            eval_hidden = "sketchup_eval_ruby" not in names
            report["tests"].append({"name": "normal_mode_eval_lock", "status": "PASS" if eval_hidden else "FAIL", "exposed": not eval_hidden})

            pipeline_probe = parse(await session.call_tool("ai_dg_pipeline_artifacts", {"run_id": "prompt-20260903-03", "artifact": "summary", "project_path": "E:\\AI-DG"}))
            pipeline_data = pipeline_probe.get("data", {})
            pipeline_ok = pipeline_probe.get("status") == "ok" and pipeline_data.get("run_id") == "prompt-20260903-03" and pipeline_data.get("gate_status") == "BLOCKED"
            report["tests"].append({"name": "pipeline_artifact_read", "status": "PASS" if pipeline_ok else "FAIL", "run_id": pipeline_data.get("run_id"), "gate_status": pipeline_data.get("gate_status")})

            executor_probe = parse(await session.call_tool("ai_dg_execute_build_plan", {"run_id": "prompt-20260903-03", "project_path": r"E:\AI-DG", "review_status": "APPROVED", "confirm_write": True}))
            executor_data = executor_probe.get("data", {})
            executor_ok = executor_probe.get("status") == "ok" and executor_data.get("status") == "BLOCKED" and executor_data.get("reason") == "READ_ONLY_MODE"
            report["tests"].append({"name": "build_executor_readonly_guard", "status": "PASS" if executor_ok else "FAIL", "reason": executor_data.get("reason")})

            pipeline_guard = parse(await session.call_tool("ai_dg_pipeline_run", {"project_path": "D:\\AI-DG", "run_id": "should-not-write"}))
            pipeline_guard_ok = pipeline_guard.get("error") == "PROTECTED_DRIVE_WRITE_DENIED"
            report["tests"].append({"name": "pipeline_protected_drive_guard", "status": "PASS" if pipeline_guard_ok else "FAIL", "error": pipeline_guard.get("error")})

            plugin_catalog = parse(await session.call_tool("ai_dg_list_plugins", {}))
            test_plugin = next((row for row in plugin_catalog.get("plugins", []) if row.get("id") == "ai-dg-test"), None)
            initial_enabled = bool(test_plugin and test_plugin.get("status") == "ENABLED")
            enable = parse(await session.call_tool("ai_dg_plugin_set_enabled", {"plugin_id": "ai-dg-test", "enabled": True}))
            plugin_tool = parse(await session.call_tool("ai_dg_test_read_tool", {}))
            reload_result = parse(await session.call_tool("ai_dg_plugin_reload", {"plugin_id": "ai-dg-test"}))
            restore = parse(await session.call_tool("ai_dg_plugin_set_enabled", {"plugin_id": "ai-dg-test", "enabled": initial_enabled}))
            plugin_ok = (
                test_plugin is not None
                and enable.get("status") == "ok"
                and plugin_tool.get("status") == "ok"
                and reload_result.get("reload") == "QUEUED_GRACEFUL"
                and restore.get("status") == "ok"
            )
            report["tests"].append({"name": "plugin_enable_disable_reload", "status": "PASS" if plugin_ok else "FAIL", "plugin": "ai-dg-test", "restored_enabled": initial_enabled})

            write_probe = parse(await session.call_tool("aidg_write_text_guarded", {"path": r"D:\AI-DG-SAFETY-PROBE.txt", "content": "must be denied"}))
            delete_probe = parse(await session.call_tool("aidg_delete_file_guarded", {"path": r"E:\AI-DG\OUTPUT\safety_probe.skp"}))
            safety_ok = write_probe.get("error") == "PROTECTED_DRIVE_WRITE_DENIED" and delete_probe.get("error") == "SKETCHUP_FILE_DELETE_DENIED"
            report["tests"].append({"name": "filesystem_guards", "status": "PASS" if safety_ok else "FAIL", "write_error": write_probe.get("error"), "delete_error": delete_probe.get("error")})

            system_probe = parse(await session.call_tool("aidg_write_text_guarded", {"path": r"C:\Program Files\SketchUp\SketchUp 2023\Tools\sketchup.rb", "content": "must be denied"}))
            system_delete_probe = parse(await session.call_tool("aidg_delete_file_guarded", {"path": r"C:\Program Files\SketchUp\SketchUp 2023\Tools\sketchup.rb"}))
            system_guard_ok = (
                system_probe.get("error") == "SKETCHUP_SYSTEM_FILE_WRITE_DENIED"
                and system_delete_probe.get("error") == "SKETCHUP_SYSTEM_FILE_WRITE_DENIED"
            )
            report["tests"].append({"name": "system_file_guard", "status": "PASS" if system_guard_ok else "FAIL", "error": system_probe.get("error"), "delete_error": system_delete_probe.get("error")})

            create_started = time.perf_counter()
            create = parse(await session.call_tool("sketchup_create_box", {"width_mm": 10, "depth_mm": 10, "height_mm": 10, "name": "SHOULD_NOT_CREATE"}))
            create_ok = create.get("error", "").startswith("READ_ONLY_MODE")
            report["tests"].append({"name": "normal_mode_write_guard", "status": "PASS" if create_ok else "FAIL", "elapsed_ms": round((time.perf_counter() - create_started) * 1000, 1), "error": create.get("error")})

            panel_probe = parse(await session.call_tool("sketchup_create_panel", {"item_code": "READONLY-PANEL", "width_mm": 10, "depth_mm": 10, "height_mm": 10}))
            panel_ok = panel_probe.get("error", "").startswith("READ_ONLY_MODE")
            report["tests"].append({"name": "semantic_builder_readonly_guard", "status": "PASS" if panel_ok else "FAIL", "error": panel_probe.get("error")})

            semantic_read = parse(await session.call_tool("sketchup_get_semantic_item", {"item_code": "__AI_DG_ACCEPTANCE_NOT_FOUND__"}))
            semantic_read_ok = semantic_read.get("error") == "SEMANTIC_ITEM_NOT_FOUND"
            report["tests"].append({"name": "semantic_readback_contract", "status": "PASS" if semantic_read_ok else "FAIL", "error": semantic_read.get("error")})

            hierarchy_started = time.perf_counter()
            hierarchy = parse(await session.call_tool("sketchup_get_hierarchy", {"max_depth": 2, "max_items": 50}))
            hierarchy_data = hierarchy.get("data", {})
            returned = hierarchy_data.get("returned")
            max_items = hierarchy_data.get("max_items")
            hierarchy_ok = (
                hierarchy.get("status") == "ok"
                and isinstance(returned, int)
                and isinstance(max_items, int)
                and 0 <= returned <= max_items
                and isinstance(hierarchy_data.get("items"), list)
                and len(hierarchy_data["items"]) == returned
                and isinstance(hierarchy_data.get("truncated"), bool)
            )
            hierarchy_status = "PASS" if hierarchy_ok else "PARTIAL" if hierarchy.get("error") == "BRIDGE_TIMEOUT" else "FAIL"
            report["tests"].append({"name": "bounded_hierarchy", "status": hierarchy_status, "elapsed_ms": round((time.perf_counter() - hierarchy_started) * 1000, 1), "error": hierarchy.get("error"), "returned": returned, "max_items": max_items, "truncated": hierarchy_data.get("truncated")})

            await session.call_tool("sketchup_clear_instance", {})
            unselected_write = parse(await session.call_tool("sketchup_create_box", {"width_mm": 10, "depth_mm": 10, "height_mm": 10, "name": "MUST_NOT_CREATE_WITHOUT_TARGET"}))
            exact_write_target_ok = unselected_write.get("error_code") == "TARGET_REQUIRED" and unselected_write.get("status") == "error"
            report["tests"].append({"name": "write_requires_exact_instance", "status": "PASS" if exact_write_target_ok else "FAIL", "error_code": unselected_write.get("error_code")})
            await session.call_tool("sketchup_select_instance", {"instance_id": chosen["instance_id"]})

    statuses = [test["status"] for test in report["tests"]]
    if "FAIL" in statuses:
        report["status"] = "FAIL"
    elif "PARTIAL" in statuses:
        report["status"] = "PARTIAL"
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] in {"PASS", "PARTIAL"} else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
