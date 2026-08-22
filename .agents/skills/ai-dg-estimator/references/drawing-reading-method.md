# AI-dg Drawing Reading Method

This reference defines the reading order for interior/joinery/CNC drawing packages. The goal is not to summarize pages independently; the goal is to reconstruct the logical design and preserve evidence.

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
- elevation;
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
- vanity;
- counter;
- shelf system;
- door/panel assembly;
- decorative joinery assembly.

Prefer explicit item codes and names. If an item has no explicit code, create a temporary internal identifier and mark it for review.

## 4. Link views before counting

A plan, elevation, section, and detail can describe the same physical item.

Example:

```text
TB-01
├─ plan P-02
├─ elevation E-03
├─ section A-A
└─ detail D-17
```

Do not count those as four objects.

Use evidence such as:

- shared item code;
- matching dimensions;
- section callout;
- nearby labels;
- room/zone;
- matching geometry;
- matching material code.

If two views might refer to different items, keep them separate until evidence resolves the relation.

## 5. Read dimensions by role

Separate:

- overall width;
- overall height;
- overall depth;
- panel/part dimensions;
- offsets/gaps;
- thicknesses;
- installation dimensions;
- coordinate/placement dimensions.

Never treat every numeric annotation as a panel size.

For each value, preserve the source view and evidence text/region.

## 6. Use sections/details for construction

Sections and details are often the strongest evidence for:

- depth;
- substrate thickness;
- back panel construction;
- shelves;
- door/front construction;
- junctions;
- edge treatment;
- wall fixing;
- shadow gaps/reveals;
- profile relationships.

However, only extract what is actually shown or stated. Do not add standard cabinet construction from habit.

## 7. Resolve materials through the package

A short code such as `WD-03` may refer to a finish, not a full board specification.

Follow the chain:

```text
part/view annotation
→ material code
→ legend/schedule/specification
→ core/substrate + thickness + surfaces + edge + finish
```

Preserve unresolved distinctions.

## 8. Panel/part decomposition

Only decompose an assembly when the drawing provides enough construction evidence.

A part record should ideally contain:

- item id;
- assembly id;
- part name;
- length/width/thickness;
- quantity;
- core material;
- surface front/back;
- edge treatment;
- grain direction;
- source view(s);
- confidence;
- review status.

If construction is not shown, keep the object at assembly level instead of inventing panels.

## 9. Placement and orientation

When CAD or another machine-readable representation is available, capture:

- insertion/anchor point;
- X/Y/Z;
- rotation;
- footprint;
- room/zone;
- related wall/axis when identifiable.

These values still belong to the same reconciled drawing package and must be checked against PDF labels/geometry where possible.

## 10. Cross-sheet consistency checks

Before takeoff, check at least:

- item codes repeated consistently;
- dimensions agree between views;
- material codes agree between views/schedules;
- section/detail references resolve;
- quantities in schedules agree with identified physical items;
- revision/title information is consistent.

Any unresolved conflict enters the review queue.

## 11. Takeoff gate

An item is ready for detailed takeoff only when:

- it is not a duplicate view of another item;
- required dimensions are known;
- material identity is known to the required level;
- conflicting source values are resolved or explicitly excluded;
- quantity is supported by evidence.

## 12. Reconstruction gate

An item is ready for SketchUp reconstruction only when:

- overall W/H/D are known or the missing axis is intentionally left unresolved;
- placement/orientation is known if the item must be positioned in project space;
- the assembly/part structure is sufficient for the requested modeling level;
- PDF/CAD conflicts affecting geometry are resolved;
- source units and project origin are known.
