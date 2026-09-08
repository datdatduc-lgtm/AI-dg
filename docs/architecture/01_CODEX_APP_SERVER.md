# Codex App Server contract

Agent Host starts one long-lived process:

```text
codex app-server --stdio
```

The host performs the native JSON-RPC lifecycle:

1. `initialize`
2. `initialized`
3. `thread/start` or `thread/resume`
4. `turn/start`
5. forward `thread/*`, `turn/*`, and `item/*` notifications
6. use `turn/interrupt` for cancellation

The shared `ai-dg` MCP server is injected with per-process `-c` overrides.
Global Codex configuration is not rewritten and `codex mcp add` is not part
of the production path. After initialization the host requests
`mcpServerStatus/list` and forwards the result to diagnostics.

Default safety is `approvalPolicy=on-request` and read-only sandbox. The host
never passes a dangerous bypass flag and does not auto-approve write actions.
Approval requests are forwarded to the SketchUp UI and the user's decision is
returned to the original JSON-RPC request ID.

The host persists only this mapping shape:

```json
{
  "schema_version": 1,
  "documents": {
    "document-key": {
      "codex": {
        "thread_id": "real-thread-id",
        "session_id": "optional-runtime-id",
        "cwd": "E:/project"
      }
    }
  }
}
```

If resume fails, the failure is emitted as a real diagnostic and a new thread
is created only after the runtime rejects the old thread. No conversation is
replayed by the plugin.
