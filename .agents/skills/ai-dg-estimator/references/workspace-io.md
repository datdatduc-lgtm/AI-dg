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
│  ├─ IMAGES/
│  ├─ TAKEOFF/
│  ├─ EXCEL/
│  ├─ REPORTS/
│  └─ MODEL/
└─ project.ai-dg.json
```

The skill installation under `~/.agents/skills/ai-dg-estimator` is code/reference only. Never store user drawing packages inside the installed skill.

## Mandatory fresh-run policy

Every new analysis/deployment is a **fresh run**.

Before reading or reasoning over the project, AI-dg must run:

```text
scripts/workspace/prepare_run.py <project_root>
```

This operation must:

1. require a valid `project.ai-dg.json` marker;
2. preserve `INPUT/` completely;
3. preserve `project.ai-dg.json`;
4. delete the previous generated `WORK/` tree;
5. delete the previous `OUTPUT/` tree and every artifact inside it;
6. recreate the canonical WORK/OUTPUT folders;
7. generate a new run marker;
8. rescan current INPUT and create a new `WORK/manifests/input-manifest.json`.

**Cross-run merging is forbidden.** Ruby, JSON, Excel, images, reports, models, manifests, geometry ledgers, review queues and other artifacts from an older run must not survive into the new run unless they are explicitly re-generated from the current INPUT.

Because `OUTPUT/` is disposable generated state, users must not place manually maintained source files there. Files that must survive reruns belong outside OUTPUT, normally under INPUT/OTHER or another project-controlled folder outside WORK/OUTPUT.

## INPUT contract

Codex must scan `INPUT/` recursively after the fresh-run reset. Supported categories are inferred from extension and preserved by original relative path.

Typical source files:

- PDF: `.pdf`
- CAD: `.dwg`, `.dxf`, `.dwt`
- SketchUp: `.skp`
- spreadsheets/specifications: `.xlsx`, `.xls`, `.csv`
- text/reference: `.txt`, `.md`, `.docx`
- images: `.png`, `.jpg`, `.jpeg`, `.tif`, `.tiff`

Do not silently ignore an unknown file. Put it in the manifest as `OTHER` or `UNSUPPORTED` and report whether it was inspected.

Never modify or delete an INPUT source during cleanup, analysis, reconstruction, takeoff or export.

## Input manifest

The authoritative inventory for the current run is:

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

The manifest must describe the current INPUT state after the fresh-run reset, not a previous run.

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

1. locate `project.ai-dg.json`;
2. run `scripts/workspace/prepare_run.py` against the project root;
3. confirm the previous WORK/OUTPUT were removed and a fresh input manifest was created;
4. inspect the current manifest and all relevant source files;
5. build Drawing Index, View Link Graph, Geometry Ledger, material mapping and reconciliation;
6. write intermediate machine-readable results under the newly created `WORK/`;
7. write user deliverables only under the newly created `OUTPUT/`;
8. create `OUTPUT/output-manifest.json` at the end;
9. never require the user to upload the same local files into chat when filesystem access is available.

Do not start a deployment by calling `scan_input.py` alone if prior WORK/OUTPUT may exist. `scan_input.py` is an inventory helper; `prepare_run.py` is the required deployment entry point.

## WORK contract

`WORK/` is reproducible intermediate state for exactly one run.

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
WORK/logs/run-start.json
WORK/logs/run-log.md
```

Only create files supported by the current adapters. Missing adapters remain explicit.

## OUTPUT contract

`OUTPUT/` contains artifacts for the current run only.

### RUBY

```text
OUTPUT/RUBY/<item-or-project>.rb
```

Standalone SketchUp reconstruction prototypes. Ruby must preserve source/readiness metadata and mark review hypotheses.

### IMAGES

```text
OUTPUT/IMAGES/<item>_iso.png
OUTPUT/IMAGES/<item>_front.png
OUTPUT/IMAGES/<item>_side.png
```

Use actual generated/model views when available; do not present invented renders as verified model output.

### TAKEOFF

```text
OUTPUT/TAKEOFF/items.json
OUTPUT/TAKEOFF/material-regions.json
OUTPUT/TAKEOFF/bom.json
OUTPUT/TAKEOFF/review-queue.json
```

Fabrication BOM is allowed only when its readiness gate passes. Geometry/material-region takeoff may exist earlier and must be labeled accordingly.

### EXCEL

```text
OUTPUT/EXCEL/AI-dg_Tong-hop-vat-lieu.xlsx
OUTPUT/EXCEL/AI-dg_Bao-gia.xlsx
```

Excel may include item images, drawing/item index, material-region detail, summarized materials, sources, review status, supplier references, prices and quotations when verified inputs exist.

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

Do not claim a model exists unless it was actually created and verified.

## Output manifest

At the end of the current run, create:

```text
OUTPUT/output-manifest.json
```

It should inventory every artifact actually generated in this run with path, type, status and source basis.

## Cleanup safety rules

- `INPUT/` is immutable and never deleted by the fresh-run reset.
- `project.ai-dg.json` is preserved.
- Only `WORK/` and `OUTPUT/` directly under the validated project root are disposable.
- If WORK or OUTPUT is a symlink/junction, cleanup must refuse to run.
- `project.ai-dg.json` is required before destructive cleanup; without it, abort.
- No backup of old OUTPUT is created by default because the user requires zero cross-run overlap.
- If old deliverables must be preserved, copy them outside WORK/OUTPUT before starting a new run.

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

Do not suppress useful current-run artifacts merely because one later-stage deliverable is blocked.
