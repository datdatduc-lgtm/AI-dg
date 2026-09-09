# 2D→3D V2 Implementation Status

Cập nhật: 2026-09-09

| Phase | State | Evidence |
|---|---|---|
| P0 Current failure audit | REAL | `00_CURRENT_FAILURE.md`; first failure dựa trên artifact VN-1 |
| P1 Geometry Ledger V2 | REAL | hierarchical span tests PASS |
| P2 Region Graph V2 | REAL | spatial/visibility graph tests PASS |
| P3 ModelSpec V2 | REAL | READY + negative REVIEW_REQUIRED tests PASS |
| P4 Build IR V2 | REAL | semantic assembly test PASS |
| P5 Pre-build projection | REAL | positive/negative projection tests PASS |
| P6 VN-1 A–F fixture | REAL | fixture hash validated; A–F PASS |
| P7 SketchUp execution gate | REAL | dedicated executor/profile; Python/Ruby checks PASS |
| P8 Live VN-1 build | REAL | exact target PID 25228; operation `op-20260909T093215.349Z-2920`; MCP result PASS |
| P9 Read-back + post-build projection | REAL | independent official Ruby API read-back PASS; every projection contract PASS |
| P10 Full regression/docs/release | REAL | 33 tests PASS; Python compile + Ruby syntax + artifact + secret + diff checks PASS |

## Live evidence

- Exact target: `su-25228-cfbdf60107fd`, PID `25228`, boot ID `cfbdf601-07fd-4915-a554-8d61901c921a`, port `51172`.
- Bridge reload generation `6`; main SHA-256 `ae21c2ba645f9d5f9d4859a313a962f5d00cc37bdd8754e4f700f1f9c1ab3dd8`; geometry helper SHA-256 `603e494aca0a83f97ca8138d140bd2a758cd872c47d3b06b27fab12d36dd2726`.
- Live operation: `op-20260909T093215.349Z-2920`.
- Ruby read-back lower region: X `0..8000`, Y `0..40`, Z `0..800`, material `mat-lower`.
- Ruby read-back upper region: X `0..8000`, Y `15..25`, Z `800..1100`, material `mat-glass`.
- Forbidden visible region list is empty; the 50 mm section-only refinement was not built as a visible band.
- Independent `ai_dg_verify_sketchup_build_v2` returned `PASS` from `official_sketchup_ruby_api`.
- No alternate SketchUp instance was selected.

## Scoped native pre-approval

The user explicitly authorized self-approval in SketchUp. The bridge honors it
only when the payload simultaneously identifies schema V2, pipeline
`2D3D-V2`, tool `ai_dg_execute_build_ir_v2`, and explicit `confirm_write=true`.
The Python executor emits that payload only after all V2 gates pass. Raw model
writes and Undo continue to use native confirmation.

## P10 release evidence

- Regression: `33 passed` across V2, legacy pipeline and multi-instance router tests.
- Python compile: all V2 stages, MCP server/exposure and fixture runner PASS.
- Ruby syntax: `main_safe.rb` and `geometry_builder.rb` PASS.
- All eight required V2 work/model/verification artifacts exist.
- Secret scan: PASS; no API key or bearer token found in release files.
- `git diff --check`: PASS.
- Factory `C:/Program Files/SketchUp/SketchUp 2023/Tools/sketchup.rb` remains at
  SHA-256 `6AB10B1D66742C8F9897BBC065DE2842CEFA86EBF47190719E7F269F65E6C715`;
  it is not part of the repository changes or bridge deployment.

## Completion rule

Release chỉ được đẩy sau khi toàn bộ trạng thái P0→P10 đều là `REAL`.
