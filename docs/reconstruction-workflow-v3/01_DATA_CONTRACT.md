# Reconstruction V3 Data Contract

Interpreted source dùng `schema_version: 3` và chứa các collection tổng quát:

```text
views[]
constraints[]
section_profiles[]
items[]
  └─ hypotheses[]
```

## View

Mỗi view có `view_id`, `sheet_id`, `view_type`, hai `projection_axes`,
`item_refs`, `mandatory`, `source_refs` và `verification_contract`. Section và
detail có thể thêm `cut_plane`, `look_direction`, `section_marker`; detail dùng
`refines_view_id` để liên kết về parent.

View được phép nằm trên nhiều sheet. View không có item link hoặc detail trỏ tới
parent không tồn tại là blocker.

## Constraints

Mỗi dimension/feature constraint cần semantic `start_ref`, `end_ref`, source
view và state. Chỉ `EXPLICIT`, `DERIVED_FROM_VIEWS` hoặc `APPROVED_DERIVED`
được đi vào build gate.

## Section profile

Feature taxonomy production:

`SLOT, GROOVE, RECESS, HOLE, CUTOUT, CHAMFER, RADIUS, BEVEL, LIP, STEP,
POCKET, OPENING, LAYER, PANEL, GLASS, HARDWARE_ZONE`.

Không có feature riêng mang tên fixture. Mỗi feature phải có source evidence.

## Verification contract

Một contract có thể kiểm tra:

- `overall_mm` theo trục;
- `visible_region_ids` và `forbidden_visible_region_ids`;
- `region_spans` theo projection axes;
- `section_features` và dimensions của feature.

Comparator không trộn kết quả giữa revision/hash khác nhau. Một mandatory view
FAIL làm model FAIL dù mọi view còn lại PASS.

## Artifacts

```text
WORK/reconstruction/<run-id>/
  raw-evidence-v3.json
  interpreted-payload-v3.json
  view-registry-v3.json
  view-link-graph-v3.json
  constraint-graph-v3.json
  section-profile-graph-v3.json
  hypotheses-v3.json
  workflow-summary-v3.json

OUTPUT/MODEL/reconstruction/<run-id>/
  model-spec-v3.json
  build-ir-v3.json

OUTPUT/VERIFICATION/reconstruction/<run-id>/
  view-comparison-v3.json
  repair-plan-v3.json
  sketchup-view-back-v3.json
  autonomous-repair-v3.json
```

`raw-evidence-v3.json` là artifact máy sinh trực tiếp từ source. Production flow
không yêu cầu và không cho phép sửa JSON này để làm test PASS. Mỗi derived
constraint lưu `source_id`, sheet/view, OCR bbox, raw text, confidence và hướng
OCR.
