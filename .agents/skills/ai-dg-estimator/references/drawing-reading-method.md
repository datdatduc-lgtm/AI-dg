# AI-dg Drawing Reading Method

This reference defines the reading order for interior/joinery/CNC drawing packages. The goal is not to summarize pages independently; the goal is to reconstruct the physical design from multiple projections and preserve evidence.

## 1. Start with package identity

Before extracting quantities, identify whenever visible:

- project name;
- drawing package name;
- drawing number / sheet number;
- revision;
- issue date;
- drawing title;
- scale;
- unit system;
- author/company if relevant to matching revisions.

Do not combine sheets from different revisions without reporting the revision conflict.

## 2. Build a drawing index first

For each sheet/layout/page, classify visible regions as one or more of:

- plan;
- front elevation;
- side elevation;
- section;
- detail;
- schedule;
- material legend;
- general note;
- specification;
- title block.

Record section/detail labels such as `A-A`, `B-B`, `D01`, `DETAIL 05`, and their callouts.

## 3. Identify physical items

Create one logical item for a real object such as:

- cabinet;
- wardrobe;
- wall panel;
- partition;
- vanity;
- counter;
- shelf system;
- door/panel assembly;
- decorative joinery assembly.

Prefer explicit item codes and names. If an item has no explicit code, create a temporary internal identifier and mark it for review.

## 4. Link views before interpreting dimensions

A plan, front elevation, side elevation, section, and detail can describe the same physical item.

Example:

```text
TB-01
├─ plan P-02
├─ front elevation E-03
├─ side elevation S-01
├─ section A-A
└─ detail D-17
```

Do not count those as separate objects.

Use evidence such as:

- shared item code;
- matching overall dimensions;
- section callout;
- nearby labels;
- room/zone;
- matching geometry;
- matching material code;
- detail leader/callout relationships.

If two views might refer to different items, keep them separate until evidence resolves the relation.

## 5. Establish a local 3D coordinate frame

For each item, map the linked views into one logical frame:

- `X`: main item length/width;
- `Y`: depth/perpendicular direction;
- `Z`: height.

Typical projection roles:

- front elevation: `X × Z`;
- side elevation: `Y × Z`;
- plan/top: `X × Y`;
- section: the cut plane exposes one of those axis pairs plus hidden internal geometry.

Do not assign a number to X/Y/Z merely because it is nearby. Use the dimension line, extension lines, view orientation and geometry.

## 6. Reconstruct the overall envelope first

Determine the item envelope before decomposing it:

```text
overall X
overall Y
overall Z
```

Use all linked views that constrain the same object.

A missing axis can be `UNKNOWN` if the package does not show it. Do not substitute a typical trade dimension.

## 7. Read dimensions by geometric span and role

Classify each dimension as one of:

- overall envelope;
- region;
- subregion;
- panel/part dimension;
- material/layer thickness;
- offset;
- gap;
- installation dimension;
- coordinate/placement dimension;
- radius/profile dimension.

For each dimension preserve:

- axis;
- start reference;
- end reference;
- value;
- source view;
- role.

Never compare raw numbers without first confirming they measure the same span.

### Hierarchical dimension rule

Technical views often refine an overall region.

Example:

```text
Elevation: 800 + 300 = 1100
Section:   750 + 50 + 300 = 1100
```

If the section geometry shows that `750 + 50` occupies the same lower region represented as `800` in elevation, record:

```text
lower region = 800
  ├─ lower subregion = 750
  └─ upper subregion = 50
upper region = 300
overall = 1100
```

Status: `DIMENSION_REFINEMENT`, not `MISMATCH`.

A real mismatch exists only when two sources claim different values for the same endpoints/span.

## 8. Reconstruct regions from projection intersection

After the envelope is known, derive internal regions by intersecting the information from linked views.

Examples:

- elevation defines the X/Z boundary of a region;
- side/section defines its Y depth and internal profile;
- detail defines a local layer/thickness/joint;
- plan defines footprint and positional relationship.

The result should be a 3D geometric hypothesis that explains all available projections.

Derived geometry must be marked `DERIVED_FROM_VIEWS` and cite the views used.

## 9. Use sections/details to refine actual geometry

Sections/details are not just annotations. Use them to modify the reconstructed object:

- split an envelope into subregions;
- locate panels/layers;
- identify recessed/offset portions;
- determine thickness/depth;
- identify glass/board/finish stacking;
- identify local profiles/radii;
- understand junctions and fixing conditions.

Only add geometry that the drawing constrains. Do not add standard cabinet construction from habit.

## 10. Resolve materials and place them spatially

A short code such as `WD-03` may refer to a finish, not a complete board specification.

Follow the chain:

```text
view/part annotation
→ material code
→ legend/schedule/specification
→ material role
→ geometric region/layer/surface
```

Do not stop at `material = WD-03`. Determine, when evidenced, **where the material exists** in the reconstructed item.

Possible roles:

- core/substrate;
- board/panel;
- glass;
- surface finish;
- laminate/veneer;
- decal/film;
- edge band;
- adhesive/sealant;
- hardware.

## 11. Panel/part decomposition follows geometry

Only decompose an assembly when the reconstructed geometry provides enough evidence.

A part record should ideally contain:

- item id;
- assembly id;
- part name;
- local bounds or length/width/thickness;
- quantity;
- core material;
- surface front/back;
- edge treatment;
- grain direction;
- source view(s);
- explicit/derived state;
- confidence;
- review status.

If construction is not shown, keep the object at assembly/region level instead of inventing panels.

## 12. Projection-back validation

Before takeoff, mentally/projectively test the reconstructed item against every linked view:

- does the front projection match the elevation?
- does the side projection match the side/section?
- does the plan projection match the footprint?
- do section cuts reproduce the shown internal layering?
- do details fit inside their parent region?

If one hypothesis cannot explain all linked views, keep it `AMBIGUOUS` or create a conflict.

## 13. Placement and orientation

When CAD or another machine-readable representation is available, capture:

- insertion/anchor point;
- X/Y/Z;
- rotation;
- footprint;
- room/zone;
- related wall/axis when identifiable.

These values belong to the same reconciled drawing package and must be checked against PDF labels/geometry where possible.

## 14. Cross-source consistency checks

Before takeoff, check at least:

- item codes repeated consistently;
- dimensions agree for the **same geometric spans**;
- material codes agree between views/schedules;
- section/detail references resolve;
- quantities in schedules agree with identified physical items;
- revision/title information is consistent;
- CAD geometry/placement agrees with the published PDF where comparable.

Any unresolved real conflict enters the review queue.

## 15. Geometry Ledger gate

Before detailed takeoff, create a Geometry Ledger for each item:

```text
Item
Local axes
Overall envelope
Regions/subregions
Material placement
Dimension hierarchy
EXPLICIT facts
DERIVED_FROM_VIEWS facts
AMBIGUOUS/UNKNOWN facts
Source views
```

If the ledger cannot explain the linked views, the item is not ready for detailed BOM.

## 16. Takeoff gate

An item is ready for detailed takeoff only when:

- it is not a duplicate view of another item;
- linked projections have been reconciled;
- the physical region/part being counted is known;
- required dimensions are explicit or validly derived from linked views;
- material identity is known to the required level and mapped to the part/region;
- conflicting source values affecting quantity are resolved or excluded;
- quantity is supported by evidence.

## 17. Reconstruction gate

An item is ready for SketchUp reconstruction only when:

- its geometric hypothesis explains the available views;
- overall W/H/D are known or the missing axis is intentionally left unresolved;
- placement/orientation is known if the item must be positioned in project space;
- the assembly/part/material structure is sufficient for the requested modeling level;
- PDF/CAD conflicts affecting geometry are resolved;
- source units and project origin are known.
