# P2 — END-TO-END TEST MATRIX

## Gate A — Live SketchUp
visible window, viewport, axes, 9876, health, ping, reconnect, partial socket.

## Gate B — Provider
rotated key, real request, redaction, model sync, invalid key error.

## Gate C — Real Agent
real provider + tool call + real SketchUp result.

## Gate D — Tool exposure
minimal dynamic tool set.

## Gate E — Offline SKP
read one SKP without opening SketchUp; Model IR; source unchanged.

## Gate F — 2D input
controlled PDF/CAD/Excel → Drawing IR.

## Gate G — Reconciliation
view linking; missing/conflict → Review Queue.

## Gate H — Model Spec
provenance complete.

## Gate I — Build IR
deterministic IR + code representation.

## Gate J — Live 3D
MCP execution → SketchUp viewport.

## Gate K — Verification
actual matches expected.

## Gate L — Rollback
intentional failure rolls back.

## Gate M — Safety
- simulated D write denied
- SKP delete denied
- eval_ruby hidden
- no force-kill
- no system-file edits

Final PASS only when:
```text
2D source
→ Drawing IR
→ Reconciliation
→ Model Spec
→ Build IR
→ MCP live execution
→ SketchUp 3D
→ read-back verification
```
runs end-to-end with real evidence.
