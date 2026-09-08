# AI-DG MCP-SU Failures

## Environment issue — not changed

- SketchUp exposes several third-party toolbar groups in a stacked/detached layout. The issue reproduces independently of AI-DG and the AI-DG plugin does not enumerate, reset, move, show or hide those toolbars.

## Open technical gaps

- Cold-start/extension-load blocker: resolved. Current live health is `ONLINE` for SketchUp PID `48576`, version `23.1.340`; bridge log records `bridge_started` on `127.0.0.1:9876` and live MCP/API calls.
- Process diagnosis confirmed the executable is the official `C:\Program Files\SketchUp\SketchUp 2023\SketchUp.exe`; the current acceptance run used the user-opened visible instance and did not force-kill or restart it.
- Credential safety incident: one continuation diagnostic printed provider credential values because redaction was insufficient. AI-DG did not write those values to project files or logs, but exposed credentials must be rotated/revoked before any real provider request.

- Extension Manager toggling does not re-evaluate `main.rb` in the same process. The deployed source is now loaded through the explicit graceful reload action and live generation `21`; the Ruby catalog is reloadable. Cold-start toolbar-label/persistence verification remains deferred because the current model is unsaved.
- A read-only `sketchup_create_box` probe sent before the MCP boundary guard was added remained `RUNNING` in the old runtime trace, but the model stayed unchanged (`entities=1`). New MCP calls are blocked before dispatch while `access_mode=read_only`.
- Managed `.codex` state directories reject writes. Plugin state and sessions now use a writable `OUTPUT` fallback; the static acceptance state files remain under `.codex`.
- The first MCP viewport capture on an empty model is correctly gray; a model is needed for a visual geometry assertion.
- The provider is configured/redacted but no external 9Router request has been sent; this is an intentional safety gate requiring explicit authorization.
- Cline Nightly is installed and configured (`disabled=false`); the exact configured command passes the Cline-compatible stdio health/selection probe. A full Cline in-panel LLM task remains unrun because it would invoke the configured provider, which is still explicitly gated.
- Agent pause/cancel controls are present and the UI agent is now an asynchronous bounded state machine; completion and true mid-flight Pause/Resume/Cancel are live-verified with a temporary harness. Provider recovery controls are live-opened and safe-retry exercised; external MCP-disconnect/provider-failure simulation remains safe-gated.
- A temporary external Client Observer window interfered with fresh Control Center click actions during the final visual check; no further UI input was sent after the click outcome became uncertain. MCP/Cline/socket acceptance remained green and the SketchUp viewport/model were preserved.
- The current PDF is scanned/image-only. PyMuPDF rendering succeeds, but no Tesseract executable is installed and the optional RapidOCR native experiment was unstable; the source remains correctly BLOCKED rather than being promoted from visual inspection.
- User Mode Chat now blocks with `REAL_PROVIDER_REQUIRED` when no real provider is connected; deterministic local diagnostics are isolated to Developer Mode and marked `DEV_MOCK`.
- Acceptance regression fixed: plugin state loading now resolves the newest valid canonical/fallback snapshot, preventing a stale fallback file from masking a successful plugin enable. Current `plugin_enable_disable_reload` is `PASS`.
- Provider chat configuration gap: the Control Center helper sees the stored 9Router credential and endpoint, but `model-state.json` is currently `AUTO` with no model ID. The new Chat preflight reports `MODEL_REQUIRED` and prevents an opaque helper failure; a real model sync/test remains user-authorized work.
- Keyring-context difference: the bundled acceptance runtime cannot see the Windows credential used by the installed Python 3.12 helper. This is not treated as proof of a production credential failure; both contexts remain network-gated and no external request has been made.
- Codex backend remains unverified by design: `codex.cmd` is installed and detected, but running `codex exec` would be a real external turn. The new route is read-only/ephemeral and blocked until the user explicitly enables network after handling the provider credential rotation requirement.
- The Codex permission is intentionally separate from the existing 9Router permission; selecting Codex alone cannot inherit the 9Router network approval.
- Latest deploy/reload recheck: the chat-context, model-selection and helper-error UX patches are live at graceful reload generation `21`; Ruby/JS syntax, provider contract, Codex contract, provider-agent contract and Cline acceptance all pass. Remaining provider error risk is external and unverified because no real request was authorized.
- Codex MCP wiring gap resolved: per-invocation `-c` config points Codex to the local AI-DG stdio wrapper, and direct MCP `initialize` succeeds. Remaining gap is only the explicitly gated real Codex turn.
- Wrapper `tools/list` now provides additional evidence: 21 minimal tools, SketchUp reads present, model-write tools absent. No external turn was used for this check. Provider tool/request trace propagation is deployed and covered by syntax/live regression.
- The missing-wrapper case is now explicitly guarded as `CODEX_MCP_NOT_CONFIGURED`; this was contract-tested without starting Codex.
