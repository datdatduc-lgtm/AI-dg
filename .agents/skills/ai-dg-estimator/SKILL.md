---
name: ai-dg-estimator
description: Analyze interior/CNC drawing packages from a filesystem project INPUT workspace, reconcile PDF with CAD and optional SketchUp, reconstruct evidence-backed 3D geometry from linked orthographic views, synthesize material specifications from legends/notes/details, perform traceable quantity takeoff, generate standalone SketchUp Ruby for modelable items, and export concise material-summary and quotation Excel files without inventing missing dimensions, quantities, prices, material codes or suppliers.
license: MIT
compatibility: Agent Skills / ChatGPT / Codex / OpenCode
metadata:
  version: "0.3.3-alpha"
  stage: "concise-excel-material-swatch"
---

# AI-dg Estimator

AI-dg is a geometry-first drawing-analysis, reconstruction, material-interpretation and quantity-takeoff skill for interior, furniture, joinery and CNC work.

## Core pipeline

```text
Project INPUT/
  PDF + CAD (+ optional SKP/specs)
          ↓
MANDATORY fresh-run reset
          ↓
Input manifest
          ↓
Drawing reconciliation + view linking
          ↓
Orthographic 3D reconstruction
          ↓
Geometry Ledger
          ↓
Material Spatial Map
          ↓
Material Specification Synthesis
  legend + leader note + section + detail + schedule
          ↓
TAKEOFF JSON
          ↓
Ruby for every READY/PARTIAL_READY component
          ↓
Concise material Excel + concise quotation Excel
          ↓
Reports + output manifest
```

## Workspace contract

When filesystem access is available, use the current project workspace and do not require the user to upload local project files into chat.

```text
PROJECT/
├─ INPUT/
├─ WORK/
├─ OUTPUT/
│  ├─ RUBY/
│  ├─ IMAGES/
│  ├─ TAKEOFF/
│  ├─ EXCEL/
│  ├─ REPORTS/
│  └─ MODEL/
└─ project.ai-dg.json
```

Every deployment/re-analysis must begin with `scripts/workspace/prepare_run.py` so INPUT is preserved while old WORK/OUTPUT are deleted and regenerated from the current INPUT package.

Cross-run output merging is forbidden.

## Required reading order

For a full local project run, read and apply:

1. `references/workspace-io.md`
2. `references/drawing-reading-method.md`
3. `references/orthographic-reconstruction.md`
4. `references/pdf-cad-reconciliation.md`
5. `references/material-rules.md`
6. `references/material-specification-synthesis.md`
7. `references/sketchup-ruby-prototype.md`
8. `references/project-deliverables.md`
9. `references/chatgpt-test-protocol.md` when testing methodology

## Non-negotiable geometry rules

- Never invent dimensions, quantities, material codes, thicknesses, coordinates, rotations, prices, revisions or source references.
- Do not read plan/elevation/side/section/detail as independent lists. Reconstruct one physical object whose projections explain the linked views.
- Compare dimensions by axis and geometric span, not raw numeric value.
- A section refinement is not automatically a visible elevation split. Determine whether it represents a region, slot, embed depth, recess, offset or hidden construction.
- Geometric inference is allowed only when constrained by linked views and must be marked `DERIVED_FROM_VIEWS`.
- Missing CAD/plan does not automatically block a local component reconstruction.
- Project placement, project quantity, component geometry and fabrication readiness are separate states.
- If a binary CAD/SKP source cannot be parsed, report `adapter_unavailable`; never pretend it was inspected structurally.

## Material specification gate

Material understanding is not complete when AI-dg outputs only generic families such as `MDF` or `GLASS` while the drawing contains richer notes.

For every material/layer, reconcile all applicable facts from:

```text
material legend
+ leader notes
+ elevation/plan
+ sections
+ details
+ schedules/specifications
+ verified CAD/SKP metadata when available
```

Mandatory current-run output:

```text
OUTPUT/TAKEOFF/material-specifications.json
```

Known properties must be preserved even when thickness or quantity is unknown.

Example:

```text
MDF HOÀN THIỆN MELAMINE MÀU GHI SÁNG
→ material/core = MDF
→ finish = Melamine
→ color = ghi sáng
→ thickness = UNKNOWN unless separately proven
```

Example:

```text
KÍNH CƯỜNG LỰC DÀY 10MM
MÀI XIẾT CẠNH 1MM
DÁN DECAL MỜ MÀU XANH NDTH
KEO SILICONE
→ glass_type = kính cường lực
→ thickness_mm = 10
→ film_decal = decal mờ màu xanh NDTH
→ edge_treatment = mài xiết cạnh 1 mm
→ adhesive_sealant = silicone
```

If the PDF legend contains an actual color/material swatch and the runtime can crop it reliably, save the real crop under:

```text
OUTPUT/IMAGES/MATERIALS/<material-id-or-code>.png
```

and record its path in `material-specifications.json` as `sample_image` or `sample_image_path`. Do not create a fake swatch.

## Mandatory analysis/takeoff outputs

Write current-run artifacts as evidence permits, including:

```text
WORK/geometry/drawing-index.json
WORK/geometry/view-link-graph.json
WORK/geometry/geometry-ledger.json
WORK/reconciliation/source-reconciliation.json
WORK/reconciliation/review-queue.json

OUTPUT/TAKEOFF/items.json
OUTPUT/TAKEOFF/material-regions.json
OUTPUT/TAKEOFF/material-specifications.json
OUTPUT/TAKEOFF/bom.json
OUTPUT/TAKEOFF/review-queue.json
```

For every item with `Component Geometry = READY` or `PARTIAL_READY`, create:

```text
OUTPUT/RUBY/<item-code>.rb
```

Ruby must reconstruct local geometry from the Geometry Ledger and mark unresolved hypotheses `REVIEW_REQUIRED` or `PLACEHOLDER_GUIDE`.

## User-facing Excel gate

Every project run must attempt to create:

```text
OUTPUT/EXCEL/AI-dg_Tong-hop-vat-lieu.xlsx
OUTPUT/EXCEL/AI-dg_Bao-gia.xlsx
```

using:

```text
scripts/workspace/export_project_excel.py <project-root>
```

### Excel is not a debug report

Do **not** expose internal AI-dg engineering fields in the primary user-facing Excel tables unless the user explicitly asks for a technical/audit workbook.

Keep these out of the normal material/quotation sheets:

```text
Ruby paths
Readiness states
DERIVED_FROM_VIEWS / EXPLICIT labels
Geometry role IDs
Region IDs used only by AI
long source/evidence strings
internal AI_DG metadata
Review Queue internals
```

Those belong in JSON under WORK/OUTPUT or technical reports.

### Material workbook

The normal material workbook should be concise and use a single primary sheet:

```text
VAT_LIEU
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

- `Mã VL` is the code actually present in the drawing/spec; leave blank when the drawing has no material code. Do not expose internal `material_id` as though it were a drawing code.
- `Vật liệu / Quy cách` must preserve useful drawing descriptions such as `MDF hoàn thiện Melamine` or `Kính cường lực + decal mờ`.
- `Dày` is shown only when proven; otherwise use a clean blank/dash rather than inventing a value.
- `Màu / Mẫu` should show the drawing color text and, when an actual extracted legend/material sample exists, embed that real sample image.
- `Khối lượng (m²)` comes from current takeoff/BOM evidence.
- `Tấm 1200×2400` is `ceil(area_m2 / 2.88)` and is clearly an area-equivalent conversion, not nesting optimization or guaranteed purchasing format.
- `Ghi chú` should contain only concise fabrication-relevant details such as edge treatment or silicone; do not dump technical provenance into the cell.

### Quotation workbook

The normal quotation workbook should use one primary sheet:

```text
BAO_GIA
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

Never invent prices. Unit price stays blank unless a verified source exists. The main quotation sheet should not be cluttered with supplier URLs, verification status, source text or review/debug columns.

Supplier/source detail may remain in `OUTPUT/TAKEOFF/suppliers.json` or a separate report when needed.

### Backward compatibility

`scripts/workspace/enrich_material_excel.py` remains only as a compatibility no-op. The exporter reads `material-specifications.json` directly. Do not add a separate `THONG_SO_VAT_LIEU` sheet in the normal user-facing workbook.

## Completion rule

A local run is incomplete if:

- a modelable item has no Ruby;
- material legends/details exist but `material-specifications.json` is missing;
- known drawing-backed material description/color/thickness facts disappear from the concise material table;
- mandatory Excel deliverables were not attempted;
- old WORK/OUTPUT was reused;
- a model/image/supplier/price is claimed without actual creation or verification.

Partial BOM or partial geometry is allowed. Fabricated certainty is not.
