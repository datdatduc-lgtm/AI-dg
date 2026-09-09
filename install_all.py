#!/usr/bin/env python3
"""Trình cài đặt tự động 1-Click cho AI-DG Plugin và cấu hình MCP Servers."""

import os
import sys
import shutil
import json
import argparse
import importlib.util
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent


def best_python_executable() -> str:
    """Prefer the installed Python version that can run the MCP package."""
    configured = os.environ.get("AI_DG_PYTHON", "").strip()
    candidates = ([Path(configured)] if configured else []) + [
        Path(r"C:\Users\Admin\AppData\Local\Programs\Python\Python312\python.exe"),
        Path(sys.executable),
    ]
    for candidate in candidates:
        if str(candidate) and candidate.is_file():
            return str(candidate)
    return "py -3.12"


def runtime_check() -> dict[str, object]:
    """Report local runtime readiness without downloading or changing anything."""
    required = {
        "mcp": REPO_ROOT / "OUTPUT" / "mcp_deps",
        "pymupdf": REPO_ROOT / "OUTPUT" / "pipeline_deps",
        "openpyxl": REPO_ROOT / "OUTPUT" / "pipeline_deps",
        "ezdxf": REPO_ROOT / "OUTPUT" / "pipeline_deps",
        "PIL": REPO_ROOT / "OUTPUT" / "pipeline_deps",
        "keyring": REPO_ROOT / "OUTPUT" / "pipeline_deps",
    }
    missing = []
    for module, dependency_dir in required.items():
        if str(dependency_dir) not in sys.path:
            sys.path.insert(0, str(dependency_dir))
        if importlib.util.find_spec(module) is None:
            missing.append(module)
    version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    return {
        "python": version,
        "python_supported": sys.version_info >= (3, 10),
        "mcp_server": str(REPO_ROOT / "mcp_server" / "launcher.py"),
        "missing_modules": missing,
        "status": "READY" if sys.version_info >= (3, 10) and not missing else "INCOMPLETE",
    }


def install_runtime_dependencies() -> int:
    """Install declared dependencies into the workspace using uv, on request only."""
    uv = shutil.which("uv")
    if not uv:
        print("[!] Không tìm thấy uv; cài uv hoặc chạy install thủ công trước.")
        return 2
    commands = [
        [uv, "pip", "install", "--target", str(REPO_ROOT / "OUTPUT" / "mcp_deps"), "-r", str(REPO_ROOT / "mcp_server" / "requirements.txt")],
        [uv, "pip", "install", "--target", str(REPO_ROOT / "OUTPUT" / "pipeline_deps"), "-r", str(REPO_ROOT / "requirements.txt")],
    ]
    for command in commands:
        print("[*] Cài runtime dependencies vào workspace…")
        completed = subprocess.run(command, cwd=str(REPO_ROOT), check=False)
        if completed.returncode != 0:
            return completed.returncode
    return 0

def install_sketchup_plugin():
    print("=" * 60)
    print("1. CÀI ĐẶT SKETCHUP PLUGIN (AI-DG BRIDGE)")
    print("=" * 60)

    appdata_str = os.environ.get("APPDATA", "")
    if not appdata_str:
        print("[!] Không tìm thấy biến môi trường APPDATA.")
        return

    appdata = Path(appdata_str)
    # Tìm kiếm các phiên bản SketchUp (2020 -> 2026+)
    sketchup_roots = list(appdata.glob("SketchUp/SketchUp 20*/SketchUp/Plugins"))

    src_rb = REPO_ROOT / "bridge_sketchup" / "ai_dg_bridge.rb"
    src_dir = REPO_ROOT / "bridge_sketchup" / "ai_dg_bridge"
    headless_files = {
        "main.rb": src_dir / "main_safe.rb",
        "geometry_builder.rb": src_dir / "geometry_builder.rb",
    }
    retired_files = (
        "helper_process.rb",
        "toolbar.rb",
        "control_center.rb",
        "agent_host_client.rb",
        "icons/ai_dg_mcp.svg",
        "agent_host/host.py",
        "ui/control_center.html",
        "ui/control_center.css",
        "ui/control_center.js",
    )

    if not sketchup_roots:
        print("[!] Chưa tìm thấy thư mục SketchUp Plugins mặc định.")
        print(f"    Bạn có thể copy thủ công:")
        print(f"    - {src_rb}")
        print(f"    - {src_dir}")
        print(f"    vào thư mục Plugins của SketchUp.")
        return

    for p_dir in sketchup_roots:
        try:
            print(f"[*] Đang cài vào: {p_dir}")
            shutil.copy2(src_rb, p_dir)
            dest_dir = p_dir / "ai_dg_bridge"
            dest_dir.mkdir(parents=True, exist_ok=True)
            for destination_name, source_path in headless_files.items():
                shutil.copy2(source_path, dest_dir / destination_name)
            for relative_path in retired_files:
                retired_path = dest_dir / relative_path
                if retired_path.is_file():
                    retired_path.unlink()
            for relative_dir in ("icons", "agent_host", "ui"):
                retired_dir = dest_dir / relative_dir
                if retired_dir.is_dir() and not any(retired_dir.iterdir()):
                    retired_dir.rmdir()
            print(f"[✓] Đã cài đặt thành công cho: {p_dir.parent.parent.name}")
        except Exception as e:
            print(f"[!] Lỗi khi cài vào {p_dir}: {e}")

def generate_mcp_config():
    print("\n" + "=" * 60)
    print("2. TẠO FILE CẤU HÌNH MCP CHO CÁC NỀN TẢNG AI")
    print("=" * 60)

    python_executable = best_python_executable()
    server_script = str((REPO_ROOT / "mcp_server" / "launcher.py").resolve())

    # Cấu hình chuẩn cho Cline, Roo Code, Cursor, VSCode, OpenCode, Codex, Hermes, DSH
    config = {
        "mcpServers": {
            "ai-dg": {
                "command": python_executable,
                "args": [server_script],
                "env": {
                    "PYTHONPATH": os.pathsep.join([
                        str(REPO_ROOT / "OUTPUT" / "mcp_deps"),
                        str(REPO_ROOT),
                        str(REPO_ROOT / "mcp_server"),
                    ])
                }
            }
        }
    }

    out_file = REPO_ROOT / "mcp_config.json"
    out_file.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[✓] Đã tạo file cấu hình: {out_file}")

    # Tạo thêm file cấu hình mẫu cho OpenCode / Codex
    opencode_config = {
        "tools": [
            {
                "type": "mcp",
                "name": "ai-dg",
                "command": [python_executable, server_script]
            }
        ]
    }
    Path("E:/AI-DG/opencode_config.json").write_text(json.dumps(opencode_config, indent=2), encoding="utf-8")
    print(f"[✓] Đã tạo file cấu hình cho OpenCode/Codex: {REPO_ROOT / 'opencode_config.json'}")

    print("\n" + "=" * 60)
    print("HƯỚNG DẪN KẾT NỐI:")
    print("1. Với VSCode / Cline / Roo Code / Cursor:")
    print("   Mở Cài đặt MCP trong VSCode/Cline -> Dán cấu hình từ file 'E:/AI-DG/mcp_config.json'.")
    print("2. Với OpenCode / Codex / Hermes / DSH:")
    print(f"   Thêm Tool MCP Server trỏ tới lệnh: {python_executable} {server_script}")
    print("3. Trong SketchUp:")
    print("   Mở SketchUp; bridge headless tự đăng ký, không tạo toolbar hoặc cửa sổ.")
    print("=" * 60)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Cài AI-DG bridge, MCP config và runtime dependencies.")
    parser.add_argument("--check", action="store_true", help="Chỉ kiểm tra runtime; không ghi file/cài đặt.")
    parser.add_argument("--install-runtime", action="store_true", help="Cài dependencies vào OUTPUT/*_deps bằng uv; có thể cần network.")
    args = parser.parse_args()
    if args.check:
        print(json.dumps(runtime_check(), ensure_ascii=False, indent=2))
        raise SystemExit(0)
    if args.install_runtime:
        raise SystemExit(install_runtime_dependencies())
    install_sketchup_plugin()
    generate_mcp_config()
    print("\nRuntime check:")
    print(json.dumps(runtime_check(), ensure_ascii=False, indent=2))
