# AI-dg for ChatGPT Work

This repository keeps one canonical AI-dg skill source for ChatGPT Work, Codex and OpenCode.

Current version:

- Skill: `ai-dg-estimator`
- Version: `0.3.0-alpha`
- Stage: `workspace-io-ruby-prototype`
- Canonical source: `.agents/skills/ai-dg-estimator/`

## Upload package

GitHub Actions builds:

```text
AI-dg-Work-v0.3.0-alpha.zip
```

The ZIP root contains `SKILL.md` directly with references, schemas, examples, data and scripts.

Recommended ChatGPT Work install path:

```text
Skills → Create → Upload from your computer
```

Select `AI-dg-Work-v0.3.0-alpha.zip`.

## What is new in v0.3

The drawing methodology remains geometry-first. V0.3 adds a filesystem project contract for Codex/OpenCode/local use:

```text
INPUT → WORK → OUTPUT
```

This does not require ChatGPT Work itself to have local filesystem access. In ChatGPT Work, continue using uploaded drawing files. In Codex/OpenCode/local use, prefer the project workspace defined in `references/workspace-io.md` and root `WORKSPACE.md`.

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
dist/AI-dg-Work-v0.3.0-alpha.zip
dist/AI-dg-Work-v0.3.0-alpha.sha256
dist/AI-dg-Work-v0.3.0-alpha-contents.txt
dist/ai-dg-estimator.zip
```

For deterministic local PDF/Excel tooling:

```bash
python -m pip install -e ".[runtime]"
```

The GitHub `main` branch remains the source of truth.
