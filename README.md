# AI-dg

AI-dg is a portable Agent Skill for reading interior/joinery/CNC drawing packages, reconciling PDF with CAD and optional SketchUp, performing traceable quantity takeoff, and preparing data for BOM/Excel and later SketchUp reconstruction.

## Current stage

**V0.2.0-alpha — ChatGPT methodology test**

The immediate goal is to test whether the skill understands real drawings correctly **before asking Codex to build deeper CAD/SKP parsers and reconstruction code**.

Current intended workflow:

```text
PDF + CAD (+ optional SKP)
          ↓
Drawing package inventory
          ↓
Drawing index + view linking
          ↓
PDF ↔ CAD ↔ SKP reconciliation
          ↓
Canonical item/material graph
          ↓
Takeoff preview / review queue
          ↓
BOM / Excel / SketchUp reconstruction plan
```

PDF and CAD are treated as two representations of the same authored drawing. Overlapping facts must be compared. A mismatch is reported as a conflict; AI-dg must not silently choose one source.

## Skill location

The canonical portable skill currently lives at:

```text
.agents/skills/ai-dg-estimator/
```

Main files:

```text
.agents/skills/ai-dg-estimator/
├─ SKILL.md
├─ references/
│  ├─ drawing-reading-method.md
│  ├─ pdf-cad-reconciliation.md
│  ├─ chatgpt-test-protocol.md
│  ├─ extraction-rules.md
│  └─ material-rules.md
├─ schemas/
├─ examples/
├─ data/
├─ scripts/
└─ pyproject.toml
```

## Test in ChatGPT first

OpenAI ChatGPT Skills can contain instructions, supporting files, examples, and code. Eligible ChatGPT workspaces can upload a skill from the Skills interface.

AI-dg includes a GitHub Actions workflow that builds an upload-oriented ZIP whose root contains `SKILL.md` directly.

### Option A — use the GitHub Actions artifact

1. Open the repository's **Actions** tab.
2. Open **Build AI-dg Skill Package**.
3. Open the latest successful run.
4. Download artifact `ai-dg-estimator-chatgpt-test`.
5. Extract the downloaded artifact if GitHub wraps it in another ZIP; the target skill file is `ai-dg-estimator.zip`.
6. In an eligible ChatGPT workspace, open **Plugins → Skills → Create → Upload from your computer** and upload/select the skill package as supported by the UI.

The workflow checks that the package contains `SKILL.md` at its root before publishing the artifact.

### Option B — build the package locally

From the repository root:

```bash
python package_chatgpt.py
```

Output:

```text
dist/ai-dg-estimator.zip
```

The ZIP root contains:

```text
SKILL.md
references/
schemas/
examples/
data/
scripts/
pyproject.toml
```

## First ChatGPT acceptance test

Use one real drawing package you already understand well:

- matching PDF;
- matching CAD from the same revision;
- optional SketchUp file;
- at least one item with plan + elevation + section/detail;
- material legend/code;
- explicit dimensions.

Recommended first prompt:

```text
Dùng AI-dg phân tích bộ bản vẽ này. Chưa báo giá và chưa dựng SketchUp.
Hãy lập Drawing Index, Item Register, liên kết mặt bằng/mặt đứng/mặt cắt/detail,
đọc vật liệu và lập Source Reconciliation. Mọi điểm không chắc phải vào Review Queue.
```

Then follow:

```text
.agents/skills/ai-dg-estimator/references/chatgpt-test-protocol.md
```

The suggested methodology gate is **16/20 or better**, with no critical fabrication of dimensions, materials, quantities, coordinates, or source references.

## Important runtime limitation

The methodology is ahead of the binary adapters.

At this stage AI-dg must be honest about file accessibility:

- PDF can be used to test drawing reasoning immediately when the ChatGPT surface can inspect it.
- CAD/SKP should only be described as parsed when the current runtime actually exposes their structured contents.
- If a binary CAD/SKP adapter is unavailable, AI-dg must return `adapter_unavailable` rather than inventing geometry or metadata.

This limitation is intentional: first verify the **reading/reconciliation method**, then let Codex implement the missing adapters against concrete failed tests.

## Existing deterministic V0.1 tools

The repository still contains the original deterministic pipeline:

```bash
python scripts/analyze_pdf.py path/to/drawing.pdf --project project --render
python scripts/validate_items.py project/extracted/items.json
python scripts/calculate_bom.py project/extracted/items.json --output project/extracted/bom.json
python scripts/export_excel.py project/extracted/items.json project/extracted/bom.json --output project/output/AI-dg-estimate.xlsx
```

Inside the skill directory, dependencies can be installed with:

```bash
python -m pip install -e .
```

V0.1 uses PyMuPDF, `jsonschema`, and `openpyxl`.

## Core accuracy rules

- Never invent missing dimensions, material codes, quantities, coordinates, rotations, revisions, or source references.
- PDF and CAD must be reconciled where both describe the same fact.
- Do not count one physical item multiple times because it appears in plan/elevation/section/detail.
- Resolve material codes through legend/schedule/specification evidence.
- Separate substrate/core, thickness, surfaces, edge treatment, finish, and grain direction when the drawing supports those distinctions.
- Every important result remains traceable to its source.
- Unresolved conflicts go to the review queue and may block detailed takeoff or reconstruction.

## Roadmap

### V0.2 — current ChatGPT test

- drawing hierarchy methodology;
- plan/elevation/section/detail linking;
- physical-item identity and duplicate prevention;
- material interpretation;
- PDF ↔ CAD reconciliation rules;
- optional SKP audit methodology;
- SketchUp reconstruction planning;
- repeatable ChatGPT acceptance tests.

### After the methodology passes

Use the failure log from real drawings to ask Codex to implement, in order of demonstrated need:

1. CAD/DXF/DWG adapter;
2. robust PDF vector/text/vision extraction;
3. Drawing Graph schema + reconciliation engine;
4. SketchUp reader/exporter;
5. unified item/assembly/part/material model;
6. SketchUp Ruby reconstruction engine;
7. reconstruction verification and auto-fix;
8. production BOM/nesting;
9. pricing, labor, schedule, and cost control.

The repository is now developed directly on `main` unless a separate branch is explicitly requested.
