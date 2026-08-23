# SketchUp Ruby Prototype Method

AI-dg should test small, evidence-backed SketchUp reconstructions with plain Ruby **before** packaging reconstruction into a SketchUp plugin.

The goal of a prototype is not to pretend the drawing is fabrication-complete. The goal is to prove that the Geometry Ledger can be converted into SketchUp geometry without losing provenance or inventing missing construction.

## 1. Separate three readiness states

Do not use one generic `NOT READY` result.

### Component Geometry Readiness

Can AI-dg reconstruct the local 3D shape of one item/component from the available views?

Possible states:

- `READY`
- `PARTIAL_READY`
- `BLOCKED`

A missing project plan/CAD does **not** automatically block local component reconstruction.

### Project Placement Readiness

Can the component be placed at the correct project-space anchor, rotation and elevation?

This normally requires plan/CAD/SKP placement evidence.

### Project Quantity Readiness

Can the drawing package prove how many physical instances of the component exist in the project?

A detail sheet showing one item type does not prove project quantity = 1.

## 2. Separate takeoff readiness levels

Use independent readiness rows:

- `GEOMETRY_TAKEOFF`
- `MATERIAL_REGION_TAKEOFF`
- `FABRICATION_PART_BOM`
- `PROJECT_QUANTITY`
- `PROCUREMENT_BOM`

Example: a drawing may support the area of a glass region while still being insufficient to determine every fabricated MDF panel or the total number of item instances in the project.

## 3. Prototype only from the Geometry Ledger

Ruby geometry must come from a normalized reconstruction record, never by copying random dimensions directly from a PDF view.

Required logical inputs:

```text
item_id
local_axes
region geometry
material spatial map
derivation state
source evidence
review flags
```

Every modeled group/component should retain AI-dg attributes describing these fields.

## 4. Allowed modeling states

A Ruby prototype may create geometry with these statuses:

- `EXPLICIT` — directly dimensioned/stated;
- `DERIVED_FROM_VIEWS` — constrained by linked projections;
- `REVIEW_REQUIRED` — a geometric hypothesis useful for testing but still awaiting confirmation;
- `PLACEHOLDER_GUIDE` — non-fabrication guide geometry used only to visualize an unresolved zone.

Do not convert `AMBIGUOUS` or `UNKNOWN` facts into fabrication solids without marking them as review/guide geometry.

## 5. VN-1 prototype strategy

For the VN-1 acceptance drawing, the current geometry-first read supports the following local model test:

```text
X = 8000 mm
Z = 1100 mm
lower region = 800 mm
  ├─ lower subregion = 750 mm
  └─ transition subregion = 50 mm
upper visible glass region = 300 mm
glass thickness = 10 mm
local CT1 depth stack = 14 + 12 + 14 = 40 mm
top corner radius = R50
```

The relationship `750 + 50 = 800` is a `DIMENSION_REFINEMENT`.

The Ruby prototype may use the 40 mm CT1 stack as a **review-required local depth hypothesis** if the side/detail views support the same span. It must not claim that this proves the complete lower-body fabrication build-up.

The central 12 mm CT1 zone may be visualized as a guide/seat zone. If the drawing image clearly constrains the 10 mm glass inside that 12 mm zone, the glass position may be modeled as `DERIVED_FROM_VIEWS`; otherwise keep the Y offset review-required.

## 6. Prototype object hierarchy

Prefer a clean hierarchy such as:

```text
AI-DG_TEST_VN-1
├─ LOWER_BODY_ENVELOPE
├─ TRANSITION_LEFT_LAYER
├─ TRANSITION_RIGHT_LAYER
├─ CT1_SEAT_ZONE_GUIDE
└─ UPPER_GLASS
```

Names are semantic and should match the Geometry Ledger. Do not use anonymous groups.

## 7. Preserve provenance inside SketchUp

Use SketchUp AttributeDictionary data on the root and important child groups.

Recommended dictionary: `AI_DG`

Recommended keys:

```text
item_id
status
source
geometry_role
material_role
review_required
notes
```

This makes the generated model auditable and prepares the future plugin architecture.

## 8. Never require project placement for a local prototype

A component can be reconstructed at local origin `(0,0,0)` even when project anchor/rotation/quantity are unknown.

Report separately:

```text
Component Geometry: PARTIAL_READY or READY
Project Placement: BLOCKED / UNKNOWN
Project Quantity: BLOCKED / UNKNOWN
```

## 9. Projection-back gate for Ruby

After generating the local component, compare its dimensions/projections against the Geometry Ledger:

- front projection;
- side projection;
- relevant section/detail;
- material region boundaries.

The Ruby prototype passes only if the generated geometry explains the same linked views within the evidence actually available.

## 10. Prototype before plugin

Development order:

```text
single drawing
→ Geometry Ledger
→ one standalone .rb prototype
→ load in SketchUp Ruby Console
→ inspect geometry
→ fix reconstruction rules
→ repeat on several drawing types
→ extract reusable Ruby helpers
→ only then package as a SketchUp plugin
```

Do not build the plugin shell first. The reconstruction rules and Ruby geometry API should stabilize through standalone prototypes first.
