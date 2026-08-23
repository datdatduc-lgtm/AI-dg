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
├─ OUTPUT\IMAGES\
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

AI-dg never modifies or deletes original INPUT files.

## 3. Every deployment starts fresh

Before each new analysis/deployment, AI-dg must run:

```powershell
python "$env:USERPROFILE\.agents\skills\ai-dg-estimator\scripts\workspace\prepare_run.py" "D:\AI-dg\Villa-A"
```

This command automatically:

```text
PRESERVE  INPUT/
PRESERVE  project.ai-dg.json
DELETE    previous WORK/
DELETE    previous OUTPUT/
RECREATE  fresh WORK/OUTPUT folders
RESCAN    current INPUT/
CREATE    fresh WORK/manifests/input-manifest.json
```

Old Ruby, JSON, Excel, images, reports, models and review data are not allowed to survive into the next run.

Do not store manually maintained files in `OUTPUT/`. If a file must survive reruns, keep it in INPUT/OTHER or elsewhere outside WORK/OUTPUT.

## 4. Ask Codex to analyze the folder

Example:

```text
Dùng skill ai-dg-estimator phân tích project tại D:\AI-dg\Villa-A.
Bắt đầu bằng fresh-run cleanup bắt buộc: xóa WORK/OUTPUT cũ nhưng giữ nguyên INPUT.
Sau đó đọc toàn bộ INPUT, đối chiếu PDF/CAD/SKP, dựng Geometry Ledger,
map vật liệu, bóc các phần đủ bằng chứng, tạo Ruby prototype cho các component đủ readiness,
và ghi toàn bộ kết quả mới vào OUTPUT. Không yêu cầu tôi upload lại file vào chat.
```

Codex should use `prepare_run.py` as the deployment entry point. `scan_input.py` alone is for inventory only and does not replace fresh-run cleanup.

## 5. Expected OUTPUT

```text
OUTPUT/
├─ RUBY/
│  └─ *.rb
├─ IMAGES/
│  └─ *.png
├─ TAKEOFF/
│  ├─ items.json
│  ├─ material-regions.json
│  ├─ bom.json
│  └─ review-queue.json
├─ EXCEL/
│  ├─ AI-dg_Tong-hop-vat-lieu.xlsx
│  └─ AI-dg_Bao-gia.xlsx
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

## 6. Finalize output manifest

```powershell
python "$env:USERPROFILE\.agents\skills\ai-dg-estimator\scripts\workspace\finalize_output.py" "D:\AI-dg\Villa-A" --status PARTIAL
```

Use `PASS`, `PARTIAL`, or `FAIL` for the current run status.
