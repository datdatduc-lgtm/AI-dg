#!/usr/bin/env python3
"""Run an AI-dg compatibility smoke test.

The core smoke path intentionally requires only the Python standard library so
restricted runtimes such as ChatGPT Work can validate the skill package without
installing jsonschema/openpyxl/PyMuPDF first. Optional Excel export is tested only
when openpyxl is already available.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL_ROOT / "scripts"
EXAMPLE_ITEMS = SKILL_ROOT / "examples" / "items.example.json"
EXAMPLE_MATERIALS = SKILL_ROOT / "data" / "materials.example.json"
REQUIRED_REFERENCES = [
    SKILL_ROOT / "SKILL.md",
    SKILL_ROOT / "references" / "drawing-reading-method.md",
    SKILL_ROOT / "references" / "orthographic-reconstruction.md",
    SKILL_ROOT / "references" / "pdf-cad-reconciliation.md",
    SKILL_ROOT / "references" / "material-rules.md",
    SKILL_ROOT / "references" / "chatgpt-test-protocol.md",
]


def run(*args: str) -> None:
    print("+", " ".join(args))
    subprocess.run(args, check=True)


def check_skill_files() -> None:
    missing = [str(path.relative_to(SKILL_ROOT)) for path in REQUIRED_REFERENCES if not path.is_file()]
    if missing:
        raise SystemExit("Missing required skill files: " + ", ".join(missing))
    skill_text = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
    if "orthographic 3D reconstruction" not in skill_text and "Orthographic" not in skill_text:
        raise SystemExit("SKILL.md does not appear to contain geometry-first methodology")
    print("PASS: required geometry-first skill files are present")


def main() -> int:
    check_skill_files()

    with tempfile.TemporaryDirectory(prefix="ai-dg-smoke-") as tmp:
        tmp_path = Path(tmp)
        bom = tmp_path / "bom.json"
        excel = tmp_path / "estimate.xlsx"

        # validate_items.py now has a stdlib fallback when jsonschema is absent.
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

        payload = json.loads(bom.read_text(encoding="utf-8"))
        assert payload["bom"], "Expected at least one BOM row"
        print(f"PASS: deterministic BOM rows={len(payload['bom'])}, review={len(payload['review'])}")

        if importlib.util.find_spec("openpyxl") is not None:
            run(
                sys.executable,
                str(SCRIPTS / "export_excel.py"),
                str(EXAMPLE_ITEMS),
                str(bom),
                "--output",
                str(excel),
            )
            assert excel.exists() and excel.stat().st_size > 0, "Excel output was not created"
            print(f"PASS: optional Excel export ({excel.stat().st_size} bytes)")
        else:
            print("SKIP: openpyxl unavailable; Excel runtime test is optional in restricted Work environments")

    print("PASS: AI-dg compatibility smoke test completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
