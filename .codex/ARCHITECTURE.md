# AI-DG MCP-SU Architecture

```text
SketchUp UI / HtmlDialog Control Center
        │ action callbacks + runtime snapshots
        ▼
Ruby bridge (UI thread for API, background threads for TCP I/O)
        │ localhost JSON-lines protocol
        ▼
Python MCP server / tool registry / agent gateway / policy guards
        │ optional provider adapter
        ▼
9Router / OpenAI-compatible provider (real requests only)
```

## Ruby boundary

- `ai_dg_bridge.rb` is the only extension discovery loader.
- `main_safe.rb` owns dispatch, queueing, runtime health, trace, observers and transactional model writes.
- `geometry_builder.rb` creates provenance-aware geometry.
- `control_center.rb` owns the local `UI::HtmlDialog`, callback boundary and
  non-blocking provider-helper jobs; provider requests run outside the
  SketchUp UI thread and return to the UI through a timer.
- `toolbar.rb` owns exactly one AI-DG toolbar and command.
- `ui/` contains local HTML/CSS/JavaScript only; it does not call the network.

## Python boundary

- `server.py` exposes MCP tools and attaches request/session IDs, bounded timeouts and latency metadata; `launcher.py` makes stdio configuration portable. Normal discovery hides Developer-only Ruby eval and returns enabled/permission metadata for Tool Manager.
- `policy.py` denies D: writes before disk access and denies `.skp`/`.skb` deletion.
- `logging_utils.py` writes sanitized JSONL diagnostics to separate local MCP/agent/provider/tools/runtime/errors logs.
- Read tools request bounded metadata first: summary, selection, entity, hierarchy, components, materials, tags, scenes, camera and bounds.
- `registries.py` provides lazy skills and permissioned plugin metadata; `ai_dg_agent_ask` is bounded to two provider calls/steps and one SketchUp read tool. `provider.py` and `provider_cli.py` provide provider configuration, OS credential-store handling and one-shot real requests. When no real provider is enabled it returns `REAL_PROVIDER_REQUIRED`; no scripted production-chat fallback remains. Developer-only diagnostics are explicitly `DEV_MOCK`.
- `pipeline/stages/executor.py` connects an approved Build Plan to the official Ruby semantic builder and `get_semantic_item` read-back; it requires `APPROVED`, `write_enabled` and per-call confirmation before dispatch.
- Provider status/model sync/test telemetry is redacted and stored locally under `OUTPUT/runtime/provider-state.json`; provider metadata is separate from the OS-stored secret. External traffic is disabled until explicit process opt-in.
- `install_all.py --check` validates the Python/dependency runtime; the normal installer merges AI-DG-owned plugin files and does not recursively delete plugin directories.

## Safety invariants

- D: is read-only.
- `.skp` and `.skb` are never deleted.
- The factory SketchUp `Tools/sketchup.rb` is never edited or deleted.
- `eval_ruby` is Developer Mode only.
- Model writes require explicit `write_enabled` mode and use `start_operation`/commit/abort.
- No plugin code edits `sketchup.rb` or repositions another toolbar.
