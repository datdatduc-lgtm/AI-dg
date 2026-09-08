# P1 — LIVE SKETCHUP EXECUTOR

Goal:
AI-generated Build IR appears directly in SketchUp viewport.

```text
Agent/Python
→ Build IR
→ MCP
→ Ruby Bridge
→ SketchUp API
→ live viewport
```

`.skp` is an output/save format, not a required intermediate.

Production must not do:
```text
AI code → arbitrary eval
```

Use controlled handlers.
`sketchup_eval_ruby` = Developer Mode only.

Write flow:
```text
validate Build IR
→ model.start_operation
→ execute
→ read-back verify
→ commit
```

Failure:
rollback/abort.

Later optimize incremental rebuild using stable IDs.

PASS when controlled Build IR creates correct live geometry without freezing SketchUp.
