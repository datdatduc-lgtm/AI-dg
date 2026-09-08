# AI-dg

AI-dg is a portable Agent Skill for interior/joinery/CNC drawing understanding, PDF↔CAD↔SketchUp reconciliation, orthographic 3D reconstruction, material mapping, quantity takeoff, mandatory standalone SketchUp Ruby reconstruction and Excel material/quotation deliverables.

## Current stage

**V0.3.1-alpha — workspace + mandatory Ruby + Excel deliverables**

The prompt pack now reorients the runtime toward **Drawing-to-SketchUp
Reconstruction Engine**. The implementation audit is kept in
`.codex/PROMPT_AUDIT.md`; the MCP-SU layer provides provenance-first
2D-ingestion/review/spec/build/verification stages, semantic SketchUp tools,
real-provider-only production chat, and explicit safety gates. The legacy
filesystem-first estimator workflow below remains available for existing
projects.

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
TAKEOFF JSON
          ↓
Ruby for every READY/PARTIAL_READY component
          ↓
SketchUp preview images when Ruby is executed
          ↓
2 Excel workbooks
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

Excel exporter:

```powershell
python "$env:USERPROFILE\.agents\skills\ai-dg-estimator\scripts\workspace\export_project_excel.py" "D:\AI-dg\MyProject"
```

creates:

```text
OUTPUT/EXCEL/AI-dg_Tong-hop-vat-lieu.xlsx
OUTPUT/EXCEL/AI-dg_Bao-gia.xlsx
```

The material workbook can embed actual SketchUp preview images from `OUTPUT/IMAGES`. Missing images, prices or suppliers remain explicit review/blank values; AI-dg must never invent them.

## Fresh-run rule

Every new deployment must begin with:

```powershell
python "$env:USERPROFILE\.agents\skills\ai-dg-estimator\scripts\workspace\prepare_run.py" "D:\AI-dg\MyProject"
```

This preserves `INPUT/`, deletes prior generated `WORK/` and `OUTPUT/`, recreates them and rescans the current source package. Cross-run merging is forbidden.

## Geometry-first rule

AI-dg links plan/elevation/side/section/detail as projections of the same physical item. It reconstructs local X/Y/Z geometry, maps materials spatially and performs projection-back checks before detailed takeoff or Ruby generation.

A section refinement is not automatically a visible subdivision. For VN-1, the current corrected interpretation treats the section chain `750 + 50 = 800` as a hidden 50 mm glass embed/slot within the 800 mm lower body rather than a visible horizontal band.

## Ruby test

Current standalone VN-1 test:

```text
.agents/skills/ai-dg-estimator/scripts/sketchup/vn1_prototype.rb
```

See [`RUBY_PROTOTYPE.md`](RUBY_PROTOTYPE.md).

## ChatGPT Work package

GitHub Actions builds:

```text
AI-dg-Work-v0.3.1-alpha.zip
```

See [`CHATGPT_WORK.md`](CHATGPT_WORK.md).

## Runtime extras

For deterministic PDF, Excel with embedded images and full schema validation in local/Codex environments:

```bash
python -m pip install -e ".[runtime]"
```

Optional extras include PyMuPDF, openpyxl, Pillow and jsonschema.

## MCP-SU runtime

The SketchUp 2023 extension exposes the official Ruby API through the local
JSON-lines bridge at `127.0.0.1:9876`.  Codex/OpenCode-style clients should use
`mcp_config.json`; its command points to `mcp_server/launcher.py`, which adds
the local MCP dependency directory without requiring a shell or provider
credentials.

Run the non-destructive live regression check with:

```powershell
python .\mcp_server\acceptance_smoke.py
```

The smoke test never enables model write mode and never calls 9Router.  A
`PARTIAL` result on `bounded_hierarchy` means the already-running SketchUp
process still has a legacy Ruby runtime loaded; reload the bridge gracefully
after handling any unsaved model, then rerun the test.

The in-SketchUp Control Center is local `UI::HtmlDialog` UI.  It reports
runtime, flow, trace, tools, skills, plugins, model metadata and safety state;
provider configuration is always redacted.

The prompt-driven 2D-to-3D pipeline is implemented under `pipeline/`. It
ingests PDF/DXF/DWG/Excel/image/SKP metadata, builds the Drawing Index,
reconciles dimensions, emits Dimension/Material Graphs and Review Queue,
generates a gated ModelSpec/semantic Build Plan, and verifies model evidence.
The MCP entrypoints are `ai_dg_source_ingest`, `ai_dg_pipeline_run`,
`ai_dg_pipeline_artifacts`, `ai_dg_review_queue`, `ai_dg_model_spec`,
`ai_dg_build_plan`, `ai_dg_execute_build_plan` and `ai_dg_verification`.
Semantic SketchUp builders include explicit panel/cabinet/partition/shelf/
door/drawer/countertop/component operations plus official API read-back. See
[`.codex/DRAWING_PIPELINE.md`](.codex/DRAWING_PIPELINE.md) and
[`.codex/TEST_RESULTS.md`](.codex/TEST_RESULTS.md).

Production chat never falls back to scripted responses: without a successful
provider test, `ai_dg_agent_ask` returns `REAL_PROVIDER_REQUIRED`. Provider
network tests and SketchUp model writes remain explicit opt-in operations.

## Accuracy rules

- Never invent dimensions, materials, quantities, coordinates, suppliers, prices or source references.
- Never modify source files under `INPUT/`.
- Reconcile PDF/CAD/SKP rather than silently preferring one source.
- Compare dimensions by geometric span, not raw number.
- Never count the same physical item multiple times because it appears in multiple views.
- Never claim CAD/SKP/model/image/Excel output was parsed or generated when it was not.
