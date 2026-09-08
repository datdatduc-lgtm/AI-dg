"""Review Queue (M5).

Collects every fact that must not be silently assumed: conflicts, missing
sources, low-confidence values, ambiguities and unsupported features.  Each
item stays OPEN until the reviewer marks RESOLVED / REJECTED.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


SEVERITIES = ("LOW", "MEDIUM", "HIGH", "BLOCKER")


@dataclass
class ReviewQueue:
    run_id: str
    schema_version: str = "0.1"
    status: str = "OPEN"
    items: list[dict[str, Any]] = field(default_factory=list)
    generated_utc: str = field(default_factory=utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "run_id": self.run_id,
            "status": self.status,
            "generated_utc": self.generated_utc,
            "items": self.items,
        }

    def add(
        self,
        issue: str,
        severity: str = "MEDIUM",
        impact: str = "",
        category: str = "",
        source_refs: list[str] | None = None,
    ) -> None:
        severity = severity if severity in SEVERITIES else "MEDIUM"
        item_id = f"{category.upper()}-{len(self.items) + 1:02d}" if category else f"REV-{len(self.items) + 1:02d}"
        self.items.append(
            {
                "id": item_id,
                "severity": severity,
                "issue": issue,
                "impact": impact,
                "status": "OPEN",
                "category": category,
                "source_refs": source_refs or [],
            }
        )

    def has_blockers(self) -> bool:
        return any(item["severity"] == "BLOCKER" and item["status"] == "OPEN" for item in self.items)


def queue_from_conflicts(conflicts: list[dict[str, Any]], run_id: str = "") -> ReviewQueue:
    queue = ReviewQueue(run_id=run_id)
    for conflict in conflicts:
        queue.add(
            issue=(
                f"Dimension conflict on {conflict['item']}.{conflict['region']}."
                f"{conflict['dim']}: {conflict['values']}"
            ),
            severity=conflict.get("severity", "MEDIUM"),
            impact="Geometry blocked until resolved",
            category="conflict",
            source_refs=[conflict.get("node", "")],
        )
    return queue


def save_queue(queue: ReviewQueue, output_path: Path) -> Path:
    output_path = output_path.expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(queue.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path


def load_queue(path: Path) -> ReviewQueue:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return ReviewQueue(
        run_id=data.get("run_id", ""),
        schema_version=data.get("schema_version", "0.1"),
        status=data.get("status", "OPEN"),
        items=data.get("items", []),
        generated_utc=data.get("generated_utc", utcnow()),
    )