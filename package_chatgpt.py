#!/usr/bin/env python3
"""Build an upload-ready AI-dg Agent Skill archive.

The archive places SKILL.md at the ZIP root instead of preserving the repository's
.agents/skills/... wrapper. This keeps the package portable across Agent Skills
surfaces that expect the skill directory itself.
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SKILL_DIR = ROOT / ".agents" / "skills" / "ai-dg-estimator"
DIST_DIR = ROOT / "dist"


def build(output: Path | None = None) -> Path:
    if not SKILL_DIR.is_dir():
        raise SystemExit(f"Skill directory not found: {SKILL_DIR}")
    if not (SKILL_DIR / "SKILL.md").is_file():
        raise SystemExit("SKILL.md is missing from the skill root")

    DIST_DIR.mkdir(parents=True, exist_ok=True)
    target = output or (DIST_DIR / "ai-dg-estimator")
    target = target.resolve()

    # shutil.make_archive appends .zip itself.
    if target.suffix.lower() == ".zip":
        target = target.with_suffix("")

    archive = Path(
        shutil.make_archive(
            base_name=str(target),
            format="zip",
            root_dir=str(SKILL_DIR),
        )
    )

    print(f"Built: {archive}")
    print("ZIP root contains SKILL.md and the skill resources directly.")
    return archive


def main() -> None:
    parser = argparse.ArgumentParser(description="Package AI-dg for Agent Skills upload")
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output path/name (default: dist/ai-dg-estimator.zip)",
    )
    args = parser.parse_args()
    build(args.output)


if __name__ == "__main__":
    main()
