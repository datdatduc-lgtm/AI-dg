# AI-dg

AI-dg is a portable Agent Skill for interior/joinery/CNC drawing understanding, PDF↔CAD↔SketchUp reconciliation, orthographic 3D reconstruction, material mapping, quantity takeoff, standalone SketchUp Ruby reconstruction and concise Excel material/quotation deliverables.

## Current stage

**V0.3.3-alpha — concise Excel + material swatch support**

The local/Codex workflow is filesystem-first:

```text
Project INPUT/
  PDF + CAD + optional SKP/specs
          ↓
prepare_run.py
  clears old WORK/OUTPUT, keeps INPUT
          ↓
input-manifest.json
          ↓
Geometry-first analysis
          ↓
PDF/CAD/SKP reconciliation
          ↓
Geometry Ledger + Material Spatial Map
          ↓
Material Specification Synthesis
          ↓
TAKEOFF JSON
          ↓
Ruby for every READY/PARTIAL_READY component
          ↓
2 concise Excel workbooks
          ↓
Reports + output-manifest.json
```

The GitHub `main` branch is the canonical source. The installable skill lives at:

```text
.agents/skills/ai-dg-estimator/
```

## Local project workspace

See [`WORKSPACE.md`](WORKSPACE.md).

Recommended layout:

```text
AI-dg-PROJECT/
├─ INPUT/
│  ├─ PDF/
│  ├─ CAD/
│  ├─ SKP/
│  └─ OTHER/
├─ WORK/
└─ OUTPUT/
   ├─ RUBY/
   ├─ IMAGES/
   │  └─ MATERIALS/   # optional real legend/material swatches
   ├─ TAKEOFF/
   ├─ EXCEL/
   ├─ REPORTS/
   └─ MODEL/
```

## Mandatory current-run outputs

For each modelable item:

```text
OUTPUT/RUBY/<item>.rb
```

Material synthesis:

```text
OUTPUT/TAKEOFF/material-specifications.json
```

Excel exporter:

```powershell
python "$env:USERPROFILE\.agents\skills\ai-dg-estimator\scripts\workspace\export_project_excel.py" "D:\AI-dg\MyProject"
```

creates:

```text
OUTPUT/EXCEL/AI-dg_Tong-hop-vat-lieu.xlsx
OUTPUT/EXCEL/AI-dg_Bao-gia.xlsx
```

The normal material workbook now has one concise user-facing sheet `VAT_LIEU` with:

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

Ruby paths, readiness, source/evidence dumps and internal AI metadata stay in JSON/reports rather than cluttering the user workbook.

If the PDF legend contains a real material/color swatch and the runtime can crop it reliably, AI-dg may save it to `OUTPUT/IMAGES/MATERIALS/` and embed it in the `Màu / Mẫu` cell. It must not create a fake swatch.

The 1200×2400 column is an area-equivalent conversion (`ceil(m² / 2.88)`), not nesting optimization.

## Fresh-run rule

Every new deployment must begin with:

```powershell
python "$env:USERPROFILE\.agents\skills\ai-dg-estimator\scripts\workspace\prepare_run.py" "D:\AI-dg\MyProject"
```

This preserves `INPUT/`, deletes prior generated `WORK/` and `OUTPUT/`, recreates them and rescans the current source package. Cross-run merging is forbidden.

## Geometry-first rule

AI-dg links plan/elevation/side/section/detail as projections of the same physical item. It reconstructs local X/Y/Z geometry, maps materials spatially and performs projection-back checks before detailed takeoff or Ruby generation.

A section refinement is not automatically a visible subdivision. For VN-1, the corrected interpretation treats `750 + 50 = 800` as a hidden 50 mm glass embed/slot within the 800 mm lower body rather than a visible horizontal band.

## Ruby test

Current standalone VN-1 test:

```text
.agents/skills/ai-dg-estimator/scripts/sketchup/vn1_prototype.rb
```

See [`RUBY_PROTOTYPE.md`](RUBY_PROTOTYPE.md).

## ChatGPT Work package

GitHub Actions builds:

```text
AI-dg-Work-v0.3.3-alpha.zip
```

See [`CHATGPT_WORK.md`](CHATGPT_WORK.md).

## Runtime extras

For deterministic PDF, Excel with embedded images and full schema validation in local/Codex environments:

```bash
python -m pip install -e ".[runtime]"
```

Optional extras include PyMuPDF, openpyxl, Pillow and jsonschema.

## Accuracy rules

- Never invent dimensions, materials, quantities, coordinates, suppliers, prices or source references.
- Never modify source files under `INPUT/`.
- Reconcile PDF/CAD/SKP rather than silently preferring one source.
- Compare dimensions by geometric span, not raw number.
- Never count the same physical item multiple times because it appears in multiple views.
- Never claim CAD/SKP/model/image/Excel output was parsed or generated when it was not.
