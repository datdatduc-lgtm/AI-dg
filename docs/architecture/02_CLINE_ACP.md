# Cline ACP contract

Agent Host starts one long-lived process:

```text
cline --acp
```

The host speaks ACP JSON-RPC over stdio and uses:

- `initialize`
- `session/new` or `session/load`
- `session/prompt`
- streamed `session/update` notifications
- `session/cancel`
- `session/close` where supported

The shared MCP definition is passed to `session/new` and merged into Cline's
existing `mcpServers` configuration. Existing MCP servers are preserved. The
host recognizes common Cline settings locations and supports
`CLINE_MCP_CONFIG_PATH` for an explicit location.

Cline owns provider/model login and selection. AI-DG never asks for or stores a
Cline API key. If Cline is absent, Agent Host emits an install state and starts
an asynchronous `npm install -g cline`; if that fails it tries an isolated npm
prefix under `%LOCALAPPDATA%\AI-DG\npm`. The SketchUp UI thread remains free.

Permission responses are protocol-specific:

- ACP `request_permission`: `allow_once` or `reject_once`.
- ACP elicitation: `accept` or `decline`.

There is no `--auto-approve` path.
