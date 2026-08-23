# AI-dg

AI-dg is a portable Agent Skill for interior/joinery/CNC drawing understanding, PDF↔CAD↔SketchUp reconciliation, orthographic 3D reconstruction, material mapping, quantity takeoff, Excel export and standalone SketchUp Ruby prototyping.

## Current stage

**V0.3.0-alpha — workspace I/O + Ruby prototype**

The main local/Codex workflow is now filesystem-first:

```text
Project INPUT/
  PDF + CAD + optional SKP/specs
          ↓
input-manifest.json
          ↓
Geometry-first analysis
          ↓
PDF/CAD/SKP reconciliation
          ↓
readiness gates
          ↓
Project OUTPUT/
  Ruby + Takeoff + Excel + Reports + Model
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
├─ OUTPUT/
│  ├─ RUBY/
│  ├─ TAKEOFF/
│  ├─ EXCEL/
│  ├─ REPORTS/
│  └─ MODEL/
└─ project.ai-dg.json
```

Initialize:

```powershell
python "$env:USERPROFILE\.agents\skills\ai-dg-estimator\scripts\workspace\init_project.py" "D:\AI-dg\MyProject" --name "My Project"
```

Then copy project files into `INPUT/` and tell Codex:

```text
Dùng skill ai-dg-estimator phân tích project tại D:\AI-dg\MyProject.
Đọc toàn bộ INPUT và ghi kết quả vào OUTPUT. Không yêu cầu upload lại file vào chat.
```

AI-dg scans the source package into:

```text
WORK/manifests/input-manifest.json
```

and finalizes generated artifacts in:

```text
OUTPUT/output-manifest.json
```

## Expected outputs

```text
OUTPUT/RUBY/*.rb
OUTPUT/TAKEOFF/items.json
OUTPUT/TAKEOFF/material-regions.json
OUTPUT/TAKEOFF/bom.json
OUTPUT/TAKEOFF/review-queue.json
OUTPUT/EXCEL/AI-dg-estimate.xlsx
OUTPUT/REPORTS/analysis.md
OUTPUT/REPORTS/drawing-index.md
OUTPUT/REPORTS/geometry-ledger.md
OUTPUT/REPORTS/source-reconciliation.md
OUTPUT/REPORTS/readiness.md
OUTPUT/MODEL/*.skp        # only when actually generated
```

Partial outputs are valid. For example, a component can be ready for a review-tagged Ruby prototype while project placement or fabrication BOM remains blocked.

## Geometry-first rule

AI-dg must link plan/elevation/side/section/detail as projections of the same object, reconstruct local X/Y/Z geometry, map materials spatially and perform projection-back checks before detailed takeoff.

Example:

```text
Elevation: 800 + 300 = 1100
Section:   750 + 50 + 300 = 1100
```

If `750 + 50` subdivides the same lower `800` region, the relationship is `DIMENSION_REFINEMENT`, not a mismatch.

## Ruby prototype

Current standalone SketchUp test:

```text
.agents/skills/ai-dg-estimator/scripts/sketchup/vn1_prototype.rb
```

See [`RUBY_PROTOTYPE.md`](RUBY_PROTOTYPE.md).

## ChatGPT Work package

GitHub Actions builds:

```text
AI-dg-Work-v0.3.0-alpha.zip
```

See [`CHATGPT_WORK.md`](CHATGPT_WORK.md).

## Runtime extras

The skill core remains dependency-light. For deterministic PDF parsing, JSON Schema validation and Excel generation in local/Codex environments:

```bash
python -m pip install -e ".[runtime]"
```

Optional extras: PyMuPDF, openpyxl and jsonschema.

## Accuracy rules

- Never invent dimensions, materials, quantities, coordinates or source references.
- Never modify source files under `INPUT/`.
- Reconcile PDF/CAD/SKP rather than silently preferring one source.
- Compare dimensions by geometric span, not raw number.
- Never count the same physical item multiple times because it appears in multiple views.
- Never claim CAD/SKP/model outputs were parsed or generated when they were not.
