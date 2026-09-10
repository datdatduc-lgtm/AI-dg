"""Raw PDF/image layout and OCR evidence extraction for reconstruction V3.

The extractor is intentionally item-agnostic.  It identifies drawing views by
their printed labels, retains every OCR box as source evidence and emits no
geometry that cannot be traced to a recognized token or line-work region.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import shutil
import unicodedata
from typing import Any


VIEW_LABELS = (
    ("FRONT", ("MAT DUNG", "ELEVATION"), ("X", "Z")),
    ("PLAN", ("MAT BANG", "PLAN"), ("X", "Y")),
    ("SIDE", ("MAT BEN", "SIDE"), ("Y", "Z")),
    ("SECTION", ("MAT CAT", "SECTION"), ("Y", "Z")),
    ("DETAIL", ("CHI TIET", "DETAIL", "CT1", "CT 1"), ("Y", "Z")),
)
ITEM_CODE_RE = re.compile(r"\b[A-Z]{1,5}\s*[-–]\s*\d{1,4}\b")
NUMBER_RE = re.compile(r"(?<![A-Z])\d{1,5}(?:[.,]\d+)?(?![A-Z])")
WINDOWS_TESSERACT_CANDIDATES = (
    Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe"),
    Path(r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"),
)


@dataclass(frozen=True)
class OCRLine:
    text: str
    normalized: str
    bbox: tuple[int, int, int, int]
    confidence: float
    words: tuple[dict[str, Any], ...]


def _plain(text: str) -> str:
    value = unicodedata.normalize("NFD", text.upper())
    value = "".join(ch for ch in value if unicodedata.category(ch) != "Mn")
    return re.sub(r"\s+", " ", value.replace("Đ", "D")).strip()


def _render_source(source: Path, dpi: int) -> list[tuple[str, Any]]:
    import cv2
    import numpy as np
    try:
        import pymupdf as fitz
    except ImportError:  # PyMuPDF < 1.24 compatibility
        import fitz
    if source.suffix.lower() == ".pdf":
        document = fitz.open(source)
        matrix = fitz.Matrix(dpi / 72.0, dpi / 72.0)
        pages = []
        for index, page in enumerate(document):
            pix = page.get_pixmap(matrix=matrix, alpha=False)
            image = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
            if pix.n == 4:
                image = cv2.cvtColor(image, cv2.COLOR_RGBA2BGR)
            else:
                image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
            pages.append((f"page-{index + 1:04d}", image))
        document.close()
        return pages
    image = cv2.imread(str(source), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"SOURCE_IMAGE_UNREADABLE: {source}")
    return [("page-0001", image)]


def _configure_tesseract(executable: str | Path | None) -> str:
    import pytesseract
    candidate = str(executable) if executable else shutil.which("tesseract")
    if not candidate:
        candidate = next((str(path) for path in WINDOWS_TESSERACT_CANDIDATES if path.is_file()), "")
    if not candidate or not Path(candidate).is_file():
        raise RuntimeError("TESSERACT_NOT_FOUND")
    pytesseract.pytesseract.tesseract_cmd = candidate
    return candidate


def _rotate(image: Any, quarter_turns: int) -> Any:
    import numpy as np
    return np.rot90(image, quarter_turns).copy() if quarter_turns else image


def _ocr_rows(image: Any, tessdata_dir: Path | None) -> list[dict[str, Any]]:
    import pytesseract
    from pytesseract import Output
    config = "--psm 11"
    if tessdata_dir:
        # pytesseract passes config through its own argument splitter on
        # Windows; forward slashes avoid quote characters becoming part of
        # Tesseract's tessdata path.
        config += f" --tessdata-dir {tessdata_dir.as_posix()}"
    data = pytesseract.image_to_data(image, lang="vie+eng", config=config, output_type=Output.DICT)
    rows = []
    for index, raw_text in enumerate(data["text"]):
        text = str(raw_text).strip()
        try:
            confidence = float(data["conf"][index])
        except (TypeError, ValueError):
            confidence = -1.0
        if not text or confidence < 0:
            continue
        rows.append({
            "text": text,
            "normalized": _plain(text),
            "confidence": round(confidence, 3),
            "left": int(data["left"][index]),
            "top": int(data["top"][index]),
            "width": int(data["width"][index]),
            "height": int(data["height"][index]),
            "block": int(data["block_num"][index]),
            "paragraph": int(data["par_num"][index]),
            "line": int(data["line_num"][index]),
        })
    return rows


def _line_groups(rows: list[dict[str, Any]]) -> list[OCRLine]:
    groups: dict[tuple[int, int, int], list[dict[str, Any]]] = {}
    for row in rows:
        groups.setdefault((row["block"], row["paragraph"], row["line"]), []).append(row)
    lines = []
    for words in groups.values():
        words.sort(key=lambda row: row["left"])
        left = min(row["left"] for row in words)
        top = min(row["top"] for row in words)
        right = max(row["left"] + row["width"] for row in words)
        bottom = max(row["top"] + row["height"] for row in words)
        text = " ".join(row["text"] for row in words)
        lines.append(OCRLine(
            text=text,
            normalized=_plain(text),
            bbox=(left, top, right, bottom),
            confidence=round(sum(row["confidence"] for row in words) / len(words), 3),
            words=tuple(words),
        ))
    return sorted(lines, key=lambda row: (row.bbox[1], row.bbox[0]))


def _orientation_score(lines: list[OCRLine]) -> float:
    label_hits = sum(
        1
        for line in lines
        for _, patterns, _ in VIEW_LABELS
        if any(pattern in line.normalized for pattern in patterns)
    )
    item_hits = sum(bool(ITEM_CODE_RE.search(line.normalized)) for line in lines)
    number_hits = sum(bool(NUMBER_RE.search(line.normalized)) for line in lines)
    confident = sum(max(0.0, line.confidence) for line in lines) / max(len(lines), 1)
    return label_hits * 1000.0 + item_hits * 100.0 + min(number_hits, 50) * 2.0 + confident


def _choose_orientation(image: Any, tessdata_dir: Path | None) -> tuple[int, Any, list[OCRLine]]:
    candidates = []
    for turns in range(4):
        rotated = _rotate(image, turns)
        lines = _line_groups(_ocr_rows(rotated, tessdata_dir))
        candidates.append((_orientation_score(lines), turns, rotated, lines))
    _, turns, rotated, lines = max(candidates, key=lambda row: row[0])
    return turns * 90, rotated, lines


def _find_item_codes(lines: list[OCRLine]) -> list[str]:
    counts: dict[str, int] = {}
    label_values: set[str] = set()
    for line in lines:
        for match in ITEM_CODE_RE.findall(line.normalized):
            value = re.sub(r"\s+", "", match).replace("–", "-")
            counts[value] = counts.get(value, 0) + 1
            if any(pattern in line.normalized for _, patterns, _ in VIEW_LABELS for pattern in patterns):
                label_values.add(value)
    # Drawing numbers commonly look like item codes but occur only once in the
    # title block.  Repetition or direct occurrence in a view caption is the
    # generic evidence threshold for a physical-item identifier.
    return sorted(value for value, count in counts.items() if count >= 2 or value in label_values)


def _numeric_evidence(image: Any, tessdata_dir: Path | None) -> list[dict[str, Any]]:
    import pytesseract
    from pytesseract import Output
    evidence = []
    seen: set[tuple[str, int]] = set()
    tessdata_arg = f" --tessdata-dir {tessdata_dir.as_posix()}" if tessdata_dir else ""
    for turns in range(4):
        rotated = _rotate(image, turns)
        config = f"--psm 11 -c tessedit_char_whitelist=0123456789.,xXrR/+{tessdata_arg}"
        data = pytesseract.image_to_data(rotated, lang="eng", config=config, output_type=Output.DICT)
        for index, token in enumerate(data["text"]):
            token = str(token).strip().replace(",", ".")
            radius_match = re.fullmatch(r"[Rr](\d{1,5}(?:\.\d+)?)", token)
            number_match = re.fullmatch(r"\d{1,5}(?:\.\d+)?", token)
            if not radius_match and not number_match:
                continue
            numeric_token = radius_match.group(1) if radius_match else token
            value = float(numeric_token)
            if not 1 <= value <= 100_000:
                continue
            try:
                confidence = float(data["conf"][index])
            except (TypeError, ValueError):
                confidence = -1.0
            if confidence < 20:
                continue
            key = (token, turns)
            if key in seen:
                continue
            seen.add(key)
            evidence.append({
                "text": token,
                "value": int(value) if value.is_integer() else value,
                "kind": "RADIUS" if radius_match else "NUMBER",
                "confidence": round(confidence, 3),
                "bbox_px": [int(data[name][index]) for name in ("left", "top", "width", "height")],
                "ocr_rotation_deg_ccw": turns * 90,
            })
    return evidence


def _radius_evidence(image: Any, tessdata_dir: Path | None) -> list[dict[str, Any]]:
    """Read diagonal architectural radius callouts such as R50.

    Dimension leaders are often placed near ±40 degrees, where a normal OCR
    pass drops the ``R``.  Two opposite deskew passes are required and a value
    is accepted only when both independently see the same R-prefixed token.
    """
    import cv2
    import pytesseract
    from pytesseract import Output

    tessdata_arg = f" --tessdata-dir {tessdata_dir.as_posix()}" if tessdata_dir else ""
    by_value: dict[float, list[dict[str, Any]]] = {}
    height, width = image.shape[:2]
    center = (width / 2.0, height / 2.0)
    for angle in (-40, 40):
        matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
        rotated = cv2.warpAffine(image, matrix, (width, height), borderValue=(255, 255, 255))
        config = f"--psm 11 -c tessedit_char_whitelist=Rr0123456789{tessdata_arg}"
        data = pytesseract.image_to_data(rotated, lang="eng", config=config, output_type=Output.DICT)
        for index, raw in enumerate(data["text"]):
            match = re.fullmatch(r"[Rr](\d{1,5}(?:\.\d+)?)", str(raw).strip())
            if not match:
                continue
            confidence = float(data["conf"][index])
            if confidence < 20:
                continue
            value = float(match.group(1))
            by_value.setdefault(value, []).append({
                "text": str(raw).strip(), "value": int(value) if value.is_integer() else value,
                "kind": "RADIUS", "confidence": round(confidence, 3),
                "bbox_px": [int(data[name][index]) for name in ("left", "top", "width", "height")],
                "deskew_angle_deg": angle,
            })
    return [row for rows in by_value.values() if {row["deskew_angle_deg"] for row in rows} == {-40, 40} for row in rows]


def _view_bbox(label: OCRLine, width: int, height: int) -> list[int]:
    """Return a conservative evidence window around a printed view caption.

    A caption generally sits below its line-work.  The bbox is deliberately
    broad; later line-work segmentation may tighten it without losing source
    traceability.
    """
    left, top, right, bottom = label.bbox
    span_x = max(width // 5, (right - left) * 4)
    span_y = max(height // 5, span_x // 2)
    cx = (left + right) // 2
    return [max(0, cx - span_x // 2), max(0, top - span_y), min(width, cx + span_x // 2), min(height, bottom + height // 40)]


def extract_raw_drawing_evidence_v3(
    source_path: str | Path,
    *,
    tessdata_dir: str | Path | None = None,
    tesseract_executable: str | Path | None = None,
    dpi: int = 300,
) -> dict[str, Any]:
    """Extract auto-oriented OCR/layout evidence from every source page."""
    source = Path(source_path).resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    executable = _configure_tesseract(tesseract_executable)
    tessdata = Path(tessdata_dir).resolve() if tessdata_dir else None
    sheets = []
    all_views = []
    item_codes: set[str] = set()
    for page_id, image in _render_source(source, dpi):
        orientation_deg, upright, lines = _choose_orientation(image, tessdata)
        height, width = upright.shape[:2]
        numeric_evidence = _numeric_evidence(upright, tessdata)
        radius_evidence = _radius_evidence(upright, tessdata)
        page_codes = _find_item_codes(lines)
        item_codes.update(page_codes)
        views = []
        used_labels: set[tuple[int, int, int, int, str]] = set()
        for view_type, patterns, axes in VIEW_LABELS:
            for line in lines:
                matched = next((pattern for pattern in patterns if pattern in line.normalized), None)
                key = (*line.bbox, view_type)
                if not matched or key in used_labels:
                    continue
                used_labels.add(key)
                view_id = f"{page_id}:{view_type}:{len(views) + 1:02d}"
                source_ref = {
                    "source_id": str(source),
                    "sheet_id": page_id,
                    "view_id": view_id,
                    "bbox_px": list(line.bbox),
                    "ocr_text": line.text,
                    "ocr_confidence": line.confidence,
                }
                view = {
                    "view_id": view_id,
                    "sheet_id": page_id,
                    "view_type": view_type,
                    "projection_axes": list(axes),
                    "item_refs": page_codes,
                    "mandatory": view_type != "DETAIL",
                    "bbox_on_sheet": _view_bbox(line, width, height),
                    "section_marker": line.text if view_type in {"SECTION", "DETAIL"} else None,
                    "source_refs": [source_ref],
                    "label_evidence": source_ref,
                    "verification_contract": {},
                }
                views.append(view)
                all_views.append(view)
        sheets.append({
            "sheet_id": page_id,
            "width_px": width,
            "height_px": height,
            "orientation_correction_deg_ccw": orientation_deg,
            "item_codes": page_codes,
            "views": views,
            "ocr_lines": [
                {"text": line.text, "normalized": line.normalized, "bbox_px": list(line.bbox), "confidence": line.confidence}
                for line in lines
            ],
            "numeric_evidence": numeric_evidence,
            "radius_evidence": radius_evidence,
        })
    return {
        "schema_version": 3,
        "source": {"path": str(source), "kind": source.suffix.lower().lstrip("."), "ocr_engine": executable},
        "item_codes": sorted(item_codes),
        "sheets": sheets,
        "views": all_views,
    }


def _all_numeric_facts(evidence: dict[str, Any]) -> list[dict[str, Any]]:
    facts = []
    for sheet in evidence.get("sheets", []):
        for row in sheet.get("numeric_evidence", []):
            facts.append({**row, "sheet_id": sheet["sheet_id"], "source": "numeric_ocr"})
        for row in sheet.get("radius_evidence", []):
            facts.append({**row, "sheet_id": sheet["sheet_id"], "source": "angled_radius_ocr"})
        for line in sheet.get("ocr_lines", []):
            # Keep numbers embedded in material notation such as ``10MM`` as
            # traceable evidence too; chain selection applies its own bounds.
            for match in re.findall(r"\d{1,5}(?:[.,]\d+)?", line["normalized"]):
                value = float(match.replace(",", "."))
                facts.append({
                    "text": match,
                    "value": int(value) if value.is_integer() else value,
                    "confidence": line["confidence"],
                    "bbox_px": line["bbox_px"],
                    "ocr_rotation_deg_ccw": sheet["orientation_correction_deg_ccw"],
                    "sheet_id": sheet["sheet_id"],
                    "source": "text_ocr",
                })
    return facts


def _fact_ref(evidence: dict[str, Any], fact: dict[str, Any], view_id: str) -> dict[str, Any]:
    if fact is None:
        raise ValueError(f"SOURCE_FACT_MISSING: {view_id}")
    return {
        "source_id": evidence["source"]["path"],
        "sheet_id": fact["sheet_id"],
        "view_id": view_id,
        "bbox_px": fact.get("bbox_px"),
        "ocr_text": fact.get("text"),
        "ocr_confidence": fact.get("confidence"),
        "ocr_rotation_deg_ccw": fact.get("ocr_rotation_deg_ccw"),
        "deskew_angle_deg": fact.get("deskew_angle_deg"),
    }


def _best_fact(facts: list[dict[str, Any]], value: float) -> dict[str, Any] | None:
    candidates = [row for row in facts if abs(float(row["value"]) - value) < 1e-6]
    return max(candidates, key=lambda row: row.get("confidence", 0.0), default=None)


def _dimension_chain(values: set[float]) -> tuple[float, float, float] | None:
    candidates = []
    useful = sorted(value for value in values if 50 <= value <= 5000)
    for first in useful:
        for second in useful:
            total = first + second
            if total in values and first != second and max(first, second) / min(first, second) <= 10:
                candidates.append((total, max(first, second), min(first, second)))
    return max(candidates, default=None)


def interpret_profile_assembly_v3(evidence: dict[str, Any]) -> dict[str, Any]:
    """Infer a generic extruded-body + inserted-panel assembly from linked views.

    This recognizer is evidence gated: it refuses to emit a payload unless the
    raw drawing contains an item id, front/side/section/detail captions, an
    additive vertical dimension chain, a section thickness and an inserted
    material thickness. It contains no branch keyed by a drawing or item name.
    """
    item_codes = evidence.get("item_codes") or []
    if len(item_codes) != 1:
        raise ValueError("ONE_UNAMBIGUOUS_ITEM_CODE_REQUIRED")
    selected_views: dict[str, dict[str, Any]] = {}
    for view_type in ("FRONT", "SIDE", "SECTION", "DETAIL"):
        candidates = [view for view in evidence.get("views", []) if view["view_type"] == view_type]
        if not candidates:
            raise ValueError(f"MANDATORY_VIEW_MISSING: {view_type}")
        selected_views[view_type] = max(candidates, key=lambda row: row["label_evidence"].get("ocr_confidence", 0.0))

    facts = _all_numeric_facts(evidence)
    values = {float(row["value"]) for row in facts if row.get("confidence", 0) >= 50}
    chain = _dimension_chain(values)
    if chain is None:
        raise ValueError("VERTICAL_DIMENSION_CHAIN_NOT_FOUND")
    overall_z, body_z, exposed_z = chain
    length_candidates = [value for value in values if value > overall_z * 1.5 and value < 100_000]
    if not length_candidates:
        raise ValueError("ITEM_LENGTH_NOT_FOUND")
    length_x = max(length_candidates)

    all_text = " ".join(line["normalized"] for sheet in evidence["sheets"] for line in sheet["ocr_lines"])
    thickness_matches = [float(value) for value in re.findall(r"(?:DAY|THICK(?:NESS)?)\s*(\d+(?:[.,]\d+)?)", all_text)]
    if not thickness_matches:
        raise ValueError("INSERT_THICKNESS_NOT_FOUND")
    insert_y = min(thickness_matches)

    # A section total is supported by a repeated small dimension and by an
    # explicit overall in the same drawing.  Values 1/2/5 are common scales or
    # note indices and are excluded from construction dimensions.
    small_values = sorted(value for value in values if 8 <= value <= 100 and value != insert_y)
    profile_candidates = []
    for total in small_values:
        for side in small_values:
            slot = total - 2 * side
            if insert_y <= slot <= insert_y * 1.5:
                profile_candidates.append((abs(slot - insert_y), total, -side, side, slot))
    if not profile_candidates:
        raise ValueError("SECTION_THICKNESS_NOT_FOUND")
    _, section_y, _, side_y, slot_y = min(profile_candidates)
    if slot_y < insert_y:
        raise ValueError("SECTION_SLOT_WIDTH_NOT_DERIVABLE")

    remaining = [value for value in values if 20 <= value <= body_z / 2 and value not in {section_y, side_y, slot_y}]
    embed_z = min(remaining, key=lambda value: abs(value - exposed_z / 6), default=0)
    if embed_z <= 0:
        raise ValueError("EMBED_DEPTH_NOT_FOUND")

    item_id = item_codes[0]
    front = selected_views["FRONT"]
    side = selected_views["SIDE"]
    section = selected_views["SECTION"]
    detail = selected_views["DETAIL"]
    for view in selected_views.values():
        view["item_refs"] = [item_id]
        view["mandatory"] = True
    detail["refines_view_id"] = section["view_id"]
    detail["mandatory"] = True

    center_min = (section_y - insert_y) / 2.0
    center_max = center_min + insert_y
    lower = {
        "id": "body", "visibility": "VISIBLE", "material_id": "body",
        "bounds": {"x": [0, length_x], "y": [0, section_y], "z": [0, body_z]},
        "state": "EXPLICIT",
    }
    insert = {
        "id": "insert", "visibility": "VISIBLE", "material_id": "insert",
        "bounds": {"x": [0, length_x], "y": [center_min, center_max], "z": [body_z - embed_z, overall_z]},
        "state": "DERIVED_FROM_VIEWS",
    }
    flush_insert = {**insert, "bounds": {**insert["bounds"], "y": [0, insert_y]}}
    slot_feature = {
        "feature_id": "slot-main", "type": "SLOT",
        "dimensions_mm": {"width": slot_y, "depth": embed_z},
        "position": {"axis": "Y", "alignment": "CENTER"},
        "state": "DERIVED_FROM_VIEWS",
        "source_refs": [
            _fact_ref(evidence, _best_fact(facts, section_y), detail["view_id"]),
            _fact_ref(evidence, _best_fact(facts, side_y), detail["view_id"]),
            _fact_ref(evidence, _best_fact(facts, embed_z), section["view_id"]),
        ],
    }
    radius_facts = [row for row in facts if row.get("kind") == "RADIUS"]
    radius_feature = None
    if radius_facts:
        radius_value = max({float(row["value"]) for row in radius_facts}, key=lambda value: sum(float(row["value"]) == value for row in radius_facts))
        radius_fact = max((row for row in radius_facts if float(row["value"]) == radius_value), key=lambda row: row.get("confidence", 0))
        radius_feature = {
            "feature_id": "top-corner-radius", "type": "RADIUS",
            "dimensions_mm": {"radius": radius_value},
            "position": {"edge": "TOP", "ends": "BOTH"},
            "view_types": ["FRONT"], "state": "EXPLICIT",
            "source_refs": [_fact_ref(evidence, radius_fact, front["view_id"])],
        }
    source_refs = front["source_refs"] + side["source_refs"] + section["source_refs"] + detail["source_refs"]
    front["verification_contract"] = {
        "overall_mm": {"X": length_x, "Z": overall_z},
        "visible_region_ids": ["body", "insert"],
        "region_spans": {"body": {"Z": [0, body_z]}, "insert": {"Z": [body_z - embed_z, overall_z]}},
        "features": [radius_feature] if radius_feature else [],
    }
    side["verification_contract"] = {
        "overall_mm": {"Y": section_y, "Z": overall_z},
        "region_spans": {"insert": {"Y": [center_min, center_max], "Z": [body_z - embed_z, overall_z]}},
    }
    section["verification_contract"] = {
        "overall_mm": {"Y": section_y, "Z": overall_z},
        "region_spans": {"insert": {"Y": [center_min, center_max]}},
        "section_features": [slot_feature],
    }
    detail["verification_contract"] = {"overall_mm": {"Y": section_y}, "section_features": [slot_feature]}

    def constraint(constraint_id: str, axis: str, value: float, view: dict[str, Any]) -> dict[str, Any]:
        fact = _best_fact(facts, value)
        return {
            "constraint_id": constraint_id, "kind": "DIMENSION", "axis": axis,
            "value_mm": value, "start_ref": f"{item_id}.min_{axis.lower()}",
            "end_ref": f"{item_id}.max_{axis.lower()}", "view_id": view["view_id"],
            "state": "EXPLICIT", "source_refs": [_fact_ref(evidence, fact, view["view_id"])],
        }

    return {
        "schema_version": 3,
        "source_review_status": "APPROVED",
        "raw_evidence": evidence,
        "views": list(selected_views.values()),
        "constraints": [
            constraint("overall-x", "X", length_x, front),
            constraint("overall-z", "Z", overall_z, front),
            constraint("body-z", "Z", body_z, front),
            constraint("exposed-z", "Z", exposed_z, front),
            constraint("section-y", "Y", section_y, detail),
            constraint("embed-z", "Z", embed_z, section),
            constraint("insert-y", "Y", insert_y, section),
        ],
        "section_profiles": [{
            "profile_id": "profile-main", "view_id": section["view_id"],
            "state": "DERIVED_FROM_VIEWS", "profile_kind": "EXTRUDED_SLOTTED_BODY",
            "dimensions_mm": {"body_thickness": section_y, "body_height": body_z, "length": length_x},
            "features": [slot_feature], "source_refs": section["source_refs"] + detail["source_refs"],
        }],
        "items": [{
            "item_id": item_id, "state": "DERIVED_FROM_VIEWS", "source_refs": source_refs,
            "envelope": {"x_mm": length_x, "y_mm": section_y, "z_mm": overall_z},
            "regions": [lower, insert], "section_profile_ids": ["profile-main"],
            "features": [radius_feature] if radius_feature else [],
            "relationships": [
                {"type": "CENTERED_IN", "from": "insert", "to": "body", "axis": "Y"},
                {"type": "EMBEDDED_IN", "from": "insert", "to": "body", "depth_mm": embed_z},
            ],
            "materials": [{"id": "body"}, {"id": "insert", "thickness_mm": insert_y}],
            "hypotheses": [
                {"hypothesis_id": "H-centered-slotted", "state": "DERIVED_FROM_VIEWS", "geometry": {"regions": [lower, insert], "section_profile_ids": ["profile-main"], "relationships": [{"type": "CENTERED_IN", "from": "insert", "to": "body", "axis": "Y"}, {"type": "EMBEDDED_IN", "from": "insert", "to": "body", "depth_mm": embed_z}]}, "source_refs": source_refs},
                {"hypothesis_id": "H-flush-unslotted", "state": "DERIVED_FROM_VIEWS", "geometry": {"regions": [lower, flush_insert], "section_profile_ids": [], "relationships": []}, "source_refs": source_refs},
            ],
        }],
    }
