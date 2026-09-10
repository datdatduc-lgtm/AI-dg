"""Generate a second raw drawing fixture with no intermediate JSON."""

from __future__ import annotations

from pathlib import Path


def generate_profile_fixture_v3(path: str | Path) -> Path:
    """Create a different profile-assembly sheet for OCR acceptance.

    This is test data, not production interpretation logic.  Dimensions differ
    from VN-1 and the sheet is natively landscape rather than rotated.
    """
    try:
        import pymupdf as fitz
    except ImportError:  # PyMuPDF < 1.24 compatibility
        import fitz

    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    document = fitz.open()
    page = document.new_page(width=842, height=595)
    shape = page.new_shape()
    shape.draw_rect(fitz.Rect(20, 20, 822, 575))

    # Front elevation: body 700 + exposed insert 300 = 1000.
    shape.draw_rect(fitz.Rect(55, 210, 415, 420))
    shape.draw_rect(fitz.Rect(55, 120, 415, 210))
    shape.draw_line(fitz.Point(55, 210), fitz.Point(415, 210))
    page.insert_text((155, 445), "FRONT ELEVATION RS-2", fontsize=12)
    page.insert_text((205, 465), "2400", fontsize=11)
    page.insert_text((425, 170), "1000", fontsize=11)
    page.insert_text((425, 290), "700", fontsize=11)
    page.insert_text((425, 145), "300", fontsize=11)

    # Side and section are intentionally separate views.
    shape.draw_rect(fitz.Rect(480, 120, 525, 420))
    shape.draw_rect(fitz.Rect(496, 105, 509, 225))
    page.insert_text((455, 445), "SIDE ELEVATION", fontsize=12)
    page.insert_text((530, 275), "1000", fontsize=11)
    page.insert_text((486, 465), "60", fontsize=11)

    shape.draw_rect(fitz.Rect(580, 120, 640, 420))
    shape.draw_rect(fitz.Rect(603, 105, 617, 237))
    page.insert_text((570, 445), "SECTION A-A", fontsize=12)
    page.insert_text((645, 335), "700", fontsize=11)
    page.insert_text((645, 180), "300", fontsize=11)
    page.insert_text((645, 235), "45", fontsize=11)

    # Detail: 23 + 14 + 23 = 60, insert thickness 12.
    shape.draw_rect(fitz.Rect(685, 105, 775, 245))
    shape.draw_rect(fitz.Rect(723, 80, 737, 170))
    page.insert_text((681, 270), "DETAIL D1", fontsize=12)
    page.insert_text((690, 295), "23  14  23", fontsize=11)
    page.insert_text((715, 315), "60", fontsize=11)
    page.insert_text((675, 345), "GLASS THICKNESS 12", fontsize=10)
    page.insert_text((665, 545), "PROFILE SCREEN RS-2", fontsize=12)
    shape.finish(color=(0, 0, 0), width=0.8)
    shape.commit()
    document.save(output)
    document.close()
    return output
