# Material interpretation and spatial mapping rules

## Preserve source codes and complete drawing specifications

Never replace a drawing material code or note with a guessed product. Keep the source wording and map it only when a verified legend, schedule, note, detail or material library supplies the meaning.

Material extraction is **not complete** when AI-dg has only identified a generic family such as `MDF` or `GLASS` while the drawing gives richer specification data.

For each material system, reconcile all linked evidence from:

- material legend / note table;
- leader notes on elevation/plan/section;
- section/detail callouts;
- schedules/specifications;
- CAD/SKP metadata only when actually parseable.

The result must preserve every compatible known property, even when quantity or fabrication readiness is still partial.

Example:

```text
source note: MDF HOÀN THIỆN MELAMINE MÀU GHI SÁNG

core/material: MDF
finish: Melamine
color: ghi sáng
thickness_mm: UNKNOWN unless another verified source states it
```

Example glass system:

```text
legend: KÍNH DÁN DECAL MỜ MÀU XANH NDTH
detail: KÍNH CƯỜNG LỰC DÀY 10MM
        MÀI XIẾT CẠNH 1MM
        KEO SILICONE

material_family: glass
glass_type: kính cường lực
thickness_mm: 10
film_decal: decal mờ màu xanh NDTH
edge_treatment: mài xiết cạnh 1 mm
adhesive_sealant: silicone
```

Do not lose these facts simply because BOM quantities are not ready.

## A material must belong somewhere

Do not treat material extraction as a flat list when the drawing provides enough evidence to locate the material.

For every material, identify when possible:

- host item;
- host assembly/part/region;
- geometric bounds or affected surface;
- material role;
- thickness;
- side/orientation;
- finish;
- color;
- film/decal;
- edge treatment;
- adhesive/sealant;
- source view/detail/legend.

Typical roles:

- `CORE` — MDF, plywood, timber substrate;
- `PANEL` — sheet/board acting as a physical part;
- `GLASS`;
- `SURFACE_FINISH` — laminate, veneer, paint, Melamine finish;
- `FILM_DECAL`;
- `EDGE`;
- `ADHESIVE_SEALANT`;
- `PROFILE_TRIM`;
- `HARDWARE`.

## Spatial mapping example

If elevation identifies a lower grey region and legend states that grey is MDF finished with light-grey Melamine, while the section/detail proves that the region occupies the lower 800 mm envelope, record the material on that lower region.

If the upper region is glass and a detail identifies 10 mm tempered glass plus decal, record:

```text
upper region
├─ glass layer: 10 mm tempered glass
├─ surface layer: matte blue NDTH decal/film
├─ edge treatment: 1 mm edge grinding when stated
└─ joint/sealant: silicone where called out
```

Do not merely report both materials in a register without relating them to the geometry.

## Material specification synthesis is separate from BOM

AI-dg must create:

```text
OUTPUT/TAKEOFF/material-specifications.json
```

before final Excel export for a local project run.

This file synthesizes drawing-backed technical/descriptive properties and is independent from BOM readiness.

A material can therefore be:

```text
SPECIFICATION: READY
QUANTITY: PARTIAL / BLOCKED
```

Known specification properties must still appear in Excel.

Read and apply `references/material-specification-synthesis.md` for the required synthesis method.

## Material boundaries come from linked views

A visible color/hatch boundary in elevation establishes only the projected boundary. Use side/section/detail views to determine its depth, layer thickness and local construction.

Material geometry can be:

- `EXPLICIT` — directly called out/dimensioned;
- `DERIVED_FROM_VIEWS` — constrained by linked projections and material annotations;
- `AMBIGUOUS` — multiple placements remain possible;
- `UNKNOWN`.

## Thickness

Thickness belongs to the physical part/layer record and should be stored in millimetres.

Do not infer thickness from a material family name unless:

- the drawing/detail explicitly states it; or
- a verified project material specification uniquely defines it.

A finish code and a core thickness are different facts.

If thickness is unknown, store `null`/`UNKNOWN`; do not drop the rest of the material specification.

## Core vs finish vs layer

Never collapse these automatically:

```text
MDF MR 18 + Melamine finish
```

into one generic material if the workflow needs fabrication quantities.

Prefer:

```text
core: MDF MR
core_thickness: 18
surface_front: Melamine ...
surface_back: ...
edge: ...
```

when supported.

Likewise:

```text
glass + decal
```

should remain separate physical/material layers if the detail shows them separately, while the Excel-facing material system may summarize their combined specification for readability.

## Quantity follows geometry

Do not calculate material quantities from the material legend alone.

Correct order:

```text
reconstruct physical region/part
→ map material/layer to region
→ synthesize material specification from legend + notes + details
→ determine dimensions/thickness when known
→ calculate area/volume/length/count
```

## Sheet calculation

Sheet counts require known sheet dimensions and part geometry. The deterministic tools may calculate:

- net area from part dimensions;
- required area after an explicit waste factor;
- theoretical sheet count only when a matching library record contains sheet length and width.

Theoretical sheet count is not nesting optimization. Clearly label it as theoretical.

Grain direction, forbidden rotation, face matching and material defects must be handled by a later nesting/cutting engine rather than silently ignored.

## Waste factor

Do not invent waste percentages. Use `waste_factor` from a verified material library or an explicit user/project setting. Default deterministic calculations use zero additional waste when none is supplied.

## Pricing

Material records may contain reference metadata, but the skill must not present a final quotation unless the user supplies a verified price source and a pricing workflow is executed.

Drawing-backed material specification and supplier/commercial product identity are separate. Never turn a drawing description into a guessed brand, product code, supplier or price.
