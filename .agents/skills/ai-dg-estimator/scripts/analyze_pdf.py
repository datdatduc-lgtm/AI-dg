#!/usr/bin/env python3
"""Extract page text/signals from a PDF and optionally render pages for visual review.

V0.1 intentionally does not perform OCR. Pages with little embedded text are
flagged so an agent/user can inspect rendered images instead of trusting an
empty extraction result.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import fitz  # PyMuPDF

DIMENSION_RE = re.compile(
    r"(?<!\d)(\d{2,5}(?:\.\d+)?)\s*[xX×]\s*(\d{2,5}(?:\.\d+)?)(?:\s*[xX×]\s*(\d{1,4}(?:\.\d+)?))?"
)
MATERIAL_RE = re.compile(
    r"\b(?:MDF|HDF|MFC|PLY|PLYWOOD|WD|LAM|VEN|VENEER|HW|F)[-_ ]?\d{1,4}\b",
    re.IGNORECASE,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze a construction/interior PDF")
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--project", type=Path, default=Path("project"))
    parser.add_argument("--render", action="store_true", help="Render every page to PNG")
    parser.add_argument("--dpi", type=int, default=150)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    pdf_path = args.pdf.expanduser().resolve()
    if not pdf_path.is_file() or pdf_path.suffix.lower() != ".pdf":
        raise SystemExit(f"PDF not found or invalid extension: {pdf_path}")

    extracted_dir = args.project / "extracted"
    pages_dir = extracted_dir / "pages"
    extracted_dir.mkdir(parents=True, exist_ok=True)
    if args.render:
        pages_dir.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(pdf_path)
    pages: list[dict] = []
    scanned_pages: list[int] = []

    for index, page in enumerate(doc):
        page_number = index + 1
        text = page.get_text("text").strip()
        likely_scanned = len(text) < 20
        if likely_scanned:
            scanned_pages.append(page_number)

        dimensions = []
        for match in DIMENSION_RE.finditer(text):
            dimensions.append(
                {
                    "raw": match.group(0),
                    "a_mm": float(match.group(1)),
                    "b_mm": float(match.group(2)),
                    "c_mm": float(match.group(3)) if match.group(3) else None,
                }
            )

        material_codes = sorted({m.group(0).strip() for m in MATERIAL_RE.finditer(text)})
        image_path = None
        if args.render:
            zoom = args.dpi / 72.0
            pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
            image_path = pages_dir / f"page-{page_number:04d}.png"
            pix.save(image_path)

        pages.append(
            {
                "page": page_number,
                "text_chars": len(text),
                "likely_scanned_or_image_only": likely_scanned,
                "text": text,
                "dimension_candidates": dimensions,
                "material_code_candidates": material_codes,
                "rendered_image": str(image_path) if image_path else None,
            }
        )

    payload = {
        "schema_version": "0.1",
        "source_pdf": str(pdf_path),
        "page_count": len(doc),
        "likely_scanned_pages": scanned_pages,
        "pages": pages,
    }
    output = extracted_dir / "pages.json"
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Analyzed {len(doc)} pages -> {output}")
    if scanned_pages:
        print("Review rendered images for likely scanned/image-only pages:", scanned_pages)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
