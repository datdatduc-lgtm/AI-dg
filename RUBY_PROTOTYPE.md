# AI-dg SketchUp Ruby Prototype Test

This phase tests drawing reconstruction with a standalone Ruby file before AI-dg is packaged as a SketchUp plugin.

## Current prototype

```text
.agents/skills/ai-dg-estimator/scripts/sketchup/vn1_prototype.rb
```

Target drawing:

```text
CHI TIET VACH NGAN VN-1.pdf
```

## What the prototype models

Current geometry-first evidence used by the script:

```text
X length = 8000 mm
Z total = 1100 mm
lower region = 800 mm
  ├─ lower base = 750 mm
  └─ transition = 50 mm
upper visible glass = 300 mm
CT1 local stack = 14 + 12 + 14 = 40 mm
glass thickness = 10 mm
top corner radius = R50
```

The relationship `750 + 50 = 800` is treated as `DIMENSION_REFINEMENT`.

The script uses the CT1 `40 mm` stack as a **review-required local depth hypothesis** for prototype visualization. It does not claim that the full lower-body fabrication construction is verified.

The 10 mm glass is visualized centered inside the 12 mm CT1 central zone and is tagged `review_required=true`. Verify this against the source detail before accepting it as fabrication geometry.

## Run in SketchUp

After updating/installing the latest AI-dg skill, open SketchUp and then open:

```text
Window → Ruby Console
```

On the current Windows install path, run:

```ruby
load 'C:/Users/Admin/.agents/skills/ai-dg-estimator/scripts/sketchup/vn1_prototype.rb'
```

Use forward slashes in the Ruby path.

The script automatically runs and creates:

```text
AI-DG_TEST_VN-1
├─ LOWER_BODY_ENVELOPE
├─ TRANSITION_LEFT_LAYER
├─ CT1_SEAT_ZONE_GUIDE
├─ TRANSITION_RIGHT_LAYER
└─ UPPER_GLASS
```

Running the script again replaces only the previous top-level group named `AI-DG_TEST_VN-1`.

## Inspect metadata

Important groups receive an AttributeDictionary named:

```text
AI_DG
```

It contains fields such as:

```text
item_id
status
geometry_role
material_role
review_required
source
notes
```

The root group records separate readiness states:

```text
component_geometry_readiness = PARTIAL_READY
project_placement_readiness = BLOCKED_NO_PLAN_CAD
project_quantity_readiness = BLOCKED_NO_PLAN_SCHEDULE
fabrication_bom_readiness = BLOCKED
```

## What to check visually

Compare the generated model against the drawing:

1. front projection: 8000 × 1100;
2. lower/upper split: 800 / 300;
3. section hierarchy: 750 + 50 + 300;
4. CT1 Y stack: 14 / 12 / 14 = 40;
5. glass thickness: 10;
6. top radii: R50;
7. transition/detail geometry;
8. whether the 10 mm glass placement inside the 12 mm zone matches the actual detail.

If any reconstructed geometry does not reproduce the source view, record it as a methodology failure and fix the Geometry Ledger/rules before expanding the Ruby generator.

## Do not do yet

This prototype must not yet be treated as:

- final SketchUp plugin code;
- verified fabrication model;
- project placement;
- project quantity;
- procurement BOM.

Development order remains:

```text
small drawing
→ standalone Ruby
→ inspect in SketchUp
→ fix reconstruction methodology
→ test more drawing types
→ extract reusable Ruby geometry helpers
→ package the stable helpers into a SketchUp plugin
```
