# AI-dg Local Project Workspace

Use this workflow with Codex/OpenCode so project source files stay on disk instead of being uploaded one-by-one into chat.

## 1. Initialize a project

```powershell
python "$env:USERPROFILE\.agents\skills\ai-dg-estimator\scripts\workspace\init_project.py" "D:\AI-dg\Villa-A" --name "Villa A"
```

This creates:

```text
D:\AI-dg\Villa-A\
├─ INPUT\PDF\
├─ INPUT\CAD\
├─ INPUT\SKP\
├─ INPUT\OTHER\
├─ WORK\...
├─ OUTPUT\RUBY\
├─ OUTPUT\TAKEOFF\
├─ OUTPUT\EXCEL\
├─ OUTPUT\REPORTS\
├─ OUTPUT\MODEL\
└─ project.ai-dg.json
```

## 2. Put source files in INPUT

Copy the complete drawing package into `INPUT/`.

Examples:

```text
INPUT/PDF/noi-that.pdf
INPUT/CAD/noi-that.dwg
INPUT/SKP/noi-that.skp
INPUT/OTHER/material-schedule.xlsx
```

AI-dg never modifies the original INPUT files.

## 3. Ask Codex to analyze the folder

Example:

```text
Dùng skill ai-dg-estimator phân tích project tại D:\AI-dg\Villa-A.
Đọc toàn bộ INPUT, tạo input manifest, đối chiếu PDF/CAD/SKP, dựng Geometry Ledger,
map vật liệu, bóc các phần đủ bằng chứng, tạo Ruby prototype cho các component đủ readiness,
và ghi toàn bộ kết quả vào OUTPUT. Không yêu cầu tôi upload lại các file vào chat.
```

Codex should run the input scanner first:

```powershell
python "$env:USERPROFILE\.agents\skills\ai-dg-estimator\scripts\workspace\scan_input.py" "D:\AI-dg\Villa-A"
```

## 4. Expected OUTPUT

```text
OUTPUT/
├─ RUBY/
│  └─ *.rb
├─ TAKEOFF/
│  ├─ items.json
│  ├─ material-regions.json
│  ├─ bom.json
│  └─ review-queue.json
├─ EXCEL/
│  └─ AI-dg-estimate.xlsx
├─ REPORTS/
│  ├─ analysis.md
│  ├─ drawing-index.md
│  ├─ geometry-ledger.md
│  ├─ source-reconciliation.md
│  └─ readiness.md
├─ MODEL/
│  └─ *.skp  # only when actually generated
└─ output-manifest.json
```

Partial outputs are allowed. A blocked fabrication BOM must not prevent AI-dg from producing a valid geometry report or a review-tagged Ruby prototype.

## 5. Finalize output manifest

```powershell
python "$env:USERPROFILE\.agents\skills\ai-dg-estimator\scripts\workspace\finalize_output.py" "D:\AI-dg\Villa-A" --status PARTIAL
```

Use `PASS`, `PARTIAL`, or `FAIL` for the overall run status.
