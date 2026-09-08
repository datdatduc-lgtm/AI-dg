# CODEX MASTER PROMPT — CONTINUE AI-DG 2D→3D

Project:
`E:\AI-DG`

Mission:
> Build AI-DG as a **Drawing-to-SketchUp Reconstruction Engine with Code-First Live Execution**.

Read all files in this pack in numeric order.

## Current known state
- MCP stdio PASS
- ~75 tools discovered
- provider manager implemented but not network-verified
- old credential exposed in tool output
- bridge deployed
- `sketchup.rb` factory-clean
- `eval_ruby` hidden in normal registry
- live cold-start currently fails: no visible main window / no 9876 / BRIDGE_NOT_READY

## Execute gates in order
1. diagnose cold-start
2. restore live bridge
3. wait for credential rotation, then real provider test
4. prove real agent chat
5. reduce tool exposure
6. build offline SKP analyzer
7. build Drawing IR
8. build reconciliation + Model Spec
9. build Build IR + codegen
10. build live MCP executor
11. build verification + rollback
12. run full end-to-end matrix

## Architecture target
```text
OLD SKP → Offline Reader → Model IR ─┐
                                     ├→ Build IR → MCP → Ruby → SketchUp
PDF/DWG/Excel/Image → Drawing IR → Model Spec ┘
                                      ↓
                                  Verification
```

## Hard invariants
- `D:\` READ ONLY without explicit user permission
- no `.skp` / `.skb` deletion
- no overwrite of production SKP
- no `sketchup.rb` modification
- no force-kill normal flow
- no fake provider/model/chat
- no CONNECTED without real network verification
- no raw secret exposure
- `eval_ruby` DEV ONLY
- no giant model dumps into LLM context
- no guessing missing dimensions/materials/quantities
- missing/conflict → Review Queue
- all writes use transaction + verify
- HIGH/CRITICAL risk → STOP

## Autonomy
After each gate:
- update `.codex/CURRENT_STATE.md`
- update `TEST_RESULTS.md`
- update `FAILURES.md`
- update `RISK_REGISTER.md`
- update `NEXT_PROMPT.md`
- continue automatically if safe

Do not stop at PARTIAL while a safe fix path remains.

Final status may be:
`AI-DG 2D_TO_3D NEXT PHASE = PASS`

only with real evidence for:
```text
2D SOURCE
→ DRAWING IR
→ RECONCILIATION
→ MODEL SPEC
→ BUILD IR
→ MCP
→ SKETCHUP LIVE 3D
→ READ-BACK VERIFY
```
