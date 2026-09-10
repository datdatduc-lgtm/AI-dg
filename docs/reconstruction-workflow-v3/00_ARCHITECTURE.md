# AI-DG General Reconstruction Workflow V3

## Invariant

AI-DG không coi geometry là đúng chỉ vì SketchUp tạo được solid. Một physical
item chỉ được xác minh khi **cùng một model revision và geometry hash** giải
thích được mọi mandatory front/plan/side/section/detail view đã liên kết.

```text
raw PDF/image
  → auto orientation + OCR/layout evidence
  → evidence-gated profile-assembly interpretation
  → View Registry
  → View Link Graph
  → Constraint Graph
  → Region data + Section/Profile Graph
  → competing 3D hypotheses
  → unique hypothesis gate
  → ModelSpec V3
  → Build IR V3
  → deterministic SketchUp profile extrusion
  → official Ruby geometry read-back
  → native front/side/section/detail analysis views
  → Cross-View Comparator
  → PASS or bounded upstream Repair Loop
```

V3 không thay đổi hay làm yếu V2. VN-1 là golden fixture đầu tiên; production
logic không có nhánh theo tên VN-1. Fixture RS-2 khác kích thước và sheet layout
được dùng để kiểm tra cùng một profile-assembly family.

## Boundaries

- Drawing/OCR/CAD adapters giữ bbox, text, confidence và orientation của từng
  fact. Không đủ view/dimension/material evidence thì dừng, không tự phát minh.
- Detail refines section/parent view, không trở thành physical item mới.
- Section-only features không xuất hiện trong normal elevation projection.
- Ties giữa nhiều hypothesis khác geometry hash là `HYPOTHESIS_AMBIGUOUS`.
- Repair chọn hypothesis upstream còn lại, regenerate operation rồi full-item
  rebuild. Không kéo geometry trực tiếp trong SketchUp.
- Tối đa năm vòng; score không tăng là `STALLED`.
- Visual/pixel comparison chỉ là tầng bổ sung. Semantic geometry là gate chính.

## Production modules

- `pipeline/stages/reconstruction_workflow_v3.py`: registry, links,
  constraints, section profiles, hypotheses, ModelSpec và Build IR.
- `pipeline/stages/view_verification_v3.py`: semantic view-back và comparator.
- `pipeline/stages/repair_loop_v3.py`: mismatch taxonomy, repair plan và vòng
  lặp có giới hạn.
- `pipeline/stages/raw_drawing_understanding_v3.py`: PDF/image render, tự xoay,
  OCR tiếng Việt/Anh, view captions, item identity và evidence-gated profile
  assembly interpretation.
- `pipeline/stages/executor_v3.py`: profile operation, exact-target dispatch,
  native read-back và bounded full-item hypothesis repair.
- MCP `ai_dg_reconstruction_workflow_v3`: nhận raw PDF/image hoặc interpreted
  JSON nằm trong project.
- MCP `ai_dg_execute_reconstruction_v3`: build sai/đúng theo hypothesis,
  read-back chính SketchUp và repair có giới hạn.
- MCP `ai_dg_compare_views_v3`: so một view-back snapshot với toàn bộ contract
  và sinh repair plan.
- MCP `ai_dg_view_back_sketchup_v3`: đọc exact SketchUp target bằng Ruby API,
  tạo snapshot cùng một revision và chạy comparator cho mọi item/view.
