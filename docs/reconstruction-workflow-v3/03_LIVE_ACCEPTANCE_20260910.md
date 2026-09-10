# Live acceptance — 2026-09-10

## Target

- SketchUp 2023 PID: `25228`
- instance: `su-25228-cfbdf60107fd`
- boot id: `cfbdf601-07fd-4915-a554-8d61901c921a`
- port: `51172`
- bridge generation after safe reload: `8`
- write mode: `write_enabled`
- `sketchup.rb`: không sửa

## VN-1 raw PDF

Source: `INPUT/PDF/CHI TIET VACH NGAN VN-1.pdf`.

Không dùng JSON nhập tay. OCR/layout tự tạo bốn mandatory contracts và suy ra:

```text
8000 × 40 × 1100
body height 800
insert thickness 10
insert 15..25 on Y
insert 750..1100 on Z
slot 12 × 50
top corners R50
```

Live repair:

| Iteration | Hypothesis | Native result | Score |
|---:|---|---|---:|
| 1 | `H-flush-unslotted` | FAIL: 2 region-boundary + 2 feature-missing | 0.866667 |
| 2 | `H-centered-slotted` | PASS | 1.0 |

Final slot and R50 evidence report
`observed_from=official_sketchup_edge_geometry`.
The two writes have distinct SketchUp operation IDs and iteration 2 atomically
replaces iteration 1.

## Second raw fixture RS-2

Controlled source is generated as a PDF, not an interpreted JSON. It changes
page orientation/layout and dimensions:

```text
2400 × 60 × 1000
body height 700
insert thickness 12
slot 14 × 45
```

It follows the same live result: wrong hypothesis FAIL at `0.851852`, corrected
hypothesis PASS at `1.0`. This validates reuse within the profile-assembly
family only.

## Safety/regression

- Ruby syntax: PASS for `main_safe.rb` and `geometry_builder.rb`.
- Python compile: PASS for raw extraction, V3 executor/workflow/view-back and
  MCP registration.
- Focused Python tests: 33 PASS.
- Instance router tests: 5 PASS.
- `git diff --check`: PASS.
- Final viewport capture succeeded after both rebuilds; no white/lost viewport.
