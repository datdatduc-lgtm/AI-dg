# P1 — REDUCE MCP TOOL EXPOSURE

~75 tools may exist, but normal turns must not receive all schemas.

Capability groups:
```text
CORE
MODEL_READ
DRAWING
BUILD
VERIFY
DEV
```

Example:
"Model đang mở tên gì?"
Expose only:
- sketchup_ping
- sketchup_get_model_info

Use:
```text
intent
→ required capability
→ minimal tool set
```

Skills/tools must lazy-load.

Track:
- tool schemas exposed count
- estimated schema tokens
- tools actually used

`eval_ruby` remains DEV-only.

PASS when functionality remains intact while normal prompts no longer expose full registry.
