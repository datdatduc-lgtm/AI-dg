# ChatGPT Test Protocol — AI-dg 0.2.1-alpha

Use this protocol before continuing deep implementation in Codex. The purpose is to test the **drawing-reading and orthographic-reconstruction methodology**, not to pretend that missing CAD/SKP binary adapters already exist.

## Test objective

Verify that the skill can consistently:

1. inventory the drawing package;
2. understand sheet/view hierarchy;
3. link multiple views of the same physical item;
4. establish item X/Y/Z axes and an overall 3D envelope;
5. distinguish overall/region/subregion/thickness/offset/gap dimensions;
6. derive geometry from multiple constrained views instead of copying isolated numbers;
7. map materials to physical regions/layers/surfaces;
8. separate assemblies from physical parts/panels;
9. avoid duplicate quantity counting;
10. reconcile overlapping PDF/CAD facts by geometric span;
11. report genuine conflicts instead of hiding them;
12. create a useful review queue;
13. prepare a traceable SketchUp reconstruction plan when requested.

## Recommended first test package

Use one real, reasonably small interior/joinery package containing:

- PDF export of the drawing set;
- matching CAD file from the same revision when available;
- optional SketchUp file if one already exists;
- at least one item with front elevation + side/section/detail;
- ideally a plan/footprint view;
- at least one material code/legend;
- several explicit dimensions, including one chained/hierarchical dimension.

Prefer a package you already understand well enough to manually verify the geometry.

## Prompt A — geometry-first drawing audit

Ask:

```text
Dùng AI-dg phân tích bộ bản vẽ này. Chưa báo giá và chưa dựng SketchUp.
Hãy lập Drawing Index và View Link Graph, sau đó với từng hạng mục phải dựng Geometry Ledger:
trục X/Y/Z, envelope 3D, phân vùng/subregion, hierarchy kích thước và vị trí vật liệu.
Chỉ sau đó mới lập Item Register, Source Reconciliation và Review Queue.
Không được coi hai chuỗi kích thước là conflict nếu chúng không đo cùng một geometric span.
```

### Pass criteria

- identifies the main sheets/views correctly;
- does not count a section/elevation as a new physical item;
- creates a local X/Y/Z frame for the item;
- combines linked views into one geometric hypothesis;
- retains source page/view references;
- distinguishes `EXPLICIT` from `DERIVED_FROM_VIEWS`;
- reports unreadable CAD/SKP adapter limitations honestly.

## Prompt B — one-item deep geometric read

Select one known item, then ask:

```text
Phân tích sâu [ITEM_CODE]. Ghép tất cả view liên quan và khôi phục hình học 3D từ các hình chiếu.
Lập: View Set, Local Axes, Overall Envelope, Dimensional Hierarchy, Region/Subregion geometry,
Material Spatial Map và Projection-back Check. Chỉ đánh dấu conflict khi hai nguồn đo cùng một span nhưng khác giá trị.
```

### Pass criteria

- links the correct views;
- extracts overall W/H/D from the correct axes/views;
- uses sections/details to refine internal geometry;
- understands hierarchical dimensions;
- does not invent unseen geometry from trade habit;
- maps materials to the correct regions/layers;
- can explain how the 3D hypothesis reproduces the available views.

## Prompt C — hierarchical-dimension trap

Use a drawing where one view shows a coarse region dimension and a section subdivides that region.

Example pattern:

```text
Elevation: 800 + 300 = 1100
Section:   750 + 50 + 300 = 1100
```

### Pass criteria

AI-dg must first test whether `750 + 50` geometrically refines the `800` region.

If the endpoints/geometry support that interpretation, expected status:

```text
DIMENSION_REFINEMENT
```

not:

```text
MISMATCH
```

A failure occurs if the model compares raw numbers without span semantics.

## Prompt D — material spatial mapping

Ask:

```text
Không chỉ liệt kê vật liệu. Hãy chỉ rõ mỗi vật liệu nằm ở region/part/layer/surface nào của hạng mục,
và view/detail nào chứng minh vị trí đó.
```

### Pass criteria

- material legend is connected back to physical geometry;
- core/board/glass/finish/decal/edge/adhesive roles remain distinct when shown;
- material boundaries use view geometry, not color guessing alone;
- missing thickness/extent remains unknown rather than invented.

## Prompt E — duplicate-count test

Ask:

```text
Cho biết tổng số hạng mục vật lý trong khu vực này. Không được cộng lặp cùng một hạng mục
chỉ vì nó xuất hiện ở nhiều view.
```

### Pass criteria

The result is based on physical item identity, not number of drawing appearances.

## Prompt F — reconciliation test

Use a package where PDF and CAD should match. Ask:

```text
Đối chiếu PDF và CAD cho các item chính. Với dimension phải ghi axis + start/end span + role.
Chỉ ra MATCH, DIMENSION_REFINEMENT, MISMATCH, ONLY_PDF, ONLY_CAD hoặc UNREADABLE_SOURCE.
Không tự chọn một bên khi có MISMATCH.
```

### Pass criteria

- comparable facts are paired by semantic/geometric span;
- hierarchical refinement is not mislabeled as conflict;
- genuine mismatches are surfaced;
- revision/layout identity is checked before blaming geometry;
- no averaging or silent source preference.

## Prompt G — controlled conflict test

If practical, use a copy of test data with one known changed dimension or known revision mismatch.

### Pass criteria

AI-dg should identify the conflict and place it in the blocker/review list rather than continuing as if sources agree.

## Prompt H — takeoff preview

Ask:

```text
Tạo Takeoff Preview chỉ từ các physical regions/parts đã qua Geometry Ledger và Projection-back Check.
Không được bóc trực tiếp từ một mặt đứng riêng lẻ nếu section/detail còn thay đổi cấu tạo.
```

### Pass criteria

- takeoff rows correspond to reconstructed physical parts/regions;
- no duplicate view counting;
- dimensions/quantity/material provenance remains visible;
- unresolved parts are excluded or clearly marked;
- arithmetic uses deterministic scripts when available.

## Prompt I — SketchUp reconstruction plan

Ask:

```text
Chưa cần viết Ruby. Hãy lập SketchUp Reconstruction Plan cho [ITEM/ROOM] từ Geometry Ledger,
bao gồm local axes, origin, envelope, region/part geometry, material mapping, tọa độ/rotation,
nguồn dữ liệu và blocker còn lại.
```

### Pass criteria

- plan follows the reconstructed geometry rather than a list of dimensions;
- CAD placement is used only when item matching/reconciliation supports it;
- model plan is traceable to drawing sources;
- unresolved geometry remains a blocker;
- no claim that a final verified SKP was created.

## Scoring

Score each category 0–2:

- `0` = incorrect / invented / unusable;
- `1` = partially correct but needs manual correction;
- `2` = correct and traceable.

Categories:

1. Drawing index
2. View linking
3. Item identity
4. Axis/envelope reconstruction
5. Dimension-span & hierarchy interpretation
6. Internal region/section reconstruction
7. Material spatial mapping
8. Part/panel decomposition
9. PDF/CAD reconciliation
10. Duplicate prevention
11. Projection-back validation
12. Review queue quality
13. Reconstruction planning

Maximum score: **26**.

Suggested gate before deeper Codex implementation: **22/26 or better**, with no critical fabrication of dimensions/materials/quantities and no raw-number reconciliation error on a known hierarchical-dimension test.

## Critical failures

Any of the following is an automatic methodology failure regardless of total score:

- inventing a fabrication dimension or material;
- declaring a conflict only because two dimension chains have different intermediate values while measuring different spans;
- failing to use a section/detail that materially changes the reconstructed geometry;
- producing detailed BOM before locating the physical regions/parts being counted;
- listing materials without spatial mapping when the drawing clearly shows their regions;
- claiming a binary CAD/SKP was parsed when the adapter is unavailable.

## Failure log

For every failed test, record:

```text
Test ID:
Drawing/package:
Expected:
Actual:
Source page/layout:
Failure type:
- wrong view link
- wrong axis assignment
- wrong dimension span
- hierarchy/refinement missed
- wrong region reconstruction
- projection contradiction
- duplicate item
- material spatial mapping
- source mismatch missed
- invented data
- parser/runtime unavailable
- other
Required skill change:
```

Use the failure log to improve `SKILL.md` and `references/` first. Only then ask Codex to implement or change parsers/engines for failures that are technical rather than methodological.
