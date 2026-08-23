# Material Specification Synthesis

AI-dg must synthesize material specifications from all linked drawing evidence before Excel export. Material specification extraction is independent from BOM readiness: a material can have verified descriptive/technical properties even when fabrication quantity is not ready.

## Evidence sources

For each item, reconcile material facts from all available sources:

1. material legend / note table;
2. leader notes on elevation/plan/section;
3. section/detail callouts;
4. material schedules/specifications;
5. CAD/SKP metadata when actually parseable.

Do not stop at the first material label. Merge compatible facts that refer to the same physical material/layer, while preserving every source reference in JSON/reports.

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
      "source_material_code": null,
      "material_family": "MDF",
      "material_name": "MDF hoàn thiện Melamine màu ghi sáng",
      "role": "CORE/PANEL + SURFACE_FINISH",
      "host_region": "lower body",
      "core": "MDF",
      "finish": "Melamine",
      "color": "ghi sáng",
      "color_hex": null,
      "sample_image": null,
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

## Drawing code vs internal ID

`material_id` is an internal AI-dg identity and must not be shown as the drawing's material code unless the drawing itself contains that code.

Use:

```text
source_material_code
drawing_material_code
material_code
```

only when the source drawing/spec actually provides a code such as `WD-03`, `GL-02`, etc.

If the drawing has no code, the user-facing `Mã VL` cell should remain blank.

## Preserve known facts even when another field is unknown

If a drawing states:

```text
MDF HOÀN THIỆN MELAMINE MÀU GHI SÁNG
```

but does not state MDF thickness, keep:

```text
core = MDF
finish = Melamine
color = ghi sáng
thickness_mm = null
```

Do not discard the entire material record just because thickness is unknown.

Likewise, if a detail states:

```text
KÍNH CƯỜNG LỰC DÀY 10MM
MÀI XIẾT CẠNH 1MM
DÁN DECAL MỜ MÀU XANH NDTH
KEO SILICONE
```

then the synthesized glass record must retain all four facts.

## Material/color swatch extraction

A PDF legend may contain a colored rectangle, hatch or actual material sample beside the text label.

When the runtime can reliably crop that visual from the source, preserve the real source sample as:

```text
OUTPUT/IMAGES/MATERIALS/<material-id-or-code>.png
```

and record the relative path in one of:

```text
sample_image
sample_image_path
legend_sample_image
swatch_image
```

The Excel exporter can embed this image in the `Màu / Mẫu` column.

Do not generate a synthetic swatch and present it as if it came from the PDF. If only text such as `màu ghi sáng` is known, keep the text. If an exact `color_hex` is extracted/verified, the exporter may use it as a cell fill.

## VN-1 acceptance expectation

For the VN-1 drawing, material interpretation should preserve at minimum:

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

If the legend swatches are extracted successfully, store their actual crops for Excel use.

## Material identity vs commercial product

Drawing specification is not the same as supplier/product identification.

Do not convert `MDF hoàn thiện Melamine màu ghi sáng` into a guessed brand/product code. Supplier/brand/product data belongs to supplier research and must retain verification/source URLs in procurement data, not the normal material summary.

## User-facing Excel gate

The normal material workbook is concise. It should not expose all internal specification fields as separate technical columns.

The primary `VAT_LIEU` sheet should surface the practical subset:

```text
Hạng mục / Chi tiết
Mã VL
Vật liệu / Quy cách
Dày (mm)
Màu / Mẫu
Khối lượng (m²)
Tấm 1200×2400
Ghi chú
```

Technical provenance/status/source fields remain available in `material-specifications.json` and reports.

Before the material workbook is considered complete:

- every relevant legend entry must appear in `material-specifications.json` or be explicitly unresolved;
- linked detail notes must enrich the corresponding material/layer record;
- known material descriptions, thicknesses and colors must survive into the concise `VAT_LIEU` row;
- missing thickness/price/supplier data must remain blank/dash rather than causing known properties to disappear.
