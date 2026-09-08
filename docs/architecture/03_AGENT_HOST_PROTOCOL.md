# Agent Host internal protocol

Ruby sends bounded JSONL requests to `agent_host/host.py`:

```json
{
  "id": "ruby-12",
  "method": "turn/start",
  "backend": "codex",
  "document_key": "model-key|project-root",
  "cwd": "E:\\project",
  "text": "Đọc object đang chọn trong SketchUp"
}
```

Supported methods:

`host/status`, `agent/open`, `session/open`, `session/resume`, `turn/start`,
`turn/cancel`, `approval/respond`, `model/list`, and `session/close`.

Responses are correlated by `id`:

```json
{
  "id": "ruby-12",
  "status": "ok",
  "data": {
    "backend": "codex",
    "thread_id": "real-thread-id",
    "turn_id": "real-turn-id"
  }
}
```

Native runtime notifications are normalized without changing their content:

```json
{
  "type": "agent/event",
  "backend": "codex",
  "event": "item/agentMessage/delta",
  "session_id": "real-thread-id",
  "data": {}
}
```

The host enforces a 1 MiB line limit, bounded diagnostic tails, request
timeouts, one active turn per backend, stale mapping checks, and process-tree
termination on shutdown. Child runtime stderr is diagnostic-only and is never
treated as assistant content.
