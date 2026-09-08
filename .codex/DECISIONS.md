# AI-DG MCP-SU Decisions

- Keep `ai_dg_bridge.rb` as a standard SketchUp extension loader; never put blocking TCP or UI work in the loader.
- Use JSON-lines over localhost with request IDs; all SketchUp API calls are dispatched by the UI timer.
- Default access mode is `read_only`; model writes require explicit UI mode change.
- Use bounded metadata and hierarchy paging before detailed entity reads.
- Keep Control Center local in `UI::HtmlDialog`; external provider/network calls remain in Python.
- Treat D: as protected regardless of prompt wording and deny `.skp`/`.skb` deletion at the tool layer.
- Keep provider status redacted until endpoint/auth behavior is verified.
- Use an in-place source reload action for safe runtime updates, while preserving queues/model state; never use force-kill or Ruby eval as a reload mechanism.
- Treat `OUTPUT` as the managed writable fallback when `.codex` persistence is unavailable, and expose the fallback path in diagnostics.
- Use the configured Python 3.12 interpreter for the Cline-compatible MCP runtime; the system `py -3` Python 3.9 is not the runtime contract.
- Keep provider traffic opt-in and persist only redacted provider telemetry; fake-localhost contract tests prove endpoint/auth/adapter behavior without contacting 9Router.
- Keep provider-backed agents bounded to two provider calls, two steps and the read-only SketchUp allow-list; never let provider output select arbitrary Ruby or filesystem actions.
- Treat the factory `Tools/sketchup.rb` as a protected system file in both Python policy and Ruby deployment guards.
