# AI-DG headless SketchUp MCP bridge

## Objective

AI-DG is a headless SketchUp Ruby bridge, shared MCP server, and drawing/build
pipeline. It is not an AI chat engine and does not embed an agent workspace in
SketchUp. Codex/Cline remain external MCP clients.

```text
Codex / Cline / MCP client
             |
         AI-DG MCP
             |
 dynamic-port instance router
             |
 headless Ruby UI-thread bridge
             |
    official SketchUp API
```

## Hard invariants

- The plugin must never label a local/fallback response as Codex or Cline.
- Production must not use `codex exec --ephemeral`.
- Production must not contain a 9Router/backend selector or read
  `E:\api-key.properties`.
- Cline must be the owner of its own login, provider, and model configuration.
- The SketchUp extension never launches Codex, Cline, Python Agent Host or a provider process.
- The extension contains no toolbar, menu, HtmlDialog or transcript UI.
- SketchUp API calls stay on the SketchUp UI thread through the existing bridge.
- Enabling write mode and each write require explicit MCP/runtime intent plus
  native user confirmation in the exact SketchUp process. `eval_ruby` is Developer Mode only.
- `sketchup.rb` is a protected system file and is never edited or replaced.

## Product surface

SketchUp exposes no AI-DG window. Status, instance selection and diagnostics
are MCP responses. Native message boxes exist only for security confirmation.

## Migration rule

The deleted legacy `prompt/00` through `prompt/14` pack is intentionally not
restored. This architecture directory is the replacement source of truth.
