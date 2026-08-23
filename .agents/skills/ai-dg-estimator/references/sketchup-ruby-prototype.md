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

## 5. Projection visibility rule

A dimensional refinement seen in section/detail does **not** automatically create a visible edge in another projection.

Before generating a separate Ruby solid/band for a subregion, ask:

```text
Does this boundary appear in the target projection?
```

If a section exposes a recess, groove, embed depth, hidden joint or internal layer inside an otherwise continuous elevation silhouette, the Ruby model must preserve the continuous outer face and place the refined geometry internally.

Wrong pattern:

```text
front elevation says lower region = 800
section says 750 + 50 = 800
→ create two visible stacked solids 750 and 50
```

Correct reasoning can instead be:

```text
front silhouette remains continuous to 800
section reveals a 50-deep hidden feature inside that 800 region
→ create one continuous outer body + internal recess/embed geometry
```

A new visible seam is allowed only when the elevation/plan/side/detail evidence actually establishes that boundary on the visible surface.

This visibility test is mandatory during projection-back validation.

## 6. VN-1 corrected prototype strategy

For the VN-1 acceptance drawing, the linked views support this corrected local hypothesis:

```text
X length = 8000 mm
overall Z = 1100 mm
lower visible body = 800 mm
upper exposed glass = 300 mm
section refinement = 750 + 50 = 800
CT1 overall Y = 14 + 12 + 14 = 40 mm
glass thickness = 10 mm
top corner radius = R50
```

The crucial interpretation is:

```text
50 mm = glass slot/embed depth inside the 800 mm body
```

not:

```text
50 mm = separate visible horizontal transition band
```

Therefore the prototype should model:

```text
LOWER BODY
- continuous visible height: 800
- overall local thickness: 40
- central top slot: 12 wide × 50 deep

GLASS
- thickness: 10
- embedded depth: 50
- exposed height above body: 300
- total modeled glass height: 350
- R50 top corners
```

The 12 mm central slot is symmetric between two 14 mm side zones. A centered 10 mm glass leaves 1 mm on each side. Because the drawing indicates silicone at this joint, that 1 + 10 + 1 arrangement is a useful `DERIVED_FROM_VIEWS` / review hypothesis, but exact silicone bead geometry should not be treated as fabrication-ready unless explicitly detailed.

This corrected geometry should satisfy all three checks:

```text
front: no false horizontal seam at Z=750
side: 40 mm body with 10 mm centered glass
CT1: 14 / 12 / 14 stack with a 50 mm deep glass seat
```

## 7. Prefer profile extrusion for internal slots

When a long item has a constant cross-section, prefer generating one cross-section profile and extruding it along the long axis instead of stacking many overlapping boxes.

For VN-1, a Y/Z profile with the 12 × 50 top notch can be extruded along X=8000. This has two advantages:

- the external 800 mm face remains continuous, avoiding a false Z=750 seam;
- the side/section geometry is encoded directly in the solid profile.

Use separate solids only when they represent genuinely separate physical parts or when the source drawing requires separate material/assembly tracking.

## 8. Prototype object hierarchy

Prefer semantic names based on physical meaning, for example:

```text
AI-DG_TEST_VN-1
├─ LOWER_BODY_WITH_GLASS_SLOT
└─ GLASS_10MM_EMBED_50_EXPOSED_300
```

Do not create a separate `TRANSITION_50` child merely because a section dimension chain contains 50. The name and solid structure must reflect the reconstructed physical role.

## 9. Preserve provenance inside SketchUp

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

For hidden/refined geometry also preserve useful semantic fields such as:

```text
slot_width_mm
slot_depth_mm
glass_embedded_height_mm
glass_exposed_height_mm
projection_back_status
```

This makes the generated model auditable and prepares the future plugin architecture.

## 10. Never require project placement for a local prototype

A component can be reconstructed at local origin `(0,0,0)` even when project anchor/rotation/quantity are unknown.

Report separately:

```text
Component Geometry: PARTIAL_READY or READY
Project Placement: BLOCKED / UNKNOWN
Project Quantity: BLOCKED / UNKNOWN
```

## 11. Projection-back gate for Ruby

After generating the local component, compare its dimensions/projections against the Geometry Ledger:

- front projection;
- side projection;
- relevant section/detail;
- material region boundaries;
- visible vs hidden boundaries.

The Ruby prototype passes only if the generated geometry explains the same linked views within the evidence actually available.

A visible line that does not exist in the authored elevation is a reconstruction failure even if every individual numeric dimension used by the Ruby code is arithmetically correct.

## 12. Prototype before plugin

Development order:

```text
single drawing
→ Geometry Ledger
→ one standalone .rb prototype
→ load in SketchUp Ruby Console
→ inspect front / side / section / detail projections
→ fix reconstruction rules
→ repeat on several drawing types
→ extract reusable Ruby helpers
→ only then package as a SketchUp plugin
```

Do not build the plugin shell first. The reconstruction rules and Ruby geometry API should stabilize through standalone prototypes first.
