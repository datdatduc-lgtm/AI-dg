# AI-dg Mandatory Project Deliverables

This contract applies to Codex/OpenCode/local project runs using an AI-dg workspace.

The goal is to prevent a run from stopping at analysis text while omitting the practical files the user needs, while also preventing user-facing deliverables from being polluted with AI/debug metadata.

## 1. Mandatory fresh-run start

Before every deployment/re-analysis run:

```text
prepare_run.py <project-root>
```

This preserves `INPUT/` and `project.ai-dg.json`, deletes prior generated `WORK/` and `OUTPUT/`, recreates them, and scans the current INPUT package.

Never merge artifacts from a previous run into a new run.

## 2. Mandatory Ruby output for modelable items

For every item whose `Component Geometry Readiness` is either:

```text
READY
PARTIAL_READY
```

AI-dg must write a standalone SketchUp Ruby file:

```text
OUTPUT/RUBY/<item-code>.rb
```

Do not make Ruby generation optional merely because project placement, project quantity, fabrication BOM or procurement BOM is blocked.

The Ruby file must reconstruct the local component at a local origin from the current Geometry Ledger. Unresolved geometry may be modeled only as `REVIEW_REQUIRED` or `PLACEHOLDER_GUIDE` and must retain source/readiness metadata inside the model/script rather than the normal material Excel.

## 3. Projection-back requirement for Ruby

Ruby geometry must be designed to reproduce linked source views:

- front/elevation;
- side;
- plan when available;
- section;
- detail.

A hidden section refinement must not automatically become a visible front seam.

If SketchUp was not actually executed, report `RUBY_READY_NOT_EXECUTED` and do not claim a `.skp` or preview image was created.

## 4. Material specification synthesis

Before Excel export, synthesize technical/descriptive material properties from all linked drawing evidence, not only BOM rows.

Read and apply:

```text
references/material-specification-synthesis.md
```

Mandatory output:

```text
OUTPUT/TAKEOFF/material-specifications.json
```

Known specification facts must survive even when quantity or thickness is incomplete.

Example:

```text
MDF HOÀN THIỆN MELAMINE MÀU GHI SÁNG
→ material/core = MDF
→ finish = Melamine
→ color = ghi sáng
→ thickness = UNKNOWN unless separately proven
```

Example glass system:

```text
KÍNH CƯỜNG LỰC DÀY 10MM
MÀI XIẾT CẠNH 1MM
DÁN DECAL MỜ MÀU XANH NDTH
KEO SILICONE
```

All those facts must remain in `material-specifications.json`; the concise Excel should surface the useful user-facing subset without dumping provenance/debug fields.

## 5. Material swatch/sample image

When a PDF legend or note table contains a real material/color swatch and the runtime can crop it reliably, save the actual crop under:

```text
OUTPUT/IMAGES/MATERIALS/<material-id-or-code>.png
```

and record it in the material specification record as one of:

```text
sample_image
sample_image_path
legend_sample_image
swatch_image
```

Do not create a fake swatch. If no reliable sample image can be extracted, keep the drawing color text only.

## 6. Mandatory Excel deliverables

Every project run must attempt to create both:

```text
OUTPUT/EXCEL/AI-dg_Tong-hop-vat-lieu.xlsx
OUTPUT/EXCEL/AI-dg_Bao-gia.xlsx
```

Run:

```text
scripts/workspace/export_project_excel.py <project-root>
```

`scripts/workspace/enrich_material_excel.py` is retained only as a backward-compatible no-op for older automation. Do not use it to add technical sheets back into the normal workbook.

### User-facing material workbook

Normal workbook:

```text
AI-dg_Tong-hop-vat-lieu.xlsx
└─ VAT_LIEU
```

Primary columns:

```text
STT
Hạng mục / Chi tiết
Mã VL
Vật liệu / Quy cách
Dày (mm)
Màu / Mẫu
Khối lượng (m²)
Tấm 1200×2400
Ghi chú
```

Rules:

- No Ruby column.
- No readiness/status column.
- No source/evidence dump.
- No internal region ID or geometry-role column.
- `Mã VL` must be the drawing/spec code, not an AI-generated internal ID.
- `Màu / Mẫu` uses color text and may embed a real extracted legend swatch.
- `Khối lượng (m²)` must come from current takeoff evidence.
- `Tấm 1200×2400` is an area-equivalent conversion using `ceil(m² / 2.88)`; it is not nesting optimization.
- `Ghi chú` is short and fabrication-relevant only (for example edge treatment or silicone).

### User-facing quotation workbook

Normal workbook:

```text
AI-dg_Bao-gia.xlsx
└─ BAO_GIA
```

Primary columns:

```text
STT
Hạng mục / Chi tiết
Mã VL
Vật liệu / Quy cách
Dày (mm)
Màu / Mẫu
KL (m²)
Tấm 1200×2400
ĐVT
Đơn giá
Thành tiền
```

Do not clutter the main quotation sheet with supplier URLs, verification flags, source text or Review Queue data.

Never invent prices. If no verified price exists, leave `Đơn giá` blank.

Supplier/source research remains in:

```text
OUTPUT/TAKEOFF/suppliers.json
```

or a separate technical/procurement report when requested.

## 7. Recommended run order

```text
prepare_run
→ inspect fresh input manifest
→ read/reconcile sources
→ Drawing Index / View Link Graph
→ Geometry Ledger
→ Material Spatial Map
→ Material Specification Synthesis
→ optional real legend-swatch crop extraction
→ write material-specifications.json
→ Readiness Matrix
→ write TAKEOFF JSON
→ generate Ruby for every READY/PARTIAL_READY component
→ run/test Ruby in SketchUp when execution is available
→ export both concise Excel workbooks
→ write reports
→ finalize_output
```

## 8. Completion gate

A normal local project run is not considered complete if:

- a modelable item has no `OUTPUT/RUBY/*.rb`;
- `material-specifications.json` is missing when material legends/notes/details are present;
- known material code/name/thickness/color facts disappear from the user-facing material table;
- neither Excel workbook was attempted;
- old OUTPUT from a previous run was reused;
- a price/supplier/image/model is claimed but was not actually created or verified.

Partial geometry/BOM is acceptable. Missing mandatory deliverable attempts are not.
