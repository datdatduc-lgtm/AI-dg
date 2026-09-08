# P0 — REAL AGENT CHAT

Production chat must be real.

Forbidden:
- fixed-response `if prompt == ...`
- fake JS timeout responses
- mock provider shown as connected

Allowed statuses:
- REAL
- DEV_MOCK
- NOT_IMPLEMENTED

Required flow:
```text
SketchUp Chat UI
→ Agent Runtime
→ Real Provider
→ Real Model
→ Tool Call
→ MCP
→ SketchUp
→ Tool Result
→ Real Model
→ User
```

Tests:
1. ask model name
2. ask selected entity dimensions
3. change provider/model and verify trace changed
4. use invalid key and require AUTH_ERROR

If chat still answers under invalid key without an explicit real fallback configured by user, FAIL.

PASS requires end-to-end runtime trace proving real provider + real MCP + real SketchUp data.
