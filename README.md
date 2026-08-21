# AI-dg

AI-dg is a portable Agent Skill for construction/interior drawing takeoff.

Current V0.1 pipeline:

**PDF → extract/render pages → structured evidence-backed items → deterministic BOM → Excel**

The repository intentionally separates AI interpretation from calculations. AI may read and structure drawing evidence, but dimensions, areas, volumes, sheet counts, and aggregation are calculated by scripts.

## Skill location

The portable skill lives at:

```text
.agents/skills/ai-dg-estimator/
```

Both Codex and OpenCode can discover skills from `.agents/skills/`, including the user-level location `~/.agents/skills/`.

## Install on Windows

Clone this repository, open PowerShell in the repository root, then run:

```powershell
.\install.ps1
```

To replace an existing installation:

```powershell
.\install.ps1 -Force
```

The installer copies the skill to:

```text
~/.agents/skills/ai-dg-estimator
```

Restart Codex/OpenCode if the skill is not detected immediately.

## Install on Linux/macOS

```bash
chmod +x install.sh
./install.sh
```

Use `./install.sh --force` to replace an existing installation.

## Python dependencies

Inside the skill directory:

```bash
python -m pip install -e .
```

V0.1 uses PyMuPDF for PDF text/rendering, `jsonschema` for structured validation, and `openpyxl` for Excel export.

## First workflow

### 1. Analyze a PDF

```bash
python scripts/analyze_pdf.py path/to/drawing.pdf --project project --render
```

Outputs page text, candidate dimensions/material codes, page images, and scan/image-only warnings.

### 2. Build structured items

Create:

```text
project/extracted/items.json
```

Follow `schemas/items.schema.json`, `references/extraction-rules.md`, and `examples/items.example.json`.

Every record must retain its source PDF, page number, and evidence. Missing or uncertain values must be marked for review instead of guessed.

### 3. Validate

```bash
python scripts/validate_items.py project/extracted/items.json
```

### 4. Calculate BOM

```bash
python scripts/calculate_bom.py project/extracted/items.json --output project/extracted/bom.json
```

Optional material sheet data:

```bash
python scripts/calculate_bom.py project/extracted/items.json --materials data/materials.example.json --output project/extracted/bom.json
```

### 5. Export Excel

```bash
python scripts/export_excel.py project/extracted/items.json project/extracted/bom.json --output project/output/AI-dg-estimate.xlsx
```

Workbook sheets: `SUMMARY`, `ITEMS`, `BOM`, `REVIEW`, `SOURCES`.

## Safety / accuracy rules

- Never invent missing dimensions, material codes, quantities, prices, or page references.
- Every important extracted value must be traceable to drawing evidence.
- Scanned/image-only pages are flagged for visual review; V0.1 does not pretend OCR succeeded.
- Theoretical sheet count is not nesting optimization.
- V0.1 does not claim to produce a final quotation because price, labor, schedule, and cost-control engines are intentionally deferred.

## Roadmap

### V0.1 — current

- PDF text extraction and rendering
- drawing evidence capture
- structured item schema
- confidence/review flags
- deterministic BOM calculation
- Excel export
- shared Codex/OpenCode installation

### Next

- OCR/vision adapter for scanned drawings
- verified material library and code mapping
- quotation/price engine
- labor calculation
- construction schedule
- actual-vs-budget cost control
- audit reports and source highlighting

## Repository status

V0.1 is developed on `feature/ai-dg-estimator-v0.1` and should be reviewed before merging into `main`.
