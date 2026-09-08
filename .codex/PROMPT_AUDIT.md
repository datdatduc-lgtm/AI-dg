# Prompt implementation audit

Updated: 2026-09-04

This is the requirement-level audit for the files in `E:/AI-DG/prompt`.
It intentionally distinguishes implementation evidence from gates that still
need an external provider, OCR binary, or an explicitly approved model write.

| Milestone | State | Evidence / remaining gate |
|---|---|---|
| M0 bridge/provider architecture | REAL | Loopback bridge, UI-thread SketchUp API calls, bounded socket protocol, no factory `sketchup.rb` edit. |
| M1 real provider/agent | REAL path / NOT_CONNECTED | `provider.py`, `provider_cli.py`, OS credential-store manager, explicit network gate, bounded read-only agent. The installed Python 3.12 helper sees the redacted 9Router credential and endpoint, but no concrete model is selected; a real provider request has not been authorized/executed. |
| M2 source ingestion | REAL / REVIEW_REQUIRED | PDF, DXF/DWG, image, Excel and SKP metadata adapters. Current scanned PDF renders, but OCR is `BINARY_NOT_FOUND`; no inferred dimensions are promoted. |
| M3 index/reconciliation | REAL | Drawing classification, page/source provenance, view linking signals and conflict/missing review items. |
| M4 dimension/material graphs | REAL | Structured graphs with explicit/derived states and provenance. |
| M5 review/spec | REAL | Review Queue and Model Specification gates; missing/conflicting/low-confidence facts block build. |
| M6 semantic builder | REAL path / READ_ONLY | Semantic panel/cabinet/partition/shelf/door/drawer/countertop/component tools, transactions and metadata. Live writes require `APPROVED + WRITE_ENABLED + confirm_write`. |
| M7 verification | REAL path | Official Ruby read-back and dimension/material/tag/hierarchy verification; controlled executor contract passes. |
| P1 Build IR + codegen | REAL | `pipeline/stages/build_ir.py` converts approved ModelSpec items into deterministic semantic operations and generates readable JSON/Python/Ruby representations; Build Plan is derived from the same IR. |
| M8 workflow learning | PARTIAL | Privacy-aware live metadata profile and SKP binary metadata analyzer exist. Geometry/naming profile from multiple old SKP files needs opening each file through official SketchUp API without replacing the user's active model. |
| M9 UI/runtime | REAL path / LIVE | User/Developer separation, provider form, explicit network toggle, real provider helper, diagnostics and graceful reload. Current user-opened SketchUp instance is live and Control Center is visible. |
| M10 end-to-end acceptance | NOT_YET_PASS | Controlled Excel pipeline reaches `READY/PASS` in test fixtures; required real source → approved build → live SketchUp read-back, real provider, and external Cline/Codex evidence are not all simultaneously proven. |

## Current first failing stage

PHASE 0 is now live. The user-opened official SketchUp 2023 instance is PID
`48576`, version `23.1.340`; `bridge_started` is recorded on
`127.0.0.1:9876`, and read-only MCP/API acceptance is `27/27 PASS`. The
current model is empty (`0` entities), so the next product gate is a trusted
source with explicit dimensions and review approval; no provider request or
model write has been authorized.

## Installed-tool evidence

- `install_all.py --check`: `READY`, Python 3.12.10, mcp/PyMuPDF/openpyxl/ezdxf/Pillow available.
- `provider_contract_smoke.py`: `PASS`, including model/chat endpoint derivation, auth-header handling, network guard, manager config and telemetry redaction.
- `pipeline/tests/test_pipeline.py`: 15 passed using the bundled Python 3.12 runtime.
- `mcp_server/tool_exposure_smoke.py`: `PASS` for `minimal` 21/77, `drawing` 38/77, `build` 56/77, and `full` 77/77; normal mode excludes `sketchup_eval_ruby`.
- Source Ruby and UI JavaScript syntax checks: passed.
- The installer now merges AI-DG-owned plugin files and never recursively deletes a plugin directory on re-run.

## Safety decisions

- Factory `C:/Program Files/SketchUp/SketchUp 2023/Tools/sketchup.rb` remains unchanged; verified SHA-256: `6AB10B1D66742C8F9897BBC065DE2842CEFA86EBF47190719E7F269F65E6C715`.
- `D:` remains read-only; `.skp/.skb` deletion is denied; `eval_ruby` is developer-only.
- No model mutation was issued during this continuation.
- Live acceptance smoke on 2026-09-04: `27/27 PASS`, PID `48576`, graceful reload generation `6`; hierarchy returned a valid empty result (`0/50`, not truncated).
- A credential-inspection command in this continuation was stopped after its ad-hoc redaction proved insufficient. No credential values were written to project files or logs; any key that appeared in that tool output should be rotated.

## Next safe gates

1. Keep the current bridge live and, if needed, rerun the read-only health/Cline acceptance after a user-visible session change.
2. Provide a trusted OCR executable or a vector/CAD/Excel source with explicit dimensions; do not promote OCR candidates automatically.
3. Use the new Build IR/codegen artifact on an approved fixture, then inspect the emitted JSON/Python/Ruby before any model write.
4. Explicitly authorize one real provider test after selecting the provider/model.
5. Use a separately saved test-owned SketchUp model and explicit approval before exercising the semantic write/read-back path.

## Latest continuation

- Chat UI/backend now supports two explicit routes: 9Router OpenAI-compatible and local Codex CLI `0.147.0`.
- 9Router model suggestions may come from the installed local cache, but are labeled unverified and never auto-selected. Codex CLI uses ephemeral read-only execution and has its own network gate.
- Neither route is promoted to `CONNECTED` or `PASS` for real chat until a user-authorized external turn produces evidence; Codex and 9Router permissions are separate and no external request was made in this continuation.
- Chat context is now carried into both real routes from the local session file with bounded size and sensitive-token redaction; only successful responses are appended to that session file. The UI also offers a direct Model Manager action, quick picks from the unverified local cache and actionable helper-error guidance. Live acceptance remains `27/27 PASS` at reload generation `21`.
- Codex CLI now receives AI-DG MCP per invocation through a workspace wrapper and does not depend on a pre-existing global Codex MCP entry; wrapper stdio initialization and command-injection contract pass. Actual Codex external execution remains user-authorized and unrun.
- The wrapper tools-list regression passes with 21 minimal read-only tools, including SketchUp health and selection; no global Codex MCP configuration was changed. Provider route trace fields are now preserved through Ruby/UI for end-to-end observability.
- The Codex route fails closed when the workspace MCP wrapper is absent, preventing a misleading model-only answer that cannot access SketchUp.
