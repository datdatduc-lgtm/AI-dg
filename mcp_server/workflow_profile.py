"""Build a small, privacy-aware SketchUp workflow profile from metadata."""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def build_profile(samples: list[dict[str, Any]], output_path: str | Path) -> dict[str, Any]:
    """Aggregate metadata samples without persisting model paths or geometry."""
    group_counts: Counter[str] = Counter()
    definition_counts: Counter[str] = Counter()
    tag_counts: Counter[str] = Counter()
    material_counts: Counter[str] = Counter()
    scene_counts: Counter[str] = Counter()
    source_summaries = []

    for sample in samples:
        model = sample.get("model", {})
        components = sample.get("components", {}).get("items", [])
        tags = sample.get("tags", {}).get("items", [])
        materials = sample.get("materials", {}).get("items", [])
        scenes = sample.get("scenes", {}).get("items", [])
        hierarchy = sample.get("hierarchy", {}).get("items", [])
        group_counts.update(row.get("type", "Unknown") for row in hierarchy if row.get("type"))
        definition_counts.update(row.get("name", "") for row in components if row.get("name"))
        tag_counts.update(row.get("name", "") for row in tags if row.get("name"))
        material_counts.update(row.get("name", "") for row in materials if row.get("name"))
        scene_counts.update(row.get("name", "") for row in scenes if row.get("name"))
        source_summaries.append({
            "title_present": bool(model.get("title")),
            "entity_count": model.get("entities"),
            "component_definition_count": len(components),
            "tag_count": len(tags),
            "material_count": len(materials),
            "scene_count": len(scenes),
        })

    target = Path(output_path)
    prior: dict[str, Any] = {}
    if target.is_file():
        try:
            candidate = json.loads(target.read_text(encoding="utf-8"))
            if isinstance(candidate, dict):
                prior = candidate
        except (OSError, json.JSONDecodeError):
            prior = {}

    prior_patterns = prior.get("patterns", {}) if isinstance(prior.get("patterns"), dict) else {}
    for field, counter in (("entity_types", group_counts), ("component_names", definition_counts), ("tag_names", tag_counts), ("material_names", material_counts), ("scene_names", scene_counts)):
        old = prior_patterns.get(field, {})
        if isinstance(old, dict):
            counter.update({str(key): int(value) for key, value in old.items() if str(value).lstrip("-").isdigit()})

    prior_samples = prior.get("samples", []) if isinstance(prior.get("samples"), list) else []
    source_summaries = prior_samples[-99:] + source_summaries
    count = int(prior.get("sample_count", 0) or 0) + len(samples)
    confidence = "HIGH" if count >= 5 else "MEDIUM" if count >= 3 else "LOW"
    payload = {
        "schema_version": "0.1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "sample_count": count,
        "source_count": count,
        "confidence": confidence,
        "privacy": {"paths_persisted": False, "raw_geometry_persisted": False},
        "patterns": {
            "entity_types": dict(group_counts),
            "component_names": dict(definition_counts),
            "tag_names": dict(tag_counts),
            "material_names": dict(material_counts),
            "scene_names": dict(scene_counts),
        },
        "samples": source_summaries,
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"status": "ok", "path": str(target), "sample_count": count, "confidence": confidence, "privacy": payload["privacy"]}
