# AI-dg

AI-dg is a portable Agent Skill for reading interior/joinery/CNC drawing packages, reconciling PDF with CAD and optional SketchUp, reconstructing geometry from orthographic views, performing traceable quantity takeoff, and preparing data for BOM/Excel and later SketchUp reconstruction.

## Current stage

**V0.2.2-alpha — ChatGPT Work compatibility + geometry methodology test**

The immediate goal is to test whether the skill can reconstruct the **physical 3D logic** of real drawings in ChatGPT Work before asking Codex to build deeper CAD/SKP parsers and Ruby reconstruction code.

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

## Canonical skill source

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

The GitHub `main` branch is the canonical source of truth. ChatGPT Work, Codex and OpenCode packages are built from this same directory.

## ChatGPT Work package

See [`CHATGPT_WORK.md`](CHATGPT_WORK.md).

GitHub Actions builds:

```text
AI-dg-Work-v0.2.2-alpha.zip
```

The ZIP root contains `SKILL.md` directly.

### Why 0.2.2

A ChatGPT Work installation test of 0.2.1 successfully unpacked and validated skill metadata, but its local smoke test stopped because `jsonschema` was unavailable. V0.2.2 makes the installation/compatibility path dependency-light:

- `validate_items.py` has a stdlib fallback when `jsonschema` is absent;
- `smoke_test.py` runs its core checks without third-party packages;
- Excel validation is optional when `openpyxl` is unavailable;
- PyMuPDF/openpyxl/jsonschema are optional runtime extras for Codex/OpenCode/local deterministic tooling.

Recommended installation path in ChatGPT is the Skills UI:

```text
Skills → Create → Upload from your computer
```

Choose `AI-dg-Work-v0.2.2-alpha.zip` rather than asking a Work chat to push a locally created skill repository.

## Build locally

```bash
python package_chatgpt.py
```

Outputs:

```text
dist/AI-dg-Work-v0.2.2-alpha.zip
dist/AI-dg-Work-v0.2.2-alpha.sha256
dist/AI-dg-Work-v0.2.2-alpha-contents.txt
dist/ai-dg-estimator.zip
```

For deterministic PDF/Excel tooling in Codex/OpenCode/local environments:

```bash
python -m pip install -e ".[runtime]"
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

Example:

```text
Elevation: 800 + 300 = 1100
Section:   750 + 50 + 300 = 1100
```

AI-dg must determine whether `750 + 50` subdivides the same lower `800` region. If yes, the correct relationship is `DIMENSION_REFINEMENT`, not a mismatch.

A real conflict exists only when two sources give different values for the **same axis + same start/end geometric span**.

## Material spatial mapping

AI-dg should connect materials to geometry rather than stop at a flat material list.

```text
Item
├─ lower body region
│  └─ board/core + finish system
└─ upper region
   └─ glass layer + decal/film
```

Thickness, finish, core, edge, film/decal, glass, adhesive and hardware remain separate facts when the drawing distinguishes them.

## Recommended ChatGPT Work acceptance test

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

The methodology gate is **22/26 or better**, with no critical fabrication and no raw-number reconciliation error on hierarchical dimensions.

## Important runtime limitation

- PDF can be used to test drawing reasoning when the ChatGPT surface can inspect it.
- CAD/SKP should only be described as parsed when the runtime actually exposes their structured contents.
- If a binary CAD/SKP adapter is unavailable, AI-dg must return `adapter_unavailable` rather than inventing geometry or metadata.

## Core accuracy rules

- Never invent missing dimensions, material codes, quantities, coordinates, rotations, revisions, or source references.
- Geometric inference is allowed only when constrained by linked drawing views and must be marked `DERIVED_FROM_VIEWS`.
- Compare dimensions by axis and geometric span, not by raw number.
- Use section/detail geometry to refine the 3D hypothesis.
- Map materials to physical regions/layers/surfaces before detailed takeoff.
- Never count the same physical item multiple times because it appears in multiple views.
- Never claim CAD/SKP was parsed when the adapter is unavailable.
