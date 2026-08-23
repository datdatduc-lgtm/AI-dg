#!/usr/bin/env python3
"""Create concise user-facing AI-dg material-summary and quotation workbooks.

The workbook is intentionally NOT an AI/debug report. Technical provenance,
Ruby paths, readiness states, geometry-role IDs and review internals remain in
WORK/ and JSON/report artifacts. The Excel files focus on the information a
fabricator/estimator needs to read quickly.

Primary inputs (when present):
  OUTPUT/TAKEOFF/material-specifications.json
  OUTPUT/TAKEOFF/bom.json
  OUTPUT/TAKEOFF/items.json
  OUTPUT/TAKEOFF/suppliers.json
  OUTPUT/IMAGES/MATERIALS/*  (optional legend/material swatches)

Outputs:
  OUTPUT/EXCEL/AI-dg_Tong-hop-vat-lieu.xlsx
  OUTPUT/EXCEL/AI-dg_Bao-gia.xlsx

Rules:
- never invent material codes, thicknesses, colors, prices or quantities;
- preserve drawing-backed material properties even if BOM is partial;
- 1200x2400 conversion is area-equivalent only (2.88 m²/sheet), not nesting;
- material sample images are embedded only when an actual extracted image exists.
"""

from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path
from typing import Any, Iterable

try:
    from openpyxl import Workbook
    from openpyxl.drawing.image import Image as XLImage
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "Excel exporter requires openpyxl and Pillow. Install AI-dg runtime extras or run: "
        "python -m pip install openpyxl Pillow"
    ) from exc

TITLE_FILL = PatternFill("solid", fgColor="1F4E78")
HEADER_FILL = PatternFill("solid", fgColor="2F75B5")
NOTE_FILL = PatternFill("solid", fgColor="EAF2F8")
TITLE_FONT = Font(size=15, bold=True, color="FFFFFF")
HEADER_FONT = Font(bold=True, color="FFFFFF")
BOLD_FONT = Font(bold=True)
THIN = Side(style="thin", color="D9E2F3")
TABLE_BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
SHEET_WIDTH_MM = 1200.0
SHEET_HEIGHT_MM = 2400.0
SHEET_AREA_M2 = (SHEET_WIDTH_MM * SHEET_HEIGHT_MM) / 1_000_000.0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export concise AI-dg project Excel deliverables")
    parser.add_argument("project_root", type=Path)
    return parser.parse_args()


def load_json(path: Path, default: Any) -> Any:
    if not path.is_file():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise SystemExit(f"Invalid JSON: {path}: {exc}") from exc


def payload_rows(payload: Any, keys: Iterable[str]) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if not isinstance(payload, dict):
        return []
    for key in keys:
        value = payload.get(key)
        if isinstance(value, list):
            return [row for row in value if isinstance(row, dict)]
    return []


def first_value(row: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = row.get(key)
        if value not in (None, "", []):
            return value
    return None


def text(value: Any) -> str:
    if value in (None, "", []):
        return ""
    if isinstance(value, list):
        return "; ".join(text(v) for v in value if text(v))
    if isinstance(value, dict):
        return "; ".join(f"{k}={text(v)}" for k, v in value.items() if text(v))
    return str(value)


def slug(value: Any) -> str:
    return re.sub(r"[^A-Z0-9]+", "", str(value or "").upper())


def safe_float(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        result = float(value)
        return result if math.isfinite(result) else None
    except (TypeError, ValueError):
        return None


def compact_join(values: Iterable[Any], sep: str = " + ") -> str:
    result: list[str] = []
    for value in values:
        rendered = text(value).strip()
        if rendered and rendered not in result:
            result.append(rendered)
    return sep.join(result)


def material_code(spec: dict[str, Any]) -> str:
    # Only drawing/source code belongs in the user-facing code column.
    # Internal material_id is deliberately excluded.
    return text(first_value(
        spec,
        "source_material_code",
        "drawing_material_code",
        "material_code",
        "code",
    ))


def material_name(spec: dict[str, Any]) -> str:
    explicit = first_value(spec, "material_name", "material", "description")
    if explicit:
        return text(explicit)

    core = first_value(spec, "core", "material_family")
    finish = first_value(spec, "finish")
    glass = first_value(spec, "glass_type")
    decal = first_value(spec, "film_decal", "decal", "film")
    return compact_join([glass or core, finish, decal]) or "Vật liệu chưa đặt tên"


def material_thickness(spec: dict[str, Any], bom: dict[str, Any] | None) -> float | None:
    value = first_value(spec, "thickness_mm", "glass_thickness_mm")
    result = safe_float(value)
    if result is not None:
        return result
    if bom:
        return safe_float(bom.get("thickness_mm"))
    return None


def material_color(spec: dict[str, Any]) -> str:
    return text(first_value(spec, "color", "colour", "finish_color", "decal_color"))


def material_note(spec: dict[str, Any]) -> str:
    details = [
        first_value(spec, "edge_treatment"),
        first_value(spec, "adhesive_sealant", "sealant", "adhesive"),
        first_value(spec, "specification", "spec_text"),
    ]
    name = material_name(spec)
    result: list[str] = []
    for value in details:
        rendered = text(value).strip()
        if rendered and rendered != name and rendered not in result:
            result.append(rendered)
    return "; ".join(result)


def item_label(spec: dict[str, Any], items_by_id: dict[str, dict[str, Any]]) -> str:
    item_code = text(first_value(spec, "item_code", "item_id", "host_item"))
    item = items_by_id.get(item_code, {}) if item_code else {}
    item_name = text(first_value(item, "item_name", "name", "title"))
    region = text(first_value(spec, "host_region", "region", "part", "layer", "surface"))

    base = compact_join([item_code, item_name], sep=" — ")
    if region and slug(region) not in slug(base):
        return compact_join([base, region], sep=" — ")
    return base or region or "Hạng mục chưa xác định"


def item_index(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in items:
        key = text(first_value(row, "item_code", "item_id", "id", "code"))
        if key:
            result[key] = row
    return result


def bom_tokens(row: dict[str, Any]) -> set[str]:
    values = [
        row.get("material_code"), row.get("source_material_code"), row.get("material_name"),
        row.get("description"), row.get("name"),
    ]
    return {slug(v) for v in values if slug(v)}


def spec_tokens(spec: dict[str, Any]) -> set[str]:
    values = [
        spec.get("source_material_code"), spec.get("drawing_material_code"), spec.get("material_code"),
        spec.get("material_id"), spec.get("material_name"), spec.get("material_family"),
        spec.get("core"), spec.get("glass_type"),
    ]
    return {slug(v) for v in values if slug(v)}


def best_bom_match(spec: dict[str, Any], bom_rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    s_tokens = spec_tokens(spec)
    item_code = slug(first_value(spec, "item_code", "item_id", "host_item"))
    best: tuple[int, dict[str, Any]] | None = None

    for row in bom_rows:
        score = 0
        b_tokens = bom_tokens(row)
        if s_tokens & b_tokens:
            score += 100
        else:
            for s in s_tokens:
                if any((s in b or b in s) for b in b_tokens if s and b):
                    score += 25
                    break

        item_ids = {slug(v) for v in (row.get("item_ids") or []) if slug(v)}
        if item_code and item_code in item_ids:
            score += 40

        if score and (best is None or score > best[0]):
            best = (score, row)
    return best[1] if best else None


def area_m2(spec: dict[str, Any], bom: dict[str, Any] | None) -> float | None:
    for key in ("area_m2", "net_area_m2", "required_area_m2", "quantity_m2"):
        value = safe_float(spec.get(key))
        if value is not None:
            return value
    if bom:
        for key in ("required_area_m2", "net_area_m2"):
            value = safe_float(bom.get(key))
            if value is not None:
                return value
    return None


def equivalent_sheet_count(area: float | None) -> int | None:
    if area is None or area <= 0:
        return None
    return int(math.ceil(area / SHEET_AREA_M2))


def normalize_path(project_root: Path, value: Any) -> Path | None:
    if not value:
        return None
    path = Path(str(value))
    if not path.is_absolute():
        path = project_root / path
    try:
        path = path.resolve()
    except Exception:
        return None
    return path if path.is_file() else None


def material_sample_image(project_root: Path, spec: dict[str, Any]) -> Path | None:
    for key in (
        "sample_image", "sample_image_path", "legend_sample_image", "swatch_image",
        "material_sample_image", "color_sample_image",
    ):
        path = normalize_path(project_root, spec.get(key))
        if path:
            return path

    sample_root = project_root / "OUTPUT" / "IMAGES" / "MATERIALS"
    if not sample_root.is_dir():
        return None

    tokens = [
        slug(material_code(spec)), slug(spec.get("material_id")), slug(spec.get("material_name")),
        slug(spec.get("material_family")), slug(spec.get("core")),
    ]
    tokens = [t for t in tokens if t]
    if not tokens:
        return None

    candidates: list[Path] = []
    for path in sample_root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {".png", ".jpg", ".jpeg"}:
            continue
        stem = slug(path.stem)
        if any(token in stem or stem in token for token in tokens):
            candidates.append(path)
    return sorted(candidates, key=lambda p: (len(p.name), str(p)))[0] if candidates else None


def valid_hex_color(value: Any) -> str | None:
    raw = str(value or "").strip().lstrip("#")
    if re.fullmatch(r"[0-9A-Fa-f]{6}", raw):
        return raw.upper()
    return None


def add_image(ws, path: Path, anchor: str, max_width: int = 120, max_height: int = 52) -> bool:
    try:
        image = XLImage(str(path))
        width = float(image.width or max_width)
        height = float(image.height or max_height)
        scale = min(max_width / width, max_height / height, 1.0)
        image.width = int(width * scale)
        image.height = int(height * scale)
        ws.add_image(image, anchor)
        return True
    except Exception:
        return False


def style_title(ws, title: str, subtitle: str, end_col: int) -> None:
    end_letter = get_column_letter(end_col)
    ws.merge_cells(f"A1:{end_letter}1")
    ws["A1"] = title
    ws["A1"].fill = TITLE_FILL
    ws["A1"].font = TITLE_FONT
    ws["A1"].alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 28

    ws.merge_cells(f"A2:{end_letter}2")
    ws["A2"] = subtitle
    ws["A2"].fill = NOTE_FILL
    ws["A2"].alignment = Alignment(vertical="center", wrap_text=True)
    ws.row_dimensions[2].height = 24


def write_header(ws, headers: list[str], row: int = 4) -> None:
    for col, header in enumerate(headers, start=1):
        cell = ws.cell(row, col, header)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = TABLE_BORDER
    ws.row_dimensions[row].height = 34
    ws.freeze_panes = f"A{row + 1}"


def material_display_rows(
    project_root: Path,
    specs: list[dict[str, Any]],
    items: list[dict[str, Any]],
    bom_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    items_by_id = item_index(items)
    rows: list[dict[str, Any]] = []

    for spec in specs:
        bom = best_bom_match(spec, bom_rows)
        area = area_m2(spec, bom)
        rows.append({
            "item_label": item_label(spec, items_by_id),
            "material_code": material_code(spec),
            "material_name": material_name(spec),
            "thickness_mm": material_thickness(spec, bom),
            "color": material_color(spec),
            "color_hex": valid_hex_color(first_value(spec, "color_hex", "colour_hex", "sample_color_hex")),
            "sample_image": material_sample_image(project_root, spec),
            "area_m2": area,
            "sheet_count": equivalent_sheet_count(area),
            "note": material_note(spec),
            "price_key": material_code(spec) or text(first_value(spec, "material_name", "material_family", "core", "glass_type")),
        })

    if not rows:
        for bom in bom_rows:
            area = safe_float(first_value(bom, "required_area_m2", "net_area_m2"))
            rows.append({
                "item_label": text(bom.get("item_ids")),
                "material_code": text(first_value(bom, "source_material_code", "material_code")),
                "material_name": text(first_value(bom, "material_name", "description", "material_code")) or "Vật liệu chưa đặt tên",
                "thickness_mm": safe_float(bom.get("thickness_mm")),
                "color": "",
                "color_hex": None,
                "sample_image": None,
                "area_m2": area,
                "sheet_count": equivalent_sheet_count(area),
                "note": "",
                "price_key": text(first_value(bom, "material_code", "material_name")),
            })
    return rows


def build_material_workbook(project_root: Path, project_name: str, rows: list[dict[str, Any]], output_path: Path) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "VAT_LIEU"

    headers = [
        "STT", "Hạng mục / Chi tiết", "Mã VL", "Vật liệu / Quy cách", "Dày (mm)",
        "Màu / Mẫu", "Khối lượng (m²)", "Tấm 1200×2400", "Ghi chú",
    ]
    style_title(
        ws,
        "AI-dg — TỔNG HỢP VẬT LIỆU",
        f"{project_name}  |  Quy đổi 1 tấm 1200×2400 = {SHEET_AREA_M2:.2f} m². Đây là quy đổi diện tích, không phải tối ưu cắt/nesting.",
        len(headers),
    )
    write_header(ws, headers, row=4)

    widths = {"A": 7, "B": 31, "C": 16, "D": 34, "E": 11, "F": 20, "G": 16, "H": 19, "I": 48}
    for col, width in widths.items():
        ws.column_dimensions[col].width = width

    if not rows:
        rows = [{
            "item_label": "", "material_code": "", "material_name": "CHƯA CÓ DỮ LIỆU VẬT LIỆU",
            "thickness_mm": None, "color": "", "color_hex": None, "sample_image": None,
            "area_m2": None, "sheet_count": None, "note": "Kiểm tra material-specifications.json / bom.json",
        }]

    for index, row in enumerate(rows, start=5):
        values = [
            index - 4,
            row.get("item_label") or "",
            row.get("material_code") or "",
            row.get("material_name") or "",
            row.get("thickness_mm") if row.get("thickness_mm") is not None else "—",
            row.get("color") or "",
            row.get("area_m2"),
            row.get("sheet_count"),
            row.get("note") or "",
        ]
        for col, value in enumerate(values, start=1):
            cell = ws.cell(index, col, value)
            cell.alignment = Alignment(vertical="top", wrap_text=True)
            cell.border = TABLE_BORDER
        ws.cell(index, 1).alignment = Alignment(horizontal="center", vertical="center")
        for col in (5, 7, 8):
            ws.cell(index, col).alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        ws.cell(index, 7).number_format = "0.00"
        ws.cell(index, 8).number_format = "0"
        ws.row_dimensions[index].height = 44

        sample = row.get("sample_image")
        if isinstance(sample, Path) and add_image(ws, sample, f"F{index}"):
            ws.row_dimensions[index].height = 52
        elif row.get("color_hex"):
            ws.cell(index, 6).fill = PatternFill("solid", fgColor=row["color_hex"])

    last_row = 4 + len(rows)
    ws.auto_filter.ref = f"A4:I{last_row}"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(output_path)


def supplier_price_map(suppliers: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in suppliers:
        key = slug(first_value(row, "material_code", "material", "material_name"))
        price = safe_float(first_value(row, "unit_price_vnd", "unit_price", "price"))
        if not key or price is None:
            continue
        status = str(first_value(row, "verification_status", "status") or "").upper()
        current = result.get(key)
        if current is None or status in {"VERIFIED", "CONFIRMED", "READY"}:
            result[key] = row
    return result


def price_for_row(row: dict[str, Any], price_map: dict[str, dict[str, Any]]) -> tuple[float | None, str]:
    key = slug(row.get("price_key"))
    source = price_map.get(key, {}) if key else {}
    if not source:
        for candidate_key, candidate in price_map.items():
            if key and (key in candidate_key or candidate_key in key):
                source = candidate
                break
    price = safe_float(first_value(source, "unit_price_vnd", "unit_price", "price")) if source else None
    unit = text(source.get("unit")) if source else ""
    return price, unit


def build_quote_workbook(project_name: str, rows: list[dict[str, Any]], suppliers: list[dict[str, Any]], output_path: Path) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "BAO_GIA"

    headers = [
        "STT", "Hạng mục / Chi tiết", "Mã VL", "Vật liệu / Quy cách", "Dày (mm)",
        "Màu / Mẫu", "KL (m²)", "Tấm 1200×2400", "ĐVT", "Đơn giá", "Thành tiền",
    ]
    style_title(
        ws,
        "AI-dg — BẢNG BÁO GIÁ VẬT LIỆU",
        f"{project_name}  |  Đơn giá để trống nếu chưa có nguồn giá xác minh.",
        len(headers),
    )
    write_header(ws, headers, row=4)

    widths = {"A": 7, "B": 30, "C": 15, "D": 34, "E": 11, "F": 20, "G": 13, "H": 18, "I": 11, "J": 16, "K": 18}
    for col, width in widths.items():
        ws.column_dimensions[col].width = width

    price_map = supplier_price_map(suppliers)
    if not rows:
        rows = [{
            "item_label": "", "material_code": "", "material_name": "CHƯA CÓ DỮ LIỆU VẬT LIỆU",
            "thickness_mm": None, "color": "", "color_hex": None, "sample_image": None,
            "area_m2": None, "sheet_count": None, "note": "", "price_key": "",
        }]

    for index, row in enumerate(rows, start=5):
        price, price_unit = price_for_row(row, price_map)
        unit = price_unit or "m²"
        quantity_ref = f"H{index}" if "TẤM" in unit.upper() or "SHEET" in unit.upper() else f"G{index}"
        values = [
            index - 4,
            row.get("item_label") or "",
            row.get("material_code") or "",
            row.get("material_name") or "",
            row.get("thickness_mm") if row.get("thickness_mm") is not None else "—",
            row.get("color") or "",
            row.get("area_m2"),
            row.get("sheet_count"),
            unit,
            price,
            None,
        ]
        for col, value in enumerate(values, start=1):
            cell = ws.cell(index, col, value)
            cell.alignment = Alignment(vertical="top", wrap_text=True)
            cell.border = TABLE_BORDER
        ws.cell(index, 11, f'=IF(OR({quantity_ref}="",J{index}=""),"",{quantity_ref}*J{index})')
        ws.cell(index, 7).number_format = "0.00"
        ws.cell(index, 8).number_format = "0"
        ws.cell(index, 10).number_format = "#,##0"
        ws.cell(index, 11).number_format = "#,##0"
        ws.row_dimensions[index].height = 44

        sample = row.get("sample_image")
        if isinstance(sample, Path) and add_image(ws, sample, f"F{index}"):
            ws.row_dimensions[index].height = 52
        elif row.get("color_hex"):
            ws.cell(index, 6).fill = PatternFill("solid", fgColor=row["color_hex"])

    last_data_row = 4 + len(rows)
    total_row = last_data_row + 2
    ws.cell(total_row, 9, "TỔNG VẬT LIỆU").font = BOLD_FONT
    ws.cell(total_row, 11, f"=SUM(K5:K{last_data_row})")
    ws.cell(total_row, 11).font = BOLD_FONT
    ws.cell(total_row, 11).number_format = "#,##0"
    ws.cell(total_row, 9).fill = NOTE_FILL
    ws.cell(total_row, 10).fill = NOTE_FILL
    ws.cell(total_row, 11).fill = NOTE_FILL

    ws.auto_filter.ref = f"A4:K{last_data_row}"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(output_path)


def main() -> int:
    args = parse_args()
    root = args.project_root.expanduser().resolve()
    marker = root / "project.ai-dg.json"
    if not marker.is_file():
        raise SystemExit(f"AI-dg project marker not found: {marker}")

    meta = load_json(marker, {})
    if not isinstance(meta, dict):
        meta = {}
    project_name = str(meta.get("project_name") or root.name)

    takeoff = root / "OUTPUT" / "TAKEOFF"
    excel_root = root / "OUTPUT" / "EXCEL"

    items = payload_rows(load_json(takeoff / "items.json", {}), ["items", "rows"])
    specs = payload_rows(
        load_json(takeoff / "material-specifications.json", {}),
        ["materials", "material_specifications", "rows"],
    )
    bom_rows = payload_rows(load_json(takeoff / "bom.json", {}), ["bom", "materials", "rows"])
    suppliers = payload_rows(load_json(takeoff / "suppliers.json", {}), ["suppliers", "rows"])

    display_rows = material_display_rows(root, specs, items, bom_rows)

    material_path = excel_root / "AI-dg_Tong-hop-vat-lieu.xlsx"
    quote_path = excel_root / "AI-dg_Bao-gia.xlsx"
    build_material_workbook(root, project_name, display_rows, material_path)
    build_quote_workbook(project_name, display_rows, suppliers, quote_path)

    print(f"Material workbook: {material_path}")
    print(f"Quotation workbook: {quote_path}")
    print(f"Material rows: {len(display_rows)}")
    print("User-facing Excel intentionally excludes Ruby/readiness/source/debug columns.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
