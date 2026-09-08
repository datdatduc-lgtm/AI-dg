# P1 — 2D SOURCES → DRAWING IR

Inputs:
1. DWG/DXF
2. PDF vector
3. Excel
4. PDF scan
5. Image
6. SketchUp 2D linework

Output: `Drawing IR`.

Example:
```json
{
  "source_id":"SRC-001",
  "views":[
    {
      "view_id":"ELEV-A",
      "type":"ELEVATION",
      "dimensions":[],
      "texts":[],
      "profiles":[],
      "references":[]
    }
  ]
}
```

View types:
- PLAN
- ELEVATION
- SECTION
- DETAIL
- SCHEDULE
- MATERIAL_LEGEND
- UNKNOWN

Every critical value must preserve provenance:
- file
- page/sheet
- layer
- source object/text
- confidence

Perspective images are appearance/layout evidence, not default dimension authority.

PASS when at least one controlled PDF/CAD/Excel package becomes traceable Drawing IR.
