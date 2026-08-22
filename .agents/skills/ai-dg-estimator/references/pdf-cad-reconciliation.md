# PDF ↔ CAD ↔ SketchUp Reconciliation

AI-dg treats PDF and CAD as two representations of the same authored drawing package. Optional SketchUp is a third representation to audit or extend.

## Principle

Do not say:

- "PDF is always right";
- "CAD is always right";
- "SketchUp is always right".

Instead ask: **Do these representations agree on the same design state?**

A mismatch can mean:

- different revision;
- stale export;
- stale CAD;
- wrong layout/view matched;
- parser/extraction error;
- dimension association error;
- XREF/reference difference;
- unit/scale problem;
- model reconstruction error.

## Reconciliation levels

### Level A — package identity

Compare:

- project/package name;
- drawing/sheet/layout identifiers;
- revision;
- issue date;
- unit/scale metadata when present.

A revision mismatch is a high-priority blocker for automatic acceptance.

### Level B — view identity

Match PDF sheet regions to CAD layouts/viewports/geometry by:

- sheet/layout name;
- view title;
- item code;
- section/detail label;
- text anchors;
- geometry similarity;
- room/zone.

### Level C — item identity

Match a physical item using a combination of:

- item code/name;
- room/zone;
- overall dimensions;
- nearby text;
- footprint/shape;
- section/detail links.

Never merge items solely because their dimensions match.

### Level D — property consistency

For each matched item compare available properties:

- width;
- height;
- depth;
- quantity;
- material codes;
- thicknesses;
- section/detail references;
- footprint;
- placement;
- rotation.

### Level E — SketchUp audit

When SKP data is readable, compare:

- component/group name;
- bounding dimensions;
- material assignment;
- hierarchy;
- transformation;
- placement/rotation;
- scene/section relationships.

## Status model

Use only these statuses for a comparison row:

- `MATCH` — sources agree within the defined tolerance.
- `MISMATCH` — both sources provide comparable values and they disagree.
- `ONLY_PDF` — value is supported only by PDF.
- `ONLY_CAD` — value is supported only by CAD.
- `ONLY_SKP` — value is supported only by SketchUp.
- `UNREADABLE_SOURCE` — the relevant source exists but the runtime cannot inspect it reliably.
- `REVIEW_REQUIRED` — evidence is ambiguous or matching is uncertain.

`ONLY_*` is not automatically an error. It means cross-source confirmation is unavailable for that property.

## Tolerance

Do not invent a tolerance silently.

For exact authored dimensions such as explicit `1200 mm` labels, compare the authored numeric values exactly unless the project defines another rule.

For geometry-derived measurements, record the measurement method and use a declared tolerance appropriate to extraction/model precision.

Example:

```text
Property: width
PDF explicit DIM: 1200 mm
CAD DIM object: 1200 mm
Status: MATCH
```

Example:

```text
Property: width
PDF explicit DIM: 1200 mm
CAD DIM object: 1150 mm
Status: MISMATCH
Blocker: yes
```

## Conflict handling

When a required value is `MISMATCH`:

1. show both values;
2. show each source reference;
3. check revision/layout/view matching;
4. check whether one extraction is derived instead of explicit;
5. attempt re-read only if evidence supports it;
6. if unresolved, keep the value blocked.

Do not average conflicting values.
Do not use the newest-looking value without revision evidence.
Do not prefer machine-readable CAD over published PDF automatically.

## Placement from CAD

CAD may provide a strong spatial scaffold for SketchUp reconstruction through:

- block insertion point;
- entity coordinates;
- rotation;
- footprint;
- room geometry.

But the placement belongs to the reconciled item. Confirm item identity and drawing state first.

Recommended canonical placement fields:

```text
item_id
source_layout
anchor_x
anchor_y
anchor_z
rotation_deg
project_origin
unit
footprint_reference
reconciliation_status
```

## Required reconciliation report

For each important item, report a compact matrix:

| Property | PDF | CAD | SKP | Status | Evidence |
|---|---|---|---|---|---|
| item code | ... | ... | ... | ... | ... |
| width | ... | ... | ... | ... | ... |
| height | ... | ... | ... | ... | ... |
| depth | ... | ... | ... | ... | ... |
| material | ... | ... | ... | ... | ... |
| placement | ... | ... | ... | ... | ... |

Then create a separate blocker list so critical mismatches are not buried in the table.
