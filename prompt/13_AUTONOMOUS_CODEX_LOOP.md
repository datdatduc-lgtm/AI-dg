# AUTONOMOUS CODEX LOOP

Maintain:
```text
E:\AI-DG\.codex\
CURRENT_STATE.md
TEST_RESULTS.md
FAILURES.md
DECISIONS.md
RISK_REGISTER.md
BACKLOG.md
ARCHITECTURE.md
NEXT_PROMPT.md
CHANGELOG.md
```

Loop:
```text
AUDIT
→ FIND FIRST FAILING GATE
→ FIX
→ DEPLOY
→ TEST
→ VERIFY
→ REGRESSION
→ UPDATE STATE
→ NEXT
```

Do not stop merely because:
- syntax passes
- installer passes
- MCP stdio passes
- UI opens
- one ping works
- mock test works
- provider config saved

Continue automatically for LOW/MEDIUM risk with rollback.

STOP for HIGH/CRITICAL:
- writing D:
- delete/overwrite SKP
- unsaved production model + destructive action
- force-kill required
- uncertain secret handling
- system-file modification
- corruption
- payment/purchase
- user decision genuinely required
