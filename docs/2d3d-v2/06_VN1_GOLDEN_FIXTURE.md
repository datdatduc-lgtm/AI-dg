# VN-1 Golden Fixture

Nguồn hiện có trong repo là `INPUT/PDF/CHI TIET VACH NGAN VN-1.pdf`; nội dung được khóa bằng SHA-256 `3888604d8d715beb0f77bf50b48c747caa99292580234f5e0e6e53f003dbec7d`. Tên download có thể có hậu tố `(1)`, nhưng fixture nhận diện bằng nội dung, không phụ thuộc hậu tố của Windows.

PDF này là scan không có text layer. Fixture sidecar chứa expected interpreted facts có source/view refs và chỉ nằm dưới `tests/fixtures/vn1`; production code không hard-code VN-1. Adapter từ chối chạy nếu hash PDF khác.

Gate A→F sinh:

- `WORK/geometry/drawing-index-v2.json`
- `WORK/geometry/geometry-ledger-v2.json`
- `WORK/geometry/region-graph-v2.json`
- `OUTPUT/MODEL/model-spec-v2.json`
- `OUTPUT/MODEL/build-ir-v2.json`
- `OUTPUT/VERIFICATION/projection-prebuild-v2.json`

Live SketchUp là Test G riêng và chỉ được phép sau khi A→F đều PASS.

## Test G — Live SketchUp evidence

Ngày 2026-09-09, Build IR V2 đã được thực thi qua MCP vào explicit target
`su-25228-cfbdf60107fd` (SketchUp PID `25228`, bridge generation `6`). Ruby API
chính thức trả về operation `op-20260909T093215.349Z-2920` và hai visible
regions:

- `VN-1:lower-body`: X `0..8000`, Y `0..40`, Z `0..800`, material `mat-lower`.
- `VN-1:upper-glass`: X `0..8000`, Y `15..25`, Z `800..1100`, material `mat-glass`.

`VN-1:embed-50` không xuất hiện trong visible geometry. Independent read-back
và post-build projection đều `PASS`.

Native confirmation được pre-approve chỉ trong execution path V2 sau khi source
review, Build IR, pre-build projection, exact target, write mode và explicit
`confirm_write` đều hợp lệ. Raw write tools và Undo không nhận pre-approval này.
