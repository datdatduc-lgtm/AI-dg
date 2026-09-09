# Headless bridge implementation — 2026-09-09

## Delivered

- The installed SketchUp extension contains only the loader, Ruby bridge and
  geometry helper.
- No toolbar, menu, HtmlDialog, chat, provider manager, embedded Codex/Cline or
  Agent Host is launched by SketchUp.
- External Codex/Cline clients connect through `mcp_server/launcher.py`.
- Every SketchUp process has an independent dynamic loopback port, boot ID and
  heartbeat record. MCP routing is explicit, sticky and fail-closed.
- Read mode is the default. `sketchup_set_write_mode` requires an exact target,
  `confirm=true` and native approval inside that SketchUp process.
- Every actual model write still displays its own native approval prompt.
- The original SketchUp `Tools/sketchup.rb` remains outside all deployment targets.

## Automated acceptance

- Ruby syntax and Python compile checks.
- MCP tool-exposure, disconnect and router unit tests.
- Static headless-package test: no UI/toolbar/embedded-agent source or deployment entry.
- Live read-only MCP acceptance against an exact SketchUp instance.
- External native Codex App Server and Cline ACP selection calls through the
  same MCP endpoint remain supported but are not part of the SketchUp plugin.

## Remaining live gates

- Restart/open a fresh SketchUp process and confirm the installed headless
  bridge binds an OS-assigned port.
- Open two SketchUp processes and complete A/B read isolation.
- Manually approve write mode and the visible write/read-back/undo probe in
  each exact process.
- Confirm the viewport remains interactive after fresh startup and reload.

These live gates must not be marked PASS from mocks or source inspection.

## Reproduce

```text
python -m unittest agent_host.test_host mcp_server.test_instance_router
python mcp_server/headless_bridge_smoke.py
python mcp_server/tool_exposure_smoke.py
python mcp_server/failure_injection_smoke.py
python mcp_server/acceptance_smoke.py
python mcp_server/multi_instance_acceptance.py <instance-a> <instance-b>
```
