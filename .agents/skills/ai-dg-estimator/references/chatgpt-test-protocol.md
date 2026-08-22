# ChatGPT Test Protocol — AI-dg 0.2.0-alpha

Use this protocol before continuing deep implementation in Codex. The purpose is to test the **drawing-reading methodology**, not to pretend that missing CAD/SKP binary adapters already exist.

## Test objective

Verify that the skill can consistently:

1. inventory the drawing package;
2. understand sheet/view hierarchy;
3. link multiple views of the same physical item;
4. identify material codes and resolve them through evidence;
5. separate assemblies from physical parts/panels;
6. avoid duplicate quantity counting;
7. reconcile overlapping PDF/CAD facts;
8. report conflicts instead of hiding them;
9. create a useful review queue;
10. prepare a traceable SketchUp reconstruction plan when requested.

## Recommended first test package

Use one real, reasonably small interior/joinery package containing:

- PDF export of the drawing set;
- matching CAD file from the same revision;
- optional SketchUp file if one already exists;
- at least one item with plan + elevation + section/detail;
- at least one material code/legend;
- several explicit dimensions.

Prefer a package you already understand well enough to manually verify the result.

## Prompt A — drawing audit

Ask:

```text
Dùng AI-dg phân tích bộ bản vẽ này. Chưa báo giá và chưa dựng SketchUp.
Hãy lập Drawing Index, Item Register, liên kết mặt bằng/mặt đứng/mặt cắt/detail,
đọc vật liệu và lập Source Reconciliation. Mọi điểm không chắc phải vào Review Queue.
```

### Pass criteria

- identifies the main sheets/views correctly;
- does not count a section/elevation as a new cabinet;
- retains source page/view references;
- distinguishes explicit evidence from inference;
- reports unreadable CAD/SKP adapter limitations honestly.

## Prompt B — one-item deep read

Select one known item, then ask:

```text
Phân tích sâu [ITEM_CODE]. Ghép tất cả view liên quan, xác định kích thước tổng,
cấu tạo được thể hiện, mã vật liệu, các tấm/chi tiết có đủ bằng chứng,
và liệt kê dữ liệu còn thiếu hoặc mâu thuẫn.
```

### Pass criteria

- links the correct views;
- extracts W/H/D from the correct dimensions;
- does not invent panels not shown;
- resolves material codes through legend/schedule when available;
- source references remain traceable.

## Prompt C — duplicate-count test

Ask:

```text
Cho biết tổng số hạng mục vật lý trong khu vực này. Không được cộng lặp cùng một hạng mục
chỉ vì nó xuất hiện ở nhiều view.
```

### Pass criteria

The result is based on physical item identity, not number of drawing appearances.

## Prompt D — reconciliation test

Use a package where PDF and CAD should match. Ask:

```text
Đối chiếu PDF và CAD cho các item chính. Chỉ ra từng MATCH, MISMATCH,
ONLY_PDF, ONLY_CAD hoặc UNREADABLE_SOURCE. Không tự chọn một bên khi có MISMATCH.
```

### Pass criteria

- comparable facts are paired correctly;
- mismatches are surfaced;
- revision/layout identity is checked before blaming geometry;
- no averaging or silent source preference.

## Prompt E — controlled conflict test

If practical, use a copy of test data with one known changed dimension or known revision mismatch.

### Pass criteria

AI-dg should identify the conflict and place it in the blocker/review list rather than continuing as if sources agree.

## Prompt F — takeoff preview

Ask:

```text
Tạo Takeoff Preview cho các item đã đủ dữ liệu. Chỉ bóc các tấm/chi tiết có bằng chứng.
Các phần chưa đủ dữ liệu phải tách riêng, không được ước đoán.
```

### Pass criteria

- no duplicate view counting;
- dimensions/quantity/material provenance remains visible;
- unresolved parts are excluded or clearly marked;
- arithmetic uses deterministic scripts when available.

## Prompt G — SketchUp reconstruction plan

Ask:

```text
Chưa cần viết Ruby. Hãy lập SketchUp Reconstruction Plan cho [ITEM/ROOM],
bao gồm origin, tọa độ, rotation, kích thước, assembly/part, vật liệu,
nguồn dữ liệu và blocker còn lại.
```

### Pass criteria

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
4. Dimension extraction
5. Material interpretation
6. Part/panel decomposition
7. PDF/CAD reconciliation
8. Duplicate prevention
9. Review queue quality
10. Reconstruction planning

Maximum score: **20**.

Suggested gate before deeper Codex implementation: **16/20 or better**, with no critical fabrication of dimensions/materials/quantities.

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
- wrong dimension role
- duplicate item
- material mapping
- source mismatch missed
- invented data
- parser/runtime unavailable
- other
Required skill change:
```

Use the failure log to improve `SKILL.md` and `references/` first. Only then ask Codex to implement or change parsers/engines for failures that are actually technical rather than methodological.
