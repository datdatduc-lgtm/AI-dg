# P0/P1 acceptance gates

## Runtime gates

- `codex app-server --stdio` is the Codex production command.
- `cline --acp` is the Cline production command.
- Codex completes `initialize`/`initialized` and `mcpServerStatus/list`.
- Two Codex turns use the same persisted thread ID.
- Cline creates and resumes a real ACP session.
- Cancellation reaches `turn/interrupt` or `session/cancel`.
- No production source calls `codex exec --ephemeral` or a local chat fallback.

## SketchUp gates

- Every SketchUp process owns a fresh instance ID, boot ID and dynamic port.
- `sketchup_list_instances` reports every live process independently.
- With two or more processes, no SketchUp call chooses a target implicitly.
- Model writes require an explicitly selected instance even when only one is online.
- A dead selected target returns `TARGET_OFFLINE` and never falls back.
- Every bridge response contains validated instance/PID/boot/port evidence.
- Both runtimes can call `sketchup_get_selection` through the same AI-DG MCP
  launcher and receive the current official Ruby bridge result.
- Read operations do not change the model or camera.
- A write is denied unless read/write mode and native/user approvals all pass.
- Closing the dialog or SketchUp terminates the host and both child process trees.
- A plugin reload does not modify `sketchup.rb` and does not blank the viewport.

## UI gates

- No `Chat / Agent` tab and no backend/provider selector.
- No API key, token, or raw protocol detail in the normal view.
- Streaming preserves the input box and does not duplicate events on reconnect.
- Cancel, resume, and approval use real runtime IDs.
- Diagnostics show actual failures; they never synthesize success.

## Required checks

- Ruby syntax check for bridge files.
- Python compile check for Agent Host and MCP files.
- JavaScript syntax check.
- MCP discovery and live bridge smoke test.
- Agent Host protocol contract test with fake child processes only in tests.
- Static hard-fail scan for legacy production references.
- Offline two-instance, target-offline and PID-reuse router contracts.
- Live two-SketchUp isolation, visible write/read-back/undo and fail-closed checks.
