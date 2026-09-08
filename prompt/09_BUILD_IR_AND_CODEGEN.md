# P1 — BUILD IR + CODE GENERATION

Build IR is the central representation.

Do not make Python or Ruby the sole source of truth.

Example:
```json
{
  "schema_version":1,
  "operation":"create_cabinet",
  "id":"CAB-A01",
  "size_mm":{"w":1200,"d":600,"h":800},
  "panel_mm":18
}
```

From Build IR generate:
- Python
- Ruby
- JSON command stream
- future TypeScript

Roles:
```text
Python = parse / reason / reconcile / plan / codegen / verify
Ruby   = execute SketchUp API
MCP    = controlled execution bus
```

Prefer semantic builders:
- create_panel
- create_cabinet
- create_partition
- create_shelf
- create_door
- create_drawer
- create_countertop

Avoid LLM generating huge low-level face/edge sequences when semantic tools exist.

PASS when one Model Spec deterministically produces Build IR + readable code representation.
