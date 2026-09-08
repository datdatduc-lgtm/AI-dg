# Next milestone

Updated: 2026-09-04

## Current state

- Current live SketchUp session is PID `48576`, version `23.1.340`, with an unsaved read-only empty model; bridge `127.0.0.1:9876` is online and the Control Center is visible.
- Official Ruby API reads were live and repeatable in the previous session: health, model summary, selection, hierarchy and `Sketchup::View` camera.
- Control Center Chat/Agent, Data Flow, Plugins, Settings and Model Inspector were exercised live.
- Final current acceptance: `27/27 PASS`, graceful reload generation `21`, MCP stdio discovery `PASS` with 77 full-profile tools; default/Cline `minimal` exposes 21/77. Provider traffic remains disabled and model writes remain guarded.
- Factory `Tools/sketchup.rb` remains untouched; no SketchUp restart, save, undo or deletion was forced. See `.codex/DRAWING_PIPELINE.md` for the M2-M9 implementation.
- Build IR is now persisted under each pipeline run and readable codegen is available as JSON/Python/Ruby; only `READY` IR can produce executable codegen.

## Safe next work

1. With explicit user authorization and a concrete model choice (or after the user clicks Sync Models), run exactly one minimal 9Router provider request (`OK`), record only redacted status/latency, then verify the in-plugin Chat path. Until then keep request count at zero.
2. With explicit provider authorization, run one actual Cline in-panel prompt that invokes a read-only AI-DG tool; the enabled Cline config and exact stdio probe already pass without provider traffic.
3. Exercise provider-unavailable/MCP-disconnect UI states only after explicit authorization or a fully local UI injection; the bounded asynchronous state machine and mid-flight controls are already verified.
4. In a separately saved/test-owned model, perform cold-start toolbar and session-reload acceptance.
5. When user-owned SKP files are supplied, run metadata-only analyzer/profile aggregation without writing to D: or adjacent to source files.
6. Run an approved Excel/vector fixture through the persisted Build IR/codegen artifact and inspect the generated representations before any live write.

## Known gates

- Provider network is intentionally `NOT_RUN`; Control Center Python 3.12 sees a credential and endpoint, but production agent chat remains gated until a concrete model is selected and the user explicitly authorizes a real-provider test. The fake-localhost contract test passes without external traffic.
- Cline Nightly is installed and Cline-compatible stdio runtime is verified; only an actual in-panel LLM invocation remains provider-gated.
- Current UI agent is asynchronous; User Mode now calls the real provider helper after explicit network enable, while completion and Pause/Resume/Cancel remain bounded. Provider/MCP external states remain safe-gated.
- Do not modify the current unsaved model or issue `sketchup_create_semantic_item` until the user supplies an approved ModelSpec with explicit parts.

## Recheck note

- Latest UI redeploy is live without restarting SketchUp; acceptance smoke is `27/27 PASS` at generation `21`.
- Chat interaction is now multiline/Enter-to-send with safe message metadata and duplicate-send protection. The remaining provider gate is still a concrete 9Router model ID plus explicit user authorization for one real request.
- Optional Codex CLI backend is now available in the Chat backend selector; it remains `REAL TURN NOT RUN` until the user explicitly authorizes its separate network action. Selecting Codex does not inherit 9Router permission.
- Chat context continuity, quick model selection and actionable helper-error guidance are deployed: both 9Router and Codex CLI receive bounded recent persisted turns with sensitive-token redaction, while Model Manager offers six local-cache suggestions without auto-saving; no external request was made while verifying this change.
- Codex CLI now gets AI-DG MCP automatically for each turn through the workspace wrapper; the wrapper initialize contract passes and global Codex configuration remains untouched. A real read-only Codex turn is still the next externally gated verification.
- Wrapper `tools/list` also passes (21 read-only tools, SketchUp health/selection available), and the UI now shows provider MCP/tool/request trace; next external gate remains one user-authorized real Codex or 9Router turn after credential rotation/model selection.
- If the wrapper is unavailable, Codex now stops before the external turn rather than silently operating without SketchUp access.
