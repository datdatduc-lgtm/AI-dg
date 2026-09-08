# P1 — DRAWING IR → MODEL SPEC

Flow:
```text
Drawing IR
→ view linking
→ Dimension Graph
→ Material Graph
→ conflicts/missing
→ Review Queue
→ Model Specification
```

Link:
PLAN ↔ ELEVATION ↔ SECTION ↔ DETAIL

Do not guess missing:
- dimensions
- materials
- quantity
- construction
- hardware

Missing/conflict:
`REVIEW_REQUIRED`

Example:
```json
{
  "item_id":"CAB-A01",
  "type":"cabinet",
  "width_mm":1200,
  "height_mm":2400,
  "depth_mm":600,
  "panel_thickness_mm":18,
  "source_refs":{},
  "status":"READY"
}
```

Only READY/APPROVED items may enter Build Plan.

PASS when every critical value is linked to source evidence or an explicit derivation rule.
