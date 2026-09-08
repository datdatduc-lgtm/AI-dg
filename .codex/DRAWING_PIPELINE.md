# AI-DG Drawing-to-SketchUp Pipeline

Updated: 2026-09-04

This is the implementation record for the prompt pack in `E:/AI-DG/prompt`.
The pipeline is provenance-first and does not turn an ambiguous drawing into
geometry without review.

## Stages

| Stage | Implementation | Gate |
|---|---|---|
| M2 Source Ingestion | `pipeline/stages/source_ingestion.py` reads PDF, DXF/DWG, Excel, image and SKP metadata. Optional parsers are used when installed; pypdf/ASCII-DXF fallbacks remain explicit. | Source is never mutated; scanned/unavailable extraction is flagged. |
| M3 Drawing Index | `pipeline/stages/drawing_index.py` indexes page/sheet/type/title/scale/item codes and links views by item code. | Links are evidence-based, not geometry guesses. |
| M3 Reconciliation | `pipeline/stages/reconciliation.py` compares equal fact/axis/span observations and reports MATCH, REFINEMENT or MISMATCH. | No value is silently preferred across conflicting sources. |
| M4 Graphs | `pipeline/stages/graphs.py` emits DimensionGraph and MaterialGraph with source edges and conflicts. | Conflicts become `REVIEW_REQUIRED`. |
| M5 Review + ModelSpec | `review_queue.py` and `model_spec.py` keep missing, inferred and unresolved values out of the build gate. | Build requires `READY` facts and explicit approval. |
| M6 Build Planner | `builder.py` derives the compatibility Build Plan from `build_ir.py`; only explicit semantic part breakdowns become `CREATE_SEMANTIC_ITEM` operations. `executor.py` dispatches approved operations through the official Ruby bridge. | No single-box fallback is used for production construction. |
| M7 Verification | `verification.py` checks dimensions and optional position, angle, material, tag and hierarchy evidence with explicit tolerances; executor obtains measurements from `get_semantic_item` read-back. | Any missing/failed required check fails verification. |
| P1 Build IR + codegen | `pipeline/stages/build_ir.py` converts a reviewed ModelSpec into stable semantic operation IDs and emits readable JSON/Python/Ruby representations. | Only `READY` Build IR can be code-generated for execution. |

## MCP and SketchUp integration

`mcp_server/server.py` exposes the pipeline through:

- `ai_dg_source_ingest`
- `ai_dg_pipeline_run`
- `ai_dg_pipeline_artifacts`
- `ai_dg_review_queue`
- `ai_dg_model_spec`
- `ai_dg_build_plan`
- `ai_dg_build_ir`
- `ai_dg_codegen`
- `ai_dg_execute_build_plan`
- `ai_dg_verification`

The official SketchUp Ruby API bridge adds `sketchup_create_semantic_item`,
`sketchup_create_component`, named semantic builders for panel/cabinet/
partition/shelf/door/drawer/countertop, and guarded transform/material/tag/
undo operations. It validates explicit parts, writes metadata for
operation/item/part/role/material/source, wraps each build unit in one
transaction, verifies the result, and aborts on failure. `sketchup_get_semantic_item`
reads the generated hierarchy back through the official API. Normal mode
remains read-only; the current model is not changed by pipeline tests.

## Current real-source result

Run `prompt-20260903-ocr` was executed against the PDF currently in
`E:/AI-DG/INPUT/PDF/`. The pipeline completed ingestion and index creation but
the PDF is image-only: PyMuPDF rendered the page, while the local OCR adapter
reported `BINARY_NOT_FOUND` because no Tesseract executable is installed.
Dimension/material facts are zero. The persisted gate is therefore `BLOCKED`,
the Review Queue contains two blockers, and build operations are zero. This
is a correct review gate, not a failed reconstruction claim.

## Provider and UI policy

Provider states are restricted to `UNCONFIGURED`, `TESTING`, `CONNECTED`,
`AUTH_ERROR`, `RATE_LIMITED`, `NO_CREDIT`, `OFFLINE` and `MODEL_ERROR`.
`CONNECTED` is written only after a real successful provider response. Network
testing remains explicit opt-in and is not run by the pipeline.

Control Center User Mode shows Runtime, 2D Sources, Review Queue, Build
Progress, Chat and user settings. The Provider Manager can save provider
metadata and the API key through a one-shot local helper backed by the OS
credential store; it never persists a plaintext key. User Mode calls that real
provider helper only after an explicit network enable and reports structured
provider errors instead of falling back to deterministic chat. Developer Mode
may expose the bounded diagnostic harness as `DEV_MOCK`. Technical
trace/tool/skill/plugin/model/source diagnostics remain hidden unless enabled
before runtime startup.

## Safety

- Factory SketchUp `Tools/sketchup.rb` is preserved and guarded from writes/deletes.
- `.skp/.skb` deletion and D: writes are denied at MCP and Ruby boundaries.
- No process kill, force restart, save, undo or user-model deletion is performed.
- Pipeline artifacts are written under the project `WORK/pipeline/<run_id>` only.
