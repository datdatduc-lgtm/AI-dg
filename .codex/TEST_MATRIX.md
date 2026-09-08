# AI-DG MCP-SU Test Matrix

| Test | Evidence | Status |
|---|---|---|
| Factory `sketchup.rb` clean | SHA-256 and no AI-DG text | PASS |
| SketchUp viewport/axes | Computer Use screenshot | PASS |
| Bridge ping | `sketchup_ping`, version 23.1.340 | PASS |
| MCP stdio discovery | Registry and live MCP stdio session | PASS |
| MCP create box | `AI_DG_MCP_TEST_BOX` created | PASS (pre-write-guard) |
| Official Ruby API read | `Sketchup::Model`, `Sketchup::View`, Group/Face bounds | PASS |
| Viewport capture | PNG with visible box | PASS |
| Repeated monitoring | 3 consecutive ping/state samples | PASS |
| Control Center source syntax | Ruby syntax checks | PASS |
| Control Center deployed | `deploy_bridge.ps1` hash verification | PASS |
| Control Center live UI | Runtime + Model Inspector show PID/model/selection/camera | PASS |
| Normal-mode eval lock | MCP tool refused with `DEVELOPER_MODE=false` | PASS |
| D: write guard | `PROTECTED_DRIVE_WRITE_DENIED`, no file created | PASS |
| `.skp` delete guard | `SKETCHUP_FILE_DELETE_DENIED`, no file deleted | PASS |
| Runtime trace/observers | Live trace records tool start/finish and observer-capable source | PASS — live reload generation 3; completed lifecycle rows reconcile without false TIMEOUT |
| MCP read API set | ping/model/selection/entity/camera/bounds/components/materials/tags/scenes | PASS |
| Capability-based MCP exposure | `tool_exposure_smoke.py`: minimal/drawing/build/full profiles with reported counts | PASS — 21/77, 38/77, 56/77, 77/77; eval Ruby hidden in normal mode |
| ModelSpec → Build IR | Deterministic semantic operation IDs/order and validation | PASS — pipeline test plus approved Excel fixture |
| Build IR codegen | Readable JSON/Python/Ruby representations | PASS — generated from the same Build IR; no raw face/edge stream |
| Read-only model-write guard | MCP boundary rejects `sketchup_create_box` in `read_only` | PASS |
| Final live MCP/API/UI confirmation | 77 full-profile tools; live PID/version; Model Inspector; `Sketchup::View`; current unsaved model read-only | PASS |
| Plugin/session persistence | Fallback write/read under `OUTPUT` | PASS |
| Hierarchy bounded traversal | Source syntax/deployed fix and live MCP call | PASS — bounded call returned promptly and passed the bounded-response assertion |
| 9Router network request | Endpoint/auth not verified | BLOCKED_SAFE |
| Portable MCP launcher | `mcp_server/launcher.py` starts through stdio and discovers the configured capability profile | PASS — 21 minimal tools; 77 full-profile tools |
| Repeatable acceptance smoke | `mcp_server/acceptance_smoke.py` | PASS — 27/27: live bridge, reloadable catalogs, reads, semantic builder/read-back guards, no-fake agent gate, provider/D:/SKP/system-file guards, model-selection, plugin, session and hierarchy |
| Tool Manager MCP↔Ruby mapping | Live Control Center Tool Manager and official Ruby trace | PASS — MCP IDs correlate to completed Ruby actions; Last Run, Duration and Status are populated |
| Selection-read skill | Lazy load + selection metadata through bounded agent | PASS |
| Runtime logs | Separate MCP/agent/provider/tools/runtime/errors logs under `OUTPUT/logs` | PASS |
| In-place runtime reload source | Ruby stub and live MCP reload return source hash/generation | PASS |
| Workflow profile aggregation | Repeated live metadata samples merge to `USER_PROFILE` with privacy flags | PASS |
| Configured client executable | Exact `mcp_config.json` Python starts launcher; initialize/list-tools | PASS |
| Plugin lifecycle | Test plugin enable, read tool, graceful reload, restore disabled | PASS — newest-valid canonical/fallback state resolution |
| Session persistence | Save/load local session metadata under E:/AI-DG | PASS |
| Control Center skill loading | Skills tab `Load` renders loaded skill metadata/content | PASS — `ai-dg-selection-reader` |
| Control Center Chat/Agent | User Mode must not use scripted fallback; Developer Mode diagnostic path is explicitly labelled `DEV_MOCK` | PASS — production path returns `REAL_PROVIDER_REQUIRED` while provider is OFFLINE |
| Agent Pause/Resume/Cancel | Delayed bounded harness exercises controls mid-flight without model mutation | PASS — UI reached PAUSED, RUNNING and CANCELLED; viewport/model remained normal |
| Data Flow trace UI | Graph, status nodes, clickable event metadata, request/session/bytes/latency | PASS — live UI review |
| Settings / provider diagnostics | Redacted 9Router audit, safe retry/recovery actions and model manager AUTO/NOT_RUN state | PASS — safe retry live-checked; no network request sent |
| Plugins diagnostics UI | Registry, permissions and safe reload policy rendered | PASS — live UI review |
| Provider failure / MCP disconnect behavior | External provider failure and UI disconnect state | BLOCKED_SAFE — localhost error mapping/guard passes; real provider request and live external-failure exercise remain gated |
| Cline runtime client | Cline Nightly config plus exact stdio command initialize/list-tools and live read | PASS — config enabled; `cline_acceptance_smoke.py` reports 21 default/minimal-profile tools, SketchUp `ONLINE`, current selection count 0; in-panel LLM invocation remains provider-gated |
| MCP disconnect failure smoke | `mcp_server/failure_injection_smoke.py` against an unused localhost port | PASS — explicit error mapping, runtime DISCONNECTED, no retry loop |
| Model sync/selection gate | `ai_dg_9router_sync_models`, `ai_dg_model_select` | PASS — sync remains blocked at request_count 0; invalid IDs rejected |
| Normal-mode tool registry | `sketchup_eval_ruby` hidden; capability profile is explicit | PASS — 21 default/minimal tools; full profile 77; Developer-only eval remains absent |
| SketchUp factory-file guard | `Tools/sketchup.rb` write/delete policy | PASS — `SKETCHUP_SYSTEM_FILE_WRITE_DENIED`; factory hash unchanged |
| Provider-bounded agent contract | Fake localhost provider with bounded read-only tool loop | PASS — 2 provider calls, 2 steps, selection read only; no external request |
| Provider telemetry privacy | Redacted `OUTPUT/runtime/provider-state.json` | PASS — status/latency/model metadata only; no credential/prompt persistence |
| Settings sub-tabs | General/Provider/Model/Agent/Permissions/Logs/Recovery/Developer | PASS — rendered in live Control Center |
