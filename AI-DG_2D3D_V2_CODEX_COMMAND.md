# CODEX EXECUTION COMMAND — AI-DG 2D→3D V2 REFACTOR

## MỤC TIÊU DUY NHẤT

Refactor AI-DG để việc dựng 3D từ bản vẽ kỹ thuật không còn đi theo kiểu:

`PDF → đọc vài kích thước → tạo box/panel → SketchUp`

Mà bắt buộc đi qua chuỗi dữ liệu có thể kiểm chứng:

`Drawing Index → View Linking → Geometry Ledger V2 → Region Graph V2 → ModelSpec V2 → Build IR V2 → Projection Verification → SketchUp Execute → Read-back Verification`

Golden fixture bắt buộc: **VN-1** từ file:

`CHI TIET VACH NGAN VN-1(1).pdf`

Không mở rộng sang bộ bản vẽ khác cho tới khi VN-1 PASS đầy đủ.

---

# 0. NGUYÊN TẮC KHÔNG ĐƯỢC VI PHẠM

1. **Không sửa bằng prompt-only.**
   - Đây là refactor pipeline/schema/executor/verification.
   - Không được chỉ thêm system prompt hoặc yêu cầu model “suy nghĩ kỹ hơn”.

2. **Không cho Codex bypass pipeline bằng MCP write tool thô.**
   - Trong flow `drawing_reconstruction`, cấm gọi trực tiếp các tool kiểu:
     - `sketchup_create_box`
     - `sketchup_create_panel`
     - `sketchup_create_component`
     - `sketchup_create_group`
     - các write tool tương đương
   - Chỉ được write thông qua Build IR V2 đã PASS projection gate.

3. **Không dựng SketchUp nếu dữ liệu trung gian chưa PASS.**
   - Geometry Ledger V2 chưa hợp lệ → BLOCK.
   - Region Graph V2 chưa hợp lệ → BLOCK.
   - ModelSpec V2 chưa READY → BLOCK.
   - Build IR V2 chưa READY → BLOCK.
   - Projection Verification pre-build chưa PASS → BLOCK.

4. **Không đoán.**
   - Không tự thêm chiều dày MDF, chiều sâu, offset, rãnh, phụ kiện hoặc kết cấu nếu bản vẽ không chứng minh.
   - Fact không đủ bằng chứng phải là `UNKNOWN`, `AMBIGUOUS` hoặc `REVIEW_REQUIRED`.

5. **Không coi mọi kích thước cùng trục là cùng một span.**
   - Phải lưu start/end semantic reference của dimension.
   - Phải phân biệt:
     - overall
     - region
     - subregion
     - thickness
     - offset
     - gap
     - embed/recess/slot nếu thực sự có bằng chứng.

6. **Không coi section refinement là visible elevation split.**
   - Với VN-1, `800 + 300 = 1100`.
   - Section có `750 + 50 + 300 = 1100`.
   - `750 + 50` phải được hiểu là refinement nằm trong lower envelope 800.
   - Tuyệt đối không tự dựng `50 mm` thành một dải nhìn thấy riêng chỉ vì nó xuất hiện trong chuỗi dimension.
   - Quan hệ vật lý của vùng 50 mm phải được kết luận từ section/detail; nếu chưa đủ thì giữ `REVIEW_REQUIRED`.

7. **Không được tự báo PASS bằng unit test/mock.**
   - Cuối cùng phải có test live trên SketchUp thật qua MCP.
   - Phải có read-back từ Ruby API sau khi dựng.

8. **Nếu có nhiều SketchUp instance, không được tự chọn target.**
   - Phải dùng instance đã select rõ ràng.
   - Nếu nhiều instance và chưa target → BLOCK `TARGET_REQUIRED`.
   - Không fallback sang instance khác.

---

# 1. GOLDEN FIXTURE — VN-1

Dùng đúng file:

`CHI TIET VACH NGAN VN-1(1).pdf`

Bài test VN-1 phải đọc các view trên cùng sheet như các projection của **một physical item**, không phải các bản vẽ độc lập.

Minimum facts cần được hệ thống nhận đúng từ bản vẽ:

- Item: `VN-1`.
- Overall length theo mặt đứng: `8000 mm`.
- Overall height: `1100 mm`.
- Lower elevation region: `800 mm`.
- Upper elevation region: `300 mm`.
- Section refinement: `750 + 50 + 300 = 1100`.
- `750 + 50` thuộc cùng lower envelope `800`, không được coi là conflict.
- Detail/section có thông tin kính 10 mm và các note vật liệu/kết cấu liên quan; chỉ đưa vào geometry/material khi source evidence thực sự map được.
- Material/finish phải giữ nguyên wording hữu ích từ bản vẽ; không giảm xuống chỉ còn generic `MDF` hoặc `GLASS`.

Không hard-code VN-1 vào production logic.
Fixture có thể có expected JSON riêng trong tests.

---

# 2. AUDIT TRƯỚC KHI CODE

Đọc tối thiểu:

- `.agents/skills/ai-dg-estimator/SKILL.md`
- `.agents/skills/ai-dg-estimator/references/orthographic-reconstruction.md`
- `pipeline/stages/drawing_index.py`
- `pipeline/stages/graphs.py`
- `pipeline/stages/reconciliation.py`
- `pipeline/stages/model_spec.py`
- `pipeline/stages/build_ir.py`
- `pipeline/stages/builder.py`
- `pipeline/stages/executor.py`
- `pipeline/stages/verification.py`
- `mcp_server/server.py`
- Ruby bridge / semantic builder liên quan.

Trước khi sửa code, viết một audit ngắn vào:

`docs/2d3d-v2/00_CURRENT_FAILURE.md`

Phải nêu rõ:

1. Information nào đang bị mất từ source → facts.
2. Region granularity bị mất ở đâu.
3. Relationship/topology bị mất ở đâu.
4. Current ModelSpec không biểu diễn được gì.
5. Current Build IR không biểu diễn được gì.
6. Direct MCP write bypass hiện nằm ở đâu.
7. Vì sao VN-1 có thể bị biến thành hai thanh/khối song song.
8. First failing stage được xác định bằng evidence, không đoán.

Không code trước khi audit file này tồn tại.

---

# 3. GEOMETRY LEDGER V2

Tạo schema/version mới. Không phá artifact cũ nếu còn test legacy; có migration/adapter rõ ràng.

Suggested artifact:

`WORK/geometry/geometry-ledger-v2.json`

Mỗi item phải có ít nhất:

```json
{
  "item_code": "VN-1",
  "coordinate_frame": {
    "x_role": "main_length",
    "y_role": "depth_or_thickness",
    "z_role": "height"
  },
  "views": [],
  "envelope": {},
  "dimension_spans": [],
  "regions": [],
  "subregions": [],
  "unresolved_geometry": [],
  "source_refs": []
}
```

## 3.1 Dimension Span V2

Mỗi dimension phải lưu:

```json
{
  "id": "dim-...",
  "axis": "Z",
  "value_mm": 800,
  "start_ref": "item.bottom",
  "end_ref": "lower_body.top",
  "span_kind": "region",
  "view_id": "elevation-main",
  "state": "EXPLICIT",
  "source_refs": []
}
```

Không được reconcile chỉ bằng numeric equality.

## 3.2 Hierarchy

Ledger phải biểu diễn được:

```text
overall Z 1100
├─ lower envelope 800
│  ├─ section subspan 750
│  └─ section refinement 50
└─ upper region 300
```

VN-1 phải có automated assertion chứng minh:

- `800 + 300 = 1100`
- `750 + 50 = 800`
- không tạo conflict giả;
- không tạo visible geometry giả cho 50 mm nếu relation chưa được chứng minh.

---

# 4. REGION GRAPH V2

Tạo graph riêng:

`WORK/geometry/region-graph-v2.json`

Không dùng Material Graph thay thế cho Region Graph.

## 4.1 Node types tối thiểu

- `ITEM_ENVELOPE`
- `REGION`
- `SUBREGION`
- `MATERIAL_LAYER`
- `SURFACE`
- `DETAIL_FEATURE`
- `UNRESOLVED_REGION`

## 4.2 Edge/relationship types tối thiểu

Hỗ trợ schema cho:

- `CONTAINS`
- `WITHIN`
- `ABOVE`
- `BELOW`
- `ADJACENT_TO`
- `ALIGNED_WITH`
- `OVERLAPS`
- `REFINES`
- `VISIBLE_IN`
- `SECTION_ONLY`
- `MATERIAL_OF`

Và có khả năng bổ sung:
- `EMBEDDED_IN`
- `RECESSED_IN`
- `SLOTTED_IN`
- `OFFSET_FROM`

**Nhưng chỉ tạo các quan hệ embed/recess/slot khi source evidence chứng minh.**
Nếu chưa chắc → node/edge phải `AMBIGUOUS` hoặc `REVIEW_REQUIRED`.

## 4.3 Graph invariant

Một region được phép đi vào ModelSpec V2 chỉ khi:

- parent item rõ;
- bounds/span đủ cho axes cần thiết hoặc được đánh dấu unresolved;
- source refs tồn tại;
- material mapping không mâu thuẫn;
- relation với region khác không tự bịa.

---

# 5. MODELSPEC V2

Không sửa kiểu “thêm vài field” vào V1 rồi coi như xong.

Tạo schema/version rõ ràng:

`OUTPUT/MODEL/model-spec-v2.json`

V2 phải giữ nguyên region hierarchy và relationship.

Suggested shape:

```json
{
  "schema_version": 2,
  "run_id": "...",
  "source_review_status": "APPROVED",
  "items": [
    {
      "item_code": "VN-1",
      "coordinate_frame": {},
      "envelope": {},
      "regions": [],
      "relationships": [],
      "materials": [],
      "unresolved": [],
      "buildable_state": "READY"
    }
  ]
}
```

## 5.1 Bắt buộc sửa lỗi kiến trúc hiện tại

Không được còn logic tương đương:

`ignore region granularity`

ở V2.

Nếu V1 vẫn cần legacy, để nguyên V1 nhưng V2 phải dùng Region Graph/Geometry Ledger đầy đủ.

## 5.2 READY gate

`READY` chỉ khi:

- envelope đủ;
- region hierarchy đủ;
- mọi geometry relation cần để build đều có bằng chứng hoặc approved derived state;
- không còn ambiguity ảnh hưởng trực tiếp geometry;
- pre-build projection verifier có thể tạo projection hypothesis.

Nếu chưa đủ chiều sâu/chiều dày nào đó:
- không đoán;
- giữ `REVIEW_REQUIRED`;
- có thể build guide/placeholder chỉ khi user/policy cho phép rõ ràng và phải label placeholder.

---

# 6. BUILD IR V2

Tạo:

`OUTPUT/MODEL/build-ir-v2.json`

Build IR V2 phải là semantic source of truth cho geometry execution.

Không chỉ có:

`part_id + width/depth/height + origin`

mà phải giữ:

- item envelope;
- regions;
- subregions;
- transforms;
- relationships;
- material bindings;
- source refs;
- verification expectations.

Suggested structure:

```json
{
  "schema_version": 2,
  "status": "READY",
  "operations": [
    {
      "operation": "create_item_assembly",
      "item_code": "VN-1",
      "regions": [],
      "relationships": [],
      "materials": [],
      "source_refs": [],
      "verification_contract": {}
    }
  ]
}
```

Có thể dùng multiple semantic operations nếu sạch hơn, ví dụ:

- `create_item_envelope`
- `create_region`
- `apply_region_material`
- `apply_relationship`
- `finalize_item`

Nhưng production executor phải deterministic và không eval arbitrary Ruby.

---

# 7. PROJECTION VERIFICATION — PRE-BUILD

Đây là hard gate mới.

Tạo:

`pipeline/stages/projection_verification_v2.py`

và artifact:

`OUTPUT/VERIFICATION/projection-prebuild-v2.json`

Verifier phải lấy Geometry Ledger V2 / Region Graph V2 / ModelSpec V2 và kiểm tra projection logic trước khi SketchUp write.

## 7.1 Các projection role

Ít nhất:

- front/elevation → X×Z
- side/section → Y×Z
- plan nếu có → X×Y
- local detail → subset/refinement

## 7.2 Kiểm tra VN-1

Automated expectations tối thiểu:

- front overall: X = 8000, Z = 1100;
- lower visible region: 800;
- upper visible region: 300;
- section hierarchical spans explain `750 + 50 + 300`;
- 50 mm không được sinh thành một visible front band nếu source không chứng minh;
- material regions không bị swap;
- mọi expected view có evidence mapping.

Nếu pre-build projection fail:
- Build IR V2 không được execute.

---

# 8. SKETCHUP EXECUTION GATE

Tạo một execution path riêng cho V2, ví dụ:

`ai_dg_execute_build_ir_v2`

hoặc nâng executor hiện tại nhưng phải version/gate rõ ràng.

## 8.1 Cấm bypass

Trong `drawing_reconstruction` mode/profile:

- raw geometry write tools không được expose cho agent;
- chỉ executor V2 được quyền write.

Nếu Codex cố gọi raw write:
- trả `DRAWING_PIPELINE_REQUIRED`.

## 8.2 Target instance

Trước write phải xác minh:

- target SketchUp instance;
- instance online;
- write mode enabled;
- source review approved;
- Build IR V2 READY;
- pre-build projection PASS.

---

# 9. POST-BUILD READ-BACK + PROJECTION VERIFICATION

Sau khi dựng SketchUp:

1. Đọc lại model bằng official Ruby API.
2. Thu:
   - item/region bounds;
   - transforms;
   - materials;
   - hierarchy;
   - persistent IDs;
   - entity count delta.
3. Tạo:

`OUTPUT/VERIFICATION/sketchup-readback-v2.json`

4. Project read-back geometry về các view logic:
   - front;
   - side/section;
   - plan khi có.

5. So với contract từ pre-build.

Artifact:

`OUTPUT/VERIFICATION/projection-postbuild-v2.json`

Nếu mismatch:
- status `FAIL`;
- không được ghi completion PASS;
- nếu fixture/test-owned model thì rollback/undo operation.

---

# 10. VN-1 GOLDEN TESTS

Tạo fixture riêng, ví dụ:

`tests/fixtures/vn1/`

Bao gồm expected facts/schema, không hard-code vào production.

## Test A — interpretation only

Input PDF → Drawing Index/View Linking.

Không chạm SketchUp.

PASS khi các view chính của VN-1 được linked vào cùng item.

## Test B — Geometry Ledger V2

Không chạm SketchUp.

PASS khi:
- 8000 overall X;
- 1100 overall Z;
- 800 lower;
- 300 upper;
- 750 + 50 refines lower 800;
- source refs có thật;
- không có conflict giả.

## Test C — Region Graph V2

Không chạm SketchUp.

PASS khi:
- lower/upper region là spatial regions của cùng VN-1;
- 50 mm là refinement/subregion có đúng visibility/state;
- không biến thành independent visible plank nếu chưa có bằng chứng.

## Test D — ModelSpec V2

Không chạm SketchUp.

PASS khi hierarchy/relationships không bị mất.

## Test E — Build IR V2

Không chạm SketchUp.

PASS khi Build IR chứa semantic regions/relationships, không collapse thành hai generic boxes/panels.

## Test F — Pre-build projection

Không chạm SketchUp.

PASS toàn bộ view contracts.

## Test G — Live SketchUp

Chỉ chạy sau A→F PASS.

- Chọn explicit SketchUp target.
- Dựng VN-1.
- Read-back.
- Verify post-build projection.

## Test H — Negative regression

Cố đưa dữ liệu thiếu/ambiguous.

Expected:
- `REVIEW_REQUIRED`
- không write SketchUp.

---

# 11. ACCEPTANCE GATES

Không được báo hoàn thành nếu thiếu bất kỳ mục nào:

### Architecture
- [ ] Geometry Ledger V2 tồn tại.
- [ ] Region Graph V2 tồn tại.
- [ ] ModelSpec V2 không mất region granularity.
- [ ] Build IR V2 giữ semantic relations.
- [ ] Projection Verification pre-build tồn tại.
- [ ] Projection Verification post-build tồn tại.
- [ ] Drawing reconstruction không bypass bằng raw write tools.

### VN-1
- [ ] 8000 overall length đúng.
- [ ] 1100 overall height đúng.
- [ ] 800 lower region đúng.
- [ ] 300 upper region đúng.
- [ ] 750+50 đúng là refinement của lower 800.
- [ ] 50 mm không bị dựng thành visible band sai.
- [ ] kính 10 mm chỉ được áp khi evidence mapping đúng.
- [ ] material mapping có source refs.
- [ ] front projection PASS.
- [ ] side/section projection PASS.
- [ ] live SketchUp read-back PASS.
- [ ] post-build projection PASS.

### Safety
- [ ] Không đoán missing dimensions.
- [ ] Không raw write bypass.
- [ ] Không write khi projection precheck FAIL.
- [ ] Không write nhầm SketchUp instance.
- [ ] Không PASS bằng mock/unit-only.

---

# 12. FILES/DOCS PHẢI TẠO

Tạo tối thiểu:

```text
docs/2d3d-v2/
├─ 00_CURRENT_FAILURE.md
├─ 01_GEOMETRY_LEDGER_V2.md
├─ 02_REGION_GRAPH_V2.md
├─ 03_MODELSPEC_V2.md
├─ 04_BUILD_IR_V2.md
├─ 05_PROJECTION_VERIFICATION.md
├─ 06_VN1_GOLDEN_FIXTURE.md
└─ 07_IMPLEMENTATION_STATUS.md
```

`07_IMPLEMENTATION_STATUS.md` phải ghi theo trạng thái:

- REAL
- PARTIAL
- BLOCKED
- NOT_TESTED

Không ghi PASS nếu chưa có evidence.

---

# 13. THỨ TỰ THỰC HIỆN BẮT BUỘC

Không làm song song lộn xộn.

```text
P0 Audit failure
↓
P1 Geometry Ledger V2
↓
P2 Region Graph V2
↓
P3 ModelSpec V2
↓
P4 Build IR V2
↓
P5 Pre-build Projection Verification
↓
P6 Unit/fixture regression VN-1
↓
P7 SketchUp execution gate
↓
P8 Live VN-1 build
↓
P9 Read-back + post-build projection
↓
P10 Regression + docs
```

Chỉ chuyển phase khi phase trước PASS.

---

# 14. BÁO CÁO SAU MỖI PHASE

Sau mỗi phase, báo đúng format:

```text
PHASE:
STATE: PASS / FAIL / BLOCKED

FILES CHANGED:
- ...

EVIDENCE:
- test:
- artifact:
- observed output:

FIRST FAILING CHECK:
- ...

NEXT ACTION:
- ...
```

Không dùng câu kiểu “đã hoàn thiện về cơ bản”.

---

# 15. DEFINITION OF DONE

AI-DG 2D→3D V2 chỉ được coi là DONE khi:

1. VN-1 không còn dựng ra hai thanh/khối song song kiểu hiện tại.
2. Hệ thống chứng minh được **vì sao** geometry được dựng bằng source-backed ledger/graph/spec/IR.
3. Mọi view liên kết được giải thích bởi cùng một 3D hypothesis.
4. Projection pre-build PASS.
5. SketchUp build chạy thật qua MCP.
6. Read-back từ SketchUp khớp Build IR V2.
7. Projection post-build PASS.
8. Không cần prompt đặc biệt kiểu “hãy suy nghĩ kỹ hơn”.
9. Không hard-code VN-1 vào production.
10. Chưa mở rộng sâu sang 2D→3D khác cho tới khi golden fixture này PASS hoàn toàn.

Bắt đầu bằng `docs/2d3d-v2/00_CURRENT_FAILURE.md`.
Không sửa code trước khi audit xong.
