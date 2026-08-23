---
name: ai-dg-estimator
description: Analyze interior/CNC drawing packages from a filesystem project INPUT workspace, reconcile PDF with CAD and optional SketchUp, reconstruct evidence-backed 3D geometry from linked orthographic views, synthesize complete material specifications from legends/notes/details, perform traceable quantity takeoff, generate standalone SketchUp Ruby for every modelable item, and produce material-summary and quotation Excel deliverables without inventing missing dimensions, quantities, prices, suppliers or source references.
license: MIT
compatibility: Agent Skills / ChatGPT / Codex / OpenCode
metadata:
  version: "0.3.2-alpha"
  stage: "material-spec-synthesis-ruby-excel"
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
SketchUp model/preview images when Ruby is executed
          ↓
Material-summary Excel + quotation Excel
          ↓
Material Excel enrichment from drawing specifications
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
→ core/material = MDF
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

Do not drop these facts because BOM quantity is incomplete.

## Mandatory local project outputs

Write current-run analysis/takeoff artifacts as evidence permits, including:

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

## Excel gate

Every project run must attempt to create:

```text
OUTPUT/EXCEL/AI-dg_Tong-hop-vat-lieu.xlsx
OUTPUT/EXCEL/AI-dg_Bao-gia.xlsx
```

Run the project Excel exporter, then run:

```text
scripts/workspace/enrich_material_excel.py <project-root>
```

The material workbook must include:

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

`THONG_SO_VAT_LIEU` must expose drawing-backed properties such as material/core, finish, color, thickness, glass type, decal/film, edge treatment, adhesive/sealant, status and source.

Missing price/supplier data remains blank or explicitly `CHUA_CO_DON_GIA` / `SUPPLIER_NOT_VERIFIED`. Never invent commercial data.

## Completion rule

A local run is incomplete if:

- a modelable item has no Ruby;
- material legends/details exist but `material-specifications.json` is missing;
- known material specification facts disappear from Excel;
- `THONG_SO_VAT_LIEU` is missing from the material workbook;
- mandatory Excel deliverables were not attempted;
- old WORK/OUTPUT was reused;
- a model/image/supplier/price is claimed without actual creation or verification.

Partial BOM or partial geometry is allowed. Fabricated certainty is not.
