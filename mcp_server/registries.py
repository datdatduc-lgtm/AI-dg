"""Lazy skill and plugin registry for the local AI-DG runtime."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


ROOT_DIR = Path("E:/AI-DG")
SKILL_ROOTS = [ROOT_DIR / "skills", ROOT_DIR / ".agents" / "skills"]
PLUGIN_ROOT = ROOT_DIR / "plugins"
PRIMARY_PLUGIN_STATE_PATH = ROOT_DIR / ".codex" / "plugin-state.json"
FALLBACK_PLUGIN_STATE_PATH = ROOT_DIR / "OUTPUT" / "runtime" / "plugin-state.json"
PLUGIN_STATE_PATH = PRIMARY_PLUGIN_STATE_PATH


def _front_matter(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()[:80]
    except OSError:
        return values
    in_front = False
    for line in lines:
        if line.strip() == "---":
            if in_front:
                break
            in_front = True
            continue
        if in_front and re.match(r"^[A-Za-z0-9_-]+\s*:", line):
            key, value = line.split(":", 1)
            values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def list_skills() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for root in SKILL_ROOTS:
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("SKILL.md")):
            skill_id = path.parent.name
            if skill_id in seen:
                continue
            seen.add(skill_id)
            front = _front_matter(path)
            rows.append({
                "id": skill_id,
                "name": front.get("name", skill_id),
                "description": front.get("description", ""),
                "version": front.get("metadata.version", front.get("version", "")),
                "source": str(path),
                "lazy": True,
                "status": "AVAILABLE",
            })
    return rows


def load_skill(skill_id: str, max_chars: int = 20000) -> dict[str, Any]:
    candidates = []
    for root in SKILL_ROOTS:
        candidates.extend(root.glob(f"{skill_id}/SKILL.md"))
    if not candidates:
        return {"status": "error", "error": "SKILL_NOT_FOUND", "skill_id": skill_id}
    path = candidates[0]
    text = path.read_text(encoding="utf-8", errors="replace")
    return {
        "status": "ok",
        "skill_id": skill_id,
        "source": str(path),
        "content": text[:max_chars],
        "truncated": len(text) > max_chars,
    }


def list_plugins() -> list[dict[str, Any]]:
    state = _load_plugin_state()
    rows = [{
        "id": "ai-dg-core",
        "name": "AI-DG Core",
        "version": "1.1.0-foundation",
        "description": "Headless SketchUp Ruby bridge and MCP gateway",
        "entry": "bridge_sketchup/ai_dg_bridge.rb",
        "permissions": ["sketchup.read", "sketchup.write", "filesystem.read", "filesystem.write", "mcp"],
        "tools": ["sketchup_ping", "sketchup_get_model_summary", "sketchup_get_selection"],
        "status": "ENABLED" if state.get("ai-dg-core", {}).get("enabled", True) else "DISABLED",
    }]
    if PLUGIN_ROOT.is_dir():
        for manifest in sorted(PLUGIN_ROOT.glob("*/manifest.json")):
            try:
                payload = json.loads(manifest.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                rows.append({"id": manifest.parent.name, "status": "INVALID_MANIFEST", "source": str(manifest)})
                continue
            payload.setdefault("id", manifest.parent.name)
            payload.setdefault("source", str(manifest))
            payload.setdefault("status", "DISABLED")
            if payload["id"] in state:
                payload["status"] = "ENABLED" if state[payload["id"]].get("enabled") else "DISABLED"
            rows.append(payload)
    return rows


def _load_plugin_state() -> dict[str, Any]:
    # Merge canonical and fallback state by newest valid file first.  In
    # managed workspaces the canonical file may be readable but not writable,
    # so a successful fallback write must be visible immediately instead of
    # being shadowed by stale state.  Older files still contribute keys that
    # are absent from the newest snapshot.
    candidates: list[tuple[int, Path, dict[str, Any]]] = []
    for path in (PRIMARY_PLUGIN_STATE_PATH, FALLBACK_PLUGIN_STATE_PATH):
        if not path.is_file():
            continue
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(value, dict):
                continue
            candidates.append((path.stat().st_mtime_ns, path, value))
        except (OSError, json.JSONDecodeError):
            continue

    merged: dict[str, Any] = {}
    for _mtime_ns, _path, value in sorted(candidates, key=lambda row: row[0], reverse=True):
        for key, state in value.items():
            merged.setdefault(key, state)
    return merged


def set_plugin_enabled(plugin_id: str, enabled: bool) -> dict[str, Any]:
    known = {row["id"] for row in list_plugins()}
    if plugin_id not in known:
        return {"status": "error", "error": "PLUGIN_NOT_FOUND", "plugin_id": plugin_id}
    if plugin_id == "ai-dg-core" and not enabled:
        return {"status": "error", "error": "CORE_PLUGIN_CANNOT_BE_DISABLED", "plugin_id": plugin_id}
    state = _load_plugin_state()
    state[plugin_id] = {"enabled": bool(enabled)}
    payload = json.dumps(state, ensure_ascii=False, indent=2)
    errors = []
    for path in (PRIMARY_PLUGIN_STATE_PATH, FALLBACK_PLUGIN_STATE_PATH):
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(payload, encoding="utf-8")
            return {
                "status": "ok",
                "plugin_id": plugin_id,
                "enabled": bool(enabled),
                "persistence_path": str(path),
            }
        except OSError as exc:
            errors.append(f"{path}: {exc}")
    return {
        "status": "error",
        "error": "PLUGIN_STATE_WRITE_FAILED",
        "plugin_id": plugin_id,
        "details": errors,
    }


def reload_plugin(plugin_id: str) -> dict[str, Any]:
    known = {row["id"] for row in list_plugins()}
    if plugin_id not in known:
        return {"status": "error", "error": "PLUGIN_NOT_FOUND", "plugin_id": plugin_id}
    return {"status": "ok", "plugin_id": plugin_id, "reload": "QUEUED_GRACEFUL", "policy": "no_force_kill"}


def plugin_diagnostics() -> dict[str, Any]:
    return {
        "status": "ok",
        "plugin_root": str(PLUGIN_ROOT),
        "plugins": list_plugins(),
        "reload_policy": "manual_and_graceful_only",
        "dangerous_permissions_default": False,
    }
