# AI-DG MCP-SU — Current State

Updated: 2026-09-04
Status: PROMPT_PIPELINE_IMPLEMENTED — M2-M9 pipeline, semantic bridge, provider manager and User/Developer modes are deployed; live bridge and acceptance smoke are verified

## Verified

- SketchUp Pro 2023.1.340 runs with the factory `Tools/sketchup.rb` restored and untouched by the plugin.
- Ruby bridge listens on `127.0.0.1:9876` without blocking the SketchUp UI thread.
- MCP stdio discovers the SketchUp tools and reaches the live bridge.
- Official Ruby API model summary, selection, camera, hierarchy and material reads are verified against the current unsaved model; no current-model write was issued by this implementation.
- Current live MCP session is PID `48576`, SketchUp `23.1.340`, bridge `ONLINE`; the current unsaved model is read-only and reports `0` entities, with official model, selection, camera and hierarchy reads succeeding. PID `25008` is historical evidence only.
- Control Center was opened from the SketchUp toolbar; Runtime and Model Inspector display the live bridge/model/selection/camera state.
- Control Center Skills tab was verified live: `Load` returned `status=ok`, `action=load_skill`, and rendered `ai-dg-selection-reader` content.
- Extension Manager confirms AI-DG MCP Bridge is Enabled and the viewport remains visible after UI operations.
- AI-DG owns one toolbar and one icon; it does not alter third-party toolbars.
- Current plugin source and deployed files are hash-verified by `deploy_bridge.ps1`.
- Read-only MCP guards are verified for D: writes, `.skp/.skb` deletion, `eval_ruby`, and model writes.
- Plugin/session persistence falls back to `OUTPUT/runtime` and `OUTPUT/sessions` because managed `.codex` paths are not writable in this environment.
- Final live stdio check on 2026-09-04: 21 tools discovered in the default/Cline `minimal` profile; Cline-compatible initialize/list-tools plus official health/model/selection reads passed. The full acceptance profile exposes 77 tools. The write probe returns `READ_ONLY_MODE` before dispatch.
- A repeatable `mcp_server/acceptance_smoke.py` now covers live MCP discovery, enabled Tool Manager metadata, official API reads, live runtime catalogs/reload, real-agent no-fallback behavior, plugin enable/disable/reload, E: session persistence, filesystem/model/system-file guards, model selection validation/persistence, provider/model-sync gates, semantic builder/read-back guards, pipeline artifact/D: guards and bounded hierarchy timing. The latest live run is `PASS` (`27/27`) at graceful reload generation `24`.
- User Mode Chat/Agent now uses a real provider helper after explicit per-session network enable; provider failures remain structured and there is no scripted fallback. The bounded local diagnostic path is available only in Developer Mode and is labelled `DEV_MOCK`. Pause/Resume/Cancel remain supported.
- Live Data Flow was exercised: graph nodes showed MCP `CONNECTED`, Ruby Bridge `ONLINE`, SketchUp API/Model/Result `SUCCESS`; trace rows exposed request/session, latency, byte counts, retries and clickable metadata. A lifecycle reconciliation fix prevents completed `*_started` rows from becoming false `TIMEOUT` entries.
- Live Settings/Plugins/Model Inspector were exercised: 9Router metadata stayed redacted, Model Manager reported `AUTO`/`NOT_RUN`, plugin Diagnostics returned permissions, and Model Inspector returned current model and `Sketchup::View` camera metadata.
- Provider Manager UI is deployed and gated: redacted audit, provider name/type/base URL, key-store save, model selection, test/sync, disconnect and explicit network enable are available. The Python 3.12 runtime used by Control Center sees the configured 9Router credential and OrcaRouter endpoint; Model Manager is still `AUTO` with no model ID, so real chat correctly stops at `MODEL_REQUIRED` before any request. The bundled acceptance runtime cannot see the Windows credential by design and reports `UNCONFIGURED`; no external provider traffic was enabled.
- MCP launcher configuration now resolves the local bundled dependency directory; the Cline-compatible stdio command passed initialize/list-tools plus live health/selection with 21 minimal-profile MCP tools, while the explicit full profile exposes 77. Separate `mcp.log`, `agent.log`, `provider.log`, `tools.log`, `runtime.log`, and `errors.log` are created under `OUTPUT/logs`.
- Source now includes runtime source hash/generation, session IDs, start/end/duration trace fields, dynamic tool/skill/plugin catalogs, an in-place graceful reload action, expanded Model Inspector collections, Data Flow/Tool Calls/Agent Steps/Errors views, and local chat-session persistence.
- `ai_dg_build_workflow_profile` now aggregates repeated live metadata samples into `USER_PROFILE/sketchup_workflow_profile.json` with explicit `sample_count`, confidence and privacy flags; the latest profile has 7 samples and no persisted paths/raw geometry.
- The authoritative current regression is acceptance smoke `27/27 PASS` at graceful reload generation `24`, with MCP stdio discovery passing against 77 full-profile tools; the normal-mode registry still hides `sketchup_eval_ruby`.
- Capability-based MCP exposure is live: the default/Cline `minimal` profile exposes 21/77 tools (72.7% schema reduction); `drawing` exposes 38, `build` 56, and explicit `full` exposes 77/77. Profiles are process-level and reported in `ai_dg_list_tools`; this is not claimed as per-prompt dynamic routing.
- Tool Manager now correlates MCP tool IDs with the corresponding Ruby trace actions and exposes enabled metadata, so live Last Run, Duration and Status fields show the official API calls that actually completed.
- Settings now exposes grouped sub-tabs for General, Provider, Model, Agent, Permissions, Logs, Recovery and Developer; provider telemetry is persisted only as redacted local state in `OUTPUT/runtime/provider-state.json`.
- Chat/Agent now performs a local credential/endpoint/model preflight, reports `MODEL_REQUIRED`/credential/endpoint errors directly, keeps blocked requests in `BLOCKED` state instead of mislabeling them `CANCELLED`, and shows a live readiness banner. Graceful runtime reload also refreshes an already-open Control Center HtmlDialog so the deployed UI is visible without closing SketchUp.
- Prompt implementation now includes the real M2-M9 pipeline under `pipeline/`, including central `Build IR` plus readable JSON/Python/Ruby codegen. MCP entrypoints expose ingestion/run/artifacts/review/spec/plan/Build IR/codegen/verification, and transaction-backed Ruby `create_semantic_item` remains the only production execution path. User Mode now shows 2D Sources, Review Queue and Build Progress; Developer Mode is hidden by default. Provider configuration uses a one-shot helper and OS credential-store path; `install_all.py --check` reports Python 3.12.10 and all required runtime modules ready.

## Current implementation

- Ruby bridge: `bridge_sketchup/ai_dg_bridge/main_safe.rb`
- Control Center: `bridge_sketchup/ai_dg_bridge/control_center.rb` and `ui/`
- Geometry helpers: `bridge_sketchup/ai_dg_bridge/geometry_builder.rb`
- MCP server: `mcp_server/server.py`
- Safety helpers: `mcp_server/policy.py`
- Drawing pipeline: `pipeline/stages/` and `.codex/DRAWING_PIPELINE.md`
- Input package currently contains one PDF under `INPUT/PDF/`; no SKP/CAD input is present there.

## Known partials

- Post-deploy MCP stdio handshake/list-tools passed with 77 full-profile tools, including provider manager actions and excluding `sketchup_eval_ruby`; the current read-only `sketchup_health` call returned bridge `ONLINE` for PID `48576`. The configured Cline/default profile intentionally exposes 21 tools.

- Provider/9Router endpoint has not been network-verified; only redacted configuration metadata is inspected. The UI runtime sees a stored credential (length only) and endpoint `https://api.orcarouter.ai/v1/chat/completions`, but no concrete model ID is selected. Provider state uses only `UNCONFIGURED`, `TESTING`, `CONNECTED`, `AUTH_ERROR`, `RATE_LIMITED`, `NO_CREDIT`, `OFFLINE` and `MODEL_ERROR`.
- The external provider-backed Agent adapter is bounded to two provider calls/steps and one read-only SketchUp tool; 9Router configuration is present but not connected because no concrete model has been selected, so no real chat request is enabled.
- The currently open model is unsaved and was not modified by the prompt implementation tests; no undo/removal/save/restart was forced.
- The bounded iterative `get_hierarchy` fix is live; the final smoke returned in about `404 ms` with `returned=0`, `max_items=50`, `truncated=false`, which is valid for the current empty model.
- A stale live write request was observed in trace during testing; model entity count stayed at 1 and no extra test box was created. The MCP boundary now rejects writes before sending them in read-only mode.
- The previous hidden PID `3668` and controlled reopen PID `24460` were closed after exact executable verification. The user-opened SketchUp instance is now live at PID `48576`; no force-kill or restart was used in the current live acceptance.
- Full model-file batch analyzer remains partial because the SKP adapter is intentionally read-only metadata-only; no SKP/CAD input is present in `INPUT`.
- Cline Nightly is installed and its global `cline_mcp_settings.json` contains an enabled `ai-dg` server. The last Cline-compatible stdio probe passed with 21 default/minimal-profile tools, live SketchUp health and selection. A provider-backed Cline LLM task was not started because that would invoke the configured model/provider.
- Provider network remains intentionally untested: the Control Center Python 3.12 helper can see the stored credential and endpoint, but the model is empty and the one-request test still requires explicit process opt-in. The bundled smoke runtime has a separate keyring context and cannot see that credential.
- The asynchronous Chat/Agent state machine is deployed; User Mode invokes the real provider helper in a background thread and only returns a result from that helper. Developer diagnostic behavior remains explicitly `DEV_MOCK`. The provider-bounded adapter is contract-tested with two provider calls and one read-only selection tool; external provider traffic remains untested. A local preflight now prevents an empty model from entering the helper path.
- The safe `mcp_server/failure_injection_smoke.py` passes localhost disconnect mapping, runtime `DISCONNECTED`, and provider-sync `request_count=0` without stopping SketchUp or contacting 9Router.
- The local `mcp_server/provider_contract_smoke.py` passes `/v1/models` endpoint derivation, auth-header presence, metadata filtering and sanitized local catalog persistence using a fake localhost server only.
- The provider manager contract also passes OS-secret-store abstraction, redacted metadata persistence, disconnect behavior and no-key-output checks; this uses an in-memory test keyring only.
- A transient cold-start failure was resolved by the user opening SketchUp and loading the deployed extension. Current bridge log records `bridge_started` on port `9876`, live MCP calls, and graceful reload generation `6`.
- The deployed loader, `main.rb` and Control Center hashes match source; the factory `sketchup.rb` hash remains unchanged. No current extension-load blocker remains.

## Latest live recheck (2026-09-04)

- UI redeploy completed without stopping SketchUp; the open HtmlDialog is refreshable through the graceful runtime reload.
- Chat/Agent now exposes provider/model chips, actionable readiness text, safe role/time metadata, Enter-to-send, Shift+Enter newline and duplicate-send guards.
- Live acceptance smoke is `PASS` (`27/27`) at reload generation `24`; provider traffic remains at zero because no concrete model ID has been selected.
- Chat now translates known helper/provider error codes into actionable Vietnamese guidance, while retaining the safe diagnostic code in brackets.
- Provider-backed Chat results now preserve and display safe `mcp_server`, `tool`, `tool_calls` and `request_count` trace fields instead of dropping the real-agent tool path at the Ruby/UI boundary.
- Chat conversation context is now continuous across Control Center reloads: the backend loads the last 200 persisted messages, sends at most 6 recent user/assistant turns with bounded/redacted content to a real backend, and persists only successful answers.
- The installed Codex CLI `0.147.0` is detected as an optional `Codex CLI (local)` Chat backend. It runs with `ephemeral` + `read-only` sandbox and a separate explicit network gate; the real Codex turn has not been run.
- The Codex adapter now injects the AI-DG MCP server per invocation through `mcp_server/ai_dg_codex_mcp.cmd` and scalar `-c` overrides; global `C:/Users/Admin/.codex/config.toml` is not modified. The wrapper MCP `initialize` contract passes.
- The wrapper `tools/list` smoke passes with 21 minimal-profile tools, including `sketchup_health` and `sketchup_get_selection`, and no model-write tool.
- Codex fails closed with `CODEX_MCP_NOT_CONFIGURED` before an external turn if the AI-DG wrapper is missing; the guard is covered by the Codex contract smoke.
- The installed 9Router app cache supplies 117 sanitized `orcarouter/...` model suggestions. They are labeled `LOCAL_CACHE_UNVERIFIED`; no model is auto-selected and no provider traffic was made.
- Codex and 9Router network permissions are separate; Codex defaults to disabled even when the 9Router permission was previously enabled.
