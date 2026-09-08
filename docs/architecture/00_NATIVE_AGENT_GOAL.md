# AI-DG native Codex/Cline integration

## Objective

AI-DG is a SketchUp host, Ruby bridge, shared MCP server, and drawing/build
pipeline. It is not an AI chat engine. The visible workspace exposes the real
Codex App Server and real Cline ACP runtime inside SketchUp.

```text
SketchUp HtmlDialog
        |
Ruby UI-thread bridge
        |
Persistent Python Agent Host
        |----------------------|
Codex App Server          Cline ACP
        |----------------------|
             AI-DG MCP
                  |
          official SketchUp API bridge
```

## Hard invariants

- The plugin must never label a local/fallback response as Codex or Cline.
- Production must not use `codex exec --ephemeral`.
- Production must not contain a 9Router/backend selector or read
  `E:\api-key.properties`.
- Cline must be the owner of its own login, provider, and model configuration.
- Agent Host is the only process launcher for Codex and Cline.
- HtmlDialog and Ruby never block waiting for an AI process.
- SketchUp API calls stay on the SketchUp UI thread through the existing bridge.
- Writes require native approval, AI-DG write mode, and user confirmation in
  SketchUp. `eval_ruby` is Developer Mode only.
- Session mapping stores runtime IDs and cwd only; it never stores transcript
  copies, prompts, credentials, or model output.
- `sketchup.rb` is a protected system file and is never edited or replaced.

## Visible product surface

The default UI contains only: Codex, Cline, Bản vẽ, Dựng model, and Cài đặt.
Protocol IDs, PIDs, raw events, MCP status, and permission requests belong in
Developer Diagnostics and are hidden unless Developer Mode is enabled.

## Migration rule

The deleted legacy `prompt/00` through `prompt/14` pack is intentionally not
restored. This architecture directory is the replacement source of truth.
