# AI-dg for ChatGPT Work

This repository keeps one canonical AI-dg skill source for ChatGPT Work, Codex and OpenCode.

Current version:

- Skill: `ai-dg-estimator`
- Version: `0.3.3-alpha`
- Stage: `concise-excel-material-swatch`
- Canonical source: `.agents/skills/ai-dg-estimator/`

## Upload package

GitHub Actions builds:

```text
AI-dg-Work-v0.3.3-alpha.zip
```

The ZIP root contains `SKILL.md` directly with references, schemas, examples, data and scripts.

Recommended ChatGPT Work install path:

```text
Skills → Create → Upload from your computer
```

Select `AI-dg-Work-v0.3.3-alpha.zip`.

## What is new in v0.3.3

The geometry-first methodology remains unchanged. The Excel exporter is now explicitly user-facing rather than a debug report:

- the material workbook uses one concise `VAT_LIEU` sheet;
- the quotation workbook uses one concise `BAO_GIA` sheet;
- Ruby paths, readiness states, source/evidence dumps and internal AI metadata are excluded from normal Excel output;
- material rows focus on item/detail, drawing material code, specification, thickness, color/sample, m² and 1200×2400 area-equivalent sheets;
- when the PDF legend contains a real material/color swatch and the runtime can crop it reliably, AI-dg can store the actual crop under `OUTPUT/IMAGES/MATERIALS/` for Excel embedding;
- `material-specifications.json` remains the richer technical source while the normal workbook stays readable.

Filesystem features primarily target Codex/OpenCode/local use. ChatGPT Work may not have access to the user's local workspace; when local filesystem access is unavailable, use uploaded files and retain the same geometry/reconciliation rules.

## Core intent

AI-dg links plan/elevation/side/section/detail views as projections of one physical object, reconstructs X/Y/Z geometry, maps materials to physical regions/layers/surfaces, reconciles PDF with CAD and optional SketchUp, prevents duplicate counting, and only performs takeoff or Ruby reconstruction from evidence-backed geometry.

Unknowns and source conflicts remain explicit.

## Runtime honesty

If ChatGPT Work cannot structurally inspect a binary CAD or SKP file, AI-dg must report `adapter_unavailable`. It must not claim that CAD/SKP entities, dimensions, coordinates, components or materials were parsed when the runtime did not expose them.

## Build locally

```bash
python package_chatgpt.py
```

Outputs:

```text
dist/AI-dg-Work-v0.3.3-alpha.zip
dist/AI-dg-Work-v0.3.3-alpha.sha256
dist/AI-dg-Work-v0.3.3-alpha-contents.txt
dist/ai-dg-estimator.zip
```

For deterministic local PDF/Excel tooling:

```bash
python -m pip install -e ".[runtime]"
```

Runtime extras include PyMuPDF, openpyxl, Pillow and jsonschema.

The GitHub `main` branch remains the source of truth.
