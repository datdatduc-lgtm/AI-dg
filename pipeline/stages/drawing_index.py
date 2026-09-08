"""Drawing Index & View Linking (M3).

Builds the Drawing Index described in `prompt/05_DRAWING_RECONCILIATION.md`:

    Drawing ID | Type | Title | Page | Scale | Related items | References | Confidence

and attempts to link PLAN <-> ELEVATION <-> SECTION <-> DETAIL based on
item codes, titles, callouts and nearby annotation.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .source_ingestion import SourcePackage, classify_drawing

ITEM_CODE_RE = re.compile(r"\b([A-Z]{1,6}[-_ ]?\d{1,4})\b")
SCALE_RE = re.compile(r"(?:TL|SCALE|TỶ LỆ|TY LE)\s*1\s*[:/]\s*(\d{1,4})", re.IGNORECASE)

DRAWING_ROLE_MAP = {
    "PLAN": "plan",
    "ELEVATION": "elevation",
    "SECTION": "section",
    "DETAIL": "detail",
    "SCHEDULE": "schedule",
    "MATERIAL_LEGEND": "material_legend",
    "UNKNOWN": "unknown",
}


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def extract_item_codes(text: str) -> list[str]:
    seen: set[str] = set()
    for match in ITEM_CODE_RE.finditer(text):
        code = re.sub(r"[\s_-]+", "-", match.group(1).upper())
        seen.add(code)
    return sorted(seen)


def extract_scale(text: str) -> str | None:
    match = SCALE_RE.search(text)
    return f"1/{match.group(1)}" if match else None


def _page_title(package: SourcePackage, page_index: int) -> str:
    page = package.pages[page_index]
    candidates = page.get("title_candidates") or []
    return candidates[0] if candidates else f"{package.source_type.upper()} page {page.get('page')}"


def _page_text(page: dict[str, Any]) -> str:
    """Return bounded page text from PDF/OCR or tabular row values."""
    pieces = [str(page.get("text_excerpt") or ""), str(page.get("ocr_text_excerpt") or "")]
    rows = page.get("rows")
    if isinstance(rows, list):
        for row in rows[:500]:
            if isinstance(row, dict):
                pieces.append(" ".join(str(value) for value in row.values() if value not in (None, "")))
    pieces.extend(str(value) for value in (page.get("title_candidates") or []) if value)
    return "\n".join(pieces)[:120_000]


@dataclass
class DrawingIndex:
    """Index of drawings across all ingested sources."""

    run_id: str
    schema_version: str = "0.1"
    entries: list[dict[str, Any]] = field(default_factory=list)
    view_links: list[dict[str, Any]] = field(default_factory=list)
    generated_utc: str = field(default_factory=utcnow)
    missing_source_types: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "run_id": self.run_id,
            "generated_utc": self.generated_utc,
            "entries": self.entries,
            "view_links": self.view_links,
            "missing_source_types": self.missing_source_types,
        }


def build_drawing_index(
    packages: list[SourcePackage],
    run_id: str = "",
    extra_texts: dict[str, str] | None = None,
) -> DrawingIndex:
    """Build the index from source packages.

    `extra_texts` maps a source_id to additional text (e.g. image OCR) that is
    merged into the page text for classification/item-code extraction.
    """
    extra_texts = extra_texts or {}
    index = DrawingIndex(run_id=run_id)
    letter = 0

    for package in packages:
        for page_idx, page in enumerate(package.pages):
            text = _page_text(page)
            text = "\n".join((text, extra_texts.get(package.source_id, "") or "")).strip()
            classification = classify_drawing(text) if text else page.get("classification")
            if not classification:
                classification = {"drawing_type": "UNKNOWN", "confidence": 0.0, "signals": []}

            title = _page_title(package, page_idx)
            scale = extract_scale(text or title)
            item_codes = extract_item_codes(text + "\n" + title)
            if not item_codes:
                item_codes = extract_item_codes(title)

            letter += 1
            drawing_id = f"D{letter:02d}"
            role = DRAWING_ROLE_MAP.get(classification["drawing_type"], "unknown")
            entry = {
                "id": drawing_id,
                "source_id": package.source_id,
                "page": page.get("page", page_idx + 1),
                "type": classification["drawing_type"],
                "role": role,
                "title": title,
                "scale": scale,
                "related_items": item_codes,
                "confidence": classification["confidence"],
                "references": {
                    "text_chars": page.get("text_chars"),
                    "ocr_status": page.get("ocr_status", "NOT_REQUESTED"),
                    "ocr_text_chars": page.get("ocr_text_chars", 0),
                    "ocr_confidence": page.get("ocr_confidence", 0.0),
                    "text_source": page.get("text_source", "unknown"),
                    "likely_scanned_or_image_only": page.get("likely_scanned_or_image_only", False),
                    "rendered_image": page.get("rendered_image"),
                },
            }
            index.entries.append(entry)

    # Link views that share an item code.
    by_item: dict[str, list[dict[str, Any]]] = {}
    for entry in index.entries:
        for code in entry["related_items"]:
            by_item.setdefault(code, []).append(entry)

    for code, entries in by_item.items():
        if len(entries) < 2:
            continue
        for i in range(len(entries)):
            for j in range(i + 1, len(entries)):
                a, b = entries[i], entries[j]
                if a["role"] == b["role"]:
                    continue
                index.view_links.append(
                    {
                        "from": a["id"],
                        "to": b["id"],
                        "item_code": code,
                        "relationship": f"{a['role']}_to_{b['role']}",
                        "status": "LINKED_BY_ITEM_CODE",
                    }
                )

    return index


def save_index(index: DrawingIndex, output_path: Path) -> Path:
    output_path = output_path.expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(index.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path


def load_index(path: Path) -> DrawingIndex:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return DrawingIndex(
        run_id=data.get("run_id", ""),
        schema_version=data.get("schema_version", "0.1"),
        entries=data.get("entries", []),
        view_links=data.get("view_links", []),
        generated_utc=data.get("generated_utc", utcnow()),
        missing_source_types=data.get("missing_source_types", []),
    )
