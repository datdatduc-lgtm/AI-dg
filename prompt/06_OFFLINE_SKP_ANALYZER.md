# P1 — OFFLINE SKP ANALYZER

Goal:
read old `.skp` files without opening SketchUp one-by-one.

Architecture:
```text
SKP
→ offline reader
→ Model IR
→ metadata/code representation
→ index / user workflow profile
```

For `D:\*.skp`:
READ ONLY.
Never save/rewrite/rename/move/delete/create sidecar.

Derived outputs go to:
```text
E:\AI-DG\SKP_INDEX\
E:\AI-DG\USER_PROFILE\
```

Model IR is internal source of truth, not generated Python/Ruby alone.

Model IR should capture:
- components/groups
- hierarchy
- materials
- tags
- scenes
- dimensions/bounds
- dynamic attributes when available
- naming patterns

Generate optional representations:
- Python
- Ruby
- JSON
- TypeScript

Cross-check at least one offline parse against the same model read live in SketchUp.

PASS only if source SKP remains unchanged.
