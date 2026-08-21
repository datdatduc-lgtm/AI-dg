#!/usr/bin/env python3
"""Validate AI-dg extracted item JSON against the V0.1 schema and safety rules."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from jsonschema import Draft202012Validator

SKILL_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = SKILL_ROOT / "schemas" / "items.schema.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate AI-dg items.json")
    parser.add_argument("items", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    data = json.loads(args.items.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    errors = sorted(Draft202012Validator(schema).iter_errors(data), key=lambda e: list(e.path))
    if errors:
        for error in errors:
            location = ".".join(str(x) for x in error.absolute_path) or "<root>"
            print(f"ERROR {location}: {error.message}")
        return 2

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

    print(f"Schema valid. Items: {len(data.get('items', []))}. Review warnings: {warnings}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
