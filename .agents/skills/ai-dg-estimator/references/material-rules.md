# Material interpretation and spatial mapping rules

## Preserve source codes

Never replace a drawing material code with a guessed product. Keep the source code exactly as shown, then map it only when a verified legend, schedule, note, detail or material library supplies the meaning.

Example:

```text
source_material_code: WD-03
resolved_finish: Oak veneer
```

Only set a normalized material identity when evidence supports the mapping.

## A material must belong somewhere

Do not treat material extraction as a flat list when the drawing provides enough evidence to locate the material.

For every material, identify when possible:

- host item;
- host assembly/part/region;
- geometric bounds or affected surface;
- material role;
- thickness;
- side/orientation;
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
└─ surface layer: decal/film
```

Do not merely report both materials in a register without relating them to the geometry.

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

should remain separate physical/material layers if the detail shows them separately.

## Quantity follows geometry

Do not calculate material quantities from the material legend alone.

Correct order:

```text
reconstruct physical region/part
→ map material/layer to region
→ determine dimensions/thickness
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
