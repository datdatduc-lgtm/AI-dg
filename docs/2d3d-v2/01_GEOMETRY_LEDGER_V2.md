# Geometry Ledger V2

Schema 2 giữ coordinate frame, nhiều view trên cùng sheet, semantic dimension spans, source references, region/subregion và dimensional hierarchy. Nó không reconcile bằng numeric equality.

Production contract nằm tại `pipeline/stages/geometry_ledger_v2.py`. Fixture VN-1 nằm riêng dưới `tests/fixtures/vn1/`; không có item-specific constant trong production.

VN-1 invariant:

- `800 + 300 = 1100`;
- `750 + 50 = 800`;
- span 50 mm mang `visibility=SECTION_ONLY` và không tự sinh visible region;
- Y/depth chưa đủ bằng chứng vẫn là unresolved.
