# Execution brief

Before changing 2D/3D pipeline behavior, verify the native runtime boundary.

1. Read `00_NATIVE_AGENT_GOAL.md` through `04_ACCEPTANCE.md`.
2. Inspect current bridge, Agent Host, MCP launcher, and deployment script.
3. Run syntax/compile and static hard-fail checks.
4. Start the real Codex App Server and verify MCP status.
5. Start real Cline ACP and verify MCP/session lifecycle.
6. Test two turns, resume, cancel, approval, and graceful shutdown.
7. Only after all runtime gates pass, reconnect live selection and pipeline
   actions.

Stop and report a hard failure if any implementation introduces:

- fake chat or fake agent state;
- `codex exec --ephemeral` in production;
- a provider router or secret reader in the plugin;
- Cline simulation instead of ACP;
- mock tool success presented as a live SketchUp result;
- an unchecked write or automatic approval;
- a change to system `sketchup.rb`.
