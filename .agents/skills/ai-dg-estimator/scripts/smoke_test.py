#!/usr/bin/env python3
"""Run a local end-to-end V0.1 smoke test using bundled example data."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL_ROOT / "scripts"
EXAMPLE_ITEMS = SKILL_ROOT / "examples" / "items.example.json"
EXAMPLE_MATERIALS = SKILL_ROOT / "data" / "materials.example.json"


def run(*args: str) -> None:
    print("+", " ".join(args))
    subprocess.run(args, check=True)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="ai-dg-smoke-") as tmp:
        tmp_path = Path(tmp)
        bom = tmp_path / "bom.json"
        excel = tmp_path / "estimate.xlsx"

        run(sys.executable, str(SCRIPTS / "validate_items.py"), str(EXAMPLE_ITEMS))
        run(
            sys.executable,
            str(SCRIPTS / "calculate_bom.py"),
            str(EXAMPLE_ITEMS),
            "--materials",
            str(EXAMPLE_MATERIALS),
            "--output",
            str(bom),
        )
        run(
            sys.executable,
            str(SCRIPTS / "export_excel.py"),
            str(EXAMPLE_ITEMS),
            str(bom),
            "--output",
            str(excel),
        )

        payload = json.loads(bom.read_text(encoding="utf-8"))
        assert payload["bom"], "Expected at least one BOM row"
        assert excel.exists() and excel.stat().st_size > 0, "Excel output was not created"
        print(f"PASS: BOM rows={len(payload['bom'])}, review={len(payload['review'])}, excel={excel.stat().st_size} bytes")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
