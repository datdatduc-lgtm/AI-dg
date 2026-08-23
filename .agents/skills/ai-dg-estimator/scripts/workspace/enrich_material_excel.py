#!/usr/bin/env python3
"""Backward-compatible no-op for AI-dg >= 0.3.3.

Material specification fields are now consumed directly by export_project_excel.py.
The user-facing workbook intentionally stays concise and no longer receives a
separate THONG_SO_VAT_LIEU/debug sheet.

This file remains so older automation that still calls it does not fail.
"""

from __future__ import annotations

import argparse
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compatibility shim; material Excel is already enriched by exporter")
    parser.add_argument("project_root", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = args.project_root.expanduser().resolve()
    print(f"No-op: {root / 'OUTPUT' / 'EXCEL' / 'AI-dg_Tong-hop-vat-lieu.xlsx'} already includes material specifications.")
    print("No THONG_SO_VAT_LIEU sheet is added; user-facing Excel stays concise.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
