#!/usr/bin/env python3
"""Build upload-ready AI-dg Agent Skill archives for ChatGPT Work.

The archive places SKILL.md at the ZIP root instead of preserving the repository's
.agents/skills/... wrapper. The same canonical skill source remains portable for
ChatGPT Work, Codex and OpenCode.
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SKILL_DIR = ROOT / ".agents" / "skills" / "ai-dg-estimator"
DIST_DIR = ROOT / "dist"
VERSION = "0.3.0-alpha"
DEFAULT_NAME = f"AI-dg-Work-v{VERSION}"
REQUIRED_FILES = [
    "SKILL.md",
    "references/workspace-io.md",
    "references/drawing-reading-method.md",
    "references/orthographic-reconstruction.md",
    "references/pdf-cad-reconciliation.md",
    "references/material-rules.md",
    "references/chatgpt-test-protocol.md",
    "references/sketchup-ruby-prototype.md",
    "scripts/workspace/init_project.py",
    "scripts/workspace/scan_input.py",
    "scripts/workspace/finalize_output.py",
    "scripts/smoke_test.py",
    "scripts/validate_items.py",
]


def validate_skill() -> None:
    if not SKILL_DIR.is_dir():
        raise SystemExit(f"Skill directory not found: {SKILL_DIR}")
    missing = [rel for rel in REQUIRED_FILES if not (SKILL_DIR / rel).is_file()]
    if missing:
        raise SystemExit("Missing required skill files: " + ", ".join(missing))

    skill_text = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
    if not skill_text.startswith("---\n"):
        raise SystemExit("SKILL.md must start with YAML frontmatter")
    if f'version: "{VERSION}"' not in skill_text:
        raise SystemExit("SKILL.md version does not match package version")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inspect_archive(path: Path) -> list[str]:
    with zipfile.ZipFile(path, "r") as archive:
        names = sorted(archive.namelist())
    if "SKILL.md" not in names:
        raise SystemExit("Package invalid: SKILL.md is not at ZIP root")
    return names


def build(output: Path | None = None) -> Path:
    validate_skill()
    DIST_DIR.mkdir(parents=True, exist_ok=True)

    target = (output or (DIST_DIR / DEFAULT_NAME)).resolve()
    if target.suffix.lower() == ".zip":
        target = target.with_suffix("")

    archive = Path(
        shutil.make_archive(
            base_name=str(target),
            format="zip",
            root_dir=str(SKILL_DIR),
        )
    )

    names = inspect_archive(archive)
    checksum = sha256_file(archive)

    checksum_path = archive.with_suffix(".sha256")
    checksum_path.write_text(f"{checksum}  {archive.name}\n", encoding="utf-8")

    manifest_path = archive.with_name(archive.stem + "-contents.txt")
    manifest_path.write_text("\n".join(names) + "\n", encoding="utf-8")

    alias = DIST_DIR / "ai-dg-estimator.zip"
    if alias.resolve() != archive.resolve():
        shutil.copy2(archive, alias)

    print(f"Built: {archive}")
    print(f"SHA256: {checksum}")
    print(f"Contents: {manifest_path}")
    print(f"Compatibility alias: {alias}")
    print("ZIP root contains SKILL.md and skill resources directly.")
    return archive


def main() -> None:
    parser = argparse.ArgumentParser(description="Package AI-dg for ChatGPT Work / Agent Skills upload")
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help=f"Output path/name (default: dist/{DEFAULT_NAME}.zip)",
    )
    args = parser.parse_args()
    build(args.output)


if __name__ == "__main__":
    main()
