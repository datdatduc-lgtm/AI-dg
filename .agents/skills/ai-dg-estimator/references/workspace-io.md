# AI-dg Workspace I/O Contract

AI-dg should prefer a filesystem workspace for Codex/OpenCode/local runs instead of asking the user to upload many project files into chat.

## Project workspace

Each project lives outside the installed skill directory:

```text
AI-dg-PROJECT/
├─ INPUT/
│  ├─ PDF/
│  ├─ CAD/
│  ├─ SKP/
│  └─ OTHER/
├─ WORK/
│  ├─ manifests/
│  ├─ extracted/
│  ├─ geometry/
│  ├─ reconciliation/
│  └─ logs/
├─ OUTPUT/
│  ├─ RUBY/
│  ├─ TAKEOFF/
│  ├─ EXCEL/
│  ├─ REPORTS/
│  └─ MODEL/
└─ project.ai-dg.json
```

The skill installation under `~/.agents/skills/ai-dg-estimator` is treated as code/reference only. Do not store user drawing packages inside the installed skill.

## INPUT contract

Codex must scan `INPUT/` recursively before analysis. Supported categories are inferred from extension and preserved by original relative path.

Typical source files:

- PDF: `.pdf`
- CAD: `.dwg`, `.dxf`, `.dwt`
- SketchUp: `.skp`
- spreadsheets/specifications: `.xlsx`, `.xls`, `.csv`
- text/reference: `.txt`, `.md`, `.docx`
- images: `.png`, `.jpg`, `.jpeg`, `.tif`, `.tiff`

Do not silently ignore an unknown file. Put it in the manifest as `OTHER` or `UNSUPPORTED` and report whether it was inspected.

## Input manifest

Before reasoning, create or refresh:

```text
WORK/manifests/input-manifest.json
```

Each entry should include at least:

```text
relative_path
source_type
extension
size_bytes
sha256
modified_time_utc
analysis_status
notes
```

This manifest is the authoritative inventory of what the run actually saw.

## Source-package rule

All relevant files in `INPUT/` belong to one drawing package unless project metadata says otherwise.

PDF/CAD/SKP are not separate independent jobs. Match them by revision, sheet/layout, item code, geometry and source metadata, then reconcile overlapping facts.

If a source exists in INPUT but cannot be parsed, record `adapter_unavailable` or `UNREADABLE_SOURCE`; never pretend it was read.

## Codex invocation behavior

When the user says something like:

```text
Dùng AI-dg phân tích project tại D:/CongTrinh/Villa-A
```

Codex should:

1. locate `project.ai-dg.json` or initialize the workspace if explicitly requested;
2. run `scripts/workspace/scan_input.py` against the project root;
3. inspect the manifest and all relevant source files;
4. build Drawing Index, View Link Graph, Geometry Ledger, material mapping and reconciliation;
5. write intermediate machine-readable results under `WORK/`;
6. write user deliverables only under `OUTPUT/`;
7. never require the user to upload the same local files into chat when filesystem access is available.

## WORK contract

`WORK/` is reproducible intermediate state, not the final deliverable.

Recommended files:

```text
WORK/manifests/input-manifest.json
WORK/extracted/pdf-pages.json
WORK/extracted/cad-entities.json
WORK/extracted/sketchup-entities.json
WORK/geometry/drawing-index.json
WORK/geometry/view-link-graph.json
WORK/geometry/geometry-ledger.json
WORK/reconciliation/source-reconciliation.json
WORK/reconciliation/review-queue.json
WORK/logs/run-log.md
```

Only create files that are supported by the current adapters. Missing adapters must remain explicit.

## OUTPUT contract

`OUTPUT/` contains stable artifacts intended for the user or downstream tools.

### RUBY

```text
OUTPUT/RUBY/<item-or-project>.rb
```

Standalone SketchUp reconstruction prototypes before a full plugin exists. Ruby must preserve source/readiness metadata and clearly mark review hypotheses.

### TAKEOFF

```text
OUTPUT/TAKEOFF/items.json
OUTPUT/TAKEOFF/material-regions.json
OUTPUT/TAKEOFF/bom.json
OUTPUT/TAKEOFF/review-queue.json
```

Detailed fabrication BOM is allowed only when its readiness gate passes. Geometry/material-region takeoff may exist earlier and must be labeled accordingly.

### EXCEL

```text
OUTPUT/EXCEL/AI-dg-estimate.xlsx
```

Workbook may include Drawing Index, Items, Geometry, Materials, BOM, Review, Sources and later pricing/labor/schedule sheets.

### REPORTS

```text
OUTPUT/REPORTS/analysis.md
OUTPUT/REPORTS/drawing-index.md
OUTPUT/REPORTS/geometry-ledger.md
OUTPUT/REPORTS/source-reconciliation.md
OUTPUT/REPORTS/readiness.md
```

### MODEL

Reserved for generated or verified model artifacts when the runtime can create them:

```text
OUTPUT/MODEL/*.skp
```

Do not claim a model file exists unless it was actually created and verified.

## Output manifest

At the end of a run, create:

```text
OUTPUT/output-manifest.json
```

It should inventory every generated deliverable with path, type, status and source basis.

## Safe overwrite rules

- Never modify files under `INPUT/`.
- Do not delete user-created OUTPUT files blindly.
- Generated files should use deterministic names where possible.
- Before replacing a generated file from a previous run, preserve or record the previous version when practical.
- `WORK/` may be regenerated, but only inside the selected AI-dg project root.

## Readiness-aware output

A run may produce partial outputs. Example:

```text
Component Geometry: PARTIAL_READY
Project Placement: BLOCKED
Geometry Takeoff: READY
Material Region Takeoff: PARTIAL_READY
Fabrication BOM: BLOCKED
Ruby Prototype: READY_WITH_REVIEW
Excel: PARTIAL
```

Do not suppress useful partial artifacts merely because one later-stage deliverable is blocked.
