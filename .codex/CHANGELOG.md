# Changelog

## 2026-09-04 — actionable provider preflight and live UI refresh

- Added local Chat/Agent preflight for credential, endpoint and concrete model selection; missing configuration now returns actionable errors before spawning the provider helper.
- Added a Chat readiness banner populated from redacted provider/model state, startup provider/model refresh, and correct `BLOCKED` rendering for provider failures instead of `CANCELLED`.
- Added the bundled Codex runtime as a safe provider-helper fallback and bounded helper diagnostics without returning stdout/stderr contents or secrets.
- Graceful runtime reload now refreshes an already-open Control Center HtmlDialog, so deployed HTML/CSS/JS is visible without closing SketchUp.
- Verified Ruby/Python/JS syntax, provider contract `PASS`, live acceptance `27/27 PASS` at reload generation `11`, and unchanged factory `sketchup.rb`; no external 9Router request was made.

## 2026-09-04 — Chat interaction polish and live redeploy

- Added provider/model chips and an actionable readiness surface to Chat/Agent.
- Added safe multiline message rendering with role/time metadata, Enter-to-send, Shift+Enter newline, and duplicate-send protection while an agent request is running or paused.
- Added one-click navigation from Chat to the Provider settings group.
- Redeployed without stopping SketchUp; live acceptance remains `27/27 PASS` at graceful reload generation `14`.

## 2026-09-04 — Codex backend and local 9Router model discovery

- Added an optional `Codex CLI (local)` backend to the in-plugin Chat/Agent selector. It is read-only, ephemeral, bounded and independently network-gated.
- Added sanitized `orcarouter/...` model suggestions from the installed 9Router local cache, explicitly labeled unverified and never auto-selected.
- Safe gates and live acceptance remain green; no external Codex or 9Router turn was started.
- Split Codex network permission from the existing 9Router permission so selecting the Codex backend cannot inherit a prior provider approval.

## 2026-09-04 — capability exposure and central Build IR

- Added explicit process-level MCP capability profiles: `minimal`, `drawing`, `build`, `agent`, `full` and `dev`; normal/Cline defaults to the reduced `minimal` schema while Developer-only Ruby eval remains hidden outside Developer Mode.
- Added deterministic `pipeline/stages/build_ir.py` as the portable source of truth from approved ModelSpec to semantic operations, plus readable JSON/Python/Ruby codegen. The compatibility Build Plan is now derived from the same IR.
- Added persisted Build IR/codegen artifacts and MCP read tools `ai_dg_build_ir` and `ai_dg_codegen`.
- Added regression coverage: pipeline `15/15`, exposure profiles `PASS` (21/77, 38/77, 56/77, 77/77), Cline stdio `PASS`, and live acceptance `27/27 PASS` at reload generation `6`.

## 2026-09-04 — provider helper diagnostics

- Fixed Control Center provider helper runtime selection so a generic `py -3` cannot silently select Python 3.9; the helper now requires Python `>=3.10` and preserves structured errors even when the child exits with code `1`.
- Fixed provider-state loading and made helper parsing tolerant only of a safe JSON object line, so `API_KEY_REQUIRED`, `MODEL_REQUIRED` and runtime errors remain actionable instead of becoming `PROVIDER_HELPER_INVALID_RESPONSE`.
- Redeployed and gracefully reloaded the live plugin; acceptance remains `27/27 PASS` at generation `8`, with no provider request and no model mutation.

## 2026-09-04 — provider manager, safe installer and live-state recheck

- Added a real provider manager path for 9Router/OpenAI-compatible endpoints: provider metadata is stored locally without the key, while the key is written only through the OS credential-store abstraction. Configure, disconnect, status, test and model-sync paths return redacted state.
- Added a one-shot `mcp_server/provider_cli.py` helper so Control Center User Mode can invoke the real provider adapter asynchronously after explicit network permission; no scripted production fallback is used. Developer diagnostics remain explicitly `DEV_MOCK`.
- Added provider-manager MCP tools, redacted contract coverage, key-selection hardening for the configured Orca/9Router endpoint, Python 3.12 runtime selection, and installer preflight (`install_all.py --check`).
- Hardened installation to merge AI-DG-owned plugin files without recursive deletion and preserved the factory `Tools/sketchup.rb` guard/hash.
- Re-ran local pipeline/provider/agent/compiler/syntax checks successfully. A fresh acceptance attempt was correctly stopped at the external gate because SketchUp PID `3668` has no visible main window and no bridge listener on `127.0.0.1:9876`; no force-kill, model write, restart or provider request was issued.
- Security note: a prior diagnostic inspection exposed credential values in tool output due to insufficient redaction. No value was persisted by AI-DG; any credential visible in that output should be rotated/revoked before real provider testing.
- Revalidated the user-opened SketchUp instance: PID `48576`, bridge `ONLINE`, official API reads and graceful reload live. Fixed plugin registry state precedence so a stale fallback snapshot cannot mask a successful enable; updated the bounded hierarchy smoke assertion to accept a valid empty model. Live acceptance is now `27/27 PASS` at reload generation `3` with no model mutation or provider request.

## 2026-09-03 — prompt implementation continuation

- Added explicit semantic SketchUp builders: group, real component, cabinet, panel, partition, shelf, door, drawer, countertop, component-from-spec, transform, material, tag and confirmed undo.
- Added official Ruby API semantic read-back and a gated Build Plan executor. Execution requires `APPROVED`, `write_enabled` and `confirm_write=true`; each build unit remains transaction-backed and verification reads the model back.
- Made the Ruby runtime tool catalog reloadable so graceful reload reflects newly deployed tools in the live process.
- Removed production scripted agent/chat fallback. Provider-disabled production calls now return `REAL_PROVIDER_REQUIRED`; Developer Mode diagnostic behavior is explicitly `DEV_MOCK`.
- Added local OCR autodetection with explicit status/confidence/provenance. The current scanned PDF renders but remains `BLOCKED` because no Tesseract binary is installed; no geometry is guessed.
- Final source checks: pipeline `14/14` tests, Cline stdio `73` tools, live acceptance `26/26`, Ruby/JS/Python syntax/compile all pass. Factory `Tools/sketchup.rb` remains unchanged.

## 2026-09-02

- Read the AI-DG MCP-SU master goal and audited the current implementation.
- Added local Control Center HtmlDialog skeleton with Runtime, Data Flow, Sequence, Tools, Model, Chat, Settings and Developer tabs.
- Added Ruby runtime snapshots, trace events, selection/model/entities observers and bounded read tools.
- Added Python MCP tool registry, bounded local agent gateway and redacted provider status.
- Added D: write guard and `.skp`/`.skb` deletion guard.
- Added state/backlog/test/risk/decision records under `.codex`.
- Verified live Control Center and Model Inspector via SketchUp UI: PID/version, bridge/MCP health, selection Group `AI_DG_MCP_TEST_BOX`, persistent id `469337`, bounds and `Sketchup::View` camera.
- Verified redacted 9Router configuration discovery and safe fallback persistence under `OUTPUT` when managed `.codex` paths reject writes.
- Added MCP-side read-only write preflight so stale Ruby runtimes cannot receive model-write requests in Normal Mode.
- Deployed source with bounded iterative hierarchy traversal; same-process Extension Manager toggling did not reload Ruby, so live hierarchy verification remains pending.
- Added portable MCP launcher/config, local separated runtime logs, session/request IDs, bounded hierarchy timeout, model-status tool, redacted endpoint diagnostics, and repeatable acceptance smoke.
- Added read-only selection skill routing, dynamic Ruby tool/skill/plugin catalogs, expanded Control Center trace/registry/model panels, local chat persistence, Write-mode confirmation, and a non-destructive in-place runtime reload action. Source/deploy is current; the running SketchUp process still contains the legacy action table until reload.
- Added privacy-aware workflow-profile aggregation, safe `.skp/.skb` write guard, official error codes, endpoint redaction, runtime source timing metadata, and `acceptance_smoke.py` provider-network guard. Verified the configured launcher with 48 MCP tools and live in-place reload through Ruby Console/MCP.
- Final live acceptance: 14/14 checks PASS, including official API reads, bounded hierarchy, plugin lifecycle, session persistence, read-only write guards, and reload generation `3`. Control Center `Load` was also verified live for `ai-dg-selection-reader`.
- Re-ran the final smoke after the deployed lifecycle fix: 14/14 PASS at graceful reload generation `8`; official entity/view reads, selection skill, plugin lifecycle, session persistence, filesystem guards and bounded hierarchy remained green.
- Exercised live Chat/Agent dimensions routing, Data Flow clickable trace metadata, Settings redacted provider/model diagnostics, Plugins diagnostics and Model Inspector. The trace reconciler now closes successful `*_started` rows instead of later labeling them false `TIMEOUT`.
- Deployed the bounded asynchronous Chat/Agent state machine with local UI-thread phases, request/session trace metadata, and completion feedback; live selection completion passed after graceful reload generation `9`. Re-ran `mcp_server/acceptance_smoke.py`: `14/14 PASS`. True mid-flight controls remain a safe-harness follow-up.
- Added explicit model-selection and one-request `/models` sync tools with secret-safe local catalog persistence; added MCP disconnect/error mapping and `failure_injection_smoke.py`. Regression now passes `16/16` at live reload generation `11`; provider network remains opt-in and uncalled.
- Added local provider contract coverage for `/v1/models` derivation, metadata filtering and sanitized catalog persistence without external network; acceptance smoke now passes `17/17` at live reload generation `12`, with model selection restored to AUTO.
- Hardened the asynchronous agent scheduler with explicit step deadlines and cancel-state reset; live UI testing verified mid-flight Pause → Resume → completion and Cancel → CANCELLED without changing the unsaved SketchUp model.
- Final local regression remains green: provider-contract smoke, failure-injection smoke, acceptance smoke `17/17`, Cline stdio, workflow-profile, socket/API and Ruby/JS/Python syntax checks, and graceful in-place reload generation `18`; the factory `Tools/sketchup.rb` remains untouched.
- Added repo-local VS Code MCP configuration and verified the enabled Cline Nightly configuration with the exact configured Python/server command: Cline-compatible stdio initialize/list-tools plus live SketchUp health and selection passed (`50` tools); no provider request was sent.
- Added provider recovery controls (safe retry, model focus and diagnostics) to Control Center; live UI reload and safe-retry handler passed while provider traffic stayed gated, with recovery actions hidden in READY state. Fixed plugin state loading to prefer canonical `.codex/plugin-state.json`, restoring acceptance `17/17`.
- Fixed Tool Manager correlation between MCP tool IDs and Ruby trace action names, then reloaded the live bridge to generation `19`; post-fix acceptance remained `17/17 PASS` and Last Run/Duration/Status populated correctly in the live UI.
- Added missing MCP registry metadata and live enabled-state rows; normal mode now discovers 49 tools while `sketchup_eval_ruby` remains hidden. Acceptance smoke is `19/19 PASS` at graceful reload generation `29`.
- Added a SketchUp factory-file system guard for `Tools/sketchup.rb`, including extended-path normalization, and verified the factory SHA-256 remains unchanged.
- Added provider-bounded-agent contract coverage: fake-localhost provider, configured model, two-call/two-step ceiling, and read-only selection allow-list; no external provider traffic was sent.
- Added redacted provider state telemetry under `OUTPUT/runtime/provider-state.json` and grouped Settings sub-tabs for Provider/Model/Agent/Permissions/Logs/Recovery/Developer.
- Re-ran Cline-compatible stdio, socket, failure-injection, provider-contract, workflow-profile and acceptance regression with Python 3.12: all PASS; Cline discovery is 49 normal-mode tools and workflow profile sample count is 7.

## 2026-09-04 — chat continuity and live recheck

- Added bounded conversation context for real 9Router and Codex CLI chat routes, loading the local session file on demand, limiting context to six recent turns, redacting common sensitive-token patterns and retaining only successful answers.
- Deployed without stopping SketchUp; live acceptance is `27/27 PASS` at graceful reload generation `18`, provider-agent contract and Codex CLI contract are `PASS`, and provider request count remains zero.

## 2026-09-04 — chat setup/error UX

- Added direct Chat → Model Manager navigation, six safe quick-picks from the local 9Router cache, duplicate-placeholder cleanup after history restore, backend labeling in running messages and friendly mappings for known helper/provider error codes.
- Deployed and gracefully reloaded without stopping SketchUp; live acceptance is `27/27 PASS` at generation `21`, with provider traffic still at zero.

## 2026-09-04 — Codex MCP wiring

- Added `mcp_server/ai_dg_codex_mcp.cmd` and per-invocation Codex `-c` overrides so the local Codex backend can discover AI-DG/SketchUp MCP tools without mutating the user's global Codex configuration.
- Added contract checks for MCP injection and verified the wrapper stdio `initialize`; Codex remains ephemeral/read-only and no external turn was executed.
- Added `codex_mcp_wrapper_smoke.py`; direct `tools/list` confirms the Codex-side wrapper exposes 21 minimal read-only tools with SketchUp health/selection and no write tools.
- Added a fail-closed `CODEX_MCP_NOT_CONFIGURED` guard and contract coverage so the Codex backend cannot claim a SketchUp-capable turn without the AI-DG MCP wrapper.
- Preserved provider-backed MCP/tool/request-count metadata through Ruby `finish_chat_job` and rendered it in Chat trace, then live-reloaded SketchUp to generation `24` with `27/27` acceptance PASS.
