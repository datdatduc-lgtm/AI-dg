# Orthographic Reconstruction Method

AI-dg must read technical drawings as projections of the same physical object, not as independent tables of dimensions.

The purpose of this method is to reconstruct a **geometric hypothesis** for each item from plan/elevation/side/section/detail views before quantity takeoff.

## 1. Establish one object coordinate frame

For every physical item, define a logical local frame:

- `X` = item length / width along the main elevation;
- `Y` = depth / thickness perpendicular to the main elevation;
- `Z` = height.

If a drawing uses another orientation, map the views into this local frame and record the mapping. Do not assume that a number belongs to X/Y/Z until the view orientation and dimension line establish it.

## 2. Assign each view a projection role

Typical mappings:

- front elevation: `X × Z`;
- side elevation: `Y × Z`;
- plan/top view: `X × Y`;
- transverse section: usually `Y × Z`;
- longitudinal section: usually `X × Z`;
- detail: a local subset of one or more axes.

A section can expose hidden layers, offsets and material thicknesses that are not visible in the elevation.

## 3. Build envelopes before parts

First reconstruct the item envelope:

```text
overall X
overall Y
overall Z
```

Then reconstruct regions inside that envelope.

Do not treat every chained dimension as a competing overall dimension. Technical drawings often use **hierarchical dimensions**.

Example:

```text
Elevation: lower zone 800 + upper zone 300 = total 1100
Section:   750 + 50 + 300 = total 1100
```

If the section geometry shows that `750 + 50` occupies the same lower envelope that the elevation labels as `800`, record:

```text
lower_envelope_Z = 800
  ├─ subregion_Z = 750
  └─ subregion_Z = 50
upper_envelope_Z = 300
overall_Z = 1100
```

This is a **DIMENSION_REFINEMENT**, not a mismatch.

Only flag a dimensional conflict when two sources claim different values for the **same geometric span**.

## 4. Compare spans, not numbers

Before declaring MATCH/MISMATCH, identify the endpoints of each dimension conceptually:

```text
from: item bottom
 to: top of lower body
value: 800
```

versus:

```text
from: item bottom
 to: underside of intermediate rail
value: 750
```

These are different spans even when they lie on the same axis.

A reconciliation record must therefore include:

- axis;
- start reference;
- end reference;
- value;
- source view;
- whether it is overall / region / subregion / thickness / offset / gap.

Never reconcile numbers by arithmetic alone.

## 5. Infer geometry only from constrained projections

AI-dg is allowed to derive geometry when the derivation is constrained by multiple drawing views.

Allowed example:

- elevation proves width and height of a panel region;
- side/section proves its depth;
- detail proves a 10 mm glass thickness;
- material annotation points to that same region.

Then a 3D region can be recorded as `DERIVED_FROM_VIEWS` with all supporting sources.

This is not fabrication.

Not allowed:

- guessing an unseen depth because cabinets are "usually 600";
- assigning a board thickness from trade habit;
- assuming a hidden support exists with no drawing evidence.

Use the states:

- `EXPLICIT` — directly dimensioned/stated;
- `DERIVED_FROM_VIEWS` — geometrically constrained by linked views;
- `AMBIGUOUS` — multiple geometric interpretations remain;
- `UNKNOWN` — insufficient evidence.

## 6. Reconstruct material volumes and surfaces

A material is not only a legend entry. Map each material to a geometric region, solid, layer or surface.

For every mapped material, attempt to identify:

- host item/assembly;
- region or part name;
- X/Y/Z extent or boundary;
- whether it is a solid/core, sheet/panel, surface finish, edge, film/decal, glass layer, adhesive or hardware;
- thickness when explicitly shown;
- front/back/edge orientation when relevant;
- source views that establish the mapping.

Example:

```text
VN-1
├─ lower body envelope Z=0..800
│  ├─ MDF/Melamine region
│  └─ local 50 mm subregion if section/detail proves it
└─ upper region Z=800..1100
   └─ glass + decal system
```

Do not stop at a Material Register if the drawing provides enough evidence to place the material spatially.

## 7. Use section/detail to refine, not merely annotate

When a section/detail cuts through an item, use it to update the 3D hypothesis:

- split an envelope into subregions;
- locate material layers;
- identify offsets and recesses;
- determine thickness/depth;
- identify which surfaces meet;
- identify local profiles/radii/joints.

The resulting model should explain why the elevation, side and section all look the way they do.

## 8. Generate a Geometry Ledger

For each item, produce a compact ledger before BOM:

```text
Item: VN-1
Envelope:
  X: ... [source]
  Y: ... [source/derived]
  Z: ... [source]
Regions:
  R1: bounds / material / evidence
  R2: bounds / material / evidence
Dimensional hierarchy:
  overall -> region -> subregion -> thickness/offset
Unresolved geometry:
  ...
```

If the Geometry Ledger cannot explain all linked views, the item is not ready for detailed takeoff or reconstruction.

## 9. Projection consistency gate

A geometric hypothesis passes only if it can be projected back into the available views without contradiction.

Check:

- front projection matches elevation widths/heights;
- side projection matches depth/height;
- plan projection matches footprint;
- section cuts match internal layering;
- detail geometry is compatible with the parent region.

If a hypothesis explains one view but contradicts another, keep it `AMBIGUOUS` or create a conflict.

## 10. Takeoff follows geometry

Detailed quantity takeoff must be based on reconstructed physical regions/parts, not isolated dimensions.

Correct order:

```text
link views
→ reconstruct envelope
→ reconstruct regions/parts
→ place materials on regions
→ validate projections
→ calculate quantities
```

Never perform detailed BOM directly from a single elevation when sections/details provide additional construction geometry.