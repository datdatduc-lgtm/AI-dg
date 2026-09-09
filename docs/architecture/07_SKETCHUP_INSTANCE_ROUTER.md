# SketchUp multi-instance router

## Invariant

An MCP request is delivered to one exact SketchUp process. A selected target
that disappears is never replaced automatically, even if another process has
the same PID later.

Each SketchUp boot creates a fresh identity:

```text
su-<pid>-<boot-id-prefix>
```

The Ruby bridge binds loopback port `0`, reads the ephemeral port assigned by
Windows, and owns one heartbeat file under:

```text
OUTPUT/runtime/sketchup-instances/<instance-id>.json
```

The heartbeat contains instance ID, PID, boot ID, port, model metadata,
bridge generation, write mode and timestamp. Each process writes only its own
file. Abruptly terminated processes become `OFFLINE` after the bounded
heartbeat timeout.

## MCP routing

These tools are always available in the core profile:

- `sketchup_list_instances`
- `sketchup_select_instance`
- `sketchup_get_active_instance`
- `sketchup_clear_instance`

Read calls auto-route only when exactly one instance is online and that choice
immediately becomes sticky. Multiple instances require an explicit selection. Model writes always require an
explicit selection, including when only one instance is online.

After selection, the target is sticky for the lifetime of that MCP process.
If it stops heartbeating or refuses the connection, the result is
`TARGET_OFFLINE`; the router never falls back to another instance.

Every bridge request includes `instance_id`, PID, boot ID and port. Ruby
validates all four before touching `Sketchup.active_model`. Every response
returns target evidence, which Python validates again before exposing the
result to Codex/Cline.

## External client isolation

The SketchUp extension launches no Agent Host or model runtime. Each external
MCP process keeps its own sticky target. An optional external Agent Host may
inject `AI_DG_SKETCHUP_INSTANCE_ID`, but it is not installed in SketchUp.

## Remaining live gates

- Open two real `SketchUp.exe` processes and verify two independent registry
  entries and ports.
- Select A, create/read back a visible probe in A and prove B is unchanged.
- Repeat for B, then undo both probes.
- Kill selected A and prove the next request returns `TARGET_OFFLINE`.
- Restart SketchUp and prove a fresh boot ID prevents PID-reuse fallback.

Do not mark these gates PASS from mocks or source inspection.

Run the exact two-process gate with:

```powershell
python mcp_server/multi_instance_acceptance.py <instance-a> <instance-b>
```

The default is read-only. Before `--write-probe`, select each exact instance
and call `sketchup_set_write_mode(mode="write_enabled", confirm=true)` through
MCP, approving the native prompt in the matching SketchUp process. Each probe
and undo also requires native confirmation.
