# Material Specification Synthesis

AI-dg must synthesize material specifications from all linked drawing evidence before Excel export. Material specification extraction is independent from BOM readiness: a material can have verified descriptive/technical properties even when fabrication quantity is not ready.

## Evidence sources

For each item, reconcile material facts from all available sources:

1. material legend / note table;
2. leader notes on elevation/plan/section;
3. section/detail callouts;
4. material schedules/specifications;
5. CAD/SKP metadata when actually parseable.

Do not stop at the first material label. Merge compatible facts that refer to the same physical material/layer, while preserving every source reference.

## Required output

Write:

```text
OUTPUT/TAKEOFF/material-specifications.json
```

Recommended structure:

```json
{
  "schema_version": "0.1",
  "materials": [
    {
      "item_code": "VN-1",
      "material_id": "VN-1-MDF-LOWER",
      "material_family": "MDF",
      "material_name": "MDF hoàn thiện Melamine màu ghi sáng",
      "role": "CORE/PANEL + SURFACE_FINISH",
      "host_region": "lower body",
      "core": "MDF",
      "finish": "Melamine",
      "color": "ghi sáng",
      "thickness_mm": null,
      "glass_type": null,
      "film_decal": null,
      "edge_treatment": null,
      "adhesive_sealant": null,
      "spec_text": "MDF hoàn thiện Melamine màu ghi sáng",
      "status": "EXPLICIT",
      "sources": []
    }
  ]
}
```

## Preserve UNKNOWN instead of dropping facts

If a drawing states `MDF HOÀN THIỆN MELAMINE MÀU GHI SÁNG` but does not state MDF thickness, keep:

```text
core = MDF
finish = Melamine
color = ghi sáng
thickness_mm = null / UNKNOWN
```

Do not discard the entire material record just because thickness is unknown.

Likewise, if a detail states:

```text
KÍNH CƯỜNG LỰC DÀY 10MM
MÀI XIẾT CẠNH 1MM
DÁN DECAL MÀU XANH NDTH
KEO SILICONE
```

then the synthesized glass record must retain all four facts. Glass, decal, edge treatment and silicone may remain separate physical roles in `material-regions.json`, but the Excel-facing specification should also present them together as the complete material system for the relevant glass region.

## VN-1 acceptance expectation

For the current VN-1 drawing, the material workbook must not reduce the source to only generic `MDF` and `GLASS` rows.

At minimum it should preserve:

```text
MDF system:
- material/core: MDF
- finish: Melamine
- color: ghi sáng
- thickness: UNKNOWN unless another verified source states it

Glass system:
- type: kính cường lực
- thickness: 10 mm
- decal/film: mờ màu xanh NDTH
- edge treatment: mài xiết cạnh 1 mm
- sealant: silicone
```

## Material identity vs commercial product

Drawing specification is not the same as supplier/product identification.

Do not convert `MDF hoàn thiện Melamine màu ghi sáng` into a guessed brand/product code. Supplier/brand/product data belongs to supplier research and must retain verification/source URLs.

## Excel gate

Before a material workbook is considered complete:

- every material legend entry must appear in `material-specifications.json` or be explicitly marked unresolved;
- linked detail notes must enrich the corresponding material/layer record;
- Excel must expose the synthesized specification fields, even when BOM quantity is partial;
- missing thickness/price/supplier data must remain explicit UNKNOWN/blank, not cause known descriptive properties to disappear.
