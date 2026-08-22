#!/usr/bin/env python3
"""Validate AI-dg extracted item JSON.

Uses jsonschema when available. In restricted runtimes such as ChatGPT Work where
third-party packages may not be installed, falls back to a small stdlib validator
that checks the safety-critical contract instead of failing import-time.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

try:
    from jsonschema import Draft202012Validator  # type: ignore
except Exception:  # pragma: no cover - runtime compatibility path
    Draft202012Validator = None

SKILL_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = SKILL_ROOT / "schemas" / "items.schema.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate AI-dg items.json")
    parser.add_argument("items", type=Path)
    return parser.parse_args()


def basic_validate(data: Any) -> list[str]:
    """Validate safety-critical fields without third-party dependencies."""
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["<root>: expected object"]
    if "schema_version" not in data:
        errors.append("schema_version: missing")
    items = data.get("items")
    if not isinstance(items, list):
        errors.append("items: expected array")
        return errors

    for index, item in enumerate(items):
        loc = f"items[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{loc}: expected object")
            continue
        for field in ("id", "quantity", "confidence", "review_required", "source"):
            if field not in item:
                errors.append(f"{loc}.{field}: missing")
        if not isinstance(item.get("id"), str) or not item.get("id"):
            errors.append(f"{loc}.id: expected non-empty string")
        quantity = item.get("quantity")
        if not isinstance(quantity, int) or quantity < 1:
            errors.append(f"{loc}.quantity: expected integer >= 1")
        confidence = item.get("confidence")
        if not isinstance(confidence, (int, float)) or not (0 <= confidence <= 1):
            errors.append(f"{loc}.confidence: expected number in [0,1]")
        if not isinstance(item.get("review_required"), bool):
            errors.append(f"{loc}.review_required: expected boolean")
        source = item.get("source")
        if not isinstance(source, dict):
            errors.append(f"{loc}.source: expected object")
        else:
            if not isinstance(source.get("pdf"), str) or not source.get("pdf"):
                errors.append(f"{loc}.source.pdf: expected non-empty string")
            if not isinstance(source.get("page"), int) or source.get("page", 0) < 1:
                errors.append(f"{loc}.source.page: expected integer >= 1")
            if not isinstance(source.get("evidence"), str) or not source.get("evidence"):
                errors.append(f"{loc}.source.evidence: expected non-empty string")
    return errors


def main() -> int:
    args = parse_args()
    data = json.loads(args.items.read_text(encoding="utf-8"))

    if Draft202012Validator is not None:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        schema_errors = sorted(
            Draft202012Validator(schema).iter_errors(data),
            key=lambda e: list(e.path),
        )
        if schema_errors:
            for error in schema_errors:
                location = ".".join(str(x) for x in error.absolute_path) or "<root>"
                print(f"ERROR {location}: {error.message}")
            return 2
        validator_mode = "jsonschema"
    else:
        fallback_errors = basic_validate(data)
        if fallback_errors:
            for error in fallback_errors:
                print(f"ERROR {error}")
            return 2
        validator_mode = "stdlib-fallback"
        print("INFO jsonschema unavailable; used safety-critical stdlib fallback validator.")

    warnings = 0
    for index, item in enumerate(data.get("items", []), start=1):
        reasons: list[str] = []
        if item.get("confidence", 0) < 0.90 and not item.get("review_required"):
            reasons.append("confidence < 0.90 but review_required is false")
        if item.get("length_mm") is None or item.get("width_mm") is None:
            reasons.append("missing length/width: area cannot be calculated")
        if not item.get("material_code") and not item.get("source_material_code"):
            reasons.append("no material code available")
        if reasons:
            warnings += 1
            print(f"REVIEW item #{index} ({item.get('id')}): " + "; ".join(reasons))

    print(
        f"Validation passed ({validator_mode}). Items: {len(data.get('items', []))}. "
        f"Review warnings: {warnings}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
