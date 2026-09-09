# P0/P1 acceptance gates

## MCP client gates

- The SketchUp extension launches no Codex, Cline, Agent Host or provider process.
- External clients connect through the standard AI-DG MCP stdio launcher.
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
- Write mode can only be enabled through MCP for an exact target and a native confirmation.
- Every model write still requires its own native confirmation.
- A plugin reload does not modify `sketchup.rb` and does not blank the viewport.

## Headless gates

- No AI-DG toolbar, menu, HtmlDialog, chat or settings window is created.
- No UI, icon or embedded-agent runtime is included in the deployed plugin.
- Native dialogs are used only for write-security confirmation.

## Required checks

- Ruby syntax check for bridge files.
- Python compile check for MCP files.
- MCP discovery and live bridge smoke test.
- Static headless-extension smoke test.
- Static hard-fail scan for legacy production references.
- Offline two-instance, target-offline and PID-reuse router contracts.
- Live two-SketchUp isolation, visible write/read-back/undo and fail-closed checks.
