# AI-dg for ChatGPT Work

This repository keeps one canonical AI-dg skill source for ChatGPT Work, Codex and OpenCode.

Current version:

- Skill: `ai-dg-estimator`
- Version: `0.3.1-alpha`
- Stage: `workspace-ruby-excel-deliverables`
- Canonical source: `.agents/skills/ai-dg-estimator/`

## Upload package

GitHub Actions builds:

```text
AI-dg-Work-v0.3.1-alpha.zip
```

The ZIP root contains `SKILL.md` directly with references, schemas, examples, data and scripts.

Recommended ChatGPT Work install path:

```text
Skills → Create → Upload from your computer
```

Select `AI-dg-Work-v0.3.1-alpha.zip`.

## What is new in v0.3.1

The geometry-first methodology remains unchanged. The main local/Codex changes are:

- every deployment starts with a fresh-run reset that keeps INPUT but clears generated WORK/OUTPUT;
- every `READY` or `PARTIAL_READY` component must receive a standalone Ruby file;
- local project runs must attempt both Excel deliverables;
- material-summary Excel can embed actual SketchUp preview images from OUTPUT/IMAGES;
- quotation Excel keeps missing prices/suppliers blank and explicit rather than inventing values;
- output finalization checks mandatory Excel and Ruby coverage.

These filesystem features primarily target Codex/OpenCode/local use. ChatGPT Work may not have access to the user's local workspace; when local filesystem access is unavailable, use uploaded files and retain the same geometry/reconciliation rules.

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
dist/AI-dg-Work-v0.3.1-alpha.zip
dist/AI-dg-Work-v0.3.1-alpha.sha256
dist/AI-dg-Work-v0.3.1-alpha-contents.txt
dist/ai-dg-estimator.zip
```

For deterministic local PDF/Excel tooling:

```bash
python -m pip install -e ".[runtime]"
```

Runtime extras include PyMuPDF, openpyxl, Pillow and jsonschema.

The GitHub `main` branch remains the source of truth.
