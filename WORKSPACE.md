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

## 4. Mandatory run behavior

For every item whose Component Geometry is `READY` or `PARTIAL_READY`, Codex must create:

```text
OUTPUT/RUBY/<item-code>.rb
```

Ruby is required even if project placement, project quantity or fabrication BOM is blocked.

When Ruby is executed in SketchUp it should export, when practical:

```text
OUTPUT/IMAGES/<item>_iso.png
OUTPUT/IMAGES/<item>_front.png
OUTPUT/IMAGES/<item>_side.png
```

Do not claim the model or images were created if SketchUp was not actually run.

## 5. Mandatory Excel generation

After TAKEOFF JSON is written, always run:

```powershell
python "$env:USERPROFILE\.agents\skills\ai-dg-estimator\scripts\workspace\export_project_excel.py" "D:\AI-dg\Villa-A"
```

This creates:

```text
OUTPUT/EXCEL/AI-dg_Tong-hop-vat-lieu.xlsx
OUTPUT/EXCEL/AI-dg_Bao-gia.xlsx
```

The material workbook includes:

```text
TONG_QUAN
HANG_MUC
VAT_LIEU
CHI_TIET_VAT_LIEU
NHA_CUNG_CAP
REVIEW
SOURCE
```

The quotation workbook includes:

```text
BAO_GIA
DON_GIA_NGUON
REVIEW
```

Excel must still be created with explicit blank/review statuses when prices, suppliers, images or fabrication quantities are incomplete. AI-dg must never invent those values.

## 6. Ask Codex to analyze the folder

Example:

```text
Dùng skill ai-dg-estimator triển khai project tại D:\AI-dg\Villa-A.
Bắt đầu bằng prepare_run.py để xóa WORK/OUTPUT cũ nhưng giữ nguyên INPUT.
Đọc toàn bộ INPUT, đối chiếu PDF/CAD/SKP, dựng Geometry Ledger và Material Spatial Map.
Tạo OUTPUT/RUBY/*.rb cho mọi component READY/PARTIAL_READY.
Tạo TAKEOFF JSON, sau đó chạy export_project_excel.py để luôn sinh 2 file Excel.
Cuối cùng finalize_output.py. Không yêu cầu tôi upload lại file vào chat.
```

## 7. Expected OUTPUT

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
│  ├─ suppliers.json          # only when actual supplier research/library exists
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

Partial outputs are allowed. A blocked fabrication BOM must not prevent AI-dg from producing a valid geometry report, Ruby model prototype or Excel workbook with explicit review cells.

## 8. Finalize output manifest

```powershell
python "$env:USERPROFILE\.agents\skills\ai-dg-estimator\scripts\workspace\finalize_output.py" "D:\AI-dg\Villa-A" --status PARTIAL
```

`finalize_output.py` now checks both mandatory Excel files and Ruby coverage for modelable items. A requested `PASS` is downgraded to `PARTIAL` if those mandatory deliverables are missing.
