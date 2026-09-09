"""Capability-based MCP tool exposure for normal and developer sessions.

FastMCP registers tools at import time.  This module applies a static,
client-selectable exposure profile immediately before the server starts so a
normal client receives only the schemas needed for its capability set.  The
full registry remains available to acceptance/developer processes through an
explicit profile; hidden tools are not callable through that MCP process.
"""

from __future__ import annotations

import os
from typing import Any, Iterable


CAPABILITY_ORDER = ("CORE", "MODEL_READ", "DRAWING", "BUILD", "VERIFY", "DEV")


CORE_TOOLS = frozenset(
    {
        "sketchup_list_instances",
        "sketchup_select_instance",
        "sketchup_get_active_instance",
        "sketchup_clear_instance",
        "sketchup_ping",
        "sketchup_health",
        "sketchup_get_runtime_state",
        "sketchup_get_model_summary",
        "sketchup_get_selection",
        "sketchup_get_camera",
        "sketchup_get_bounds",
        "ai_dg_runtime_status",
        "ai_dg_list_tools",
        "ai_dg_list_skills",
        "ai_dg_load_skill",
    }
)


MODEL_READ_TOOLS = frozenset(
    {
        "sketchup_get_entity",
        "sketchup_get_hierarchy",
        "sketchup_list_components",
        "sketchup_list_materials",
        "sketchup_list_tags",
        "sketchup_list_scenes",
        "sketchup_get_semantic_item",
    }
)


DRAWING_TOOLS = frozenset(
    {
        "ai_dg_build_workflow_profile",
        "ai_dg_source_ingest",
        "ai_dg_pipeline_run",
        "ai_dg_pipeline_artifacts",
        "ai_dg_review_queue",
        "ai_dg_model_spec",
        "ai_dg_build_plan",
        "ai_dg_build_ir",
        "ai_dg_codegen",
        "aidg_prepare_run",
        "aidg_analyze_drawing_pdf",
        "aidg_analyze_skp_readonly",
        "aidg_read_cad_dxf",
        "aidg_calculate_bom",
        "aidg_export_project_excel",
        "aidg_export_dxf_netting",
    }
)


BUILD_TOOLS = frozenset(
    {
        "ai_dg_execute_build_plan",
        "sketchup_capture_viewport",
        "sketchup_create_box",
        "sketchup_create_semantic_item",
        "sketchup_create_group",
        "sketchup_create_component",
        "sketchup_create_cabinet",
        "sketchup_create_panel",
        "sketchup_create_partition",
        "sketchup_create_shelf",
        "sketchup_create_door",
        "sketchup_create_drawer",
        "sketchup_create_countertop",
        "sketchup_create_component_from_spec",
        "sketchup_transform_entity",
        "sketchup_apply_material",
        "sketchup_set_tag",
        "sketchup_undo",
        "sketchup_write_mode_status",
        "sketchup_set_write_mode",
    }
)


VERIFY_TOOLS = frozenset({"ai_dg_verification"})


DEV_TOOLS = frozenset(
    {
        "sketchup_get_trace",
        "sketchup_reload_runtime",
        "sketchup_list_runtime_tools",
        "sketchup_eval_ruby",
        "ai_dg_list_plugins",
        "ai_dg_plugin_set_enabled",
        "ai_dg_plugin_reload",
        "ai_dg_plugin_diagnostics",
        "ai_dg_test_read_tool",
        "aidg_write_text_guarded",
        "aidg_delete_file_guarded",
    }
)


GROUP_TOOLS = {
    "CORE": CORE_TOOLS,
    "MODEL_READ": MODEL_READ_TOOLS,
    "DRAWING": DRAWING_TOOLS,
    "BUILD": BUILD_TOOLS,
    "VERIFY": VERIFY_TOOLS,
    "DEV": DEV_TOOLS,
}

TOOL_TO_GROUP: dict[str, str] = {
    tool_id: group for group, tool_ids in GROUP_TOOLS.items() for tool_id in tool_ids
}

PROFILE_GROUPS = {
    "minimal": frozenset({"CORE", "MODEL_READ"}),
    "model_read": frozenset({"CORE", "MODEL_READ"}),
    "drawing": frozenset({"CORE", "MODEL_READ", "DRAWING", "VERIFY"}),
    "agent": frozenset({"CORE", "MODEL_READ"}),
    "build": frozenset({"CORE", "MODEL_READ", "DRAWING", "BUILD", "VERIFY"}),
    "full": frozenset(CAPABILITY_ORDER),
    "dev": frozenset(CAPABILITY_ORDER),
}


def _normalise_groups(raw: str) -> frozenset[str]:
    values = {part.strip().upper() for part in raw.split(",") if part.strip()}
    unknown = values.difference(CAPABILITY_ORDER)
    if unknown:
        raise ValueError(f"Unknown AI_DG_TOOL_GROUPS: {','.join(sorted(unknown))}")
    return frozenset(values)


def resolve_profile(environ: dict[str, str] | None = None) -> tuple[str, frozenset[str]]:
    env = environ if environ is not None else os.environ
    raw_profile = env.get("AI_DG_TOOL_PROFILE", "minimal").strip().lower() or "minimal"
    if raw_profile not in PROFILE_GROUPS:
        raise ValueError(
            f"Unknown AI_DG_TOOL_PROFILE '{raw_profile}'. "
            f"Choose: {', '.join(sorted(PROFILE_GROUPS))}."
        )
    raw_groups = env.get("AI_DG_TOOL_GROUPS", "").strip()
    groups = _normalise_groups(raw_groups) if raw_groups else PROFILE_GROUPS[raw_profile]
    # Discovery and exposure metadata must remain reachable for every profile.
    groups = frozenset(set(groups) | {"CORE"})
    return raw_profile, groups


def visible_tool_ids(
    registry: Iterable[dict[str, Any]],
    profile: str,
    groups: frozenset[str],
    developer_mode: bool,
) -> frozenset[str]:
    registered = {str(row.get("id")) for row in registry if row.get("id")}
    visible = {
        tool_id
        for tool_id in registered
        if TOOL_TO_GROUP.get(tool_id) in groups
    }
    if "sketchup_eval_ruby" in visible and not developer_mode:
        visible = visible.difference({"sketchup_eval_ruby"})
    return frozenset(visible)


def profile_snapshot(
    registry: Iterable[dict[str, Any]],
    profile: str,
    groups: frozenset[str],
    visible: frozenset[str],
    developer_mode: bool,
) -> dict[str, Any]:
    registered = [str(row["id"]) for row in registry if row.get("id")]
    hidden = sorted(set(registered).difference(visible))
    return {
        "profile": profile,
        "groups": [group for group in CAPABILITY_ORDER if group in groups],
        "developer_mode": developer_mode,
        "all_tool_count": len(registered),
        "exposed_tool_count": len(visible),
        "hidden_tool_count": len(hidden),
        "hidden_tool_ids": hidden,
        "schema_reduction_percent": round((len(hidden) / len(registered)) * 100, 1) if registered else 0.0,
    }


def apply_profile(mcp_server: Any, registry: list[dict[str, Any]], developer_mode: bool) -> dict[str, Any]:
    """Remove non-profile tools from a FastMCP instance and return its snapshot."""
    profile, groups = resolve_profile()
    visible = visible_tool_ids(registry, profile, groups, developer_mode)
    registered_names = {
        tool.name for tool in mcp_server._tool_manager.list_tools()  # FastMCP has no public bulk-filter API.
    }
    for tool_id in sorted(registered_names.difference(visible)):
        mcp_server.remove_tool(tool_id)
    return profile_snapshot(registry, profile, groups, visible, developer_mode)
