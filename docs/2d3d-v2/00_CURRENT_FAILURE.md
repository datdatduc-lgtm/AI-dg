# P0 — Audit lỗi pipeline 2D→3D hiện tại

Ngày audit: 2026-09-09
Golden source được kiểm tra: `INPUT/PDF/CHI TIET VACH NGAN VN-1.pdf`
Phạm vi: source ingestion → Drawing Index → reconciliation/graphs → ModelSpec → Build IR → MCP → Ruby bridge.

## Kết luận

First failing stage là **source ingestion của PDF scan**, trước cả bước suy luận hình học. Artifact thực tế `WORK/pipeline/prompt-20260903-03/packages/SRC-001-CHI TIET VACH NGAN VN-1.json` ghi `text_chars: 0`, `drawing_type: UNKNOWN`, `dimensions: []`, `materials: []`. Vì vậy Drawing Index chỉ tạo `D01 / PDF page 1 / unknown`; Dimension Graph rỗng; ModelSpec và Build Plan rỗng.

Ngay cả khi OCR/text extraction lấy được số, contract hiện tại vẫn fail ở bước kế tiếp: Drawing Index tạo **một entry cho cả trang**. VN-1 có elevation, side, section, CT1 và legend trên cùng trang, nên code không thể tạo các view node riêng hoặc link các hình chiếu cùng tờ. Các tầng sau tiếp tục làm mất vùng, topology và quan hệ kích thước.

File `WORK/geometry/geometry-ledger.json` cũ có mô tả đúng hơn về VN-1 (8000 × 1100; lower 800; upper 300; `750+50=800` là refinement; CT1 `14+12+14`; kính 10 mm), nhưng đây là artifact thủ công/legacy, không được pipeline `runner.py` tiêu thụ. Nó không chứng minh pipeline tự tái dựng được VN-1.

## 1. Information bị mất từ source → facts

- PDF scan trả về không có text, dimension hay material facts. Kết quả quan sát: `dimensions: []`, `materials: []`.
- Không có vùng ảnh/bounding box, đường kích thước, endpoint, extension line, nhãn view, viewport crop hay source reference ở cấp primitive.
- `_dimension_facts_from_package()` chỉ chuyển các số đã trích xuất thành scalar `value_mm`; không giữ geometry của dimension, endpoint, đối tượng được đo, hoặc quan hệ parent/refinement.
- `_assign_dimension_roles()` chỉ suy width/depth/height từ một ký tự axis đã có; không suy axis từ hình chiếu và không khóa coordinate frame của item.

## 2. Region granularity bị mất ở đâu

- `drawing_index.py` lập entry theo `(source_id, page)`, không theo view/region trên sheet. Tất cả view VN-1 trên trang 1 bị dồn vào `D01`.
- `graphs.py` group dimension theo `(item, region, dim)`, nhưng facts từ runner không cung cấp region có cấu trúc; region mặc định trở thành `GLOBAL`.
- `model_spec.py` ghi rõ `Group numeric facts per item+dim (ignore region granularity)`. Đây là điểm mất region có chủ ý trước ModelSpec.
- Vì vậy lower opaque body, upper glass/decal, hidden embed/slot, top/end profile và base support không thể sống xuyên suốt pipeline như các region riêng.

## 3. Relationship/topology bị mất ở đâu

- Dimension Graph 0.1 chỉ có node giá trị và edge `conflicts_with`; không có `adjacent_to`, `contains`, `embedded_in`, `aligned_with`, `touches`, `same_as` hoặc `refines`.
- Reconciliation group theo chuỗi `(fact, axis, span)` và phân loại bằng chênh lệch số. Nó không biểu diễn span endpoints, parent span hay phương trình refinement. Do đó `750+50=800` có thể bị coi là các kích thước cạnh tranh thay vì phân rã của lower 800.
- Material Graph gắn material vào item/role toàn cục, không gắn vào region có bounds và evidence.

## 4. Current ModelSpec không biểu diễn được gì

ModelSpec 0.1 chỉ có envelope width/depth/height và danh sách part box tùy chọn. Nó không biểu diễn được:

- coordinate frame và view projection của item;
- region bounds theo X/Y/Z;
- topology/adjacency/containment giữa các region;
- span hierarchy và refinement (`750+50=800`);
- visible/hidden/embedded classification;
- material assignment có điều kiện theo evidence và region;
- projection expectations cho front/side/section/detail;
- rule “50 mm không trở thành một dải thấy được ở mặt đứng”.

## 5. Current Build IR không biểu diễn được gì

Build IR 1 chỉ phát `create_semantic_item` với một danh sách part hình hộp: dimensions + origin + material. Nó không có operation cho profile/region, slot/embed, glass panel theo section, relation/topology, visibility semantics, coordinate-frame transform hoặc projection constraint.

Validation hiện chỉ kiểm tra operation ID, operation type và source refs; không kiểm tra overlap, gap, region coverage, dimension hierarchy hay consistency với các hình chiếu. Vì vậy một danh sách box hợp lệ về schema vẫn có thể sai hình học VN-1.

## 6. Direct MCP write bypass nằm ở đâu

`mcp_server/tool_exposure.py` đưa toàn bộ raw model-write tools vào profile `build`, gồm `sketchup_create_box`, `sketchup_create_semantic_item`, `sketchup_create_panel`, transform/material/tag và các builder đơn lẻ. Các tool này có thể được gọi trực tiếp sau khi chọn instance và bật write mode, không bắt buộc phải đi qua artifact V2, projection verification hay golden-fixture gate.

`mcp_server/server.py::_single_builder()` còn cho phép tạo một part box từ tham số trực tiếp rồi chuyển thẳng tới `_dispatch_semantic_item()`. Các lớp approval hiện tại bảo vệ **quyền ghi**, nhưng chưa bảo vệ **tính đúng của reconstruction**.

## 7. Vì sao VN-1 có thể thành hai thanh/khối song song

- Nếu lower 800 và chuỗi section `750 + 50` bị flatten thành các scalar độc lập, 50 có thể bị dựng như một part/region nhìn thấy thay vì hidden embed/refinement.
- Build IR không có parent span hoặc visibility semantics để nói “750 và 50 cùng tinh chỉnh lower 800”.
- Ruby bridge dựng mỗi part bằng `Geometry.create_box()` tại `origin_mm`; nó không biết quan hệ giữa các part ngoài các con số đã nhận.
- Read-back chỉ đo bounds của root/part. Verification hiện chủ yếu so envelope width/depth/height, nên hai khối song song vẫn có thể tạo đúng overall bounds và vượt qua kiểm tra envelope.

## 8. First failing stage — evidence

### Check A — Source ingestion

**FAIL.** Artifact production-like gần nhất cho đúng PDF:

- `text_chars = 0`
- `likely_scanned_or_image_only = true`
- `drawing_type = UNKNOWN`
- `dimensions = []`
- `materials = []`

Đây là lỗi đầu tiên theo thứ tự thực thi của `pipeline/stages/runner.py`.

### Check B — Drawing Index / view linking

**FAIL sau A.** Artifact chỉ có một entry `D01`, role `unknown`, `view_links: []`. Contract code cũng chỉ tạo một entry trên mỗi page nên không thể biểu diễn nhiều view cùng sheet ngay cả khi OCR được cải thiện.

### Check C — Graph → ModelSpec → Build

**FAIL dây chuyền.** Dimension Graph có `nodes: []`; ModelSpec có `items: []`; Build Plan có `operations: []`. Execution artifact ngày 2026-09-09 bị chặn ở read-only, nhưng đó không phải first failure và bật write mode không thể phục hồi dữ liệu hình học đã mất.

## P0 gate

P0 audit: **PASS** — first failing stage đã được xác định bằng artifact và source code, không bằng phỏng đoán.
Pipeline implementation: **chưa sửa**.
Phase kế tiếp được phép bắt đầu: **P1 Geometry Ledger V2**.
