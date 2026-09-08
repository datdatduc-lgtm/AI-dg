#!/usr/bin/env python3
"""AI-DG Pipeline CLI.

Usage:
    python -m pipeline.cli run <project_root> [--review-status APPROVED|OPEN] [--no-render]
    python -m pipeline.cli info <project_root>
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    from .stages.runner import run_pipeline
except ImportError:  # Support direct execution by installers and shell users.
    from pipeline.stages.runner import run_pipeline


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AI-DG 2D->3D pipeline runner")
    sub = parser.add_subparsers(dest="command", required=True)

    run_cmd = sub.add_parser("run", help="Run full 2D->3D pipeline")
    run_cmd.add_argument("project_root", type=Path)
    run_cmd.add_argument("--run-id", default="")
    run_cmd.add_argument("--review-status", default="OPEN", choices=["APPROVED", "OPEN", "BLOCKED"])
    run_cmd.add_argument("--no-render", action="store_true")
    run_cmd.add_argument("--output", type=Path, default=None)

    info_cmd = sub.add_parser("info", help="Show project metadata")
    info_cmd.add_argument("project_root", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.command == "info":
        root = args.project_root.expanduser().resolve()
        marker = root / "project.ai-dg.json"
        if marker.is_file():
            data = json.loads(marker.read_text(encoding="utf-8"))
            print(json.dumps(data, ensure_ascii=False, indent=2))
        else:
            print(f"No project.ai-dg.json marker found at {root}", file=sys.stderr)
            return 1
        return 0

    result = run_pipeline(
        args.project_root,
        run_id=args.run_id,
        render_pdf=not args.no_render,
        review_status=args.review_status,
    )
    payload = result.to_dict()

    if args.output:
        output_path = args.output.expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Run summary written to {output_path}")
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
