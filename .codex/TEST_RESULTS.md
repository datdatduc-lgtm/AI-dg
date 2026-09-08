# AI-DG Prompt Implementation Test Results

Run date: 2026-09-04

## Passing checks

- Pipeline unit/end-to-end: `15 passed` using the bundled Python 3.12 runtime, including deterministic Build IR/codegen.
- Ruby syntax: `main_safe.rb`, `control_center.rb`, `geometry_builder.rb` — `Syntax OK`.
- Python compile/import: MCP server, provider, provider helper and installer — passed; server tool registry imports with 77 metadata rows.
- Pipeline real-source run: latest `prompt-20260903-03` completed with PyMuPDF rendering and `gate_status=BLOCKED` because the current scanned PDF has no recoverable text/dimension/material facts; the rendered page artifact is preserved for review.
- Provider contract: `PASS`; fake localhost only, `/v1/models` + `/v1/chat/completions`, auth-header detection and redacted telemetry.
- Provider manager contract: `PASS`; OS-secret-store abstraction, redacted provider metadata, disconnect marker and no plaintext key persistence.
- Installer preflight: `READY`; Python 3.12.10 with mcp/PyMuPDF/openpyxl/ezdxf/Pillow available. Installer re-run path now merges AI-DG-owned files without recursive deletion.
- Capability exposure smoke: `PASS`; default/Cline `minimal` 21/77 tools, `drawing` 38/77, `build` 56/77, explicit `full` 77/77; `sketchup_eval_ruby` remains hidden outside Developer Mode.
- Cline-compatible stdio: `PASS`, 21 default-profile tools, live SketchUp bridge `ONLINE`, SketchUp `23.1.340`.
- Live acceptance smoke: `PASS`, 27 checks at graceful reload generation `11`; official Ruby API model/selection/camera/hierarchy reads, semantic builder/read-back guards, pipeline artifact/D: guards, provider network guards, plugin state and no-fallback agent gate.
- Ruby bridge deploy: source/deployed hashes verified; live graceful reload reached generation `11`.
- Final source/UI redeploy on 2026-09-04: completed without stopping or restarting SketchUp; the new Control Center provider helper is present in the deployed plugin.
- Post-deploy MCP stdio list-tools: `PASS`, 77 tools in the explicit full profile; provider manager tools are discoverable and `sketchup_eval_ruby` is not visible in the normal registry. The default/Cline profile exposes 21 tools.

## Live state observed

- SketchUp PID `48576`, version `23.1.340`.
- Bridge `127.0.0.1:9876` is `ONLINE`; MCP is `CONNECTED`.
- Current open model is unsaved and currently reports `0` entities, zero bounds, and selection count `0`. The model was not modified by these tests.
- Control Center Python 3.12 helper sees the redacted 9Router credential and endpoint, while Model Manager remains `AUTO` with no concrete model ID; no real provider request was sent. The bundled acceptance runtime intentionally has no matching Windows keyring context and reports `UNCONFIGURED`.
- Factory `C:/Program Files/SketchUp/SketchUp 2023/Tools/sketchup.rb` remains untouched.

## Intentional non-passes / remaining gates

- A full PDF-to-3D build cannot be claimed from the current scanned/image-only PDF until OCR/rendering or additional CAD/Excel evidence is supplied and reviewed.
- RapidOCR was installed in the workspace as an optional experiment, but native inference was unstable on this host; it is not used by production ingestion. The stable route remains PyMuPDF/pypdf plus explicit review.
- Semantic SketchUp writing remains gated by `read_only` plus explicit `APPROVED` source review and explicit part breakdown. No semantic write was issued against the unsaved live model.
- Real 9Router traffic and an actual provider-backed Cline task remain opt-in and untested.
- Cold-start diagnosis was resolved: the user-opened SketchUp instance now starts the bridge and the current read-only acceptance smoke is `27/27 PASS`; no model/API write or provider request was performed.
- The hierarchy assertion was corrected to validate bounded shape and response consistency while allowing an empty model; live result was `returned=0`, `max_items=50`, `truncated=false`.
- Plugin lifecycle regression was corrected by newest-valid-state resolution; plugin state was restored to `DISABLED` after the smoke.
- The current scanned PDF remains review-blocked; Build IR/codegen is emitted only when the reviewed ModelSpec is executable. The approved Excel fixture reaches `READY` and emits JSON/Python/Ruby representations without touching the live model.

## Latest provider/UI fix

- Control Center Chat now preflights local credential, endpoint and model state and returns actionable `9ROUTER_CREDENTIAL_NOT_FOUND`, `9ROUTER_ENDPOINT_NOT_FOUND` or `MODEL_REQUIRED` instead of starting a job that can surface `PROVIDER_HELPER_INVALID_RESPONSE`.
- Blocked Chat results render as `BLOCKED`, not `CANCELLED`; a readiness banner is populated on startup from redacted provider/model status.
- Graceful reload refreshes an already-open Control Center HtmlDialog. Ruby/Python/JS syntax checks pass; acceptance is `27/27`, provider contract is `PASS`, and provider network count remains zero.
- Ruby preflight check with the installed Python 3.12 helper: `PASS`; the stored credential and endpoint were found without exposing either, and the incomplete model state returned exactly `MODEL_REQUIRED` with zero network requests.
- Post-UI redeploy: Chat/Agent now has provider/model chips, readiness text, safe multiline history rendering with role/time metadata, Enter-to-send and Shift+Enter newline behavior, and disabled duplicate-send controls; JavaScript syntax and live `27/27` acceptance remain green.
- Final live recheck after the disconnected-MCP guard: `27/27 PASS`, SketchUp PID `48576`, version `23.1.340`, graceful reload generation `14`, provider request count `0`.
- Provider cache and Codex backend continuation: provider contract `PASS` with `local_cache=PASS`; safe Codex gate returns `CODEX_NETWORK_TEST_REQUIRES_EXPLICIT_ENABLE` with `request_count=0`; Codex CLI `0.147.0` and Ruby backend status are detected without launching a turn.
- Final live recheck after backend deployment: `27/27 PASS`, SketchUp PID `48576`, version `23.1.340`, graceful reload generation `17`, provider request count `0`.
- Network separation check: Codex helper remains blocked with `CODEX_NETWORK_TEST_REQUIRES_EXPLICIT_ENABLE`; 9Router and Codex permission paths are distinct and no external turn was started.
- Conversation/UI/error UX fix: Ruby/JS syntax and live deploy passed; Chat now opens Model Manager directly, offers six quick model-ID choices from the sanitized local cache, removes the duplicate placeholder after restore, shows the selected backend and translates known helper errors into actionable guidance. Provider/Codex prompts include bounded recent persisted turns with sensitive-token redaction. Live acceptance is `27/27 PASS` at graceful reload generation `21`; provider request count remains `0`.
- Codex MCP wiring: `codex_cli_contract_smoke.py` `PASS` with AI-DG MCP config injection; `ai_dg_codex_mcp.cmd` direct stdio `initialize` `PASS`. The wrapper launches the local MCP server with the minimal/read-only tool profile; no Codex model turn or provider request was made.
- Codex wrapper regression: `codex_mcp_wrapper_smoke.py` `PASS`, 21 tools listed, SketchUp health/selection present, write tools absent; live acceptance remains `27/27 PASS` at generation `24`.
- Provider trace propagation: Ruby/JS syntax and deploy passed; real-route responses now retain MCP/tool/request-count metadata for the Chat transcript. No external request was used for this change.
- Codex fail-closed regression: `codex_cli_contract_smoke.py` confirms missing-wrapper handling returns `CODEX_MCP_NOT_CONFIGURED` without spawning Codex.
