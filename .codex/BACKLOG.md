# AI-DG MCP-SU V1 Backlog

## P0 — next

- Keep the live cold-start verification green; current SketchUp PID `48576` is online with bridge port `9876`, and acceptance smoke is `27/27 PASS` at reload generation `5`.
- Keep the test model and do not undo/remove it without confirmation; the post-reload smoke is PASS.
- Reverify the guarded `.skp` analyzer contract and workflow-profile aggregation after the next fresh runtime load; no writes to D:.
- Continue the read-only SKP analyzer/profile check when user-owned SKP inputs are available; no SKP is currently present in `INPUT`.
- Preserve the current unsaved model; no model write, removal or undo is authorized by the current task.
- Provider network test remains gated behind explicit user authorization; do not transmit the discovered credential implicitly.
- Keep `sketchup_eval_ruby` hidden from normal MCP discovery; it remains Developer-only.
- Keep the full SKP analyzer adapter partial until a user-owned SKP is supplied; do not infer or persist raw geometry.
- Keep the default/Cline MCP profile minimal and use explicit `drawing`/`build`/`full` profiles for deeper work; do not claim profile selection is per-prompt dynamic routing.

## P1

- Add remaining skill/plugin action controls in the UI while preserving permission guards; provider recovery actions are now implemented and live-checked.
- Complete the 9Router adapter/model sync only after the key is re-entered into Windows Credential Manager, a model is selected, and explicit authorization is given for the one-request `OK` test; record only redacted status/latency and never print or log secrets. Current helper state is UNCONFIGURED/NOT_RUN.
- Verify provider-backed transport in Control Center Chat after cold-start. User Mode now calls the real provider helper after explicit network enable; Developer Mode diagnostic behavior is explicitly DEV_MOCK.
- Exercise the expanded Sequence/Tool Calls/Agent Steps/Errors views in a safe test harness; Data Flow trace interaction is verified.
- Use the deterministic Build IR artifact as the review boundary: inspect generated JSON/Python/Ruby, then route only approved IR to the controlled executor.

## P2

- Add safe multi-model profile and context/tool capability metadata; capability exposure profiles are now implemented, but model-aware per-intent routing remains future work.
- Add bounded large-model hierarchy paging and selection-aware analysis; the current empty-model bounded response is already covered by the smoke assertion.
- Run one actual Cline in-panel MCP tool task after explicit provider authorization; the Cline config is enabled, the Python 3.12 stdio probe passes with 21 minimal-profile tools (77 in full profile), and no credential has been sent.
