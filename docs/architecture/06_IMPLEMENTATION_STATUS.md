# Native runtime implementation — 2026-09-08

## Delivered

- Persistent Python Agent Host; Ruby/Open3 IPC runs on worker threads.
- Codex App Server initialize, native threads/turns, resume, interrupt and MCP status.
- Cline ACP initialize, session/new/load/prompt, Plan/Act, native permission options and cancel.
- Cline 3.0.61 installed on the test machine; asynchronous production installer and local-prefix fallback included.
- Runtime-owned session mapping only. Resume errors preserve the existing mapping.
- Five primary UI tabs; streaming leaves the draft intact and groups deltas by item.
- Old provider, one-shot Codex and transcript implementations moved to `legacy/` and removed from production imports/tool registry.
- Model writes require enabled write mode and a SketchUp confirmation; native runtime approvals remain interactive.
- Original SketchUp `sketchup.rb` is outside deployment targets.

## Observed checks

- Ruby syntax, Python unit contracts, JavaScript syntax and headless Edge DOM checks passed.
- Real Ruby client opens the Python host, exchanges host/status and shuts it down.
- Both real runtimes completed two consecutive turns with unchanged runtime PID and session/thread ID.
- Both real runtimes resumed their sessions after a turn.
- Codex turn/interrupt and Cline session/cancel passed; Cline reported `cancelled`.
- Both agents called `sketchup_get_selection` through AI-DG MCP with native permission responses.
- Codex readback returned `count: 0, items: []`; the current SketchUp document is empty.
- MCP acceptance passed against SketchUp 23.1.340, including official view/model reads, graceful runtime reload and read-only/system-file guards.
- Protocol cleanup passed with no orphan Agent Host from the successful probes.
- Native JSONL permits bounded 16 MiB catalogues; UI messages remain bounded to 1 MiB.
- Ruby now binds an OS-assigned loopback port and publishes a per-process
  heartbeat/identity file; MCP target selection is sticky and fail-closed.
- Agent Host runtime/session files and embedded MCP targets are scoped to the
  owning SketchUp instance.
- Offline contracts cover multiple instances, explicit write targeting,
  target death and PID reuse without fallback.
- The running SketchUp 23.1.340 bridge was upgraded in place and registered as
  `su-32644-48d19cbb55d7`; live MCP acceptance returned matching PID/boot/port
  target evidence for model, selection and native Codex/Cline tool calls.

## Remaining manual acceptance

- Select a known component and compare both agents' returned dimensions to SketchUp.
- Visually confirm viewport and interaction after opening the updated dialog and after restarting SketchUp. Native desktop UI control was unavailable in the execution environment; API health is not visual proof.
- Exercise close/reopen and document switching interactively in SketchUp with an unsaved model.
- Complete the two-live-SketchUp target A/B write, read-back, undo and process-death matrix.
- Restart/open a fresh SketchUp process and confirm its newly loaded bridge uses
  an OS-assigned port rather than the bootstrapped legacy process's port 9876.

These manual checks are not represented as PASS. The 2D/3D pipeline is preserved,
and deeper 2D→3D work remains gated on the complete acceptance checklist.

## Reproduce

Run from the repository root:

```text
python -m unittest agent_host.test_host
python agent_host/real_contract_smoke.py
python agent_host/native_session_smoke.py
python agent_host/cancel_smoke.py
ruby agent_host/ruby_client_smoke.rb
node agent_host/ui_dom_smoke.cjs
python mcp_server/tool_exposure_smoke.py
python mcp_server/acceptance_smoke.py
python mcp_server/multi_instance_acceptance.py <instance-a> <instance-b>
```

The DOM test requires Playwright and Edge. Live tests require authenticated native
runtimes and an online SketchUp bridge. The selection probe permits only the
specific read-selection permission it requests and denies unrelated requests.
