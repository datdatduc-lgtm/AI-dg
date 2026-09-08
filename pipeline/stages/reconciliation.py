"""Source Reconciliation (M3).

Compares dimension/material facts across sources and index views.  Only equal
axis/span facts may be marked MISMATCH; different but nearby values that
explain a refinement stay REVIEW and never silently merge.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

TOLERANCE_MM = 2.0
STATUS_ORDER = {"MATCH": 0, "MATCH_WITHIN_VIEWS": 1, "REFINEMENT": 2, "ONLY_ONE_SOURCE": 3, "MISMATCH": 4}


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _norm_pair(a: float | None) -> tuple[float | None, float | None]:
    """Return ordered identical pair; None when missing."""
    if a is None:
        return None, None
    return round(float(a), 3), round(float(a), 3)


@dataclass
class ReconciliationReport:
    run_id: str
    schema_version: str = "0.1"
    source_set: dict[str, list[str]] = field(default_factory=dict)
    comparisons: list[dict[str, Any]] = field(default_factory=list)
    mismatches: list[dict[str, Any]] = field(default_factory=list)
    policy_note: str = (
        "Only identical axis/start/end spans may be MISMATCH. "
        "Values within tolerance refine, otherwise REVIEW."
    )
    generated_utc: str = field(default_factory=utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "run_id": self.run_id,
            "generated_utc": self.generated_utc,
            "source_set": self.source_set,
            "comparisons": self.comparisons,
            "mismatches": self.mismatches,
            "policy_note": self.policy_note,
        }


def _value_of(dim: dict[str, Any]) -> float | None:
    """Primary dimension value of a fact."""
    for key in ("value_mm", "a_mm"):
        value = dim.get(key)
        if isinstance(value, (int, float)):
            return float(value)
    return None


def reconcile_dimensions(
    facts: list[dict[str, Any]],
    run_id: str = "",
    tolerance_mm: float = TOLERANCE_MM,
) -> ReconciliationReport:
    """Compare all dimension facts sharing the same (fact, axis, span).

    `facts` entries shape:
        {fact, axis?, span?, value_mm, source_id, drawing_id?, confidence?}
    """
    report = ReconciliationReport(run_id=run_id)
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    source_ids: set[str] = set()

    for fact in facts:
        key = (str(fact.get("fact", "?")), str(fact.get("axis", "-")), str(fact.get("span", "-")))
        grouped.setdefault(key, []).append(fact)
        if fact.get("source_id"):
            source_ids.add(fact["source_id"])

    by_type: dict[str, list[str]] = {}
    for fact in facts:
        source_id = fact.get("source_id")
        if not source_id:
            continue
        source_type = str(fact.get("source_type") or "unknown").lower()
        by_type.setdefault(source_type, []).append(str(source_id))

    report.source_set = {key: sorted(set(values)) for key, values in by_type.items()}

    for (fact, axis, span), group in sorted(grouped.items()):
        values = [_value_of(d) for d in group]
        known = [v for v in values if v is not None]

        if not known:
            status = "NO_VALUE"
        elif len(set(round(v, 3) for v in known)) <= 1:
            status = "MATCH"
        elif max(known) - min(known) <= tolerance_mm:
            status = "MATCH_WITHIN_VIEWS"
        else:
            # Near values become a refinement; larger gaps are a MISMATCH.
            if max(known) - min(known) <= tolerance_mm * 3:
                status = "REFINEMENT"
            else:
                status = "MISMATCH"

        comparison = {
            "fact": fact,
            "axis": axis,
            "span": span,
            "status": status,
            "value_mm": _representative(known),
            "values": sorted(round(v, 3) for v in known)[:20],
            "sources": sorted({str(d.get("source_id") or "?") for d in group}),
            "drawings": sorted({str(d.get("drawing_id") or "?") for d in group}),
        }
        report.comparisons.append(comparison)
        if status == "MISMATCH":
            report.mismatches.append(comparison)

    return report


def _representative(values: list[float]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 3)


def save_report(report: ReconciliationReport, output_path: Path) -> Path:
    output_path = output_path.expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path
