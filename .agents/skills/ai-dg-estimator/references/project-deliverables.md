# AI-dg Mandatory Project Deliverables

This contract applies to Codex/OpenCode/local project runs using an AI-dg workspace.

The goal is to prevent a run from stopping at analysis text while omitting the practical files the user needs.

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

The Ruby file must reconstruct the local component at a local origin from the current Geometry Ledger.

If unresolved geometry is still useful for visual testing it may be modeled only as:

```text
REVIEW_REQUIRED
PLACEHOLDER_GUIDE
```

and must retain source/readiness metadata.

If Component Geometry is `BLOCKED`, create no fake solid. Record the reason in Review Queue and readiness output.

## 3. Projection-back requirement for Ruby

Before the run is considered geometrically successful, the Ruby geometry must be designed to reproduce the linked source views:

- front/elevation;
- side;
- plan when available;
- section;
- detail.

A hidden section refinement must not automatically become a visible front seam.

For example, if a 50 mm section dimension is the embed depth of glass inside a slot, Ruby must model a hidden slot/embed relationship rather than a visible 50 mm front band.

## 4. Ruby should export model preview images

Project Ruby files should include a preview-export block when practical.

When the script resides in:

```text
<PROJECT>/OUTPUT/RUBY/<item>.rb
```

it should write preview images to:

```text
<PROJECT>/OUTPUT/IMAGES/<item>_iso.png
<PROJECT>/OUTPUT/IMAGES/<item>_front.png
<PROJECT>/OUTPUT/IMAGES/<item>_side.png
```

The images are for projection checking and Excel summaries. They are not fabrication evidence by themselves.

If SketchUp was not actually executed, report:

```text
RUBY_READY_NOT_EXECUTED
```

and do not claim the images/model were created.

## 5. Mandatory material specification synthesis

Before Excel export, AI-dg must synthesize technical/descriptive material properties from all linked drawing evidence, not only from BOM rows.

Read and apply:

```text
references/material-specification-synthesis.md
```

Mandatory output:

```text
OUTPUT/TAKEOFF/material-specifications.json
```

This file must reconcile, when available:

- material legend / note table;
- leader notes;
- sections;
- details;
- schedules/specifications;
- verified CAD/SKP metadata.

Known specification facts must survive even when quantity or thickness is incomplete.

For example, if the drawing gives:

```text
MDF HOÀN THIỆN MELAMINE MÀU GHI SÁNG
```

then the material record must keep:

```text
core/material = MDF
finish = Melamine
color = ghi sáng
thickness = UNKNOWN unless separately proven
```

If a glass detail gives:

```text
KÍNH CƯỜNG LỰC DÀY 10MM
MÀI XIẾT CẠNH 1MM
DÁN DECAL MỜ MÀU XANH NDTH
KEO SILICONE
```

all those facts must be preserved in `material-specifications.json` and exposed in Excel.

Do not reduce a rich drawing specification to generic `MDF` / `GLASS` labels.

## 6. Mandatory Excel deliverables

Every project run must attempt to create both:

```text
OUTPUT/EXCEL/AI-dg_Tong-hop-vat-lieu.xlsx
OUTPUT/EXCEL/AI-dg_Bao-gia.xlsx
```

First run:

```text
scripts/workspace/export_project_excel.py <project-root>
```

Then enrich the material workbook using:

```text
scripts/workspace/enrich_material_excel.py <project-root>
```

The enrichment step reads:

```text
OUTPUT/TAKEOFF/material-specifications.json
```

and must create/update:

```text
THONG_SO_VAT_LIEU
```

inside `AI-dg_Tong-hop-vat-lieu.xlsx`, while also adding synthesized drawing specifications to the existing `VAT_LIEU` sheet where a safe material match is possible.

The workbooks must still be created when some downstream data is partial.

Missing information is represented by explicit blank/status/UNKNOWN cells, not invented values.

### Material workbook

Required sheets:

```text
TONG_QUAN
HANG_MUC
VAT_LIEU
CHI_TIET_VAT_LIEU
THONG_SO_VAT_LIEU
NHA_CUNG_CAP
REVIEW
SOURCE
```

`THONG_SO_VAT_LIEU` must expose drawing-backed properties such as:

```text
Hạng mục
Material ID
Vật liệu / hệ vật liệu
Vai trò
Region / Part / Layer
Core
Finish
Color
Thickness
Glass type
Decal / film
Edge treatment
Adhesive / sealant
Synthesized specification
Status
Source
```

`HANG_MUC` should embed the SketchUp preview image when `OUTPUT/IMAGES` contains a matching item image. If no image exists yet, the workbook must say that Ruby needs to be run/exported; it must not invent a picture.

### Quotation workbook

Required sheets:

```text
BAO_GIA
DON_GIA_NGUON
REVIEW
```

Never invent prices. If no verified price exists, leave unit price blank and set status such as:

```text
CHUA_CO_DON_GIA
SUPPLIER_NOT_VERIFIED
```

The workbook may contain formulas for totals but only over real supplied/verified quantity and price cells.

## 7. Supplier data

When web access or a user supplier library is available, create:

```text
OUTPUT/TAKEOFF/suppliers.json
```

Each supplier record should retain:

```text
material_code / material_name
supplier_name
brand
product_code
spec
unit_price_vnd (when verified)
unit
area/location
website
checked_date
source_url
verification_status
```

If no supplier research was actually performed, keep `SUPPLIER_NOT_VERIFIED` rather than fabricating companies or prices.

## 8. Recommended run order

```text
prepare_run
→ inspect fresh input manifest
→ read/reconcile sources
→ Drawing Index / View Link Graph
→ Geometry Ledger
→ Material Spatial Map
→ Material Specification Synthesis
→ write material-specifications.json
→ Readiness Matrix
→ write TAKEOFF JSON
→ generate Ruby for every READY/PARTIAL_READY component
→ run/test Ruby in SketchUp when execution is available
→ export preview images when Ruby runs
→ export both Excel workbooks
→ enrich material Excel from material-specifications.json
→ write reports
→ finalize_output
```

## 9. Completion gate

A normal local project run is not considered complete if:

- a modelable item has no `OUTPUT/RUBY/*.rb`;
- `material-specifications.json` is missing when material legends/notes/details are present;
- known legend/detail material properties disappear from Excel;
- `THONG_SO_VAT_LIEU` is missing from the material workbook;
- neither Excel workbook was attempted;
- old OUTPUT from a previous run was reused;
- a price/supplier/image/model is claimed but was not actually created or verified.

Partial geometry/BOM is acceptable. Missing mandatory deliverable attempts are not.
