---
name: AI-DG Selection Reader
description: Read selected SketchUp entity metadata and dimensions without modifying the model.
version: 0.1.0
---

# AI-DG Selection Reader

This is a bounded, read-only skill for the SketchUp bridge.

Workflow:

1. Read the current selection metadata.
2. If there is exactly one selected group or component, report its name,
   persistent ID, bounds, child count, faces, and edges.
3. If the selection is empty or ambiguous, report that state explicitly.

Never write to the model, change selection, save a SketchUp file, or bypass a
permission guard. Do not request full face, edge, or vertex dumps by default.
