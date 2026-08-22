# AI-dg for ChatGPT Work

This repository keeps **one canonical AI-dg skill source** for ChatGPT Work, Codex and OpenCode.

Current test version:

- Skill: `ai-dg-estimator`
- Version: `0.2.1-alpha`
- Stage: `chatgpt-geometry-test`
- Canonical source: `.agents/skills/ai-dg-estimator/`

## Upload package

The GitHub Actions workflow **Build AI-dg Skill Package** builds an upload-ready archive:

```text
AI-dg-Work-v0.2.1-alpha.zip
```

The ZIP root contains `SKILL.md` directly, followed by the skill resources:

```text
SKILL.md
references/
schemas/
examples/
data/
scripts/
pyproject.toml
```

This is intentional. Do not upload the whole GitHub repository as the skill package.

## Build locally

From the repository root:

```bash
python package_chatgpt.py
```

Outputs:

```text
dist/AI-dg-Work-v0.2.1-alpha.zip
dist/AI-dg-Work-v0.2.1-alpha.sha256
dist/AI-dg-Work-v0.2.1-alpha-contents.txt
dist/ai-dg-estimator.zip
```

`ai-dg-estimator.zip` is a compatibility alias of the same package.

## Install / create in ChatGPT Work

Use ChatGPT Work's Skills creation/upload flow and provide `AI-dg-Work-v0.2.1-alpha.zip`.

If ChatGPT Work asks what the skill should do, use this intent:

> AI-dg reads interior/joinery/CNC drawing packages using a geometry-first method. It links plan/elevation/side/section/detail views as projections of one physical object, reconstructs X/Y/Z geometry, maps materials to physical regions/layers/surfaces, reconciles PDF with CAD and optional SketchUp, prevents duplicate counting, and only performs takeoff from evidence-backed geometry. Unknowns and source conflicts must remain explicit.

## First acceptance test

Use a drawing that you already understand well. Recommended prompt:

```text
Dùng AI-dg phân tích bộ bản vẽ này. Chưa báo giá và chưa dựng SketchUp.

Không được chỉ trích xuất các kích thước rời rạc.
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

## Geometry test rule

A response fails the test if it only lists dimensions/materials without reconstructing the physical relationship between views.

Example:

```text
Elevation: 800 + 300 = 1100
Section:   750 + 50 + 300 = 1100
```

The skill must first test whether `750 + 50` geometrically refines the same lower `800` region. If yes, this is `DIMENSION_REFINEMENT`, not a mismatch.

## Runtime honesty

If ChatGPT Work cannot structurally inspect a binary CAD or SKP file, AI-dg must report:

```text
adapter_unavailable
```

It must not claim that CAD/SKP entities, dimensions, coordinates, components or materials were parsed when the runtime did not actually expose them.

## Development loop

```text
ChatGPT Work test
      ↓
record wrong drawing interpretation
      ↓
fix SKILL.md / references on GitHub main
      ↓
rebuild Work package
      ↓
retest
      ↓
when methodology is stable
      ↓
use Codex to implement CAD/SKP parsers + SketchUp Ruby reconstruction
```

The GitHub source is the canonical source of truth. Do not maintain a separate manually edited Work-only skill unless a platform-specific compatibility change becomes necessary.
