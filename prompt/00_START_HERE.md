# AI-DG 2D→3D — NEXT PHASE

## Current state
- MCP stdio: PASS
- ~75 tools discovered
- Provider Manager implemented, network not yet verified
- Credential previously exposed in tool output: rotate/revoke before any real provider call
- Bridge/UI deployed; source/deploy hash matched
- `sketchup.rb` factory-clean
- `sketchup_eval_ruby` hidden from normal MCP registry
- Current live gate:
  - SketchUp process exists but no main window
  - 127.0.0.1:9876 not listening
  - `sketchup_health = BRIDGE_NOT_READY`

## Target
```text
DIAGNOSE RUNTIME
→ RESTORE LIVE SKETCHUP
→ VERIFY REAL PROVIDER
→ VERIFY REAL AGENT
→ OPTIMIZE MCP TOOL EXPOSURE
→ OFFLINE SKP ANALYZER
→ 2D SOURCE → DRAWING IR
→ RECONCILIATION → MODEL SPEC
→ BUILD IR / CODEGEN
→ MCP LIVE EXECUTION
→ VERIFY / ROLLBACK
```

## Hard safety
- `D:\` READ ONLY unless user explicitly allows otherwise
- never delete `.skp` / `.skb`
- never modify `sketchup.rb`
- no force-kill in normal flow
- no overwrite of production SKP
- no secret in logs/output/source
- `eval_ruby` = DEV ONLY
- HIGH/CRITICAL risk = STOP

Read files in numeric order, then execute `14_CODEX_MASTER_PROMPT.md`.
