# Reconstruction Workflow V3 Status

Cập nhật: 2026-09-10

## Trạng thái đã chứng minh

| Capability | State | Evidence |
|---|---|---|
| Raw PDF orientation + OCR evidence | REAL | VN-1 tự xoay 90°, nhận Việt/Anh, bbox/confidence được lưu |
| Auto View Registry | REAL_FOR_PROFILE_ASSEMBLY | tự nhận front, side, section, detail từ caption |
| Cross-view item link | REAL_FOR_SINGLE_ITEM_SHEET | loại drawing-number một lần xuất hiện khỏi item identity |
| Constraint/profile inference | REAL_FOR_PROFILE_ASSEMBLY | additive height chain, section total/sides/slot, insert thickness/embed, angled R callout |
| Competing hypotheses | REAL | centered/slotted và flush/unslotted cùng đi qua comparator |
| SketchUp profile builder | REAL | arbitrary closed Y/Z profile extrusion, không stack body boxes |
| Native SketchUp geometric view-back | REAL | bounds/regions + slot và top radius đo từ Ruby Edge/Vertex geometry |
| Front/side/section/detail comparator | REAL | mọi mandatory view dùng cùng revision/hash |
| Autonomous repair | REAL | wrong hypothesis FAIL → full-item rebuild → PASS |
| Multiple-instance targeting | REAL | write yêu cầu exact instance identity; nghiệm thu PID 25228 |
| Second raw fixture | REAL_FOR_SAME_FAMILY | RS-2: 2400×60×1000, slot 14×45, insert 12 |
| Per-view camera/section-plane screenshots | NOT_IMPLEMENTED | semantic native geometry là gate hiện tại |
| Pixel/visual comparator | NOT_IMPLEMENTED | chỉ là tầng bổ sung, chưa được dùng để báo PASS |
| Delta rebuild | DEFERRED | full-item atomic replacement đang được dùng |
| Other furniture families | NOT_PROVEN | cần fixture thực tế ngoài profile-assembly family |

Regression: 33 focused tests PASS và 5 instance-router tests PASS. Full pytest
collection cần đúng Python 3.12 dependency runtime; lỗi collection trên Python
3.11 là binary ABI của dependency bundle, không phải test failure.

## Kết luận hiện tại

Milestone yêu cầu đã PASS cho VN-1 và fixture RS-2 mà không sửa JSON trung gian.
Không được diễn giải kết quả này thành engine tổng quát cho tủ, quầy, cửa hoặc
mọi bản vẽ nội thất. Production recognizer hiện mới tổng quát trong family:

```text
extruded body profile + centered inserted panel + slot/embed detail
```

Mở rộng family tiếp theo phải thêm recognizer theo feature topology và chạy lại
cùng raw-source → native-view-back → repair loop, không thêm nhánh theo item code.
