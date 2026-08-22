# AI-dg

AI-dg is a portable Agent Skill for reading interior/joinery/CNC drawing packages, reconciling PDF with CAD and optional SketchUp, reconstructing geometry from orthographic views, performing traceable quantity takeoff, and preparing data for BOM/Excel and later SketchUp reconstruction.

## Current stage

**V0.2.1-alpha — ChatGPT geometry methodology test**

The immediate goal is to test whether the skill can reconstruct the **physical 3D logic** of real drawings before asking Codex to build deeper CAD/SKP parsers and Ruby reconstruction code.

Current intended workflow:

```text
PDF + CAD (+ optional SKP)
          ↓
Drawing package inventory
          ↓
View linking
          ↓
Orthographic reconstruction (X/Y/Z)
          ↓
Geometry Ledger + dimensional hierarchy
          ↓
Material spatial mapping
          ↓
PDF ↔ CAD ↔ SKP reconciliation
          ↓
Takeoff preview / review queue
          ↓
BOM / Excel / SketchUp reconstruction plan
```

PDF and CAD are treated as two representations of the same authored drawing. Overlapping facts must be compared by **geometric span**, not by raw numeric values alone. A section/detail may refine a coarser elevation dimension without creating a conflict.

## Skill location

The canonical portable skill lives at:

```text
.agents/skills/ai-dg-estimator/
```

Main files:

```text
.agents/skills/ai-dg-estimator/
├─ SKILL.md
├─ references/
│  ├─ drawing-reading-method.md
│  ├─ orthographic-reconstruction.md
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

## Geometry-first rule

AI-dg must not read plan/elevation/section/detail as separate tables.

For each physical item it should attempt to build:

```text
Item
├─ Local axes X/Y/Z
├─ Overall envelope
├─ Region / subregion geometry
├─ Dimensional hierarchy
├─ Material-to-region/layer mapping
├─ EXPLICIT facts
├─ DERIVED_FROM_VIEWS facts
└─ unresolved geometry
```

Example dimension pattern:

```text
Elevation: 800 + 300 = 1100
Section:   750 + 50 + 300 = 1100
```

AI-dg must determine whether `750 + 50` subdivides the same lower `800` region. If yes, the correct relationship is:

```text
DIMENSION_REFINEMENT
```

not a mismatch.

A real conflict exists only when two sources give different values for the **same axis + same start/end geometric span**.

## Material spatial mapping

AI-dg should not stop at a flat material list when the drawing shows placement.

It should connect materials to geometry, for example:

```text
Item
├─ lower body region
│  └─ board/core + finish system
└─ upper region
   └─ glass layer + decal/film
```

Thickness, finish, core, edge, film/decal, glass, adhesive and hardware remain separate facts when the drawing distinguishes them.

## Test in ChatGPT first

AI-dg includes a GitHub Actions workflow that builds an upload-oriented ZIP whose root contains `SKILL.md` directly.

### Option A — GitHub Actions artifact

1. Open the repository's **Actions** tab.
2. Open **Build AI-dg Skill Package**.
3. Open the latest successful run.
4. Download artifact `ai-dg-estimator-chatgpt-test`.
5. Extract the downloaded artifact if GitHub wraps it in another ZIP; the target skill file is `ai-dg-estimator.zip`.
6. Upload the skill in an eligible ChatGPT Skills workspace.

### Option B — build locally

From the repository root:

```bash
python package_chatgpt.py
```

Output:

```text
dist/ai-dg-estimator.zip
```

## Recommended next acceptance test

Use a small drawing you understand well and ask:

```text
Dùng AI-dg phân tích bộ bản vẽ này. Chưa báo giá và chưa dựng SketchUp.

Không được chỉ trích xuất kích thước rời rạc.
Với từng hạng mục, phải ghép mặt bằng/mặt đứng/mặt bên/mặt cắt/detail thành một mô hình hình học thống nhất.

Hãy xuất theo thứ tự:
1. Drawing Index
2. View Link Graph
3. Geometry Ledger: trục X/Y/Z, envelope, region/subregion
4. Dimensional Hierarchy: overall → region → subregion → thickness/offset/gap
5. Material Spatial Map: vật liệu nằm ở region/part/layer/surface nào
6. Projection-back Check
7. Item Register
8. Source Reconciliation
9. Review Queue
10. Takeoff Readiness

Cho phép suy diễn hình học khi nhiều view cùng ràng buộc một kết quả và phải ghi DERIVED_FROM_VIEWS.
Không được suy đoán theo thói quen nghề.
Chỉ coi hai kích thước là MISMATCH khi chúng đo cùng geometric span nhưng khác giá trị.
```

Then follow:

```text
.agents/skills/ai-dg-estimator/references/chatgpt-test-protocol.md
```

The methodology gate is now **22/26 or better**, with no critical fabrication and no raw-number reconciliation error on hierarchical dimensions.

## Important runtime limitation

The methodology is ahead of the binary adapters.

At this stage AI-dg must be honest about file accessibility:

- PDF can be used to test drawing reasoning immediately when the ChatGPT surface can inspect it.
- CAD/SKP should only be described as parsed when the current runtime actually exposes their structured contents.
- If a binary CAD/SKP adapter is unavailable, AI-dg must return `adapter_unavailable` rather than inventing geometry or metadata.

This limitation is intentional: first verify the geometry/reconciliation method, then let Codex implement the missing adapters against concrete failed tests.

## Existing deterministic V0.1 tools

The repository still contains the original deterministic pipeline:

```bash
python scripts/analyze_pdf.py path/to/drawing.pdf --project project --render
python scripts/validate_items.py project/extracted/items.json
python scripts/calculate_bom.py project/extracted/items.json --output project/extracted/bom.json
python scripts/export_excel.py project/extracted/items.json project/extracted/bom.json --output project/output/AI-dg-estimate.xlsx
```

V0.1 uses PyMuPDF, `jsonschema`, and `openpyxl`.

## Core accuracy rules

- Never invent missing dimensions, material codes, quantities, coordinates, rotations, revisions, or source references.
- Geometric inference is allowed only when constrained by linked drawing views and must be marked `DERIVED_FROM_VIEWS`.
- Compare dimensions by axis and geometric span, not by raw number.
- Use section/detail geometry to refine the 3D hypothesis.
- Map materials to physical regions/layers/surfaces before detailed takeoff.
- Never count the same physical item multiple times because it appears in multiple views.
- Never claim CAD/SKP was parsed when the adapter is unavailable.
