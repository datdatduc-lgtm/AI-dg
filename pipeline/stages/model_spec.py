"""Model Specification (M5 core).

Converts reconciled dimension + material facts into a strict ModelSpec per
physical item, ready for the 3D builder.  The generator only writes values
whose state is EXPLICIT / EXPLICIT_LOCAL_DETAIL; DERIVED values must be
approved by the reviewer before they can be built, and UNKNOWN fields are
never silently filled.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BUILDABLE_STATES = {"EXPLICIT", "MATCH", "MATCH_WITHIN_VIEWS", "EXPLICIT_LOCAL_DETAIL"}


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class ModelSpec:
    run_id: str
    schema_version: str = "0.1"
    items: list[dict[str, Any]] = field(default_factory=list)
    generated_utc: str = field(default_factory=utcnow)
    source_review_status: str = "OPEN"  # OPEN / APPROVED / BLOCKED

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "run_id": self.run_id,
            "generated_utc": self.generated_utc,
            "source_review_status": self.source_review_status,
            "items": self.items,
        }


def _body_materials(item: str, mat_graph: Any) -> list[str]:
    rows = [m for m in getattr(mat_graph, "materials", []) if m.get("item_code") == item]
    return [m["code"] for m in rows]


def _explicit_parts(item: str, facts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Carry an explicit part breakdown forward without inventing cabinet parts."""
    grouped: dict[str, list[dict[str, Any]]] = {}
    for fact in facts:
        if str(fact.get("item_code") or fact.get("item") or "UNKNOWN") != item:
            continue
        part_id = str(fact.get("part_id") or "").strip()
        if part_id:
            grouped.setdefault(part_id, []).append(fact)

    parts: list[dict[str, Any]] = []
    for part_id, part_facts in sorted(grouped.items()):
        dimensions: dict[str, dict[str, Any]] = {}
        for dim in ("width", "depth", "height"):
            candidates = [fact for fact in part_facts if str(fact.get("dim") or "") == dim and fact.get("value_mm") is not None]
            if not candidates:
                continue
            best = max(candidates, key=lambda fact: float(fact.get("confidence", 0.0) or 0.0))
            state = str(best.get("state") or "EXPLICIT").upper()
            dimensions[dim] = {
                "value_mm": round(float(best["value_mm"]), 3),
                "state": state,
                "buildable": state in BUILDABLE_STATES,
                "sources": best.get("sources") or [best.get("source_id")],
            }
        if set(dimensions) != {"width", "depth", "height"}:
            continue
        source_refs = sorted({str(fact.get("source_id")) for fact in part_facts if fact.get("source_id")})
        material_codes = sorted({str(fact.get("material_code")) for fact in part_facts if fact.get("material_code")})
        origin = next((fact.get("origin_mm") for fact in part_facts if isinstance(fact.get("origin_mm"), list)), [0.0, 0.0, 0.0])
        parts.append({
            "part_id": part_id,
            "role": str(next((fact.get("part_role") for fact in part_facts if fact.get("part_role")), "unspecified")),
            "dimensions_mm": {
                "width_mm": dimensions["width"]["value_mm"],
                "depth_mm": dimensions["depth"]["value_mm"],
                "height_mm": dimensions["height"]["value_mm"],
            },
            "origin_mm": origin,
            "material_code": material_codes[0] if material_codes else "",
            "source_refs": source_refs,
        })
    return parts


def generate_model_spec(
    facts: list[dict[str, Any]],
    run_id: str = "",
    mat_graph: Any | None = None,
) -> ModelSpec:
    """Build one spec item per physical item.

    `facts` entries: {item_code, region?, dim?, axis?, value_mm, state, sources}.
    """
    spec = ModelSpec(run_id=run_id)

    # Group numeric facts per item+dim (ignore region granularity).
    per_item: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for fact in facts:
        item = str(fact.get("item_code") or fact.get("item") or "UNKNOWN")
        dim = str(fact.get("dim") or fact.get("role") or "d0")
        per_item.setdefault(item, {}).setdefault(dim, []).append(fact)

    for item, dims in sorted(per_item.items()):
        envelope: dict[str, dict[str, Any]] = {}
        buildable = True
        for dim in ("width", "depth", "height"):
            candidates = [d for d in dims.get(dim, []) if d.get("value_mm") is not None]
            if not candidates:
                envelope[dim] = {"value_mm": None, "state": "UNKNOWN", "buildable": False}
                buildable = False
                continue
            # Use the highest-confidence buildable state.
            best = max(
                candidates,
                key=lambda d: (1 if str(d.get("state") or "").upper() in BUILDABLE_STATES else 0, float(d.get("confidence", 0))),
            )
            state = str(best.get("state") or "EXPLICIT").upper()
            ok = state in BUILDABLE_STATES
            buildable = buildable and ok
            envelope[dim] = {
                "value_mm": round(float(best["value_mm"]), 3),
                "state": state,
                "buildable": ok,
                "sources": best.get("sources") or [best.get("source_id")],
            }

        item_facts = [fact for fact in facts if str(fact.get("item_code") or fact.get("item") or "UNKNOWN") == item]
        spec.items.append(
            {
                "item_code": item,
                "name": f"ITEM {item}",
                "dimensions_mm": envelope,
                "buildable_state": "READY" if buildable else "REVIEW_REQUIRED",
                "materials": _body_materials(item, mat_graph) if mat_graph else [],
                "parts": _explicit_parts(item, item_facts),
                "provider_instruction": (
                    "Build now" if buildable else "Blocked: unresolved dimensions require Source Review"
                ),
            }
        )
    return spec


def save_spec(spec: ModelSpec, output_path: Path) -> Path:
    output_path = output_path.expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(spec.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path


def load_spec(path: Path) -> ModelSpec:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return ModelSpec(
        run_id=data.get("run_id", ""),
        schema_version=data.get("schema_version", "0.1"),
        items=data.get("items", []),
        generated_utc=data.get("generated_utc", utcnow()),
        source_review_status=data.get("source_review_status", "OPEN"),
    )
